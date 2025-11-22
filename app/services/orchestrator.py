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
from app.services.html_renderer import HTMLTemplateRenderer
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
    html_renderer: Optional[HTMLTemplateRenderer] = None
    id_factory: Callable[[], UUID] = uuid4
    default_voice_provider: str = "azure_basic"
    story_base_url: Optional[str] = None
    save_to_database: bool = True  # Default to True - save stories to database

    def create_story(self, request: StoryCreateRequest) -> StoryRecord:
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            payload = self._build_intake_payload(request)
            logger.debug("Built intake payload")
        except Exception as e:
            logger.error("Failed to build intake payload: %s", e, exc_info=True)
            raise ValueError(f"Invalid request payload: {e}") from e
        
        try:
            language = self.language_service.detect(payload)
            logger.debug("Detected language: %s", language.language_code)
        except Exception as e:
            logger.error("Language detection failed: %s", e, exc_info=True)
            raise ValueError(f"Language detection failed: {e}") from e
        
        try:
            job_request = self.ingestion_aggregator.aggregate(payload, language)
            logger.debug("Aggregated job request")
        except Exception as e:
            logger.error("Job request aggregation failed: %s", e, exc_info=True)
            raise ValueError(f"Failed to aggregate job request: {e}") from e
        
        try:
            doc_insights = self.doc_pipeline.run(job_request)
            logger.debug("Document intelligence completed, chunks: %d", len(doc_insights.semantic_chunks))
        except Exception as e:
            logger.error("Document intelligence pipeline failed: %s", e, exc_info=True)
            raise ValueError(f"Document processing failed: {e}") from e
        
        try:
            analysis = self.analysis_facade.analyze(doc_insights)
            self._apply_analysis(doc_insights, analysis)
            logger.debug("Analysis completed")
        except Exception as e:
            logger.error("Analysis failed: %s", e, exc_info=True)
            raise ValueError(f"Analysis failed: {e}") from e

        try:
            rendered_prompt = self.prompt_controller.select_prompt(
                mode=payload.mode.value,
                category=request.category or ("News" if payload.mode == Mode.NEWS else "Art"),
                language=language.language_code,
                analysis=analysis,
                keywords=payload.prompt_keywords,
            )
            logger.debug("Prompt selected and rendered")
        except Exception as e:
            logger.error("Prompt selection/rendering failed: %s", e, exc_info=True)
            raise ValueError(f"Prompt rendering failed: {e}") from e

        try:
            model_client = self.model_router.route(payload.mode)
            # Pass slide_count and metadata to NewsModelClient if it's NEWS mode
            if payload.mode == Mode.NEWS and hasattr(model_client, 'generate'):
                # For NewsModelClient, pass slide_count and category metadata
                narrative = model_client.generate(
                    rendered_prompt,
                    doc_insights,
                    slide_count=payload.slide_count,
                    category=request.category,
                    subcategory=None,  # Will be detected automatically
                    emotion=None,  # Will be detected automatically
                )
            elif payload.mode == Mode.CURIOUS and hasattr(model_client, 'generate'):
                # For CuriousModelClient, pass slide_count if available
                # Note: CuriousModelClient may not support slide_count yet, but we pass it for future compatibility
                try:
                    narrative = model_client.generate(
                        rendered_prompt,
                        doc_insights,
                        slide_count=payload.slide_count,
                    )
                except TypeError:
                    # Fallback if slide_count parameter not supported yet
                    logger.debug("CuriousModelClient doesn't support slide_count yet, using default")
                    narrative = model_client.generate(rendered_prompt, doc_insights)
            else:
                narrative = model_client.generate(rendered_prompt, doc_insights)
            logger.debug("Narrative generated, slides: %d", len(narrative.slide_deck.slides))
        except Exception as e:
            logger.error("Narrative generation failed: %s", e, exc_info=True)
            raise ValueError(f"Narrative generation failed: {e}") from e

        # Extract article images from doc_insights metadata
        article_images = None
        if doc_insights.metadata and "article_images" in doc_insights.metadata:
            article_images = doc_insights.metadata["article_images"]

        # For Curious mode, extract alt texts from narrative and pass to image pipeline
        updated_payload = payload  # Default to original payload
        if payload.mode == Mode.CURIOUS and hasattr(narrative, "raw_output"):
            try:
                import json
                narrative_json = json.loads(narrative.raw_output) if isinstance(narrative.raw_output, str) else narrative.raw_output
                if isinstance(narrative_json, dict):
                    # Properly update Pydantic model metadata (create new instance)
                    updated_metadata = dict(payload.metadata) if payload.metadata else {}
                    updated_metadata["narrative_json"] = narrative_json
                    # Create new payload with updated metadata
                    updated_payload = payload.model_copy(update={"metadata": updated_metadata})
                    logger.debug("Extracted alt texts from Curious narrative for image generation")
                    logger.debug(f"Narrative JSON has keys: {list(narrative_json.keys())[:15]}")
                    # Log alt text availability
                    alt_keys = [k for k in narrative_json.keys() if "alt1" in k]
                    logger.debug(f"Found alt text keys: {alt_keys}")
                    logger.info(f"Updated payload metadata with narrative_json for {len(alt_keys)} alt texts")
            except Exception as e:
                logger.warning("Failed to extract alt texts from narrative: %s", e, exc_info=True)
        
        try:
            image_assets = self.image_pipeline.process(narrative.slide_deck, updated_payload, article_images=article_images)
            logger.debug("Image assets processed: %d", len(image_assets))
        except Exception as e:
            logger.warning("Image pipeline failed (non-critical): %s", e)
            image_assets = []  # Continue without images
        
        try:
            voice_provider = payload.voice_engine or self.default_voice_provider
            voice_assets = (
                self.voice_service.synthesize(narrative.slide_deck, language, voice_provider)
                if voice_provider
                else []
            )
            logger.debug("Voice assets synthesized: %d", len(voice_assets))
        except Exception as e:
            logger.warning("Voice synthesis failed (non-critical): %s", e)
            voice_assets = []  # Continue without voice

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

        # Save to database only if enabled
        if self.save_to_database:
            self.repository.save(record)

        # Generate and save HTML if renderer is available
        html_file_path = None
        if self.html_renderer:
            try:
                html_content = self.html_renderer.render(
                    record=record,
                    template_key=payload.template_key,
                    template_source="file",
                    image_source=payload.image_source,
                )
                # Save HTML to file
                html_file_path = self.html_renderer.save_html_to_file(
                    html_content=html_content,
                    story_id=story_id,
                )
                import logging
                logging.getLogger(__name__).info("HTML saved to: %s", html_file_path)
            except Exception as e:
                # Log error but don't fail story creation - HTML saving is optional
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("HTML rendering/saving failed (non-critical): %s", e)
                logger.debug("HTML error details:", exc_info=True)
                # Continue without HTML file - story creation should succeed

        return record

    def get_story(self, story_id: str) -> StoryRecord:
        return self.repository.get(story_id)

    def _build_intake_payload(self, request: StoryCreateRequest) -> IntakePayload:
        return self.user_input_service.build_payload(
            user_input=request.user_input,  # NEW: Unified input support
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

