"""FastAPI application entrypoint."""

from __future__ import annotations

from functools import lru_cache
from typing import List

from fastapi import Depends, FastAPI, HTTPException

from app.api.schemas import StoryCreateRequest, StoryResponse
from app.config import get_settings
from app.domain.dto import Mode
from app.domain.interfaces import PromptTemplateService
from app.persistence import Base, SqlAlchemyStoryRepository, create_session_factory
from app.services.analysis import CompositeAnalysisFacade, HeuristicFunctionAnalyzer, PromptRecommendationAnalyzer
from app.services.document_intelligence import DefaultDocumentIntelligencePipeline
from app.services.image_pipeline import (
    AIImageProvider,
    DefaultImageAssetPipeline,
    PexelsImageProvider,
    S3ImageStorageService,
    UserUploadProvider,
)
from app.services.ingestion import DefaultIngestionAggregator
from app.services.language_detection import DefaultLanguageDetectionService, LanguageDetectionStrategy
from app.services.model_clients import CuriousModelClient, LanguageModel, NewsModelClient
from app.services.model_router import DefaultModelRouter
from app.services.orchestrator import StoryOrchestrator
from app.services.prompt_templates import DefaultPromptTemplateService, PromptSelectionController
from app.services.user_input import DefaultUserInputService
from app.services.voice_synthesis import (
    AzureTTSClient,
    DefaultVoiceSynthesisService,
    ElevenLabsClient,
    S3VoiceStorageService,
)


app = FastAPI(title="NewsLab Service v2")


class SimpleLanguageStrategy(LanguageDetectionStrategy):
    """Basic language detection fallback."""

    def detect(self, text: str) -> tuple[str, float]:
        return ("en", 0.8)


class EchoLanguageModel(LanguageModel):
    """Stub language model that echoes prompts."""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return f"{system_prompt}\n\n{user_prompt}"


@lru_cache(maxsize=1)
def get_prompt_service() -> PromptTemplateService:
    return DefaultPromptTemplateService()


@lru_cache(maxsize=1)
def get_session_factory():
    settings = get_settings()
    factory = create_session_factory(settings.database.url)
    engine = factory.kw["bind"]
    Base.metadata.create_all(engine)
    return factory


@lru_cache(maxsize=1)
def get_orchestrator() -> StoryOrchestrator:
    settings = get_settings()

    user_input_service = DefaultUserInputService()
    language_service = DefaultLanguageDetectionService(strategy=SimpleLanguageStrategy())
    ingestion = DefaultIngestionAggregator()
    doc_pipeline = DefaultDocumentIntelligencePipeline(ocr_adapters=[], parser_adapters=[])

    analysis = CompositeAnalysisFacade(
        [HeuristicFunctionAnalyzer(), PromptRecommendationAnalyzer()]
    )
    prompt_service = get_prompt_service()
    prompt_controller = PromptSelectionController(prompt_service)

    language_model = EchoLanguageModel()
    curious_client = CuriousModelClient(language_model=language_model)
    news_client = NewsModelClient(language_model=language_model)
    model_router = DefaultModelRouter({Mode.CURIOUS: curious_client, Mode.NEWS: news_client})

    image_providers = []
    if settings.ai_image:
        image_providers.append(
            AIImageProvider(endpoint=settings.ai_image.endpoint, api_key=settings.ai_image.api_key)
        )
    if settings.pexels:
        image_providers.append(PexelsImageProvider(api_key=settings.pexels.api_key))
    image_providers.append(UserUploadProvider())

    resize_map = {}
    if settings.image_processing and settings.image_processing.resize_variants:
        for variant in settings.image_processing.resize_variants.split(","):
            if ":" in variant:
                key, value = variant.split(":", 1)
                resize_map[key.strip()] = value.strip()
    image_storage = S3ImageStorageService(
        bucket=settings.aws.bucket,
        prefix=settings.aws.s3_prefix,
        cdn_base=settings.aws.cdn_base,
        resize_variants=resize_map or None,
    )
    image_pipeline = DefaultImageAssetPipeline(image_providers, image_storage)

    voice_providers = []
    default_voice_provider = None
    if settings.elevenlabs:
        voice_providers.append(
            ElevenLabsClient(api_key=settings.elevenlabs.api_key, voice_id=settings.elevenlabs.voice_id)
        )
        default_voice_provider = "elevenlabs_pro"
    if settings.azure_voice:
        voice_providers.append(
            AzureTTSClient(
                api_key=settings.azure_voice.speech_key,
                region=settings.azure_voice.region,
                voice=settings.azure_voice.voice,
            )
        )
        if not default_voice_provider:
            default_voice_provider = "azure_basic"
    if not voice_providers:
        # fallback stub provider
        voice_providers.append(AzureTTSClient(api_key="stub", region="eastus", voice="en-US-AriaNeural"))
        default_voice_provider = "azure_basic"

    voice_storage_settings = settings.voice_storage or None
    voice_storage = S3VoiceStorageService(
        bucket=(voice_storage_settings.bucket if voice_storage_settings else settings.aws.bucket),
        prefix=(voice_storage_settings.prefix if voice_storage_settings else "media/audio"),
        cdn_base=settings.aws.cdn_base,
    )
    voice_service = DefaultVoiceSynthesisService(voice_providers, voice_storage)

    repository = SqlAlchemyStoryRepository(get_session_factory())

    return StoryOrchestrator(
        user_input_service=user_input_service,
        language_service=language_service,
        ingestion_aggregator=ingestion,
        doc_pipeline=doc_pipeline,
        analysis_facade=analysis,
        prompt_controller=prompt_controller,
        model_router=model_router,
        image_pipeline=image_pipeline,
        voice_service=voice_service,
        repository=repository,
        default_voice_provider=default_voice_provider or "azure_basic",
        story_base_url=settings.aws.cdn_html_base,
    )


@app.post("/stories", response_model=StoryResponse)
def create_story(request: StoryCreateRequest, orchestrator: StoryOrchestrator = Depends(get_orchestrator)):
    try:
        record = orchestrator.create_story(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StoryResponse.model_validate(record.model_dump())


@app.get("/stories/{story_id}", response_model=StoryResponse)
def get_story(story_id: str, orchestrator: StoryOrchestrator = Depends(get_orchestrator)):
    try:
        record = orchestrator.get_story(story_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Story not found") from exc
    return StoryResponse.model_validate(record.model_dump())


@app.get("/templates", response_model=List[str])
def list_templates(prompt_service: PromptTemplateService = Depends(get_prompt_service)):
    return [info.mode for info in prompt_service.list_templates()]


@app.get("/health")
def healthcheck():
    return {"status": "ok"}

