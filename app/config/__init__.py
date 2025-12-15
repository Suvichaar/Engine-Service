"""Configuration loader for service credentials."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = BASE_DIR.parent / "config" / "settings.toml"


class AzureAPISettings(BaseModel):
    endpoint: str
    api_key: str
    deployment: str
    api_version: str


class DalleSettings(BaseModel):
    endpoint: str = ""  # Optional - ai_image is used instead for image generation
    api_key: str = ""   # Optional - ai_image is used instead for image generation


class AzureSpeechSettings(BaseModel):
    api_key: str
    region: str
    voice_name: str


class AzureDocumentIntelligenceSettings(BaseModel):
    endpoint: str
    api_key: str


class AWSSettings(BaseModel):
    access_key: str
    secret_key: str
    region: str
    bucket: str
    s3_prefix: str
    html_s3_prefix: str = ""  # Default empty string - HTML files go to bucket root
    cdn_prefix_media: str
    cdn_html_base: str
    cdn_base: str
    default_error_image: str = "https://media.suvichaar.org/default-error.jpg"  # Default error image URL


class AIImageSettings(BaseModel):
    endpoint: str
    api_key: str


class PexelsSettings(BaseModel):
    api_key: str


class ImageProcessingSettings(BaseModel):
    resize_variants: str = "sm:300x200,md:768x432,lg:1280x720"


class ElevenLabsSettings(BaseModel):
    api_key: str
    voice_id: str


class AzureVoiceSettings(BaseModel):
    speech_key: str
    region: str
    voice: str


class VoiceStorageSettings(BaseModel):
    bucket: str
    prefix: str


class DatabaseSettings(BaseModel):
    url: str = "sqlite:///./stories.db"


class AppSettings(BaseModel):
    azure_api: AzureAPISettings
    dalle: DalleSettings = DalleSettings()  # Optional with defaults - ai_image is preferred
    azure_speech: AzureSpeechSettings
    azure_di: AzureDocumentIntelligenceSettings
    aws: AWSSettings
    ai_image: AIImageSettings | None = None
    pexels: PexelsSettings | None = None
    image_processing: ImageProcessingSettings = ImageProcessingSettings()
    elevenlabs: ElevenLabsSettings | None = None
    azure_voice: AzureVoiceSettings | None = None
    voice_storage: VoiceStorageSettings | None = None
    database: DatabaseSettings = DatabaseSettings()


def _load_toml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as fp:
        return tomllib.load(fp)


def _env_override() -> Dict[str, Any]:
    """Get environment variable with fallback to Azure Container Apps format.
    
    Azure Container Apps requires environment variable names to be lowercase
    alphanumeric with hyphens. This function tries the original format first,
    then falls back to the Azure-compatible format.
    """
    def get_env_with_fallback(env_name: str) -> str | None:
        # Try original format first (uppercase with underscores)
        value = os.getenv(env_name)
        if value is not None and value != "":
            return value
        # Try Azure-compatible format (lowercase with hyphens)
        azure_name = env_name.lower().replace("_", "-")
        value = os.getenv(azure_name)
        if value is not None and value != "":
            return value
        # Treat empty strings as not set so they don't override settings.toml
        return None
    
    mapping = {
        "azure_api": {
            "endpoint": get_env_with_fallback("AZURE_OPENAI_ENDPOINT"),
            "api_key": get_env_with_fallback("AZURE_OPENAI_API_KEY"),
            "deployment": get_env_with_fallback("AZURE_OPENAI_DEPLOYMENT"),
            "api_version": get_env_with_fallback("AZURE_OPENAI_API_VERSION"),
        },
        "dalle": {
            "endpoint": get_env_with_fallback("DALL_E_ENDPOINT"),
            "api_key": get_env_with_fallback("DALL_E_KEY"),
        },
        "azure_speech": {
            "api_key": get_env_with_fallback("AZURE_SPEECH_KEY"),
            "region": get_env_with_fallback("AZURE_SPEECH_REGION"),
            "voice_name": get_env_with_fallback("VOICE_NAME"),
        },
        "azure_di": {
            "endpoint": get_env_with_fallback("AZURE_DI_ENDPOINT"),
            "api_key": get_env_with_fallback("AZURE_DI_KEY"),
        },
        "aws": {
            "access_key": get_env_with_fallback("AWS_ACCESS_KEY"),
            "secret_key": get_env_with_fallback("AWS_SECRET_KEY"),
            "region": get_env_with_fallback("AWS_REGION"),
            "bucket": get_env_with_fallback("AWS_BUCKET"),
            "s3_prefix": get_env_with_fallback("S3_PREFIX"),
            "html_s3_prefix": get_env_with_fallback("HTML_S3_PREFIX"),
            "cdn_prefix_media": get_env_with_fallback("CDN_PREFIX_MEDIA"),
            "cdn_html_base": get_env_with_fallback("CDN_HTML_BASE"),
            "cdn_base": get_env_with_fallback("CDN_BASE"),
            "default_error_image": get_env_with_fallback("DEFAULT_ERROR_IMAGE"),
        },
        "ai_image": {
            "endpoint": get_env_with_fallback("AI_IMAGE_ENDPOINT"),
            "api_key": get_env_with_fallback("AI_IMAGE_API_KEY"),
        },
        "pexels": {"api_key": get_env_with_fallback("PEXELS_API_KEY")},
        "image_processing": {"resize_variants": get_env_with_fallback("RESIZE_VARIANTS")},
        "elevenlabs": {
            "api_key": get_env_with_fallback("ELEVENLABS_API_KEY"),
            "voice_id": get_env_with_fallback("ELEVENLABS_VOICE_ID"),
        },
        "azure_voice": {
            "speech_key": get_env_with_fallback("AZURE_SPEECH_KEY"),
            "region": get_env_with_fallback("AZURE_SPEECH_REGION"),
            "voice": get_env_with_fallback("AZURE_SPEECH_VOICE"),
        },
        "voice_storage": {
            "bucket": get_env_with_fallback("VOICE_BUCKET"),
            "prefix": get_env_with_fallback("VOICE_PREFIX"),
        },
        "database": {
            "url": get_env_with_fallback("DATABASE_URL"),
        },
    }
    # Filter out None values but keep empty strings (which are valid values)
    # Also include sections that have at least one non-None value
    result = {}
    for section, values in mapping.items():
        filtered_values = {k: v for k, v in values.items() if v is not None}
        # Include section if it has any values (even empty strings are valid)
        if filtered_values:
            result[section] = filtered_values
    return result


def _deep_merge(base: MutableMapping[str, Any], overrides: Mapping[str, Any]) -> MutableMapping[str, Any]:
    for key, value in overrides.items():
        if isinstance(value, Mapping):
            node = base.setdefault(key, {})
            if isinstance(node, MutableMapping):
                _deep_merge(node, value)
            else:
                base[key] = value
        else:
            base[key] = value
    return base


SECTION_MAPPING: Dict[str, Dict[str, str]] = {
    "azure_api": {
        "AZURE_OPENAI_ENDPOINT": "endpoint",
        "AZURE_OPENAI_API_KEY": "api_key",
        "AZURE_OPENAI_DEPLOYMENT": "deployment",
        "AZURE_OPENAI_API_VERSION": "api_version",
    },
    "dalle": {
        "DALL_E_ENDPOINT": "endpoint",
        "DALL_E_KEY": "api_key",
    },
    "azure_speech": {
        "AZURE_SPEECH_KEY": "api_key",
        "AZURE_SPEECH_REGION": "region",
        "VOICE_NAME": "voice_name",
    },
    "azure_di": {
        "AZURE_DI_ENDPOINT": "endpoint",
        "AZURE_DI_KEY": "api_key",
    },
    "aws": {
        "AWS_ACCESS_KEY": "access_key",
        "AWS_SECRET_KEY": "secret_key",
        "AWS_REGION": "region",
        "AWS_BUCKET": "bucket",
        "S3_PREFIX": "s3_prefix",
        "HTML_S3_PREFIX": "html_s3_prefix",
        "CDN_PREFIX_MEDIA": "cdn_prefix_media",
        "CDN_HTML_BASE": "cdn_html_base",
        "CDN_BASE": "cdn_base",
        "DEFAULT_ERROR_IMAGE": "default_error_image",
    },
    "ai_image": {
        "AI_IMAGE_ENDPOINT": "endpoint",
        "AI_IMAGE_API_KEY": "api_key",
    },
    "pexels": {
        "PEXELS_API_KEY": "api_key",
    },
    "image_processing": {
        "RESIZE_VARIANTS": "resize_variants",
    },
    "elevenlabs": {
        "ELEVENLABS_API_KEY": "api_key",
        "ELEVENLABS_VOICE_ID": "voice_id",
    },
    "azure_voice": {
        "AZURE_SPEECH_KEY": "speech_key",
        "AZURE_SPEECH_REGION": "region",
        "AZURE_SPEECH_VOICE": "voice",
    },
    "voice_storage": {
        "VOICE_BUCKET": "bucket",
        "VOICE_PREFIX": "prefix",
    },
    "database": {
        "DATABASE_URL": "url",
    },
}


def _normalize_config(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for section, values in data.items():
        mapping = SECTION_MAPPING.get(section, {})
        normalized_section: Dict[str, Any] = {}
        if isinstance(values, Mapping):
            for key, value in values.items():
                normalized_key = mapping.get(key, key.lower())
                normalized_section[normalized_key] = value
        normalized[section] = normalized_section
    return normalized


def load_settings(config_path: Optional[Path] = None) -> AppSettings:
    """Load settings from a TOML file, overridden by environment variables."""

    path = config_path or DEFAULT_CONFIG_PATH
    data: Dict[str, Any] = _normalize_config(_load_toml(path))
    overrides = _env_override()
    merged = _deep_merge(data, overrides)
    
    # Ensure fields with defaults are present if their parent section exists
    # This is needed because Pydantic defaults only work when field is completely absent,
    # not when parent dict exists but field is missing
    if "aws" in merged and isinstance(merged["aws"], dict):
        aws_dict = merged["aws"]
        if "html_s3_prefix" not in aws_dict:
            aws_dict["html_s3_prefix"] = ""
        if "default_error_image" not in aws_dict:
            aws_dict["default_error_image"] = "https://media.suvichaar.org/default-error.jpg"
    
    # Ensure dalle section has defaults if missing
    if "dalle" not in merged:
        merged["dalle"] = {"endpoint": "", "api_key": ""}
    elif isinstance(merged.get("dalle"), dict):
        dalle_dict = merged["dalle"]
        if "endpoint" not in dalle_dict:
            dalle_dict["endpoint"] = ""
        if "api_key" not in dalle_dict:
            dalle_dict["api_key"] = ""
    
    # Ensure ai_image section exists - IMPORTANT for AIImageProvider initialization
    # This ensures settings.ai_image is never None, even if environment variables are missing
    if "ai_image" not in merged:
        merged["ai_image"] = {"endpoint": "", "api_key": ""}
    elif isinstance(merged.get("ai_image"), dict):
        ai_image_dict = merged["ai_image"]
        if "endpoint" not in ai_image_dict:
            ai_image_dict["endpoint"] = ""
        if "api_key" not in ai_image_dict:
            ai_image_dict["api_key"] = ""
    
    # Note: ai_image endpoint and api_key should be set via environment variables
    # In Azure Container Apps, set: AI_IMAGE_ENDPOINT and AI_IMAGE_API_KEY
    
    # Ensure pexels section exists - IMPORTANT for PexelsImageProvider initialization
    if "pexels" not in merged:
        merged["pexels"] = {"api_key": ""}
    elif isinstance(merged.get("pexels"), dict):
        pexels_dict = merged["pexels"]
        if "api_key" not in pexels_dict:
            pexels_dict["api_key"] = ""
    
    # Note: Pexels API key should be set via environment variable
    # In Azure Container Apps, set: PEXELS_API_KEY or pexels-api-key
    
    return AppSettings(**merged)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Cached accessor using the default configuration path."""

    return load_settings()


__all__ = [
    "AppSettings",
    "AzureAPISettings",
    "AzureDocumentIntelligenceSettings",
    "AzureSpeechSettings",
    "AWSSettings",
    "DalleSettings",
    "AIImageSettings",
    "PexelsSettings",
    "ImageProcessingSettings",
    "ElevenLabsSettings",
    "AzureVoiceSettings",
    "VoiceStorageSettings",
    "DatabaseSettings",
    "get_settings",
    "load_settings",
]

