"""Tests for etch.py — prompt construction and audience validation."""

import base64

import pytest

import etch


def test_build_prompt_without_audience_returns_description_unchanged():
    """Backward-compat: audience=None must produce a prompt identical to today's."""
    description = "Architecture diagram with three services and a database."
    assert etch._build_prompt(description, None) == description


def test_build_prompt_treats_empty_audience_as_none():
    """Empty string audience behaves like None."""
    description = "Some description."
    assert etch._build_prompt(description, "") == description


def test_build_prompt_treats_whitespace_audience_as_none():
    """Whitespace-only audience behaves like None."""
    description = "Some description."
    assert etch._build_prompt(description, "   \n\t  ") == description


def test_build_prompt_with_audience_wraps_in_frame():
    """When audience is present, prompt is wrapped with the audience frame."""
    description = "Three services and a database."
    audience = "Reader is a software architect evaluating system structure."
    result = etch._build_prompt(description, audience)

    assert "[Target audience]" in result
    assert "[Diagram]" in result
    assert audience in result
    assert description in result
    # Audience block must precede diagram block.
    assert result.index("[Target audience]") < result.index("[Diagram]")
    assert result.index(audience) < result.index(description)


def test_build_prompt_strips_audience_whitespace():
    """Surrounding whitespace on the audience string is stripped before framing."""
    description = "A diagram."
    result = etch._build_prompt(description, "  Some audience.  \n")
    assert "  Some audience.  " not in result
    assert "Some audience." in result


def test_build_prompt_includes_tailoring_directive():
    """The frame must instruct the model to tailor its output."""
    result = etch._build_prompt("desc", "exec audience")
    assert "Tailor" in result
    assert "audience" in result


def test_build_prompt_rejects_audience_over_cap():
    """An audience string over the cap must raise ValueError."""
    description = "A diagram."
    too_long = "x" * (etch.MAX_AUDIENCE_LEN + 1)
    with pytest.raises(ValueError, match="audience"):
        etch._build_prompt(description, too_long)


def test_build_prompt_accepts_audience_at_cap():
    """An audience string exactly at the cap must succeed."""
    description = "A diagram."
    at_cap = "x" * etch.MAX_AUDIENCE_LEN
    result = etch._build_prompt(description, at_cap)
    assert at_cap in result


# --- Provider seam ---------------------------------------------------------


def test_default_model_is_gemini_and_supports_legacy_defaults():
    """Backward-compat: the default model must accept etch's current default request."""
    provider = etch.resolve_provider(etch.DEFAULT_MODEL)
    assert provider.model_id == "gemini-3-pro-image-preview"
    assert provider.key_env_var == "GOOGLE_API_KEY"
    assert provider.supports("16:9", "2K")  # the existing default (aspect_ratio, resolution)


def test_resolve_provider_unknown_raises():
    with pytest.raises(ValueError, match="unknown model"):
        etch.resolve_provider("does-not-exist")


def test_gemini_supports_full_matrix():
    g = etch.resolve_provider("gemini-3-pro-image-preview")
    for ar in ["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"]:
        for res in ["1K", "2K"]:
            assert g.supports(ar, res), f"{ar} {res}"


def test_mai_rejects_2k_and_ultrawide():
    """MAI is ~1 MP only: 2K (4x over cap) and 21:9 (>1.37 MP) are unsupported."""
    m = etch.resolve_provider("mai-image-2.5")
    assert not m.supports("16:9", "2K")
    assert not m.supports("1:1", "2K")
    assert not m.supports("21:9", "1K")
    assert not m.supports("21:9", "2K")


def test_mai_supports_1k_non_wide_ratios():
    m = etch.resolve_provider("mai-image-2.5")
    for ar in ["1:1", "16:9", "9:16", "4:3", "3:4"]:
        assert m.supports(ar, "1K"), ar


def test_mai_size_map_obeys_hard_limits():
    """Single source of truth: every mapped size satisfies MAI's documented limits."""
    m = etch.resolve_provider("mai-image-2.5")
    assert m._SIZE_MAP, "size map must not be empty"
    for (ar, res), (w, h) in m._SIZE_MAP.items():
        assert w >= 768 and h >= 768, f"{ar} {res} -> {w}x{h} below 768 floor"
        assert w * h <= 1_048_576, f"{ar} {res} -> {w}x{h} exceeds 1 MP cap"


def test_validate_capabilities_rejects_with_clear_message():
    m = etch.resolve_provider("mai-image-2.5")
    with pytest.raises(ValueError, match="does not support"):
        etch.validate_capabilities(m, "21:9", "2K")


def test_validate_capabilities_passes_for_supported_combo():
    g = etch.resolve_provider("gemini-3-pro-image-preview")
    assert etch.validate_capabilities(g, "16:9", "2K") is None  # no raise


def test_resolve_api_key_missing_raises(monkeypatch):
    """Fail-fast: a missing key for the selected provider raises before any work."""
    g = etch.resolve_provider("gemini-3-pro-image-preview")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        etch.resolve_api_key(g)


def test_generation_error_is_runtime_error():
    """The error contract stays RuntimeError-compatible across providers."""
    assert issubclass(etch.GenerationError, RuntimeError)


# --- MAI transports (Foundry + OpenRouter), HTTP mocked ---------------------

# A 1x1 PNG, base64-encoded.
_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_mai_openrouter_transport_uses_openrouter_key():
    p = etch.MAIProvider(transport="openrouter")
    assert p.key_env_var == "OPENROUTER_API_KEY"
    # Same capability surface as the Foundry transport.
    assert p.supports("16:9", "1K")
    assert not p.supports("21:9", "1K")
    assert not p.supports("16:9", "2K")


def test_mai_openrouter_builds_chat_request_and_decodes_data_url(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json)
        return _FakeResp(
            {"choices": [{"message": {"images": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_PNG_B64}"}}
            ]}}]}
        )

    monkeypatch.setattr(etch.httpx, "post", fake_post)
    p = etch.MAIProvider(transport="openrouter")
    out = p.generate("draw a box", "16:9", "1K", "sk-or-test")

    assert out == base64.b64decode(_PNG_B64)
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-or-test"
    assert captured["json"]["model"] == "microsoft/mai-image-2.5"
    assert captured["json"]["modalities"] == ["image"]
    assert captured["json"]["image_config"]["aspect_ratio"] == "16:9"
    assert captured["json"]["messages"][0]["content"] == "draw a box"


def test_mai_openrouter_no_image_raises(monkeypatch):
    monkeypatch.setattr(
        etch.httpx, "post",
        lambda url, headers, json, timeout: _FakeResp({"choices": [{"message": {"content": "no"}}]}),
    )
    p = etch.MAIProvider(transport="openrouter")
    with pytest.raises(etch.GenerationError, match="NO_IMAGE"):
        p.generate("x", "1:1", "1K", "sk-or-test")


def test_mai_foundry_builds_request_and_decodes_b64json(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json)
        return _FakeResp({"data": [{"b64_json": _PNG_B64}]})

    monkeypatch.setattr(etch.httpx, "post", fake_post)
    p = etch.MAIProvider(
        transport="foundry", endpoint="https://res.services.ai.azure.com", deployment="MAI-Image-2.5"
    )
    out = p.generate("draw a box", "16:9", "1K", "azkey")

    assert out == base64.b64decode(_PNG_B64)
    assert captured["url"] == "https://res.services.ai.azure.com/mai/v1/images/generations"
    assert captured["headers"]["api-key"] == "azkey"
    assert captured["json"] == {
        "model": "MAI-Image-2.5", "prompt": "draw a box", "width": 1360, "height": 768,
    }


def test_mai_foundry_missing_endpoint_raises():
    p = etch.MAIProvider(transport="foundry", endpoint="")
    with pytest.raises(etch.GenerationError, match="MAI_ENDPOINT"):
        p.generate("x", "1:1", "1K", "k")


# --- Reference-image conditioning -------------------------------------------


def test_gemini_max_reference_images_is_14():
    g = etch.resolve_provider("gemini-3-pro-image-preview")
    assert g.max_reference_images == 14


def test_mai_max_reference_images_is_0():
    m = etch.resolve_provider("mai-image-2.5")
    assert m.max_reference_images == 0


def test_gemini_generate_without_references_is_byte_identical_to_baseline(monkeypatch):
    """Hard constraint: empty reference_images must build the same contents as before."""
    captured = {}

    class _Client:
        def __init__(self, api_key):
            self.models = self

        def generate_content(self, model, contents, config):
            captured["contents"] = contents
            captured["config"] = config
            part = etch.types.Part(
                inline_data=etch.types.Blob(
                    data=base64.b64decode(_PNG_B64), mime_type="image/png"
                )
            )
            candidate = etch.types.Candidate(content=etch.types.Content(role="model", parts=[part]))
            return etch.types.GenerateContentResponse(candidates=[candidate])

    monkeypatch.setattr(etch.genai, "Client", _Client)
    g = etch.resolve_provider("gemini-3-pro-image-preview")
    out = g.generate("draw a box", "16:9", "2K", "gk")

    assert out == base64.b64decode(_PNG_B64)
    contents = captured["contents"]
    assert len(contents) == 1
    assert contents[0].role == "user"
    assert len(contents[0].parts) == 1
    assert contents[0].parts[0].text == "draw a box"
    assert contents[0].parts[0].inline_data is None


def test_gemini_generate_with_references_includes_image_parts(monkeypatch):
    captured = {}

    class _Client:
        def __init__(self, api_key):
            self.models = self

        def generate_content(self, model, contents, config):
            captured["contents"] = contents
            part = etch.types.Part(
                inline_data=etch.types.Blob(
                    data=base64.b64decode(_PNG_B64), mime_type="image/png"
                )
            )
            candidate = etch.types.Candidate(content=etch.types.Content(role="model", parts=[part]))
            return etch.types.GenerateContentResponse(candidates=[candidate])

    monkeypatch.setattr(etch.genai, "Client", _Client)
    g = etch.resolve_provider("gemini-3-pro-image-preview")
    refs = [
        etch.ReferenceImage(b"fake-png-bytes-1", "image/png"),
        etch.ReferenceImage(b"fake-png-bytes-2", "image/jpeg"),
    ]
    g.generate("draw a box", "16:9", "2K", "gk", reference_images=refs)

    contents = captured["contents"]
    assert len(contents) == 1
    parts = contents[0].parts
    assert len(parts) == 3  # 2 reference images + 1 text part
    image_parts = [p for p in parts if p.inline_data is not None]
    text_parts = [p for p in parts if p.text is not None]
    assert len(image_parts) == 2
    assert len(text_parts) == 1
    assert text_parts[0].text == "draw a box"
    assert {p.inline_data.data for p in image_parts} == {b"fake-png-bytes-1", b"fake-png-bytes-2"}
    assert {p.inline_data.mime_type for p in image_parts} == {"image/png", "image/jpeg"}


def test_mai_generate_raises_when_reference_images_supplied():
    p = etch.MAIProvider(transport="foundry", endpoint="https://res.services.ai.azure.com")
    refs = [etch.ReferenceImage(b"data", "image/png")]
    with pytest.raises(etch.GenerationError, match="does not support"):
        p.generate("x", "1:1", "1K", "k", reference_images=refs)


def test_mai_generate_unaffected_when_no_reference_images(monkeypatch):
    """Existing MAI transport behavior is unchanged when reference_images is omitted."""
    monkeypatch.setattr(
        etch.httpx, "post",
        lambda url, headers, json, timeout: _FakeResp({"data": [{"b64_json": _PNG_B64}]}),
    )
    p = etch.MAIProvider(transport="foundry", endpoint="https://res.services.ai.azure.com")
    out = p.generate("draw a box", "16:9", "1K", "azkey")
    assert out == base64.b64decode(_PNG_B64)


def test_load_reference_images_empty_paths_returns_empty_list():
    g = etch.resolve_provider("gemini-3-pro-image-preview")
    assert etch._load_reference_images([], g) == []


def test_load_reference_images_missing_file_raises(tmp_path):
    g = etch.resolve_provider("gemini-3-pro-image-preview")
    missing = str(tmp_path / "does-not-exist.png")
    with pytest.raises(ValueError, match="cannot read"):
        etch._load_reference_images([missing], g)


def test_load_reference_images_unsupported_format_raises(tmp_path):
    g = etch.resolve_provider("gemini-3-pro-image-preview")
    bad_file = tmp_path / "not-an-image.txt"
    bad_file.write_bytes(b"just some text, not an image")
    with pytest.raises(ValueError, match="not a supported format"):
        etch._load_reference_images([str(bad_file)], g)


def test_load_reference_images_over_provider_max_raises(tmp_path):
    g = etch.resolve_provider("gemini-3-pro-image-preview")
    png_bytes = base64.b64decode(_PNG_B64)
    paths = []
    for i in range(g.max_reference_images + 1):
        f = tmp_path / f"ref_{i}.png"
        f.write_bytes(png_bytes)
        paths.append(str(f))
    with pytest.raises(ValueError, match="at most"):
        etch._load_reference_images(paths, g)


def test_load_reference_images_provider_with_max_zero_raises(tmp_path):
    m = etch.resolve_provider("mai-image-2.5")
    png_bytes = base64.b64decode(_PNG_B64)
    f = tmp_path / "ref.png"
    f.write_bytes(png_bytes)
    with pytest.raises(ValueError, match="does not support reference-image conditioning"):
        etch._load_reference_images([str(f)], m)


def test_load_reference_images_oversized_file_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(etch, "MAX_REFERENCE_IMAGE_BYTES", 10)
    g = etch.resolve_provider("gemini-3-pro-image-preview")
    f = tmp_path / "ref.png"
    f.write_bytes(base64.b64decode(_PNG_B64))  # well over 10 bytes
    with pytest.raises(ValueError, match="exceeding"):
        etch._load_reference_images([str(f)], g)


def test_load_reference_images_valid_png_returns_bytes_and_mime(tmp_path):
    g = etch.resolve_provider("gemini-3-pro-image-preview")
    png_bytes = base64.b64decode(_PNG_B64)
    f = tmp_path / "ref.png"
    f.write_bytes(png_bytes)
    result = etch._load_reference_images([str(f)], g)
    assert result == [etch.ReferenceImage(png_bytes, "image/png")]


# --- MCP tool layer: reference_images wiring ---------------------------------


class _FakeProvider:
    """A minimal ImageProvider stand-in that records generate() calls."""

    model_id = "fake-model"
    key_env_var = "FAKE_API_KEY"
    max_reference_images = 14

    def __init__(self):
        self.calls = []

    def supports(self, aspect_ratio, resolution):
        return True

    def describe_support(self):
        return "fake"

    def generate(self, prompt, aspect_ratio, resolution, api_key, reference_images=()):
        self.calls.append(
            {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "api_key": api_key,
                "reference_images": list(reference_images),
            }
        )
        return base64.b64decode(_PNG_B64)


def test_run_generation_default_calls_provider_with_empty_references(tmp_path):
    """Hard constraint: reference_images omitted -> provider.generate sees an empty sequence."""
    provider = _FakeProvider()
    etch._jobs["job-default"] = {"status": "queued", "created": etch.datetime.now()}
    etch._run_generation(
        "job-default", provider, "k", "draw a box", None, "16:9", "2K", tmp_path
    )
    assert len(provider.calls) == 1
    assert provider.calls[0]["reference_images"] == []
    assert etch._jobs["job-default"]["status"] == "complete"


def test_run_generation_threads_references_through_to_provider(tmp_path):
    provider = _FakeProvider()
    refs = [
        etch.ReferenceImage(b"fake-bytes-1", "image/png"),
        etch.ReferenceImage(b"fake-bytes-2", "image/jpeg"),
    ]
    etch._jobs["job-refs"] = {"status": "queued", "created": etch.datetime.now()}
    etch._run_generation(
        "job-refs", provider, "k", "draw a box", None, "16:9", "2K", tmp_path,
        reference_images=refs,
    )
    assert len(provider.calls) == 1
    assert provider.calls[0]["reference_images"] == refs
    assert etch._jobs["job-refs"]["status"] == "complete"


def test_start_diagram_job_default_reference_images_is_byte_identical(monkeypatch, tmp_path):
    """Hard constraint: reference_images=None threads an empty sequence into _run_generation."""
    captured = {}

    def fake_run_generation(job_id, provider, api_key, description, audience,
                             aspect_ratio, resolution, output_dir, reference_images=()):
        captured["reference_images"] = list(reference_images)
        with etch._jobs_lock:
            etch._jobs[job_id]["status"] = "complete"
            etch._jobs[job_id]["file_path"] = "unused"

    monkeypatch.setenv("GOOGLE_API_KEY", "gk")
    monkeypatch.setattr(etch, "_run_generation", fake_run_generation)
    monkeypatch.setattr(etch.threading, "Thread", _SyncThread)

    job_id = etch.start_diagram_job("draw a box", output_dir=str(tmp_path))
    assert job_id in etch._jobs
    assert captured["reference_images"] == []


def test_start_diagram_job_threads_reference_image_paths(monkeypatch, tmp_path):
    """Passing file paths threads decoded ReferenceImages through to _run_generation."""
    captured = {}

    def fake_run_generation(job_id, provider, api_key, description, audience,
                             aspect_ratio, resolution, output_dir, reference_images=()):
        captured["reference_images"] = list(reference_images)
        with etch._jobs_lock:
            etch._jobs[job_id]["status"] = "complete"
            etch._jobs[job_id]["file_path"] = "unused"

    monkeypatch.setenv("GOOGLE_API_KEY", "gk")
    monkeypatch.setattr(etch, "_run_generation", fake_run_generation)
    monkeypatch.setattr(etch.threading, "Thread", _SyncThread)

    png_bytes = base64.b64decode(_PNG_B64)
    paths = []
    for i in range(2):
        f = tmp_path / f"ref_{i}.png"
        f.write_bytes(png_bytes)
        paths.append(str(f))

    job_id = etch.start_diagram_job(
        "draw a box", output_dir=str(tmp_path), reference_images=paths
    )
    assert job_id in etch._jobs
    refs = captured["reference_images"]
    assert len(refs) == 2
    assert all(r == etch.ReferenceImage(png_bytes, "image/png") for r in refs)


def test_start_diagram_job_rejects_references_for_unsupported_provider_before_queuing(
    monkeypatch, tmp_path
):
    """A provider with max_reference_images == 0 must raise ValueError before any job is queued."""
    monkeypatch.setenv("MAI_API_KEY", "mk")
    monkeypatch.setenv("MAI_ENDPOINT", "https://res.services.ai.azure.com")

    png_bytes = base64.b64decode(_PNG_B64)
    f = tmp_path / "ref.png"
    f.write_bytes(png_bytes)

    jobs_before = dict(etch._jobs)
    with pytest.raises(ValueError, match="does not support reference-image conditioning"):
        etch.start_diagram_job(
            "draw a box",
            aspect_ratio="1:1",
            resolution="1K",
            output_dir=str(tmp_path),
            model="mai-image-2.5",
            reference_images=[str(f)],
        )
    assert etch._jobs == jobs_before


# --- Nano Banana 2 (gemini-3.1-flash-image) ----------------------------------


def _fake_gemini_client(captured):
    """A genai.Client stand-in that records the generate_content call and
    returns a single inline PNG, matching the shape of a real response."""

    class _Client:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.models = self

        def generate_content(self, model, contents, config):
            captured.update(model=model, contents=contents, config=config)
            part = etch.types.Part(
                inline_data=etch.types.Blob(
                    data=base64.b64decode(_PNG_B64), mime_type="image/png"
                )
            )
            candidate = etch.types.Candidate(content=etch.types.Content(role="model", parts=[part]))
            return etch.types.GenerateContentResponse(candidates=[candidate])

    return _Client


def test_providers_registry_lists_both_gemini_models_and_mai():
    assert set(etch.PROVIDERS) == {
        "gemini-3-pro-image-preview",
        "gemini-3.1-flash-image",
        "mai-image-2.5",
    }


def test_resolve_provider_nb2_returns_gemini_backed_provider():
    nb2 = etch.resolve_provider("gemini-3.1-flash-image")
    assert isinstance(nb2, etch.GeminiProvider)
    assert nb2.model_id == "gemini-3.1-flash-image"
    assert nb2.key_env_var == "GOOGLE_API_KEY"


def test_nb2_supports_512px_and_full_matrix():
    nb2 = etch.resolve_provider("gemini-3.1-flash-image")
    for ar in ["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"]:
        for res in ["512px", "1K", "2K"]:
            assert nb2.supports(ar, res), f"{ar} {res}"


def test_pro_still_rejects_512px_via_validate_capabilities():
    """Pro's matrix is unchanged: 1K/2K only, and 512px fails with the existing message style."""
    pro = etch.resolve_provider("gemini-3-pro-image-preview")
    assert not pro.supports("16:9", "512px")
    with pytest.raises(ValueError, match="does not support"):
        etch.validate_capabilities(pro, "16:9", "512px")


def test_nb2_max_reference_images_is_positive():
    """NB2 must accept reference images so it can refine a picked variant."""
    nb2 = etch.resolve_provider("gemini-3.1-flash-image")
    assert nb2.max_reference_images > 0


def test_nb2_generate_uses_nb2_model_id_and_maps_512px_to_sdk_literal(monkeypatch):
    """NB2 sends its own model_id and maps etch's '512px' to the SDK's '512'."""
    captured = {}
    monkeypatch.setattr(etch.genai, "Client", _fake_gemini_client(captured))
    nb2 = etch.resolve_provider("gemini-3.1-flash-image")
    out = nb2.generate("draw a box", "16:9", "512px", "gk")

    assert out == base64.b64decode(_PNG_B64)
    assert captured["model"] == "gemini-3.1-flash-image"
    assert captured["config"].image_config.image_size == "512"
    assert captured["config"].image_config.aspect_ratio == "16:9"


def test_nb2_generate_passes_1k_and_2k_through_unchanged(monkeypatch):
    captured = {}
    monkeypatch.setattr(etch.genai, "Client", _fake_gemini_client(captured))
    nb2 = etch.resolve_provider("gemini-3.1-flash-image")
    for res in ["1K", "2K"]:
        nb2.generate("draw a box", "16:9", res, "gk")
        assert captured["config"].image_config.image_size == res


def test_nb2_generate_with_references_includes_image_parts(monkeypatch):
    captured = {}
    monkeypatch.setattr(etch.genai, "Client", _fake_gemini_client(captured))
    nb2 = etch.resolve_provider("gemini-3.1-flash-image")
    refs = [etch.ReferenceImage(b"fake-png-bytes-1", "image/png")]
    nb2.generate("refine the pick", "16:9", "512px", "gk", reference_images=refs)

    assert captured["model"] == "gemini-3.1-flash-image"
    parts = captured["contents"][0].parts
    assert len(parts) == 2  # 1 reference image + 1 text part
    image_parts = [p for p in parts if p.inline_data is not None]
    assert len(image_parts) == 1
    assert image_parts[0].inline_data.data == b"fake-png-bytes-1"
    assert parts[-1].text == "refine the pick"


def test_pro_generate_request_is_byte_identical_after_nb2(monkeypatch):
    """Hard constraint: Pro still sends its own model_id and an unmapped 1K/2K image_size."""
    captured = {}
    monkeypatch.setattr(etch.genai, "Client", _fake_gemini_client(captured))
    pro = etch.resolve_provider("gemini-3-pro-image-preview")
    pro.generate("draw a box", "16:9", "2K", "gk")

    assert captured["model"] == "gemini-3-pro-image-preview"
    assert captured["config"].image_config.image_size == "2K"
    assert captured["config"].image_config.aspect_ratio == "16:9"
    assert captured["contents"][0].parts[0].text == "draw a box"


class _SyncThread:
    """A threading.Thread stand-in that runs the target synchronously on start()."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)
