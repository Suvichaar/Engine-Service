from __future__ import annotations

from dataclasses import dataclass

from app.domain.dto import LanguageMetadata, Mode, SlideBlock, SlideDeck, VoiceAsset
from app.services.voice_synthesis import (
    AzureTTSClient,
    DefaultVoiceSynthesisService,
    ElevenLabsClient,
    VoiceGenerationResult,
    VoiceProvider,
    VoiceStorageService,
)


class StubVoiceProvider:
    name = "stub"

    def __init__(self, response: VoiceGenerationResult):
        self._response = response
        self.calls: list[tuple[str, str]] = []

    def supports(self, provider_id: str) -> bool:
        return provider_id == self.name

    def synthesize(self, text: str, *, language: str) -> VoiceGenerationResult:
        self.calls.append((text, language))
        return self._response


class StubStorage(VoiceStorageService):
    def __init__(self):
        self.calls: list[VoiceGenerationResult] = []

    def store(self, *, audio: VoiceGenerationResult, filename: str) -> VoiceAsset:
        self.calls.append(audio)
        return VoiceAsset(
            provider="stub",
            voice_id=audio.voice_id,
            audio_url=f"https://cdn.example.com/{filename}",
            duration_seconds=None,
        )


def make_deck() -> SlideDeck:
    return SlideDeck(
        template_key="modern",
        language_code="en",
        slides=[
            SlideBlock(placeholder_id="title", text="Welcome to the revolution."),
            SlideBlock(placeholder_id="body", text="This slide explores the impacts."),
        ],
    )


def make_language() -> LanguageMetadata:
    return LanguageMetadata(language_code="en-US", confidence=0.99)


def test_voice_service_uses_provider_and_storage():
    provider = StubVoiceProvider(response=VoiceGenerationResult(audio_bytes=b"bytes", format="mp3"))
    storage = StubStorage()
    service = DefaultVoiceSynthesisService([provider], storage)

    assets = service.synthesize(make_deck(), make_language(), provider="stub")

    assert len(assets) == 1
    assert provider.calls[0][0].startswith("Slide 1")
    assert storage.calls[0].audio_bytes == b"bytes"
    assert str(assets[0].audio_url).startswith("https://cdn.example.com/")


def test_voice_service_returns_empty_when_no_provider_found():
    storage = StubStorage()
    service = DefaultVoiceSynthesisService([], storage)

    assets = service.synthesize(make_deck(), make_language(), provider="stub")

    assert assets == []
    assert storage.calls == []


def test_elevenlabs_and_azure_clients_generate_bytes():
    elevenlabs = ElevenLabsClient(api_key="key", voice_id="voice-1")
    azure = AzureTTSClient(api_key="key", region="eastus", voice="en-US-Aria")

    res1 = elevenlabs.synthesize("Hello world", language="en-US")
    res2 = azure.synthesize("Hello world", language="en-US")

    assert res1.audio_bytes.startswith(b"ELEVENLABS")
    assert res2.audio_bytes.startswith(b"AZURE")

