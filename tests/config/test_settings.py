from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config import load_settings


def write_config(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_load_settings_from_toml(tmp_path: Path):
    config_path = write_config(
        tmp_path / "settings.toml",
        """
[azure_api]
AZURE_OPENAI_ENDPOINT = "https://example.com"
AZURE_OPENAI_API_KEY = "key"
AZURE_OPENAI_DEPLOYMENT = "deployment"
AZURE_OPENAI_API_VERSION = "version"

[dalle]
DALL_E_ENDPOINT = "https://dalle"
DALL_E_KEY = "dallekey"

[azure_speech]
AZURE_SPEECH_KEY = "speechkey"
AZURE_SPEECH_REGION = "eastus"
VOICE_NAME = "voice"

[azure_di]
AZURE_DI_ENDPOINT = "https://di"
AZURE_DI_KEY = "dikey"

[aws]
AWS_ACCESS_KEY = "aws-access"
AWS_SECRET_KEY = "aws-secret"
AWS_REGION = "region"
AWS_BUCKET = "bucket"
S3_PREFIX = "prefix"
HTML_S3_PREFIX = "html"
CDN_PREFIX_MEDIA = "media"
CDN_HTML_BASE = "html-base"
CDN_BASE = "base"
DEFAULT_ERROR_IMAGE = "error-image"

[image_processing]
RESIZE_VARIANTS = "sm:100x100,md:200x200"

[database]
DATABASE_URL = "sqlite:///tmp.db"
""",
    )

    settings = load_settings(config_path=config_path)

    assert settings.azure_api.endpoint == "https://example.com"
    assert settings.dalle.api_key == "dallekey"
    assert settings.aws.bucket == "bucket"


def test_load_settings_env_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_path = write_config(
        tmp_path / "settings.toml",
        """
[azure_api]
AZURE_OPENAI_ENDPOINT = "https://from-config"
AZURE_OPENAI_API_KEY = "config-key"
AZURE_OPENAI_DEPLOYMENT = "deployment"
AZURE_OPENAI_API_VERSION = "version"

[dalle]
DALL_E_ENDPOINT = "https://dalle"
DALL_E_KEY = "config-dalle-key"

[azure_speech]
AZURE_SPEECH_KEY = "config-speech-key"
AZURE_SPEECH_REGION = "eastus"
VOICE_NAME = "voice"

[azure_di]
AZURE_DI_ENDPOINT = "https://di"
AZURE_DI_KEY = "config-di-key"

[aws]
AWS_ACCESS_KEY = "config-access"
AWS_SECRET_KEY = "config-secret"
AWS_REGION = "config-region"
AWS_BUCKET = "config-bucket"
S3_PREFIX = "config-prefix"
HTML_S3_PREFIX = "config-html"
CDN_PREFIX_MEDIA = "config-media"
CDN_HTML_BASE = "config-html-base"
CDN_BASE = "config-base"
DEFAULT_ERROR_IMAGE = "config-error"

[database]
DATABASE_URL = "sqlite:///tmp.db"
""",
    )

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://from-env")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///env.db")
    monkeypatch.setenv("AWS_BUCKET", "env-bucket")

    settings = load_settings(config_path=config_path)

    assert settings.azure_api.endpoint == "https://from-env"
    assert settings.aws.bucket == "env-bucket"
    assert settings.database.url == "sqlite:///env.db"

