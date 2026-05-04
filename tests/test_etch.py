"""Tests for etch.py — prompt construction and audience validation."""

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
