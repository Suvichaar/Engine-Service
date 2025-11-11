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
    endpoint: str
    api_key: str


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
    html_s3_prefix: str
    cdn_prefix_media: str
    cdn_html_base: str
    cdn_base: str
    default_error_image: str


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
    dalle: DalleSettings
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
    mapping = {
        "azure_api": {
            "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
            "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
            "deployment": os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            "api_version": os.getenv("AZURE_OPENAI_API_VERSION"),
        },
        "dalle": {
            "endpoint": os.getenv("DALL_E_ENDPOINT"),
            "api_key": os.getenv("DALL_E_KEY"),
        },
        "azure_speech": {
            "api_key": os.getenv("AZURE_SPEECH_KEY"),
            "region": os.getenv("AZURE_SPEECH_REGION"),
            "voice_name": os.getenv("VOICE_NAME"),
        },
        "azure_di": {
            "endpoint": os.getenv("AZURE_DI_ENDPOINT"),
            "api_key": os.getenv("AZURE_DI_KEY"),
        },
        "aws": {
            "access_key": os.getenv("AWS_ACCESS_KEY"),
            "secret_key": os.getenv("AWS_SECRET_KEY"),
            "region": os.getenv("AWS_REGION"),
            "bucket": os.getenv("AWS_BUCKET"),
            "s3_prefix": os.getenv("S3_PREFIX"),
            "html_s3_prefix": os.getenv("HTML_S3_PREFIX"),
            "cdn_prefix_media": os.getenv("CDN_PREFIX_MEDIA"),
            "cdn_html_base": os.getenv("CDN_HTML_BASE"),
            "cdn_base": os.getenv("CDN_BASE"),
            "default_error_image": os.getenv("DEFAULT_ERROR_IMAGE"),
        },
        "ai_image": {
            "endpoint": os.getenv("AI_IMAGE_ENDPOINT"),
            "api_key": os.getenv("AI_IMAGE_API_KEY"),
        },
        "pexels": {"api_key": os.getenv("PEXELS_API_KEY")},
        "image_processing": {"resize_variants": os.getenv("RESIZE_VARIANTS")},
        "elevenlabs": {
            "api_key": os.getenv("ELEVENLABS_API_KEY"),
            "voice_id": os.getenv("ELEVENLABS_VOICE_ID"),
        },
        "azure_voice": {
            "speech_key": os.getenv("AZURE_SPEECH_KEY"),
            "region": os.getenv("AZURE_SPEECH_REGION"),
            "voice": os.getenv("AZURE_SPEECH_VOICE"),
        },
        "voice_storage": {
            "bucket": os.getenv("VOICE_BUCKET"),
            "prefix": os.getenv("VOICE_PREFIX"),
        },
        "database": {
            "url": os.getenv("DATABASE_URL"),
        },
    }
    return {
        section: {k: v for k, v in values.items() if v is not None}
        for section, values in mapping.items()
        if any(values.values())
    }


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

