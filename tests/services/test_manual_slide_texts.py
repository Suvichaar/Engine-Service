"""Tests for the manual slide_texts bypass in StoryOrchestrator (News mode only)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.api.schemas import StoryCreateRequest
from app.domain.dto import (
    AnalysisReport,
    DocInsights,
    IntakePayload,
    LanguageMetadata,
    Mode,
    RenderedPrompt,
    SemanticChunk,
    StructuredJobRequest,
)
from app.services.orchestrator import StoryOrchestrator


_SLIDE_TEXTS = ["Cover text", "Slide 2", "Slide 3", "Slide 4"]


def _make_orchestrator() -> StoryOrchestrator:
    """Build a StoryOrchestrator with all heavy dependencies stubbed."""

    user_input_service = MagicMock()
    user_input_service.build_payload.return_value = IntakePayload(
        mode=Mode.NEWS,
        template_key="news_default",
        slide_count=4,
        slide_texts=_SLIDE_TEXTS,
    )

    language_service = MagicMock()
    language_service.detect.return_value = LanguageMetadata(
        language_code="en", confidence=1.0
    )

    ingestion_aggregator = MagicMock()
    ingestion_aggregator.aggregate.return_value = StructuredJobRequest(
        text_input="stub article content",
        url_list=[],
    )

    # doc_pipeline stub: needs _ocr_adapters / _parser_adapters for the inline
    # DefaultDocumentIntelligencePipeline construction inside create_story.
    doc_pipeline = MagicMock()
    doc_pipeline._ocr_adapters = []
    doc_pipeline._parser_adapters = []

    analysis_facade = MagicMock()
    analysis_facade.analyze.return_value = AnalysisReport()

    prompt_controller = MagicMock()
    prompt_controller.select_prompt.return_value = RenderedPrompt(
        system="system",
        user="user",
        metadata={"language": "en"},
    )

    # model_router must NOT be called when the bypass path is taken.
    model_router = MagicMock()

    image_pipeline = MagicMock()
    image_pipeline.process.return_value = []

    voice_service = MagicMock()
    voice_service.synthesize.return_value = []

    repository = MagicMock()

    return StoryOrchestrator(
        user_input_service=user_input_service,
        language_service=language_service,
        ingestion_aggregator=ingestion_aggregator,
        doc_pipeline=doc_pipeline,
        analysis_facade=analysis_facade,
        prompt_controller=prompt_controller,
        model_router=model_router,
        image_pipeline=image_pipeline,
        voice_service=voice_service,
        repository=repository,
        save_to_database=False,
    )


def _run_with_patched_deps(orchestrator: StoryOrchestrator, request: StoryCreateRequest):
    """Run create_story with heavy internal imports patched to lightweight stubs."""

    stub_settings = MagicMock()
    stub_settings.serper = None
    stub_settings.azure_api = MagicMock(api_key=None)

    stub_doc_insights = DocInsights(
        semantic_chunks=[SemanticChunk(id="c1", text="stub article")]
    )

    stub_mode_pipeline = MagicMock()
    stub_mode_pipeline.run.return_value = stub_doc_insights

    with (
        patch("app.config.get_settings", return_value=stub_settings),
        patch(
            "app.services.url_extractor.URLContentExtractor",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.document_intelligence.DefaultDocumentIntelligencePipeline",
            return_value=stub_mode_pipeline,
        ),
    ):
        return orchestrator.create_story(request)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_news_mode_slide_texts_bypass_produces_correct_slides():
    """When slide_texts is provided for News mode the LLM is skipped and the
    resulting SlideDeck must have exactly 4 SlideBlocks whose text values match."""

    orchestrator = _make_orchestrator()

    request = StoryCreateRequest(
        mode=Mode.NEWS,
        template_key="news_default",
        slide_count=4,
        slide_texts=_SLIDE_TEXTS,
    )

    record = _run_with_patched_deps(orchestrator, request)

    slides = record.slide_deck.slides
    assert len(slides) == 4, f"Expected 4 slides, got {len(slides)}"
    assert slides[0].text == "Cover text"
    assert slides[1].text == "Slide 2"
    assert slides[2].text == "Slide 3"
    assert slides[3].text == "Slide 4"


def test_news_mode_slide_texts_bypass_does_not_call_model_router():
    """model_router.route must NOT be called when the bypass path is taken."""

    orchestrator = _make_orchestrator()

    request = StoryCreateRequest(
        mode=Mode.NEWS,
        template_key="news_default",
        slide_count=4,
        slide_texts=_SLIDE_TEXTS,
    )

    _run_with_patched_deps(orchestrator, request)

    orchestrator.model_router.route.assert_not_called()


def test_news_mode_no_slide_texts_calls_model_router():
    """Without slide_texts the orchestrator must fall through to the LLM path
    and call model_router.route."""
    from app.domain.dto import NewsNarrative, SlideBlock, SlideDeck

    orchestrator = _make_orchestrator()

    # Override build_payload to return a payload WITHOUT slide_texts.
    orchestrator.user_input_service.build_payload.return_value = IntakePayload(
        mode=Mode.NEWS,
        template_key="news_default",
        slide_count=4,
        slide_texts=None,
    )

    # Provide a realistic stub for the model client.
    stub_slide_deck = SlideDeck(
        template_key="news_default",
        language_code="en",
        slides=[SlideBlock(placeholder_id=f"s{i}", text=f"LLM slide {i}") for i in range(4)],
    )
    stub_narrative = NewsNarrative(
        mode=Mode.NEWS,
        slide_deck=stub_slide_deck,
        raw_output="llm_output",
        headlines=["LLM slide 0"],
        bullet_points=["LLM slide 1", "LLM slide 2", "LLM slide 3"],
    )
    stub_client = MagicMock()
    stub_client.generate.return_value = stub_narrative
    orchestrator.model_router.route.return_value = stub_client

    request = StoryCreateRequest(
        mode=Mode.NEWS,
        template_key="news_default",
        slide_count=4,
        slide_texts=None,
    )

    _run_with_patched_deps(orchestrator, request)

    orchestrator.model_router.route.assert_called_once()


def test_curious_mode_with_slide_texts_still_calls_model_router():
    """Curious mode with slide_texts must not take the News bypass; model_router.route
    is invoked once."""
    from app.domain.dto import NewsNarrative, SlideBlock, SlideDeck

    orchestrator = _make_orchestrator()

    curious_slides = ["a", "b", "c", "d"]
    orchestrator.user_input_service.build_payload.return_value = IntakePayload(
        mode=Mode.CURIOUS,
        template_key="modern",
        slide_count=4,
        slide_texts=curious_slides,
    )

    stub_slide_deck = SlideDeck(
        template_key="modern",
        language_code="en",
        slides=[SlideBlock(placeholder_id=f"s{i}", text=f"LLM slide {i}") for i in range(4)],
    )
    stub_narrative = NewsNarrative(
        mode=Mode.CURIOUS,
        slide_deck=stub_slide_deck,
        raw_output="llm_output",
        headlines=["LLM slide 0"],
        bullet_points=["LLM slide 1", "LLM slide 2", "LLM slide 3"],
    )
    stub_client = MagicMock()
    stub_client.generate.return_value = stub_narrative
    orchestrator.model_router.route.return_value = stub_client

    request = StoryCreateRequest(
        mode=Mode.CURIOUS,
        template_key="modern",
        slide_count=4,
        slide_texts=curious_slides,
    )

    _run_with_patched_deps(orchestrator, request)

    orchestrator.model_router.route.assert_called_once()


def test_curious_mode_with_slide_texts_still_calls_model_router():
    """Curious mode with slide_texts must not take the News bypass; model_router.route
    is invoked once."""
    from app.domain.dto import NewsNarrative, SlideBlock, SlideDeck

    orchestrator = _make_orchestrator()

    curious_slides = ["a", "b", "c", "d"]
    orchestrator.user_input_service.build_payload.return_value = IntakePayload(
        mode=Mode.CURIOUS,
        template_key="modern",
        slide_count=4,
        slide_texts=curious_slides,
    )

    stub_slide_deck = SlideDeck(
        template_key="modern",
        language_code="en",
        slides=[SlideBlock(placeholder_id=f"s{i}", text=f"LLM slide {i}") for i in range(4)],
    )
    stub_narrative = NewsNarrative(
        mode=Mode.CURIOUS,
        slide_deck=stub_slide_deck,
        raw_output="llm_output",
        headlines=["LLM slide 0"],
        bullet_points=["LLM slide 1", "LLM slide 2", "LLM slide 3"],
    )
    stub_client = MagicMock()
    stub_client.generate.return_value = stub_narrative
    orchestrator.model_router.route.return_value = stub_client

    request = StoryCreateRequest(
        mode=Mode.CURIOUS,
        template_key="modern",
        slide_count=4,
        slide_texts=curious_slides,
    )

    _run_with_patched_deps(orchestrator, request)

    orchestrator.model_router.route.assert_called_once()
