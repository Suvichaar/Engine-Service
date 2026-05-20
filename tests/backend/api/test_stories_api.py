from __future__ import annotations

import os
import time
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
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "stub-key")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "deployment")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "version")
    monkeypatch.setenv("DALL_E_ENDPOINT", "https://dalle")
    monkeypatch.setenv("DALL_E_KEY", "stub-key")
    monkeypatch.setenv("AZURE_SPEECH_KEY", "stub-speechkey")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
    monkeypatch.setenv("VOICE_NAME", "voice")
    monkeypatch.setenv("AZURE_SPEECH_VOICE", "en-US-AriaNeural")
    monkeypatch.setenv("AZURE_DI_ENDPOINT", "https://di")
    monkeypatch.setenv("AZURE_DI_KEY", "stub-dikey")
    monkeypatch.setenv("AWS_ACCESS_KEY", "stub-access")
    monkeypatch.setenv("AWS_SECRET_KEY", "stub-secret")
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
        "template_key": "curious-template-1",
        "slide_count": 4,
        "category": "Art",
        "text_prompt": "Tell me about AI art.",
        "prompt_keywords": ["AI", "art"],
        "image_source": "ai",
    }

    response = client.post("/stories", json=payload)
    assert response.status_code == 202, response.text
    ack = response.json()
    story_id = ack["id"]
    UUID(story_id)  # valid UUID
    assert ack["status"] == "pending"

    deadline = time.monotonic() + 60
    body = None
    final_status = None
    while time.monotonic() < deadline:
        status_response = client.get(f"/stories/{story_id}/status")
        assert status_response.status_code == 200, status_response.text
        body = status_response.json()
        final_status = body["status"]
        if final_status in ("completed", "failed"):
            break
        time.sleep(0.2)

    assert final_status == "completed", body
    assert body["story"]["id"] == story_id

    get_response = client.get(f"/stories/{story_id}")
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["id"] == story_id
    assert fetched["category"] == "Art"
    assert fetched["template_key"] == "curious-template-1"
