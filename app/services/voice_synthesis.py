"""Voice synthesis service with pluggable providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Protocol, Sequence
from uuid import uuid4

from app.domain.dto import LanguageMetadata, SlideDeck, VoiceAsset
from app.domain.interfaces import VoiceSynthesisService


class VoiceProvider(Protocol):
    """Provider interface for generating narration audio."""

    name: str

    def supports(self, provider_id: str) -> bool:
        """Return True if this provider matches the requested provider identifier."""

    def synthesize(self, text: str, *, language: str) -> "VoiceGenerationResult":
        """Generate audio content for a given text and language."""


@dataclass
class VoiceGenerationResult:
    """Represents generated audio prior to storage."""

    audio_bytes: bytes
    format: str
    voice_id: Optional[str] = None
    metadata: dict | None = None


class VoiceStorageService(Protocol):
    """Persist audio content and return URLs."""

    def store(self, *, audio: VoiceGenerationResult, filename: str) -> VoiceAsset:
        """Store audio content and return a VoiceAsset."""


class DefaultVoiceSynthesisService(VoiceSynthesisService):
    """Coordinate voice providers and storage to produce voice assets."""

    def __init__(self, providers: Sequence[VoiceProvider], storage: VoiceStorageService) -> None:
        self._providers = list(providers)
        self._storage = storage

    def synthesize(self, deck: SlideDeck, language: LanguageMetadata, provider: str) -> list[VoiceAsset]:
        voice_provider = self._resolve_provider(provider)
        if voice_provider is None:
            return []

        combined_text = self._assemble_script(deck)
        audio = voice_provider.synthesize(combined_text, language=language.language_code)
        filename = f"{uuid4()}.{audio.format}"
        asset = self._storage.store(audio=audio, filename=filename)
        return [asset]

    def _resolve_provider(self, provider_id: str) -> Optional[VoiceProvider]:
        for voice_provider in self._providers:
            if voice_provider.supports(provider_id):
                return voice_provider
        return None

    def _assemble_script(self, deck: SlideDeck) -> str:
        lines = []
        for idx, slide in enumerate(deck.slides, start=1):
            if slide.text:
                lines.append(f"Slide {idx}: {slide.text}")
        return "\n".join(lines)


# --- Provider Implementations -------------------------------------------------


class ElevenLabsClient:
    """Stubbed ElevenLabs provider."""

    name = "elevenlabs_pro"

    def __init__(self, api_key: str, voice_id: str) -> None:
        self._api_key = api_key
        self._voice_id = voice_id

    def supports(self, provider_id: str) -> bool:
        return provider_id == self.name

    def synthesize(self, text: str, *, language: str) -> VoiceGenerationResult:
        audio_bytes = f"ELEVENLABS:{language}:{text}".encode("utf-8")
        return VoiceGenerationResult(
            audio_bytes=audio_bytes, format="mp3", voice_id=self._voice_id, metadata={"provider": self.name}
        )


class AzureTTSClient:
    """Stubbed Azure Text-to-Speech provider."""

    name = "azure_basic"

    def __init__(self, api_key: str, region: str, voice: str) -> None:
        self._api_key = api_key
        self._region = region
        self._voice = voice

    def supports(self, provider_id: str) -> bool:
        return provider_id == self.name

    def synthesize(self, text: str, *, language: str) -> VoiceGenerationResult:
        audio_bytes = f"AZURE:{language}:{text}".encode("utf-8")
        return VoiceGenerationResult(
            audio_bytes=audio_bytes, format="wav", voice_id=self._voice, metadata={"provider": self.name}
        )


# --- Storage Implementation ---------------------------------------------------


class S3VoiceStorageService:
    """Persist voice assets to S3 (simulated) and provide CDN URLs."""

    def __init__(self, bucket: str, prefix: str, cdn_base: str) -> None:
        self._bucket = bucket
        self._prefix = prefix.rstrip("/") + "/" if prefix else ""
        self._cdn_base = cdn_base.rstrip("/") + "/"

    def store(self, *, audio: VoiceGenerationResult, filename: str) -> VoiceAsset:
        object_key = f"{self._prefix}{filename}"
        cdn_url = f"{self._cdn_base}{object_key}"
        return VoiceAsset(
            provider=(audio.metadata or {}).get("provider") or "voice",
            voice_id=audio.voice_id,
            audio_url=cdn_url,
            duration_seconds=None,
        )


__all__ = [
    "DefaultVoiceSynthesisService",
    "ElevenLabsClient",
    "AzureTTSClient",
    "S3VoiceStorageService",
    "VoiceProvider",
    "VoiceStorageService",
    "VoiceGenerationResult",
]

