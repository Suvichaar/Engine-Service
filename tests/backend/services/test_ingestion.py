from __future__ import annotations

from app.domain.dto import IntakePayload, LanguageMetadata
from app.services.ingestion import DefaultIngestionAggregator


def make_payload(**overrides):
    defaults = dict(
        text_prompt="Primary text",
        notes="Additional context",
        urls=[],  # Removed URL so text_prompt is included
        attachments=["file1.pdf"],
        prompt_keywords=["analysis", "insights"],
        mode="curious",
        template_key="modern",
        slide_count=4,
    )
    defaults.update(overrides)
    return IntakePayload(**defaults)


def make_language(**overrides):
    defaults = dict(
        language_code="en", confidence=0.9, source_text_preview="Sample preview"
    )
    defaults.update(overrides)
    return LanguageMetadata(**defaults)


def test_aggregator_builds_structured_request():
    payload = make_payload()
    language = make_language()
    aggregator = DefaultIngestionAggregator()

    job_request = aggregator.aggregate(payload, language)

    assert job_request.text_input and "Primary text" in job_request.text_input
    assert "Additional context" in job_request.text_input
    assert job_request.url_list == []
    assert job_request.attachments[0].uri == "file1.pdf"
    assert job_request.attachments[0].id == "attachment-1"
    assert job_request.focus_keywords == ["analysis", "insights"]


def test_aggregator_handles_url_priority():
    payload = make_payload(urls=["https://example.com"])
    language = make_language()
    aggregator = DefaultIngestionAggregator()

    job_request = aggregator.aggregate(payload, language)

    # text_prompt is skipped when urls are present
    assert "Primary text" not in (job_request.text_input or "")
    assert "[Additional Context]: Additional context" in job_request.text_input
    assert [str(url) for url in job_request.url_list] == ["https://example.com/"]


def test_aggregator_handles_empty_values():
    payload = make_payload(
        text_prompt=None, notes=None, prompt_keywords=[], attachments=[], urls=[]
    )
    language = make_language(source_text_preview=None)
    aggregator = DefaultIngestionAggregator()

    job_request = aggregator.aggregate(payload, language)

    assert job_request.text_input is None
    assert job_request.url_list == []
    assert job_request.attachments == []
    assert job_request.focus_keywords == []
