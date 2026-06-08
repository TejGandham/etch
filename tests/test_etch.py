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
    assert captured["json"]["modalities"] == ["image", "text"]
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
