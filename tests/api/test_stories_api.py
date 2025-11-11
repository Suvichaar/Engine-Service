from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = Path("test_stories.db")
    if db_path.exists():
        db_path.unlink()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "deployment")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "version")
    monkeypatch.setenv("DALL_E_ENDPOINT", "https://dalle")
    monkeypatch.setenv("DALL_E_KEY", "key")
    monkeypatch.setenv("AZURE_SPEECH_KEY", "speechkey")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
    monkeypatch.setenv("VOICE_NAME", "voice")
    monkeypatch.setenv("AZURE_SPEECH_VOICE", "en-US-AriaNeural")
    monkeypatch.setenv("AZURE_DI_ENDPOINT", "https://di")
    monkeypatch.setenv("AZURE_DI_KEY", "dikey")
    monkeypatch.setenv("AWS_ACCESS_KEY", "access")
    monkeypatch.setenv("AWS_SECRET_KEY", "secret")
    monkeypatch.setenv("AWS_REGION", "region")
    monkeypatch.setenv("AWS_BUCKET", "bucket")
    monkeypatch.setenv("S3_PREFIX", "media")
    monkeypatch.setenv("HTML_S3_PREFIX", "")
    monkeypatch.setenv("CDN_PREFIX_MEDIA", "https://media.example.com/")
    monkeypatch.setenv("CDN_HTML_BASE", "https://stories.example.com/")
    monkeypatch.setenv("CDN_BASE", "https://cdn.example.com/")
    monkeypatch.setenv("DEFAULT_ERROR_IMAGE", "https://cdn.example.com/error.jpg")
    from app.main import app  # imported after env override

    client = TestClient(app)
    yield client
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass


def test_create_and_get_story(client: TestClient):
    payload = {
        "mode": "curious",
        "template_key": "modern",
        "slide_count": 4,
        "category": "Art",
        "text_prompt": "Tell me about AI art.",
        "prompt_keywords": ["AI", "art"],
        "image_source": "ai",
    }

    response = client.post("/stories", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    story_id = data["id"]
    UUID(story_id)  # valid UUID

    get_response = client.get(f"/stories/{story_id}")
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["id"] == story_id
    assert fetched["category"] == "Art"
    assert fetched["template_key"] == "modern"

