from __future__ import annotations

import pytest

from app.domain.dto import Mode
from app.services.user_input import DefaultUserInputService


def test_build_payload_normalizes_inputs():
    def normalizer(obj) -> str:
        return f"normalized:{obj}"

    service = DefaultUserInputService(attachment_normalizer=normalizer)

    payload = service.build_payload(
        text_prompt="Tell me a story",
        notes="Some notes",
        urls=["https://example.com/one", "https://example.com/two"],
        attachments=["file1.pdf", "file2.png"],
        prompt_keywords=["news", "technology"],
        mode="news",
        template_key="modern_dark",
        slide_count="8",
        category="News",
        image_source="pexels",
        voice_engine="elevenlabs_pro",
    )

    assert payload.text_prompt == "Tell me a story"
    assert payload.slide_count == 8
    assert payload.attachments == ["normalized:file1.pdf", "normalized:file2.png"]
    assert payload.prompt_keywords == ["news", "technology"]
    assert payload.mode == Mode.NEWS
    assert payload.template_key == "modern_dark"
    assert payload.voice_engine == "elevenlabs_pro"


def test_build_payload_filters_invalid_urls():
    service = DefaultUserInputService()

    payload = service.build_payload(
        urls=["https://valid.com", "not-a-url"],
        mode="curious",
        template_key="classic",
        slide_count=4,
    )

    assert [str(url) for url in payload.urls] == ["https://valid.com/"]


def test_build_payload_invalid_mode_raises_value_error():
    service = DefaultUserInputService()

    with pytest.raises(ValueError):
        service.build_payload(
            mode="invalid",
            template_key="classic",
            slide_count=4,
        )

