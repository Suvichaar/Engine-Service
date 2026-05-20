"""FastAPI application entrypoint."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import logging
import re
import sys
import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional
from uuid import UUID, uuid4

# ============================================
# LOGGING CONFIGURATION - MUST BE FIRST
# ============================================
# Configure logging BEFORE creating FastAPI app
# Azure Container Apps captures stdout/stderr
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, LOG_LEVEL, logging.INFO)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),  # stdout for Azure Container Apps
        logging.StreamHandler(sys.stderr),  # stderr as backup
    ],
    force=True  # Override any existing config
)

# Set specific loggers to INFO for better visibility
logging.getLogger("app").setLevel(logging.INFO)
logging.getLogger("app.services").setLevel(logging.INFO)
logging.getLogger("app.services.voice_synthesis").setLevel(logging.INFO)
logging.getLogger("app.services.orchestrator").setLevel(logging.INFO)
logging.getLogger("app.services.image_pipeline").setLevel(logging.INFO)

# Uvicorn and FastAPI logs
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("fastapi").setLevel(logging.INFO)

# Confirm logging is configured
logger = logging.getLogger(__name__)
logger.info("=" * 60)
logger.info("✅ LOGGING CONFIGURED FOR AZURE CONTAINER APPS")
logger.info(f"Log Level: {LOG_LEVEL}")
logger.info("Handlers: stdout, stderr")
logger.info("=" * 60)


RECENT_LOGS: Deque[Dict[str, Any]] = deque(maxlen=500)

_SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(api[_ -]?key|secret|password|token|speech[_ -]?key)\s*=\s*['\"]?([^,'\"\s]+)"),
    re.compile(r"(?i)(aws_access_key_id|aws_secret_access_key)\s*=\s*['\"]?([^,'\"\s]+)"),
]


def _sanitize_log_message(message: str) -> str:
    sanitized = message
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(lambda m: f"{m.group(1)}='***REDACTED***'", sanitized)
    return sanitized


class InMemoryLogHandler(logging.Handler):
    """Keep a rolling window of structured logs for the local UI."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            RECENT_LOGS.append(
                {
                    "timestamp": datetime.fromtimestamp(
                        record.created, tz=timezone.utc
                    ).isoformat(),
                    "logger": record.name,
                    "level": record.levelname,
                    "message": _sanitize_log_message(record.getMessage()),
                }
            )
        except Exception:
            self.handleError(record)


_memory_log_handler = InMemoryLogHandler()
_memory_log_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(_memory_log_handler)

import httpx
from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.schemas import (
    PromptActivateRequest,
    PromptCreateRequest,
    PromptListingResponse,
    PromptUpdateRequest,
    PromptVersionResponse,
    TemplateActivateRequest,
    TemplateCreateRequest,
    TemplateListingResponse,
    TemplateUpdateRequest,
    TemplateVersionResponse,
    StoryCreateRequest,
    StoryJobAck,
    StoryJobStatusResponse,
    StoryResponse,
)
from app.core import get_settings
from app.domain.dto import AttachmentDescriptor, Mode
from app.domain.interfaces import ModelClient, PromptTemplateService
from app.persistence import (
    Base,
    SqlAlchemyStoryRepository,
    create_session_factory,
    ensure_story_schema,
)
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
from app.services.model_clients import LanguageModel, NewsModelClient
from app.services.job_registry import StoryJobRegistry, get_job_registry
from app.services.orchestrator import StoryOrchestrator
from app.services.prompt_templates import DefaultPromptTemplateService, PromptSelectionController
from app.services.prompt_management import PromptManagementError, PromptManagementService
from app.services.template_management import TemplateManagementError, TemplateManagementService
from app.services.template_registry import list_template_definitions
from app.services.template_slide_generators import configure_template_generators
from app.services.user_input import DefaultUserInputService
from app.services.voice_synthesis import (
    AzureTTSClient,
    DefaultVoiceSynthesisService,
    ElevenLabsClient,
    S3VoiceStorageService,
)
from app.services.html_renderer import HTMLTemplateRenderer
from app.utils import is_placeholder_value


def _parse_cors_allowed_origins(raw_value: Optional[str]) -> list[str]:
    default_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://suvichaar-storygenerator.vercel.app",
        "https://suvichaar.org",
        "https://www.suvichaar.org",
    ]
    origins = [item.strip() for item in raw_value.split(",") if item.strip()] if raw_value else []
    return list(dict.fromkeys([*default_origins, *origins]))


settings = get_settings()
app = FastAPI(title="Engine Service News Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_allowed_origins(settings.fastapi.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom exception handler for better error messages
@app.on_event("startup")
async def startup_event():
    """Initialize orchestrator at startup to show config logs immediately."""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("🚀 Application startup - initializing orchestrator...")
    # Force initialization to show config logs
    get_orchestrator()
    logger.warning("✅ Orchestrator initialized successfully")

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
def get_prompt_management_service() -> PromptManagementService:
    return PromptManagementService()


@lru_cache(maxsize=1)
def get_template_management_service() -> TemplateManagementService:
    return TemplateManagementService(mode=Mode.NEWS)


@lru_cache(maxsize=1)
def get_model_client() -> ModelClient:
    settings = get_settings()
    if settings.azure_api and not is_placeholder_value(settings.azure_api.api_key):
        language_model: LanguageModel = AzureOpenAILanguageModel(
            endpoint=settings.azure_api.endpoint,
            api_key=settings.azure_api.api_key,
            deployment=settings.azure_api.deployment,
            api_version=settings.azure_api.api_version,
        )
    else:
        language_model = EchoLanguageModel()
    return NewsModelClient(language_model=language_model)


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
        ensure_story_schema(engine)
        return factory
    except Exception as e:
        # Database connection failed - return None to skip database
        logger = logging.getLogger(__name__)
        logger.warning("Database connection failed, will skip database operations: %s", e)
        return None


@lru_cache(maxsize=1)
def get_orchestrator() -> StoryOrchestrator:
    settings = get_settings()
    logger = logging.getLogger(__name__)

    # Debug: log loaded voice settings (warn level so they appear by default)
    logger.warning(
        "Voice config - elevenlabs: api_key_set=%s voice_id_set=%s",
        bool(settings.elevenlabs and not is_placeholder_value(settings.elevenlabs.api_key)),
        bool(settings.elevenlabs and not is_placeholder_value(settings.elevenlabs.voice_id)),
    )
    logger.warning(
        "Voice config - azure_voice: speech_key_set=%s region=%s voice=%s",
        bool(settings.azure_voice and not is_placeholder_value(settings.azure_voice.speech_key)),
        settings.azure_voice.region if settings.azure_voice else None,
        settings.azure_voice.voice if settings.azure_voice else None,
    )

    user_input_service = DefaultUserInputService()
    language_service = _build_language_service(settings)
    ingestion = DefaultIngestionAggregator()
    doc_pipeline = _build_document_pipeline(settings)

    analysis = CompositeAnalysisFacade(
        [HeuristicFunctionAnalyzer(), PromptRecommendationAnalyzer()]
    )
    prompt_service = get_prompt_service()
    prompt_controller = PromptSelectionController(prompt_service)
    model_client = get_model_client()
    language_model = getattr(model_client, "_language_model", EchoLanguageModel())

    image_providers = []
    if settings.ai_image and not (
        is_placeholder_value(settings.ai_image.endpoint) or is_placeholder_value(settings.ai_image.api_key)
    ):
        logger.warning("✅ Initializing AIImageProvider with endpoint: %s...", settings.ai_image.endpoint[:80])
        image_providers.append(
            AIImageProvider(
                endpoint=settings.ai_image.endpoint,
                api_key=settings.ai_image.api_key,
                language_model=language_model,  # Pass language_model for automatic alt_text generation
            )
        )
    else:
        logger.warning("❌ AIImageProvider not initialized - missing ai_image configuration")
    if settings.pexels and not is_placeholder_value(settings.pexels.api_key):
        logger.warning("✅ Initializing PexelsImageProvider")
        image_providers.append(PexelsImageProvider(api_key=settings.pexels.api_key))
    else:
        logger.warning("❌ PexelsImageProvider not initialized - missing pexels configuration")
    image_providers.append(UserUploadProvider())
    # Add NewsDefaultImageProvider for News mode when no image_source is specified
    from app.services.image_pipeline import NewsDefaultImageProvider
    image_providers.append(NewsDefaultImageProvider())
    logger.warning(
        "📷 Registered image providers: %s",
        [getattr(p, 'source', type(p).__name__) for p in image_providers],
    )

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
        og_cdn_base=settings.aws.cdn_base,
    )
    image_pipeline = DefaultImageAssetPipeline(image_providers, image_storage)

    voice_providers = []
    default_voice_provider = None

    if settings.elevenlabs and not (
        is_placeholder_value(settings.elevenlabs.api_key) or is_placeholder_value(settings.elevenlabs.voice_id)
    ):
        voice_providers.append(
            ElevenLabsClient(
                api_key=settings.elevenlabs.api_key,
                voice_id=settings.elevenlabs.voice_id,
            )
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

    # Debug: log which voice providers are available and which is default
    try:
        provider_names = [getattr(p, "name", type(p).__name__) for p in voice_providers]
    except Exception:
        provider_names = [type(p).__name__ for p in voice_providers]
    logger.warning("Registered voice providers: %s", provider_names)
    logger.warning("Default voice provider: %s", default_voice_provider)

    voice_storage_settings = settings.voice_storage or None
    voice_storage = S3VoiceStorageService(
        bucket=(voice_storage_settings.bucket if voice_storage_settings else settings.aws.bucket),
        prefix=(voice_storage_settings.prefix if voice_storage_settings else "media/audio"),
        cdn_base=settings.aws.cdn_base,
        aws_access_key=settings.aws.access_key,
        aws_secret_key=settings.aws.secret_key,
        aws_region=settings.aws.region,
    )
    voice_service = DefaultVoiceSynthesisService(
        voice_providers,
        voice_storage,
        placeholder_audio_url=settings.branding.placeholder_audio_url,
    )

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

    configure_template_generators(default_background_image=settings.branding.default_bg_image)

    # HTML Template Renderer (pass language_model for SEO metadata generation)
    html_renderer = HTMLTemplateRenderer(
        template_base_path=Path("app/templates"),
        cdn_prefix_media=settings.aws.cdn_prefix_media,
        aws_bucket=settings.aws.bucket,
        default_bg_image=settings.branding.default_bg_image,
        default_cover_image=settings.branding.default_cover_image,
        placeholder_audio_url=settings.branding.placeholder_audio_url,
        organization=settings.branding.organization,
        publisher_logo_src=settings.branding.publisher_logo_src,
        user_name=settings.branding.user_name,
        user_profile_url=settings.branding.user_profile_url,
        site_logo_base=settings.branding.site_logo_base,
        analytics_id=settings.analytics.google_analytics_id,
        adsense_client_id=settings.analytics.adsense_client_id,
        adsense_slot_id=settings.analytics.adsense_slot_id,
        default_og_image=f"{settings.aws.cdn_base.rstrip('/')}/og-images/_default.jpg" if settings.aws.cdn_base else "",
        language_model=language_model,  # Pass language model for LLM-based SEO generation
    )

    return StoryOrchestrator(
        user_input_service=user_input_service,
        language_service=language_service,
        ingestion_aggregator=ingestion,
        doc_pipeline=doc_pipeline,
        analysis_facade=analysis,
        prompt_controller=prompt_controller,
        model_client=model_client,
        image_pipeline=image_pipeline,
        voice_service=voice_service,
        repository=repository,
        html_renderer=html_renderer,
        default_voice_provider=default_voice_provider or "azure_basic",
        story_base_url=settings.story.base_url,
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


def _run_story_job_in_background(
    orchestrator: StoryOrchestrator,
    registry: StoryJobRegistry,
    request: StoryCreateRequest,
    story_id: UUID,
) -> None:
    """Run the long-running story generation on a detached daemon thread.

    A plain thread decouples the work from the request's ASGI scope so the
    HTTP response can be flushed immediately; the front-end proxy can close
    the connection while generation continues server-side.
    """

    def _runner() -> None:
        log = logging.getLogger(__name__)
        registry.mark_processing(story_id)
        try:
            record = orchestrator.create_story(request, preset_story_id=story_id)
            registry.mark_completed(story_id, record)
            log.info("✅ Story job %s completed", story_id)
        except ValueError as exc:
            log.warning("Story job %s rejected: %s", story_id, exc)
            registry.mark_failed(story_id, str(exc))
        except Exception as exc:
            log.error("Story job %s failed: %s", story_id, exc, exc_info=True)
            registry.mark_failed(story_id, f"{type(exc).__name__}: {exc}")

    threading.Thread(
        target=_runner,
        name=f"story-job-{story_id}",
        daemon=True,
    ).start()


@app.post("/stories", response_model=StoryJobAck, status_code=202)
def create_story(
    request: StoryCreateRequest = Body(
        ...,
        openapi_examples={
            "ai_example": {
                "summary": "AI Image Example",
                "description": "Generate a story from a Suvichaar story URL and let the backend generate AI images.",
                "value": {
                    "mode": "news",
                    "template_key": "test-news-1",
                    "slide_count": 4,
                    "user_input": "https://suvichaar.org/stories/trump-said-prefer-taking-oil-from-iran-possibility-of-seizing-kharg-island_300326094600956",
                    "notes": "make it in english",
                    "category": "News",
                    "image_source": "ai",
                    "voice_engine": "elevenlabs_pro",
                    "prompt_keywords": ["I want a good images"],
                },
            },
            "pexels_example": {
                "summary": "Pexels Image Example",
                "description": "Generate a story from the Indian Express cricket article and source images from Pexels.",
                "value": {
                    "mode": "news",
                    "template_key": "test-news-1",
                    "slide_count": 4,
                    "user_input": "https://indianexpress.com/article/sports/cricket/ipl-cameron-green-bowling-cricket-australia-ajinkya-rahane-kkr-10608515/?ref=rhs_mar_30_latest_news_world",
                    "notes": "I want it in english",
                    "category": "News",
                    "image_source": "pexels",
                    "voice_engine": "elevenlabs_pro",
                    "prompt_keywords": ["news", "breaking"],
                },
            },
            "custom_s3_images_example": {
                "summary": "Custom S3 Images Example",
                "description": "Generate a story using pre-uploaded custom background images stored in S3.",
                "value": {
                    "mode": "news",
                    "template_key": "test-news-1",
                    "slide_count": 4,
                    "user_input": "https://indianexpress.com/article/sports/cricket/ipl-cameron-green-bowling-cricket-australia-ajinkya-rahane-kkr-10608515/?ref=rhs_mar_30_latest_news_world",
                    "notes": "I want it english",
                    "category": "News",
                    "image_source": "custom",
                    "voice_engine": "elevenlabs_pro",
                    "attachments": [
                        "s3://suvichaarapp/media/images/backgrounds/20260330/51d7eccb-2ce3-4de5-90af-ea7caba6f31f.JPG",
                        "s3://suvichaarapp/media/images/backgrounds/20260330/aca7c320-4a47-43c2-bb20-cecbc556e4bd.png",
                        "s3://suvichaarapp/media/images/backgrounds/20260330/dcc7adbd-1377-4776-85b4-18cfad7243ed.png",
                    ],
                },
            },
        },
    ),
    orchestrator: StoryOrchestrator = Depends(get_orchestrator),
    registry: StoryJobRegistry = Depends(get_job_registry),
):
    logger = logging.getLogger(__name__)
    if request.mode != Mode.NEWS:
        raise HTTPException(status_code=400, detail="Only news mode is supported by this backend.")

    story_id = uuid4()
    registry.create(story_id)
    logger.warning(
        "📥 Queued story job %s: mode=%s image_source=%s voice_engine=%s slide_count=%s",
        story_id,
        request.mode.value,
        request.image_source,
        request.voice_engine,
        request.slide_count,
    )
    _run_story_job_in_background(orchestrator, registry, request, story_id)
    return StoryJobAck(id=story_id, status="pending")


@app.get("/stories/{story_id}/status", response_model=StoryJobStatusResponse)
def get_story_status(
    story_id: str,
    orchestrator: StoryOrchestrator = Depends(get_orchestrator),
    registry: StoryJobRegistry = Depends(get_job_registry),
):
    job = registry.get(story_id)
    if job is not None:
        story = (
            StoryResponse.model_validate(job.record.model_dump())
            if job.record is not None
            else None
        )
        return StoryJobStatusResponse(
            id=job.id,
            status=job.status,
            error=job.error,
            story=story,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    # Fall back to the persistent repository for jobs whose in-memory entry
    # has been evicted or that completed on a previous worker instance.
    try:
        story_uuid = UUID(story_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Unknown story id") from exc

    try:
        record = orchestrator.get_story(str(story_uuid))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown story id") from exc

    return StoryJobStatusResponse(
        id=story_uuid,
        status="completed",
        story=StoryResponse.model_validate(record.model_dump()),
        created_at=record.created_at,
        updated_at=record.created_at,
    )


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
def list_templates():
    return sorted(definition.key for definition in list_template_definitions(Mode.NEWS))


@app.get("/template-management", response_model=TemplateListingResponse)
def list_template_management_templates(
    template_service: TemplateManagementService = Depends(get_template_management_service),
):
    return TemplateListingResponse.model_validate(template_service.list_templates())


@app.post("/template-management", response_model=TemplateVersionResponse)
def create_template_version(
    request: TemplateCreateRequest,
    template_service: TemplateManagementService = Depends(get_template_management_service),
):
    try:
        result = template_service.create_template(**request.model_dump())
    except TemplateManagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TemplateVersionResponse.model_validate(result)


@app.put("/template-management/{key}/{version}", response_model=TemplateVersionResponse)
def update_template_version(
    key: str,
    version: str,
    request: TemplateUpdateRequest,
    template_service: TemplateManagementService = Depends(get_template_management_service),
):
    try:
        result = template_service.update_template(
            key=key,
            version=version,
            **request.model_dump(),
        )
    except TemplateManagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TemplateVersionResponse.model_validate(result)


@app.post("/template-management/activate", response_model=TemplateVersionResponse)
def activate_template_version(
    request: TemplateActivateRequest,
    template_service: TemplateManagementService = Depends(get_template_management_service),
):
    try:
        result = template_service.activate_template(**request.model_dump())
    except TemplateManagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TemplateVersionResponse.model_validate(result)


@app.delete("/template-management/{key}/{version}")
def delete_template_version(
    key: str,
    version: str,
    template_service: TemplateManagementService = Depends(get_template_management_service),
):
    try:
        template_service.delete_template(key=key, version=version)
    except TemplateManagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "deleted"}


@app.get("/prompt-management", response_model=PromptListingResponse)
def list_prompt_management_prompts(
    prompt_service: PromptManagementService = Depends(get_prompt_management_service),
):
    return PromptListingResponse.model_validate(prompt_service.list_prompts())


@app.post("/prompt-management", response_model=PromptVersionResponse)
def create_prompt_version(
    request: PromptCreateRequest,
    prompt_service: PromptManagementService = Depends(get_prompt_management_service),
):
    try:
        result = prompt_service.create_prompt(**request.model_dump())
    except PromptManagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PromptVersionResponse.model_validate(result)


@app.put("/prompt-management/{group}/{key}/{version}", response_model=PromptVersionResponse)
def update_prompt_version(
    group: str,
    key: str,
    version: str,
    request: PromptUpdateRequest,
    prompt_service: PromptManagementService = Depends(get_prompt_management_service),
):
    try:
        result = prompt_service.update_prompt(
            group=group,
            key=key,
            version=version,
            **request.model_dump(),
        )
    except PromptManagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PromptVersionResponse.model_validate(result)


@app.post("/prompt-management/activate", response_model=PromptVersionResponse)
def activate_prompt_version(
    request: PromptActivateRequest,
    prompt_service: PromptManagementService = Depends(get_prompt_management_service),
):
    try:
        result = prompt_service.activate_prompt(**request.model_dump())
    except PromptManagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PromptVersionResponse.model_validate(result)


@app.delete("/prompt-management/{group}/{key}/{version}")
def delete_prompt_version(
    group: str,
    key: str,
    version: str,
    prompt_service: PromptManagementService = Depends(get_prompt_management_service),
):
    try:
        prompt_service.delete_prompt(group=group, key=key, version=version)
    except PromptManagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "deleted"}


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


@app.get("/logs")
def get_logs(limit: int = 200, level: Optional[str] = None):
    safe_limit = max(1, min(limit, 500))
    entries = list(RECENT_LOGS)

    if level:
        level_upper = level.upper()
        entries = [entry for entry in entries if entry["level"] == level_upper]

    return {
        "count": min(len(entries), safe_limit),
        "total_buffered": len(RECENT_LOGS),
        "logs": entries[-safe_limit:],
    }


@app.get("/stories/{story_id}/html")
def get_story_html(story_id: str, orchestrator: StoryOrchestrator = Depends(get_orchestrator)):
    """Get rendered HTML for a story."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"🔍 Getting HTML for story_id: {story_id}")
        record = orchestrator.get_story(story_id)
        logger.info(f"✅ Story found: template_key={record.template_key}, mode={record.mode}")
        
        if not orchestrator.html_renderer:
            logger.error("❌ HTML renderer not available")
            raise HTTPException(status_code=503, detail="HTML renderer not available")

        logger.info(f"🔍 Rendering HTML with template_key={record.template_key}, template_source=file")
        html_content = orchestrator.html_renderer.render(
            record=record,
            template_key=record.template_key,
            template_source="file",
        )
        logger.info(f"✅ HTML rendered successfully, length={len(html_content)}")
        return {"html": html_content, "story_id": story_id, "template_key": record.template_key}
    except KeyError as exc:
        logger.error(f"❌ Story not found: {story_id}")
        raise HTTPException(status_code=404, detail="Story not found") from exc
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as exc:
        logger.error(f"❌ HTML rendering failed for story_id={story_id}: {exc}", exc_info=True)
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
