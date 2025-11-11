"""Application service orchestrating the full story workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, Sequence
from uuid import UUID, uuid4

from app.domain.dto import (
    AnalysisReport,
    DocInsights,
    ImageAsset,
    IntakePayload,
    LanguageMetadata,
    Mode,
    RenderedPrompt,
    SlideDeck,
    StoryRecord,
    VoiceAsset,
)
from app.domain.interfaces import (
    AnalysisFacade,
    DocumentIntelligencePipeline,
    ImageAssetPipeline,
    IngestionAggregator,
    LanguageDetectionService,
    ModelRouter,
    PromptTemplateService,
    StoryRepository,
    UserInputService,
    VoiceSynthesisService,
)
from app.services.prompt_templates import PromptSelectionController
from app.api.schemas import StoryCreateRequest


@dataclass
class StoryOrchestrator:
    """Coordinate all services to create and retrieve stories."""

    user_input_service: UserInputService
    language_service: LanguageDetectionService
    ingestion_aggregator: IngestionAggregator
    doc_pipeline: DocumentIntelligencePipeline
    analysis_facade: AnalysisFacade
    prompt_controller: PromptSelectionController
    model_router: ModelRouter
    image_pipeline: ImageAssetPipeline
    voice_service: VoiceSynthesisService
    repository: StoryRepository
    id_factory: Callable[[], UUID] = uuid4
    default_voice_provider: str = "azure_basic"
    story_base_url: Optional[str] = None

    def create_story(self, request: StoryCreateRequest) -> StoryRecord:
        payload = self._build_intake_payload(request)
        language = self.language_service.detect(payload)
        job_request = self.ingestion_aggregator.aggregate(payload, language)
        doc_insights = self.doc_pipeline.run(job_request)
        analysis = self.analysis_facade.analyze(doc_insights)
        self._apply_analysis(doc_insights, analysis)

        rendered_prompt = self.prompt_controller.select_prompt(
            mode=payload.mode.value,
            category=request.category or ("News" if payload.mode == Mode.NEWS else "Art"),
            language=language.language_code,
            analysis=analysis,
            keywords=payload.prompt_keywords,
        )

        model_client = self.model_router.route(payload.mode)
        narrative = model_client.generate(rendered_prompt, doc_insights)

        image_assets = self.image_pipeline.process(narrative.slide_deck, payload)
        voice_provider = payload.voice_engine or self.default_voice_provider
        voice_assets = (
            self.voice_service.synthesize(narrative.slide_deck, language, voice_provider)
            if voice_provider
            else []
        )

        story_id = self.id_factory()
        created_at = datetime.utcnow()
        canurl, canurl1 = self._build_canurls(story_id)

        record = StoryRecord(
            id=story_id,
            mode=payload.mode,
            category=request.category or narrative.mode.value.title(),
            input_language=language.language_code,
            slide_count=payload.slide_count,
            template_key=payload.template_key,
            doc_insights=doc_insights,
            slide_deck=narrative.slide_deck,
            image_assets=image_assets,
            voice_assets=voice_assets,
            prompt_news=rendered_prompt.user if payload.mode == Mode.NEWS else None,
            prompt_curious=rendered_prompt.user if payload.mode == Mode.CURIOUS else None,
            canurl=canurl,
            canurl1=canurl1,
            created_at=created_at,
        )

        self.repository.save(record)
        return record

    def get_story(self, story_id: str) -> StoryRecord:
        return self.repository.get(story_id)

    def _build_intake_payload(self, request: StoryCreateRequest) -> IntakePayload:
        return self.user_input_service.build_payload(
            text_prompt=request.text_prompt,
            notes=request.notes,
            urls=request.urls,
            attachments=request.attachments,
            prompt_keywords=request.prompt_keywords,
            mode=request.mode.value,
            template_key=request.template_key,
            slide_count=request.slide_count,
            category=request.category,
            image_source=request.image_source,
            voice_engine=request.voice_engine,
        )

    def _apply_analysis(self, doc_insights: DocInsights, analysis: AnalysisReport) -> None:
        if analysis.recommended_prompts:
            doc_insights.recommended_prompts = analysis.recommended_prompts
        if analysis.gaps:
            doc_insights.gaps = analysis.gaps
        if analysis.narrative_summary:
            doc_insights.summaries = [analysis.narrative_summary]

    def _build_canurls(self, story_id: UUID) -> tuple[Optional[str], Optional[str]]:
        if not self.story_base_url:
            return None, None
        base = self.story_base_url.rstrip("/")
        primary = f"{base}/{story_id}"
        secondary = f"{primary}?variant=alt"
        return primary, secondary

