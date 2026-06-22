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
from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.schemas import (
    LoginRequest,
    PromptActivateRequest,
    PromptCreateRequest,
    PromptListingResponse,
    PromptUpdateRequest,
    PromptVersionResponse,
    PublishHistoryResponse,
    PublishRequest,
    PublishResponse,
    BroadcastHistoryResponse,
    BroadcastRequest,
    BroadcastResponse,
    StoryListItem,
    StoryListResponse,
    StoryboardBulkCreateRequest,
    StoryboardBulkCreateResponse,
    StoryboardCreateRequest,
    StoryboardItem,
    StoryboardListResponse,
    StoryboardUpdateRequest,
    SubscriberBulkCreateRequest,
    SubscriberBulkCreateResponse,
    SubscriberCreateRequest,
    SubscriberItem,
    SubscriberListResponse,
    SubscriberTagsResponse,
    SubscriberUpdateRequest,
    TemplateActivateRequest,
    TemplateCreateRequest,
    TemplateListingResponse,
    TemplateUpdateRequest,
    TemplateVersionResponse,
    StoryCreateRequest,
    StoryJobAck,
    StoryJobStatusResponse,
    StoryResponse,
    TokenResponse,
    UserResponse,
)
from app.core import get_settings
from app.core.auth import (
    CurrentUser,
    create_access_token,
    get_auth_config,
    get_current_user,
    verify_password,
)
from app.domain.dto import AttachmentDescriptor, Mode
from app.domain.interfaces import ModelClient, PromptTemplateService
from app.services.broadcast import BroadcastService, RecipientRef
from app.persistence import (
    Base,
    SqlAlchemyBroadcastRepository,
    SqlAlchemyPublishRepository,
    SqlAlchemyStoryRepository,
    SqlAlchemyStoryboardRepository,
    SqlAlchemySubscriberRepository,
    StoryboardNotFound,
    StoryboardSlugTaken,
    SubscriberNotFound,
    create_session_factory,
    ensure_broadcast_schema,
    ensure_publish_schema,
    ensure_story_schema,
    ensure_storyboard_schema,
    ensure_subscriber_schema,
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
        ensure_publish_schema(engine)
        ensure_storyboard_schema(engine)
        ensure_broadcast_schema(engine)
        ensure_subscriber_schema(engine)
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


def get_publish_repository() -> Optional[SqlAlchemyPublishRepository]:
    """Return a publish repo backed by the configured DB, or None when no DB."""
    factory = get_session_factory()
    if factory is None:
        return None
    return SqlAlchemyPublishRepository(factory)


def get_story_repository() -> Optional[SqlAlchemyStoryRepository]:
    """Return a story repo backed by the configured DB, or None when no DB."""
    factory = get_session_factory()
    if factory is None:
        return None
    return SqlAlchemyStoryRepository(factory)


# ── Auth endpoints ───────────────────────────────────────────────────────────


@app.post("/auth/login", response_model=TokenResponse)
def auth_login(payload: LoginRequest):
    cfg = get_auth_config()
    if not cfg.configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "Auth is not configured on the server. "
                "Set ADMIN_EMAIL, ADMIN_PASSWORD_HASH, and JWT_SECRET."
            ),
        )

    submitted_email = (payload.email or "").strip().lower()
    if submitted_email != cfg.admin_email or not verify_password(payload.password, cfg.admin_password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(subject=cfg.admin_email)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=cfg.jwt_expires_minutes * 60,
        user=UserResponse(email=cfg.admin_email, role="admin"),
    )


@app.get("/auth/me", response_model=UserResponse)
def auth_me(current: CurrentUser = Depends(get_current_user)):
    return UserResponse(email=current.email, role=current.role)


# ── Stories listing ──────────────────────────────────────────────────────────


@app.get("/stories", response_model=StoryListResponse)
def list_stories(
    mode: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
    _user: CurrentUser = Depends(get_current_user),
):
    """List stored stories with filters and pagination."""
    repo = get_story_repository()
    if repo is None:
        return StoryListResponse(items=[], total=0, limit=limit, offset=offset)

    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)
    rows, total = repo.list_summary(
        mode=mode,
        category=category,
        q=q,
        date_from=date_from,
        date_to=date_to,
        limit=safe_limit,
        offset=safe_offset,
    )
    items = [
        StoryListItem(
            id=row.id,
            title=row.title,
            mode=row.mode,
            category=row.category,
            input_language=row.input_language,
            slide_count=row.slide_count,
            template_key=row.template_key,
            canurl=row.canurl,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return StoryListResponse(items=items, total=total, limit=safe_limit, offset=safe_offset)


# ── Publish ──────────────────────────────────────────────────────────────────


@app.post("/stories/{story_id}/publish", response_model=PublishResponse)
def publish_story(
    story_id: str,
    payload: PublishRequest,
    current: CurrentUser = Depends(get_current_user),
    orchestrator: StoryOrchestrator = Depends(get_orchestrator),
):
    publish_repo = get_publish_repository()
    if publish_repo is None:
        raise HTTPException(
            status_code=503,
            detail="Database is not configured; cannot record publish events.",
        )

    # Validate inputs
    if payload.target == "webhook" and not (payload.webhook_url or "").strip():
        raise HTTPException(status_code=400, detail="webhook_url is required when target is 'webhook'.")

    # Ensure story exists before recording a publish.
    try:
        orchestrator.get_story(story_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Story not found.") from exc

    event = publish_repo.record(
        story_id=story_id,
        target=payload.target,
        status="success",
        published_by=current.email,
        webhook_url=payload.webhook_url,
        error=None,
    )
    return PublishResponse(
        id=event.id,
        story_id=event.story_id,
        target=event.target,
        status=event.status,
        webhook_url=event.webhook_url,
        error=event.error,
        published_by=event.published_by,
        published_at=event.published_at,
    )


@app.get("/stories/{story_id}/publishes", response_model=PublishHistoryResponse)
def list_publishes(
    story_id: str,
    _user: CurrentUser = Depends(get_current_user),
):
    publish_repo = get_publish_repository()
    if publish_repo is None:
        return PublishHistoryResponse(items=[])

    events = publish_repo.list_for_story(story_id)
    return PublishHistoryResponse(
        items=[
            {
                "id": event.id,
                "story_id": event.story_id,
                "target": event.target,
                "status": event.status,
                "webhook_url": event.webhook_url,
                "error": event.error,
                "published_by": event.published_by,
                "published_at": event.published_at,
            }
            for event in events
        ]
    )


# ── Broadcast endpoints ──────────────────────────────────────────────────────


def get_broadcast_repository() -> Optional[SqlAlchemyBroadcastRepository]:
    factory = get_session_factory()
    if factory is None:
        return None
    return SqlAlchemyBroadcastRepository(factory)


@lru_cache(maxsize=1)
def get_broadcast_service() -> BroadcastService:
    return BroadcastService()


def _story_title(story_record) -> str:
    deck = getattr(story_record, "slide_deck", None)
    if deck is not None:
        cover = getattr(deck, "cover", None)
        if cover is not None:
            title = getattr(cover, "title", None) or getattr(cover, "heading", None)
            if title:
                return str(title)
    return getattr(story_record, "category", None) or "Suvichaar story"


@app.post("/stories/{story_id}/broadcast", response_model=BroadcastResponse)
def broadcast_story(
    story_id: str,
    payload: BroadcastRequest,
    current: CurrentUser = Depends(get_current_user),
    orchestrator: StoryOrchestrator = Depends(get_orchestrator),
    service: BroadcastService = Depends(get_broadcast_service),
):
    broadcast_repo = get_broadcast_repository()
    if broadcast_repo is None:
        raise HTTPException(
            status_code=503,
            detail="Database is not configured; cannot record broadcast events.",
        )

    try:
        story_record = orchestrator.get_story(story_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Story not found.") from exc

    story_url = str(story_record.canurl or story_record.canurl1 or "")
    if not story_url:
        raise HTTPException(
            status_code=400,
            detail="Story has no shareable URL (canurl/canurl1 missing).",
        )

    story_title = _story_title(story_record)

    # Filter recipients so each channel sees only contacts that can be reached.
    requested: List[RecipientRef] = [
        RecipientRef(phone=r.phone, email=r.email, name=r.name)
        for r in payload.recipients
        if r.phone or r.email
    ]

    # When `audience_tag` is set, pull active subscribers carrying that tag and
    # merge them in. De-dup by phone first, then by email — so an explicit
    # recipient with the same phone as a tagged subscriber is not sent twice.
    if payload.audience_tag:
        sub_repo = get_subscriber_repository()
        if sub_repo is not None:
            seen_phones = {r.phone for r in requested if r.phone}
            seen_emails = {r.email for r in requested if r.email}
            for sub in sub_repo.find_by_tag(payload.audience_tag):
                if sub.phone and sub.phone in seen_phones:
                    continue
                if sub.email and sub.email in seen_emails:
                    continue
                if not (sub.phone or sub.email):
                    continue
                requested.append(RecipientRef(phone=sub.phone, email=sub.email, name=sub.name))
                if sub.phone:
                    seen_phones.add(sub.phone)
                if sub.email:
                    seen_emails.add(sub.email)

    if not requested:
        raise HTTPException(
            status_code=400,
            detail="No recipients resolved (no explicit list and no subscribers match the audience tag).",
        )

    result = service.broadcast(
        story_title=story_title,
        story_url=story_url,
        channels=list(payload.channels),
        recipients=requested,
        message=payload.message,
    )

    recipients_dump = [
        {"phone": r.phone, "email": r.email, "name": r.name} for r in requested
    ]
    outcomes_dump = [
        {"channel": o.channel, "recipient": o.recipient, "status": o.status, "error": o.error}
        for o in result.outcomes
    ]
    event = broadcast_repo.record(
        story_id=story_id,
        channels=list(payload.channels),
        status=result.status,
        recipients=recipients_dump,
        outcomes=outcomes_dump,
        total_count=result.total,
        sent_count=result.sent,
        failed_count=result.failed,
        triggered_by=current.email,
        audience_tag=payload.audience_tag,
        message=payload.message,
    )
    return BroadcastResponse(
        id=event.id,
        story_id=event.story_id,
        channels=event.channels,
        status=event.status,
        audience_tag=event.audience_tag,
        message=event.message,
        total_count=event.total_count,
        sent_count=event.sent_count,
        failed_count=event.failed_count,
        triggered_by=event.triggered_by,
        created_at=event.created_at,
        updated_at=event.updated_at,
        outcomes=event.outcomes,
    )


@app.get(
    "/stories/{story_id}/broadcasts",
    response_model=BroadcastHistoryResponse,
)
def list_broadcasts(
    story_id: str,
    _user: CurrentUser = Depends(get_current_user),
):
    broadcast_repo = get_broadcast_repository()
    if broadcast_repo is None:
        return BroadcastHistoryResponse(items=[])
    events = broadcast_repo.list_for_story(story_id)
    return BroadcastHistoryResponse(
        items=[
            {
                "id": e.id,
                "story_id": e.story_id,
                "channels": e.channels,
                "status": e.status,
                "audience_tag": e.audience_tag,
                "message": e.message,
                "total_count": e.total_count,
                "sent_count": e.sent_count,
                "failed_count": e.failed_count,
                "triggered_by": e.triggered_by,
                "created_at": e.created_at,
                "updated_at": e.updated_at,
                "outcomes": e.outcomes,
            }
            for e in events
        ]
    )


# ── Razorpay webhook ─────────────────────────────────────────────────────────


def _razorpay_signature_ok(body: bytes, signature: str, secret: str) -> bool:
    import hashlib
    import hmac

    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _extract_razorpay_subscriber(event: dict) -> dict:
    """Pull phone/email/name/tags + subscription summary from a Razorpay event.

    Razorpay puts most contact info under either `payment.entity` (for
    `payment.captured`) or `subscription.entity` (for subscription events).
    Tags are expected to be passed via Razorpay `notes` (the labs subscribe
    page should populate `notes.tags = "tag1,tag2"` at checkout time).
    """
    payload = (event.get("payload") or {})
    entity_root: dict = {}
    event_name = (event.get("event") or "").lower()

    for key in ("payment", "subscription", "order"):
        ent = (payload.get(key) or {}).get("entity") or {}
        if ent:
            entity_root = ent
            break

    notes = entity_root.get("notes") or {}
    if not isinstance(notes, dict):
        notes = {}

    phone = (
        entity_root.get("contact")
        or notes.get("phone")
        or notes.get("mobile")
        or ""
    )
    email = entity_root.get("email") or notes.get("email") or ""
    name = (
        entity_root.get("name")
        or notes.get("name")
        or notes.get("full_name")
        or ""
    )

    raw_tags = notes.get("tags") or notes.get("categories") or ""
    if isinstance(raw_tags, str):
        tags = [t.strip() for t in raw_tags.replace(";", ",").split(",") if t.strip()]
    elif isinstance(raw_tags, list):
        tags = [str(t).strip() for t in raw_tags if str(t).strip()]
    else:
        tags = []

    subscription = {
        "event": event_name,
        "razorpay_payment_id": entity_root.get("id") if "payment" in event_name else entity_root.get("payment_id"),
        "razorpay_order_id": entity_root.get("order_id"),
        "razorpay_subscription_id": entity_root.get("subscription_id") or (
            entity_root.get("id") if "subscription" in event_name else None
        ),
        "amount": entity_root.get("amount"),
        "currency": entity_root.get("currency"),
        "status": entity_root.get("status"),
        "method": entity_root.get("method"),
        "notes": notes,
    }
    return {
        "phone": (phone or "").strip() or None,
        "email": (email or "").strip() or None,
        "name": (name or "").strip() or None,
        "tags": tags,
        "subscription": subscription,
    }


@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    """Verify Razorpay HMAC and upsert subscriber on relevant events.

    Always returns 200 to ack the webhook (so Razorpay does not retry storms
    on transient downstream issues); the payload includes a `handled` flag for
    debuggability.
    """
    secret = (os.getenv("RAZORPAY_WEBHOOK_SECRET") or "").strip()
    signature = request.headers.get("x-razorpay-signature", "")
    body = await request.body()

    if not secret:
        logger.warning("Razorpay webhook received but RAZORPAY_WEBHOOK_SECRET is unset; rejecting.")
        raise HTTPException(status_code=503, detail="Razorpay webhook is not configured.")

    if not _razorpay_signature_ok(body, signature, secret):
        raise HTTPException(status_code=400, detail="Invalid Razorpay signature.")

    try:
        event = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

    event_name = (event.get("event") or "").lower()
    INTERESTED = {
        "payment.captured",
        "subscription.activated",
        "subscription.charged",
        "order.paid",
    }
    if event_name not in INTERESTED:
        return JSONResponse({"handled": False, "event": event_name})

    repo = get_subscriber_repository()
    if repo is None:
        return JSONResponse({"handled": False, "event": event_name, "reason": "no_db"})

    extracted = _extract_razorpay_subscriber(event)
    if not (extracted["phone"] or extracted["email"]):
        return JSONResponse(
            {"handled": False, "event": event_name, "reason": "no_contact_info"}
        )

    record = repo.upsert_from_payment(
        phone=extracted["phone"],
        email=extracted["email"],
        name=extracted["name"],
        tags=extracted["tags"],
        subscription=extracted["subscription"],
        source="razorpay",
    )
    return JSONResponse(
        {
            "handled": True,
            "event": event_name,
            "subscriber_id": str(record.id),
        }
    )


# ── Subscriber endpoints ─────────────────────────────────────────────────────


def get_subscriber_repository() -> Optional[SqlAlchemySubscriberRepository]:
    factory = get_session_factory()
    if factory is None:
        return None
    return SqlAlchemySubscriberRepository(factory)


def _subscriber_to_item(record) -> dict:
    return {
        "id": record.id,
        "name": record.name,
        "phone": record.phone,
        "email": record.email,
        "tags": record.tags,
        "subscription": record.subscription,
        "extra": record.extra,
        "status": record.status,
        "source": record.source,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


@app.get("/subscribers", response_model=SubscriberListResponse)
def list_subscribers(
    q: Optional[str] = None,
    tag: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    _user: CurrentUser = Depends(get_current_user),
):
    repo = get_subscriber_repository()
    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)
    if repo is None:
        return SubscriberListResponse(items=[], total=0, limit=safe_limit, offset=safe_offset)
    records, total = repo.list(
        limit=safe_limit, offset=safe_offset, q=q, tag=tag, status=status
    )
    return SubscriberListResponse(
        items=[_subscriber_to_item(r) for r in records],
        total=total,
        limit=safe_limit,
        offset=safe_offset,
    )


@app.get("/subscribers/tags", response_model=SubscriberTagsResponse)
def list_subscriber_tags(_user: CurrentUser = Depends(get_current_user)):
    repo = get_subscriber_repository()
    if repo is None:
        return SubscriberTagsResponse(items=[])
    pairs = repo.distinct_tags()
    return SubscriberTagsResponse(
        items=[{"tag": t, "count": c} for t, c in pairs]
    )


@app.post("/subscribers", response_model=SubscriberItem, status_code=201)
def create_subscriber(
    payload: SubscriberCreateRequest,
    _user: CurrentUser = Depends(get_current_user),
):
    repo = get_subscriber_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    if not payload.phone and not payload.email:
        raise HTTPException(status_code=400, detail="phone or email is required.")
    record = repo.create(
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        tags=payload.tags,
        subscription=payload.subscription,
        extra=payload.extra,
        status=payload.status,
        source="manual",
    )
    return _subscriber_to_item(record)


@app.post(
    "/subscribers/bulk",
    response_model=SubscriberBulkCreateResponse,
    status_code=201,
)
def bulk_create_subscribers(
    payload: SubscriberBulkCreateRequest,
    _user: CurrentUser = Depends(get_current_user),
):
    repo = get_subscriber_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    rows = [
        {
            "name": item.name,
            "phone": item.phone,
            "email": item.email,
            "tags": item.tags,
            "subscription": item.subscription,
            "extra": item.extra,
            "status": item.status,
        }
        for item in payload.items
    ]
    created, errors = repo.bulk_create(rows)
    return SubscriberBulkCreateResponse(
        created=[_subscriber_to_item(r) for r in created],
        errors=errors,
        requested=len(rows),
        succeeded=len(created),
        failed=len(errors),
    )


@app.get("/subscribers/{sub_id}", response_model=SubscriberItem)
def get_subscriber(
    sub_id: str,
    _user: CurrentUser = Depends(get_current_user),
):
    repo = get_subscriber_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        record = repo.get(sub_id)
    except SubscriberNotFound as exc:
        raise HTTPException(status_code=404, detail="Subscriber not found.") from exc
    return _subscriber_to_item(record)


@app.put("/subscribers/{sub_id}", response_model=SubscriberItem)
def update_subscriber(
    sub_id: str,
    payload: SubscriberUpdateRequest,
    _user: CurrentUser = Depends(get_current_user),
):
    repo = get_subscriber_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    updates = payload.model_dump(exclude_unset=True)
    try:
        record = repo.update(sub_id, updates=updates)
    except SubscriberNotFound as exc:
        raise HTTPException(status_code=404, detail="Subscriber not found.") from exc
    return _subscriber_to_item(record)


@app.delete("/subscribers/{sub_id}", status_code=204)
def delete_subscriber(
    sub_id: str,
    _user: CurrentUser = Depends(get_current_user),
):
    repo = get_subscriber_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        repo.delete(sub_id)
    except SubscriberNotFound as exc:
        raise HTTPException(status_code=404, detail="Subscriber not found.") from exc
    return None


# ── StoryBoard endpoints ─────────────────────────────────────────────────────


def get_storyboard_repository() -> Optional[SqlAlchemyStoryboardRepository]:
    """Return a storyboard repo backed by the configured DB, or None when no DB."""
    factory = get_session_factory()
    if factory is None:
        return None
    return SqlAlchemyStoryboardRepository(factory)


def _record_to_item(record) -> dict:
    return {
        "id": record.id,
        "title": record.title,
        "slug": record.slug,
        "category": record.category,
        "tags": record.tags,
        "cover_url": record.cover_url,
        "media_urls": record.media_urls,
        "language": record.language,
        "mode": record.mode,
        "status": record.status,
        "source": record.source,
        "external_id": record.external_id,
        "notes": record.notes,
        "created_by": record.created_by,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


@app.get("/storyboard", response_model=StoryboardListResponse)
def list_storyboard(
    q: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    _user: CurrentUser = Depends(get_current_user),
):
    repo = get_storyboard_repository()
    safe_limit = max(1, min(limit, 100))
    safe_offset = max(0, offset)
    if repo is None:
        return StoryboardListResponse(items=[], total=0, limit=safe_limit, offset=safe_offset)
    records, total = repo.list(
        limit=safe_limit,
        offset=safe_offset,
        category=category,
        status=status,
        tag=tag,
        q=q,
    )
    return StoryboardListResponse(
        items=[_record_to_item(r) for r in records],
        total=total,
        limit=safe_limit,
        offset=safe_offset,
    )


@app.post("/storyboard", response_model=StoryboardItem, status_code=201)
def create_storyboard(
    payload: StoryboardCreateRequest,
    current: CurrentUser = Depends(get_current_user),
):
    repo = get_storyboard_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        record = repo.create(
            title=payload.title,
            slug=payload.slug,
            category=payload.category,
            tags=payload.tags,
            cover_url=payload.cover_url,
            media_urls=[m.model_dump() for m in payload.media_urls],
            language=payload.language,
            mode=payload.mode,
            status=payload.status,
            source="manual",
            external_id=payload.external_id,
            notes=payload.notes,
            created_by=current.email,
        )
    except StoryboardSlugTaken as exc:
        raise HTTPException(status_code=409, detail=f"Slug already exists: {exc}") from exc
    return _record_to_item(record)


@app.post(
    "/storyboard/bulk",
    response_model=StoryboardBulkCreateResponse,
    status_code=201,
)
def bulk_create_storyboard(
    payload: StoryboardBulkCreateRequest,
    current: CurrentUser = Depends(get_current_user),
):
    repo = get_storyboard_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    rows = []
    for item in payload.items:
        rows.append(
            {
                "title": item.title,
                "slug": item.slug,
                "category": item.category,
                "tags": item.tags,
                "cover_url": item.cover_url,
                "media_urls": [m.model_dump() for m in item.media_urls],
                "language": item.language,
                "mode": item.mode,
                "status": item.status,
                "external_id": item.external_id,
                "notes": item.notes,
            }
        )
    created, errors = repo.bulk_create(rows, created_by=current.email)
    return StoryboardBulkCreateResponse(
        created=[_record_to_item(r) for r in created],
        errors=errors,
        requested=len(rows),
        succeeded=len(created),
        failed=len(errors),
    )


@app.get("/storyboard/{board_id}", response_model=StoryboardItem)
def get_storyboard(
    board_id: str,
    _user: CurrentUser = Depends(get_current_user),
):
    repo = get_storyboard_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        record = repo.get(board_id)
    except StoryboardNotFound as exc:
        raise HTTPException(status_code=404, detail="Storyboard not found.") from exc
    return _record_to_item(record)


@app.put("/storyboard/{board_id}", response_model=StoryboardItem)
def update_storyboard(
    board_id: str,
    payload: StoryboardUpdateRequest,
    _user: CurrentUser = Depends(get_current_user),
):
    repo = get_storyboard_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    updates = payload.model_dump(exclude_unset=True)
    if "media_urls" in updates and updates["media_urls"] is not None:
        updates["media_urls"] = [
            m if isinstance(m, dict) else m.model_dump() for m in updates["media_urls"]
        ]
    try:
        record = repo.update(board_id, updates=updates)
    except StoryboardNotFound as exc:
        raise HTTPException(status_code=404, detail="Storyboard not found.") from exc
    except StoryboardSlugTaken as exc:
        raise HTTPException(status_code=409, detail=f"Slug already exists: {exc}") from exc
    return _record_to_item(record)


@app.delete("/storyboard/{board_id}", status_code=204)
def delete_storyboard(
    board_id: str,
    _user: CurrentUser = Depends(get_current_user),
):
    repo = get_storyboard_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        repo.delete(board_id)
    except StoryboardNotFound as exc:
        raise HTTPException(status_code=404, detail="Storyboard not found.") from exc
    return None


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
