"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException

from app.api.schemas import StoryCreateRequest, StoryResponse
from app.config import get_settings
from app.domain.dto import AttachmentDescriptor, Mode
from app.domain.interfaces import PromptTemplateService
from app.persistence import Base, SqlAlchemyStoryRepository, create_session_factory
from app.services.analysis import CompositeAnalysisFacade, HeuristicFunctionAnalyzer, PromptRecommendationAnalyzer
from app.services.document_intelligence import (
    AzureDocumentIntelligenceAdapter,
    DefaultDocumentIntelligencePipeline,
)
from app.services.image_pipeline import (
    AIImageProvider,
    DefaultImageAssetPipeline,
    PexelsImageProvider,
    S3ImageStorageService,
    UserUploadProvider,
)
from app.services.ingestion import DefaultIngestionAggregator
from app.services.language_detection import (
    AzureLanguageDetectionStrategy,
    DefaultLanguageDetectionService,
    LanguageDetectionStrategy,
)
from app.services.azure_openai_client import AzureOpenAILanguageModel
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
from app.services.html_renderer import HTMLTemplateRenderer
from app.utils import is_placeholder_value


app = FastAPI(title="NewsLab Service v2")

# Add custom exception handler for better error messages
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler to return detailed error messages."""
    import traceback
    logger = logging.getLogger(__name__)
    
    # Print to console for immediate visibility
    print("\n" + "="*60)
    print("GLOBAL EXCEPTION HANDLER - UNHANDLED ERROR:")
    print("="*60)
    print(f"Exception Type: {type(exc).__name__}")
    print(f"Exception Message: {str(exc)}")
    print("\nFull Traceback:")
    traceback.print_exc()
    print("="*60 + "\n")
    
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    
    # Return detailed error in JSON format
    error_detail = f"{type(exc).__name__}: {str(exc)}"
    return JSONResponse(
        status_code=500,
        content={"detail": error_detail, "error_type": type(exc).__name__}
    )


class EchoLanguageModel(LanguageModel):
    """Stub language model that echoes prompts (fallback)."""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return f"{system_prompt}\n\n{user_prompt}"


@lru_cache(maxsize=1)
def get_prompt_service() -> PromptTemplateService:
    return DefaultPromptTemplateService()


@lru_cache(maxsize=1)
def get_session_factory():
    """Get session factory, or return None if database is not available."""
    try:
        settings = get_settings()
        # Check if database URL is a placeholder or empty
        if not settings.database or not settings.database.url or is_placeholder_value(settings.database.url):
            return None
        factory = create_session_factory(settings.database.url)
        engine = factory.kw["bind"]
        Base.metadata.create_all(engine)
        return factory
    except Exception as e:
        # Database connection failed - return None to skip database
        logger = logging.getLogger(__name__)
        logger.warning("Database connection failed, will skip database operations: %s", e)
        return None


@lru_cache(maxsize=1)
def get_orchestrator() -> StoryOrchestrator:
    settings = get_settings()

    user_input_service = DefaultUserInputService()
    language_service = _build_language_service(settings)
    ingestion = DefaultIngestionAggregator()
    doc_pipeline = _build_document_pipeline(settings)

    analysis = CompositeAnalysisFacade(
        [HeuristicFunctionAnalyzer(), PromptRecommendationAnalyzer()]
    )
    prompt_service = get_prompt_service()
    prompt_controller = PromptSelectionController(prompt_service)

    # Use Azure OpenAI if credentials are available, otherwise fallback to stub
    if settings.azure_api and not is_placeholder_value(settings.azure_api.api_key):
        language_model = AzureOpenAILanguageModel(
            endpoint=settings.azure_api.endpoint,
            api_key=settings.azure_api.api_key,
            deployment=settings.azure_api.deployment,
            api_version=settings.azure_api.api_version,
        )
    else:
        language_model = EchoLanguageModel()
    curious_client = CuriousModelClient(language_model=language_model)
    news_client = NewsModelClient(language_model=language_model)
    model_router = DefaultModelRouter({Mode.CURIOUS: curious_client, Mode.NEWS: news_client})

    image_providers = []
    if settings.ai_image and not (
        is_placeholder_value(settings.ai_image.endpoint) or is_placeholder_value(settings.ai_image.api_key)
    ):
        logging.info(f"✅ Initializing AIImageProvider with endpoint: {settings.ai_image.endpoint[:50]}...")
        image_providers.append(
            AIImageProvider(endpoint=settings.ai_image.endpoint, api_key=settings.ai_image.api_key)
        )
    else:
        logging.warning("❌ AIImageProvider not initialized - missing ai_image configuration")
    if settings.pexels and not is_placeholder_value(settings.pexels.api_key):
        image_providers.append(PexelsImageProvider(api_key=settings.pexels.api_key))
    image_providers.append(UserUploadProvider())
    # Add NewsDefaultImageProvider for News mode when no image_source is specified
    from app.services.image_pipeline import NewsDefaultImageProvider
    image_providers.append(NewsDefaultImageProvider())

    resize_map = {}
    if settings.image_processing and settings.image_processing.resize_variants:
        for variant in settings.image_processing.resize_variants.split(","):
            if ":" in variant:
                key, value = variant.split(":", 1)
                resize_map[key.strip()] = value.strip()
    image_storage = S3ImageStorageService(
        bucket=settings.aws.bucket,
        prefix=settings.aws.s3_prefix,
        cdn_base=settings.aws.cdn_prefix_media,
        resize_variants=resize_map or None,
        aws_access_key=settings.aws.access_key,
        aws_secret_key=settings.aws.secret_key,
        aws_region=settings.aws.region,
    )
    image_pipeline = DefaultImageAssetPipeline(image_providers, image_storage)

    voice_providers = []
    default_voice_provider = None
    if settings.elevenlabs and not is_placeholder_value(settings.elevenlabs.api_key):
        voice_providers.append(
            ElevenLabsClient(api_key=settings.elevenlabs.api_key, voice_id=settings.elevenlabs.voice_id)
        )
        default_voice_provider = "elevenlabs_pro"
    if settings.azure_voice and not is_placeholder_value(settings.azure_voice.speech_key):
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
        aws_access_key=settings.aws.access_key,
        aws_secret_key=settings.aws.secret_key,
        aws_region=settings.aws.region,
    )
    voice_service = DefaultVoiceSynthesisService(voice_providers, voice_storage)

    # Use database repository only if database is available, otherwise use no-op repository
    from app.persistence.noop_repository import NoOpStoryRepository
    
    session_factory = get_session_factory()
    if session_factory:
        try:
            repository = SqlAlchemyStoryRepository(session_factory)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning("Failed to create database repository, using no-op: %s", e)
            repository = NoOpStoryRepository()
    else:
        repository = NoOpStoryRepository()

    # HTML Template Renderer (pass language_model for SEO metadata generation)
    # Use app/ as base path - mode-specific logic will handle news_template vs curious_template
    html_renderer = HTMLTemplateRenderer(
        template_base_path=Path("app"),
        cdn_prefix_media=settings.aws.cdn_prefix_media,
        aws_bucket=settings.aws.bucket,
        language_model=language_model,  # Pass language model for LLM-based SEO generation
    )

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
        html_renderer=html_renderer,
        default_voice_provider=default_voice_provider or "azure_basic",
        story_base_url=settings.aws.cdn_html_base,
        save_to_database=session_factory is not None,  # Enable database saving if database is available
    )


def _build_language_service(settings) -> DefaultLanguageDetectionService:
    strategy: LanguageDetectionStrategy
    translator_key = os.getenv("AZURE_TRANSLATOR_KEY")  # optional external key
    translator_endpoint = os.getenv("AZURE_TRANSLATOR_ENDPOINT")
    if translator_endpoint and translator_key and not is_placeholder_value(translator_key):
        strategy = AzureLanguageDetectionStrategy(
            endpoint=translator_endpoint,
            api_key=translator_key,
            region=os.getenv("AZURE_TRANSLATOR_REGION"),
        )
    else:
        strategy = SimpleLanguageStrategy()
    return DefaultLanguageDetectionService(strategy=strategy)


class SimpleLanguageStrategy(LanguageDetectionStrategy):
    """Basic language detection fallback."""

    def detect(self, text: str) -> tuple[str, float]:
        return ("en", 0.8)


def _build_document_pipeline(settings, url_extractor=None) -> DefaultDocumentIntelligencePipeline:
    ocr_adapters = []
    if settings.azure_di and not is_placeholder_value(settings.azure_di.api_key):
        ocr_adapters.append(
            AzureDocumentIntelligenceAdapter(
                endpoint=settings.azure_di.endpoint,
                api_key=settings.azure_di.api_key,
                attachment_loader=_load_attachment_bytes,
            )
        )
    return DefaultDocumentIntelligencePipeline(
        ocr_adapters=ocr_adapters, parser_adapters=[], url_extractor=url_extractor
    )


def _load_attachment_bytes(attachment: AttachmentDescriptor) -> Optional[bytes]:
    """Load attachment bytes from local file, S3, or Azure Blob."""
    settings = get_settings()
    uri = attachment.uri
    logger = logging.getLogger(__name__)

    try:
        # Check if it's an S3 URI (s3://bucket/key)
        if uri.startswith("s3://"):
            return _load_from_s3(uri, settings, logger)

        # Check if it's an S3 HTTPS URL
        elif "s3" in uri.lower() or "amazonaws.com" in uri.lower():
            return _load_from_s3_url(uri, logger)

        # Check if it's an Azure Blob URI
        elif uri.startswith("https://") and ".blob.core.windows.net" in uri:
            return _load_from_azure_blob(uri, logger)

        # Fallback to local file
        path = Path(uri)
        if path.exists():
            return path.read_bytes()
    except Exception as e:  # pragma: no cover - filesystem issues
        logger.warning("Failed to load attachment %s: %s", attachment.uri, e)
    return None


def _load_from_s3(s3_uri: str, settings, logger: logging.Logger) -> Optional[bytes]:
    """Load file from S3 using boto3."""
    try:
        import boto3
        from urllib.parse import urlparse

        parsed = urlparse(s3_uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.aws.access_key,
            aws_secret_access_key=settings.aws.secret_key,
            region_name=settings.aws.region,
        )
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
    except ImportError:
        logger.warning("boto3 not installed, cannot load from S3")
        return None
    except Exception as e:
        logger.error("S3 load error: %s", e)
        return None


def _load_from_s3_url(url: str, logger: logging.Logger) -> Optional[bytes]:
    """Load file from S3 public URL or signed URL."""
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content
    except Exception as e:
        logger.error("S3 URL load error: %s", e)
        return None


def _load_from_azure_blob(blob_url: str, logger: logging.Logger) -> Optional[bytes]:
    """Load file from Azure Blob Storage."""
    try:
        # For public blobs, direct GET works
        # For private blobs, you'd need SAS token or account key
        with httpx.Client(timeout=30.0) as client:
            response = client.get(blob_url)
            response.raise_for_status()
            return response.content
    except Exception as e:
        logger.error("Azure Blob load error: %s", e)
        return None


@app.post("/stories", response_model=StoryResponse)
def create_story(request: StoryCreateRequest, orchestrator: StoryOrchestrator = Depends(get_orchestrator)):
    try:
        record = orchestrator.create_story(request)
        # HTML is already rendered and saved in orchestrator.create_story()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Log the full error for debugging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error("Error creating story: %s", exc, exc_info=True)
        # Return detailed error message
        error_msg = str(exc)
        # Get the exception type name
        exc_type = type(exc).__name__
        error_detail = f"{exc_type}: {error_msg}"
        
        # Log full traceback to server logs
        logger.error("Full traceback:", exc_info=True)
        
        # Return concise but informative error
        raise HTTPException(status_code=500, detail=error_detail) from exc
    return StoryResponse.model_validate(record.model_dump())


@app.get("/stories/{story_id}", response_model=StoryResponse)
def get_story(story_id: str, orchestrator: StoryOrchestrator = Depends(get_orchestrator)):
    """
    Get story by UUID or slug.
    If story_id looks like a UUID, use UUID lookup.
    Otherwise, treat it as a slug and look up by canurl.
    """
    import re
    from uuid import UUID
    
    try:
        # Check if story_id is a valid UUID format
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
        if uuid_pattern.match(story_id):
            # It's a UUID, use regular lookup
            record = orchestrator.get_story(story_id)
        else:
            # It's a slug, use slug-based lookup
            record = orchestrator.get_story_by_slug(story_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Story not found") from exc
    return StoryResponse.model_validate(record.model_dump())


@app.get("/templates", response_model=List[str])
def list_templates(prompt_service: PromptTemplateService = Depends(get_prompt_service)):
    return [info.mode for info in prompt_service.list_templates()]


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


@app.get("/stories/{story_id}/html")
def get_story_html(story_id: str, orchestrator: StoryOrchestrator = Depends(get_orchestrator)):
    """Get rendered HTML for a story."""
    try:
        record = orchestrator.get_story(story_id)
        if not orchestrator.html_renderer:
            raise HTTPException(status_code=503, detail="HTML renderer not available")

        html_content = orchestrator.html_renderer.render(
            record=record,
            template_key=record.template_key,
            template_source="file",
        )
        return {"html": html_content, "story_id": story_id, "template_key": record.template_key}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Story not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"HTML rendering failed: {str(exc)}") from exc


@app.get("/stories/{story_id}/test")
def test_story_generation(story_id: str, orchestrator: StoryOrchestrator = Depends(get_orchestrator)):
    """Test endpoint to verify story generation and components."""
    try:
        record = orchestrator.get_story(story_id)

        test_results = {
            "story_id": str(record.id),
            "status": "ok",
            "components": {
                "slides": {
                    "count": len(record.slide_deck.slides),
                    "expected": record.slide_count.value,
                    "status": "ok" if len(record.slide_deck.slides) == record.slide_count.value else "mismatch",
                },
                "images": {
                    "count": len(record.image_assets),
                    "status": "ok" if len(record.image_assets) > 0 else "missing",
                },
                "voice": {
                    "count": len(record.voice_assets),
                    "status": "ok" if len(record.voice_assets) > 0 else "missing",
                },
                "html_rendering": {
                    "status": "available" if orchestrator.html_renderer else "unavailable",
                },
            },
            "metadata": {
                "mode": record.mode.value,
                "category": record.category,
                "language": record.input_language,
                "template_key": record.template_key,
                "created_at": record.created_at.isoformat(),
            },
        }

        # Test HTML rendering if available
        if orchestrator.html_renderer:
            try:
                html_content = orchestrator.html_renderer.render(
                    record=record,
                    template_key=record.template_key,
                    template_source="file",
                )
                test_results["components"]["html_rendering"]["status"] = "success"
                test_results["components"]["html_rendering"]["html_length"] = len(html_content)
            except Exception as e:
                test_results["components"]["html_rendering"]["status"] = "error"
                test_results["components"]["html_rendering"]["error"] = str(e)

        return test_results
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Story not found") from exc

