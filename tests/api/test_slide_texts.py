"""Unit tests for the slide_texts field on StoryCreateRequest."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.schemas import StoryCreateRequest


VALID_BASE = dict(
    mode="news",
    template_key="template_a",
    slide_count=4,
)


def test_slide_texts_none_is_valid():
    """Backward-compat: omitting slide_texts should still produce a valid request."""
    req = StoryCreateRequest(**VALID_BASE)
    assert req.slide_texts is None


def test_slide_texts_matching_length_is_valid():
    """slide_texts with exactly slide_count items should be accepted."""
    req = StoryCreateRequest(**VALID_BASE, slide_texts=["a", "b", "c", "d"])
    assert req.slide_texts == ["a", "b", "c", "d"]


def test_slide_texts_too_short_raises():
    """slide_texts shorter than slide_count must raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        StoryCreateRequest(**VALID_BASE, slide_texts=["a", "b", "c"])
    assert "slide_texts length must equal slide_count" in str(exc_info.value)


def test_slide_texts_too_long_raises():
    """slide_texts longer than slide_count must raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        StoryCreateRequest(**VALID_BASE, slide_texts=["a", "b", "c", "d", "e"])
    assert "slide_texts length must equal slide_count" in str(exc_info.value)


def test_slide_texts_stripped():
    """Each string in slide_texts is stripped of leading/trailing whitespace."""
    req = StoryCreateRequest(**VALID_BASE, slide_texts=["  hello  ", " world ", "foo", "bar"])
    assert req.slide_texts == ["hello", "world", "foo", "bar"]


def test_slide_texts_empty_string_preserved():
    """Empty strings are NOT stripped away — caller's responsibility to validate content."""
    req = StoryCreateRequest(**VALID_BASE, slide_texts=["a", "", "c", "d"])
    assert req.slide_texts[1] == ""


def test_slide_texts_with_larger_slide_count():
    """Validation scales with slide_count — e.g. 6 items for slide_count=6."""
    req = StoryCreateRequest(
        mode="news",
        template_key="template_b",
        slide_count=6,
        slide_texts=["s1", "s2", "s3", "s4", "s5", "s6"],
    )
    assert len(req.slide_texts) == 6
