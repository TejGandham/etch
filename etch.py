#!/usr/bin/env python3
import base64
import os
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Protocol

import httpx
from google import genai
from google.genai import types
from mcp.server.fastmcp import FastMCP

DEFAULT_MODEL = "gemini-3-pro-image-preview"
ALLOWED_ASPECT_RATIOS = {"1:1", "16:9", "9:16", "4:3", "3:4", "21:9"}
ALLOWED_RESOLUTIONS = {"1K", "2K"}
MAX_JOBS = 10
JOB_TTL = timedelta(minutes=10)
MAX_AUDIENCE_LEN = 4000


# --- Provider seam ---------------------------------------------------------
# One abstraction over image backends. Adapters take a prompt plus etch's
# semantic (aspect_ratio, resolution) and return PNG bytes. The key is injected
# per call (never read from env inside an adapter) so resolution stays fail-fast
# at the tool layer and the adapters stay testable.


class GenerationError(RuntimeError):
    """A sanitized, provider-agnostic generation failure.

    Adapters wrap provider-native exceptions (httpx errors, SDK errors) in this
    type so the message stored in job state never leaks URLs, keys, or raw HTML.
    Subclasses RuntimeError to stay compatible with the existing error contract.
    Messages tagged ``NO_IMAGE:`` mark the "model returned no image" case.
    """


class ImageProvider(Protocol):
    """The seam every image backend implements. ``generate`` returns PNG bytes."""

    model_id: str
    key_env_var: str

    def supports(self, aspect_ratio: str, resolution: str) -> bool: ...
    def describe_support(self) -> str: ...
    def generate(self, prompt: str, aspect_ratio: str, resolution: str, api_key: str) -> bytes: ...


class GeminiProvider:
    """Google Gemini (default). Takes aspect_ratio and resolution natively."""

    model_id = DEFAULT_MODEL
    key_env_var = "GOOGLE_API_KEY"

    def supports(self, aspect_ratio: str, resolution: str) -> bool:
        return aspect_ratio in ALLOWED_ASPECT_RATIOS and resolution in ALLOWED_RESOLUTIONS

    def describe_support(self) -> str:
        return (
            f"aspect_ratio ∈ {sorted(ALLOWED_ASPECT_RATIOS)}, "
            f"resolution ∈ {sorted(ALLOWED_RESOLUTIONS)}"
        )

    def generate(self, prompt: str, aspect_ratio: str, resolution: str, api_key: str) -> bytes:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=self.model_id,
                contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
                config=types.GenerateContentConfig(
                    max_output_tokens=32768,
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect_ratio, image_size=resolution
                    ),
                ),
            )
        except Exception as e:
            raise GenerationError(f"Gemini request failed: {type(e).__name__}") from e

        if not response.candidates:
            feedback = getattr(response, "prompt_feedback", None)
            raise GenerationError(
                f"NO_IMAGE: Gemini returned no candidates (prompt_feedback={feedback})"
            )
        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            reason = getattr(candidate, "finish_reason", None)
            raise GenerationError(f"NO_IMAGE: Gemini returned empty content (finish_reason={reason})")
        for part in candidate.content.parts:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                data = inline.data
                return base64.b64decode(data) if isinstance(data, str) else data
        raise GenerationError("NO_IMAGE: Gemini response had no inline image data")


class MAIProvider:
    """Microsoft MAI-Image-2.5, reachable via two transports.

    Selected by the ``MAI_TRANSPORT`` env var (default ``"foundry"``):

    - ``foundry`` — Azure AI Foundry REST. POSTs ``{model, prompt, width, height}``
      to ``{MAI_ENDPOINT}/mai/v1/images/generations`` with an ``api-key`` header;
      reads ``data[0].b64_json``. Requires ``MAI_ENDPOINT`` and ``MAI_API_KEY``.
    - ``openrouter`` — OpenRouter's OpenAI-style chat endpoint (no Azure
      provisioning). POSTs a chat-completions request with
      ``modalities: ["image", "text"]`` and ``image_config`` to
      ``/api/v1/chat/completions`` with a ``Bearer`` token; reads the image back
      from ``choices[0].message.images[0].image_url.url`` (a base64 data URL).
      Requires ``OPENROUTER_API_KEY``.

    Both transports share the same capability surface. MAI is ~1 MP: it cannot do
    "2K" (~4x over the pixel cap) or 21:9 (min-768 on both edges forces > 1.37 MP).
    ``_SIZE_MAP`` is the single source of truth for the supported
    (aspect_ratio, resolution) set; ``supports`` is membership in it. The Foundry
    transport reads the mapped (width, height); OpenRouter passes the aspect_ratio
    string straight to ``image_config`` (it derives the pixel dims itself).
    """

    model_id = "mai-image-2.5"

    # Supported (aspect_ratio, resolution) -> Foundry (width, height); dims are
    # multiples of 8 and each satisfies width,height >= 768 and w*h <= 1,048,576.
    # OpenRouter accepts the same ratios (no 21:9) and derives its own dims.
    _SIZE_MAP: dict[tuple[str, str], tuple[int, int]] = {
        ("1:1", "1K"): (1024, 1024),
        ("16:9", "1K"): (1360, 768),
        ("9:16", "1K"): (768, 1360),
        ("4:3", "1K"): (1024, 768),
        ("3:4", "1K"): (768, 1024),
    }

    _OPENROUTER_DEFAULT_URL = "https://openrouter.ai/api/v1/chat/completions"
    _OPENROUTER_DEFAULT_MODEL = "microsoft/mai-image-2.5"

    def __init__(
        self,
        transport: Optional[str] = None,
        endpoint: Optional[str] = None,
        deployment: Optional[str] = None,
        key_env_var: Optional[str] = None,
    ) -> None:
        # Read transport config once with os.environ.get (never raises at import).
        self._transport = (transport or os.environ.get("MAI_TRANSPORT", "foundry")).lower()
        if self._transport == "openrouter":
            self.key_env_var = key_env_var or "OPENROUTER_API_KEY"
            self._or_url = os.environ.get("OPENROUTER_URL", self._OPENROUTER_DEFAULT_URL)
            self._or_model = os.environ.get("MAI_OPENROUTER_MODEL", self._OPENROUTER_DEFAULT_MODEL)
        else:
            self.key_env_var = key_env_var or "MAI_API_KEY"
            self._endpoint = endpoint if endpoint is not None else os.environ.get("MAI_ENDPOINT")
            self._deployment = deployment or os.environ.get("MAI_DEPLOYMENT", "MAI-Image-2.5")

    def supports(self, aspect_ratio: str, resolution: str) -> bool:
        return (aspect_ratio, resolution) in self._SIZE_MAP

    def describe_support(self) -> str:
        return f"{sorted(self._SIZE_MAP)} (1K only — no 21:9, no 2K)"

    def generate(self, prompt: str, aspect_ratio: str, resolution: str, api_key: str) -> bytes:
        if self._transport == "openrouter":
            return self._generate_openrouter(prompt, aspect_ratio, resolution, api_key)
        return self._generate_foundry(prompt, aspect_ratio, resolution, api_key)

    def _generate_foundry(self, prompt: str, aspect_ratio: str, resolution: str, api_key: str) -> bytes:
        try:
            width, height = self._SIZE_MAP[(aspect_ratio, resolution)]
        except KeyError:
            raise GenerationError(
                f"mai-image-2.5 does not support aspect_ratio={aspect_ratio!r}, "
                f"resolution={resolution!r}"
            )
        if not self._endpoint:
            raise GenerationError("MAI_ENDPOINT is not configured")

        url = f"{self._endpoint.rstrip('/')}/mai/v1/images/generations"
        payload = {"model": self._deployment, "prompt": prompt, "width": width, "height": height}
        body = self._post(url, {"api-key": api_key}, payload, "MAI")

        items = body.get("data") or []
        if not items or not items[0].get("b64_json"):
            raise GenerationError("NO_IMAGE: MAI response had no image data")
        return base64.b64decode(items[0]["b64_json"])

    def _generate_openrouter(self, prompt: str, aspect_ratio: str, resolution: str, api_key: str) -> bytes:
        payload = {
            "model": self._or_model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image", "text"],
            "image_config": {"aspect_ratio": aspect_ratio, "image_size": resolution},
        }
        body = self._post(self._or_url, {"Authorization": f"Bearer {api_key}"}, payload, "OpenRouter")

        choices = body.get("choices") or []
        images = (choices[0].get("message", {}).get("images") if choices else None) or []
        url = images[0].get("image_url", {}).get("url", "") if images else ""
        if not url:
            raise GenerationError("NO_IMAGE: OpenRouter response had no image data")
        b64 = url.split(",", 1)[1] if "," in url else url  # strip "data:image/png;base64," prefix
        if not b64:
            raise GenerationError("NO_IMAGE: OpenRouter image had no data")
        return base64.b64decode(b64)

    @staticmethod
    def _post(url: str, auth_headers: dict, payload: dict, label: str) -> dict:
        """POST JSON and return the parsed body, wrapping transport errors sanitized."""
        try:
            resp = httpx.post(
                url,
                headers={**auth_headers, "Content-Type": "application/json"},
                json=payload,
                timeout=120.0,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise GenerationError(f"{label} request failed (HTTP {e.response.status_code})") from e
        except httpx.HTTPError as e:
            raise GenerationError(f"{label} request error: {type(e).__name__}") from e
        except ValueError as e:  # JSON decode failure
            raise GenerationError(f"{label} returned a non-JSON response") from e


PROVIDERS: dict[str, ImageProvider] = {
    p.model_id: p for p in (GeminiProvider(), MAIProvider())
}


def resolve_provider(model: str) -> ImageProvider:
    """Map a model id to its provider, or raise ValueError listing valid ids."""
    provider = PROVIDERS.get(model)
    if provider is None:
        raise ValueError(f"unknown model {model!r}; available: {sorted(PROVIDERS)}")
    return provider


def validate_capabilities(provider: ImageProvider, aspect_ratio: str, resolution: str) -> None:
    """Reject an (aspect_ratio, resolution) the provider can't honor, with a clear message."""
    if not provider.supports(aspect_ratio, resolution):
        raise ValueError(
            f"{provider.model_id} does not support aspect_ratio={aspect_ratio!r}, "
            f"resolution={resolution!r}. Supported: {provider.describe_support()}"
        )


def resolve_api_key(provider: ImageProvider) -> str:
    """Read the selected provider's key from the environment (fail-fast)."""
    api_key = os.environ.get(provider.key_env_var)
    if not api_key:
        raise RuntimeError(f"{provider.key_env_var} environment variable is not set")
    return api_key


mcp = FastMCP("etch")

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _build_prompt(description: str, audience: Optional[str]) -> str:
    """Construct the prompt sent to the image model.

    When audience is None, empty, or whitespace-only, returns the description
    unchanged (byte-identical to the pre-audience behavior).
    """
    if audience is None or not audience.strip():
        return description
    audience_text = audience.strip()
    if len(audience_text) > MAX_AUDIENCE_LEN:
        raise ValueError(
            f"audience must be {MAX_AUDIENCE_LEN} characters or fewer "
            f"(got {len(audience_text)})"
        )
    return (
        f"[Target audience]\n{audience_text}\n"
        "Tailor abstraction level, vocabulary, what to emphasize, "
        "what to omit, and visual register to suit this audience.\n\n"
        f"[Diagram]\n{description}"
    )


def _cleanup_jobs() -> None:
    now = datetime.now()
    with _jobs_lock:
        for jid in [j for j, job in _jobs.items() if now - job["created"] > JOB_TTL]:
            del _jobs[jid]
        if len(_jobs) > MAX_JOBS:
            done = sorted(
                (
                    (jid, job["created"])
                    for jid, job in _jobs.items()
                    if job["status"] in ("complete", "failed")
                ),
                key=lambda x: x[1],
            )
            for jid, _ in done[: len(_jobs) - MAX_JOBS]:
                del _jobs[jid]


def _run_generation(
    job_id: str,
    provider: ImageProvider,
    api_key: str,
    description: str,
    audience: Optional[str],
    aspect_ratio: str,
    resolution: str,
    output_dir: Path,
) -> None:
    try:
        with _jobs_lock:
            _jobs[job_id]["status"] = "generating"

        prompt = _build_prompt(description, audience)
        image_bytes = provider.generate(prompt, aspect_ratio, resolution, api_key)

        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"diagram_{datetime.now():%Y%m%d_%H%M%S}_{job_id[:8]}.png"
        file_path.write_bytes(image_bytes)

        with _jobs_lock:
            _jobs[job_id]["status"] = "complete"
            _jobs[job_id]["file_path"] = str(file_path)
    except Exception as e:
        with _jobs_lock:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = f"{type(e).__name__}: {e}"


@mcp.tool()
def start_diagram_job(
    description: str,
    aspect_ratio: str = "16:9",
    resolution: str = "2K",
    output_dir: Optional[str] = None,
    audience: Optional[str] = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """Start an async diagram-generation job. Returns a job_id; poll check_job_status.

    Args:
        description: What to draw — components, labels, relationships.
        aspect_ratio: 1:1, 16:9, 9:16, 4:3, 3:4, or 21:9.
        resolution: 1K or 2K.
        output_dir: Where to save the PNG (defaults to cwd).
        audience: Optional free-form description of the target audience.
            When provided, the description is wrapped with a frame instructing
            the model to tailor abstraction, vocabulary, emphasis, and visual
            register accordingly. Skill callers (see skills/etch/SKILL.md) are
            expected to author rich audience prose; raw human-typed audience
            strings ("for developers") also work but produce weaker steering.
        model: Image backend. "gemini-3-pro-image-preview" (default) supports
            every aspect_ratio at 1K/2K. "mai-image-2.5" is ~1 MP only: it
            rejects 2K and 21:9 — use 1K with a non-ultrawide ratio.
    """
    provider = resolve_provider(model)
    validate_capabilities(provider, aspect_ratio, resolution)
    api_key = resolve_api_key(provider)

    # Validate audience eagerly: raises ValueError if over cap, before queuing.
    _build_prompt(description, audience)

    _cleanup_jobs()
    job_id = str(uuid.uuid4())
    out_dir = Path(output_dir) if output_dir else Path.cwd()

    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "created": datetime.now()}

    threading.Thread(
        target=_run_generation,
        args=(job_id, provider, api_key, description, audience, aspect_ratio, resolution, out_dir),
        daemon=True,
    ).start()

    return job_id


@mcp.tool()
def check_job_status(job_id: str) -> str:
    """Check progress of a diagram job. Poll every ~10s; generation typically takes 30-60s.

    Returns one of:
      - "queued (Xs elapsed)"
      - "generating (Xs elapsed, typically 30-60s)"
      - "complete (Xs) — saved to <path>"
      - "failed (Xs): <reason>"
    """
    _cleanup_jobs()
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise ValueError(f"job not found: {job_id}")
        snapshot = dict(job)

    elapsed = (datetime.now() - snapshot["created"]).total_seconds()
    status = snapshot["status"]
    if status == "complete":
        return f"complete ({elapsed:.0f}s) — saved to {snapshot['file_path']}"
    if status == "failed":
        return f"failed ({elapsed:.0f}s): {snapshot.get('error', 'unknown error')}"
    if status == "generating":
        return f"generating ({elapsed:.0f}s elapsed, typically 30-60s)"
    return f"queued ({elapsed:.0f}s elapsed)"


def main():
    mcp.run()


if __name__ == "__main__":
    main()
