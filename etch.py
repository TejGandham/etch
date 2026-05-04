#!/usr/bin/env python3
import base64
import os
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types
from mcp.server.fastmcp import FastMCP

MODEL = "gemini-3-pro-image-preview"
ALLOWED_ASPECT_RATIOS = {"1:1", "16:9", "9:16", "4:3", "3:4", "21:9"}
ALLOWED_RESOLUTIONS = {"1K", "2K"}
MAX_JOBS = 10
JOB_TTL = timedelta(minutes=10)
MAX_AUDIENCE_LEN = 4000

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
    api_key: str,
    description: str,
    aspect_ratio: str,
    resolution: str,
    output_dir: Path,
) -> None:
    try:
        with _jobs_lock:
            _jobs[job_id]["status"] = "generating"

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL,
            contents=[types.Content(role="user", parts=[types.Part(text=description)])],
            config=types.GenerateContentConfig(
                max_output_tokens=32768,
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio, image_size=resolution),
            ),
        )

        if not response.candidates:
            feedback = getattr(response, "prompt_feedback", None)
            raise RuntimeError(f"no candidates returned (prompt_feedback={feedback})")
        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            reason = getattr(candidate, "finish_reason", None)
            raise RuntimeError(f"empty content (finish_reason={reason})")

        image_bytes = None
        for part in candidate.content.parts:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                data = inline.data
                image_bytes = base64.b64decode(data) if isinstance(data, str) else data
                break
        if not image_bytes:
            raise RuntimeError("response had no inline image data")

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
) -> str:
    """Start an async diagram-generation job. Returns a job_id; poll check_job_status.

    Args:
        description: What to draw — components, labels, relationships.
        aspect_ratio: 1:1, 16:9, 9:16, 4:3, 3:4, or 21:9.
        resolution: 1K or 2K.
        output_dir: Where to save the PNG (defaults to cwd).
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY environment variable is not set")
    if aspect_ratio not in ALLOWED_ASPECT_RATIOS:
        raise ValueError(f"aspect_ratio must be one of {sorted(ALLOWED_ASPECT_RATIOS)}")
    if resolution not in ALLOWED_RESOLUTIONS:
        raise ValueError(f"resolution must be one of {sorted(ALLOWED_RESOLUTIONS)}")

    _cleanup_jobs()
    job_id = str(uuid.uuid4())
    out_dir = Path(output_dir) if output_dir else Path.cwd()

    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "created": datetime.now()}

    threading.Thread(
        target=_run_generation,
        args=(job_id, api_key, description, aspect_ratio, resolution, out_dir),
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
