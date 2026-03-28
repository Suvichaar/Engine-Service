from __future__ import annotations

from app.domain.dto import IntakePayload, LanguageMetadata
from app.services.ingestion import DefaultIngestionAggregator


def make_payload(**overrides):
    defaults = dict(
        text_prompt="Primary text",
        notes="Additional context",
        urls=["https://example.com"],
        attachments=["file1.pdf"],
        prompt_keywords=["analysis", "insights"],
        mode="news",
        template_key="modern",
        slide_count=4,
    )
    defaults.update(overrides)
    return IntakePayload(**defaults)


def make_language(**overrides):
    defaults = dict(language_code="en", confidence=0.9, source_text_preview="Sample preview")
    defaults.update(overrides)
    return LanguageMetadata(**defaults)


def test_aggregator_builds_structured_request():
    # No URLs so text_prompt is included (URL branch skips primary text)
    payload = make_payload(urls=[])
    language = make_language()
    aggregator = DefaultIngestionAggregator()

    job_request = aggregator.aggregate(payload, language)

    assert job_request.text_input and "Primary text" in job_request.text_input
    assert "Additional context" in job_request.text_input
    assert job_request.url_list == []
    assert job_request.attachments[0].uri == "file1.pdf"
    assert job_request.attachments[0].id == "attachment-1"
    assert job_request.focus_keywords == ["analysis", "insights"]


def test_aggregator_handles_empty_values():
    payload = make_payload(text_prompt=None, notes=None, prompt_keywords=[], attachments=[], urls=[])
    language = make_language(source_text_preview=None)
    aggregator = DefaultIngestionAggregator()

    job_request = aggregator.aggregate(payload, language)

    assert job_request.text_input is None
    assert job_request.url_list == []
    assert job_request.attachments == []
    assert job_request.focus_keywords == []


def test_aggregator_includes_slide_texts_when_no_urls():
    payload = make_payload(
        text_prompt=None,
        notes=None,
        urls=[],
        slide_texts=["Slide A", "Slide B", "Slide C", "Slide D"],
    )
    language = make_language(source_text_preview=None)
    job_request = DefaultIngestionAggregator().aggregate(payload, language)
    assert job_request.text_input
    assert "Slide A" in job_request.text_input
    assert "Slide D" in job_request.text_input

