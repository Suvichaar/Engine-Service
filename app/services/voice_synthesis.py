"""Voice synthesis service with pluggable providers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional, Protocol, Sequence
from uuid import uuid4

import httpx
from pydantic import HttpUrl

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
        logger = logging.getLogger(__name__)
        voice_provider = self._resolve_provider(provider)
        if voice_provider is None:
            logger.warning("No voice provider found for id=%s; available providers=%s",
                           provider, [getattr(p, 'name', type(p).__name__) for p in self._providers])
            return []

        # Generate separate audio for each slide (not combined)
        # Important: Generate assets for ALL slides in order, even if empty, to match slide indices
        assets: list[VoiceAsset] = []
        for idx, slide in enumerate(deck.slides):
            if not slide.text or not slide.text.strip():
                # For empty slides, create a placeholder/minimal audio asset to maintain index alignment
                logger.warning("Slide %d has no text, generating placeholder audio", idx + 1)
                # Generate minimal audio for empty slides (short silence or placeholder text)
                slide_text = " "  # Single space as placeholder
            else:
                # Use slide text directly (no "Slide 1:", "Slide 2:" prefix)
                slide_text = slide.text.strip()
            
            try:
                audio = voice_provider.synthesize(slide_text, language=language.language_code)
                filename = f"{uuid4()}.{audio.format}"
                asset = self._storage.store(audio=audio, filename=filename)
                assets.append(asset)
            except Exception as e:
                logger.warning("Failed to generate audio for slide %d: %s", idx + 1, e)
                # Create a placeholder asset to maintain index alignment
                # This ensures voice_assets[0] = slide 0, voice_assets[1] = slide 1, etc.
                from app.domain.dto import VoiceAsset
                from pydantic import HttpUrl
                placeholder_url = HttpUrl("https://media.suvichaar.org/placeholder-audio.mp3")
                placeholder_asset = VoiceAsset(
                    provider=voice_provider.name,
                    voice_id=None,
                    audio_url=placeholder_url,
                    duration_seconds=None,
                )
                assets.append(placeholder_asset)
        
        logger.warning("Generated %d voice assets for %d slides", len(assets), len(deck.slides))
        return assets

    def _resolve_provider(self, provider_id: str) -> Optional[VoiceProvider]:
        for voice_provider in self._providers:
            if voice_provider.supports(provider_id):
                return voice_provider
        return None


# --- Provider Implementations -------------------------------------------------


class ElevenLabsClient:
    """Stubbed ElevenLabs provider."""

    name = "elevenlabs_pro"

    def __init__(self, api_key: str, voice_id: str) -> None:
        self._api_key = api_key
        self._voice_id = voice_id

    def supports(self, provider_id: str) -> bool:
        match = provider_id == self.name
        logging.getLogger(__name__).warning(
            "ElevenLabsClient.supports(%s) -> %s (name=%s)", provider_id, match, self.name
        )
        return match

    def synthesize(self, text: str, *, language: str) -> VoiceGenerationResult:
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{self._voice_id}",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                audio_bytes = response.content
        except Exception as exc:  # pragma: no cover - network fallback
            logging.getLogger(__name__).warning("ElevenLabs synthesis failed: %s", exc)
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
        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3",
        }
        # Escape special XML/SSML characters for safe SSML generation
        import html
        # html.escape handles &, <, > automatically
        # quote=False means don't escape quotes (we use single quotes in SSML)
        escaped_text = html.escape(text, quote=False)
        ssml = (
            "<speak version='1.0' xml:lang='en-US'>"
            f"<voice name='{self._voice}'>{escaped_text}</voice>"
            "</speak>"
        )
        url = f"https://{self._region}.tts.speech.microsoft.com/cognitiveservices/v1"
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, headers=headers, content=ssml.encode("utf-8"))
                response.raise_for_status()
                audio_bytes = response.content
        except Exception as exc:  # pragma: no cover - network fallback
            logging.getLogger(__name__).warning("Azure TTS synthesis failed: %s", exc)
            audio_bytes = f"AZURE:{language}:{text}".encode("utf-8")
        return VoiceGenerationResult(
            audio_bytes=audio_bytes, format="wav", voice_id=self._voice, metadata={"provider": self.name}
        )


# --- Storage Implementation ---------------------------------------------------


class S3VoiceStorageService:
    """Persist voice assets to S3 and provide CDN URLs."""

    def __init__(
        self,
        bucket: str,
        prefix: str,
        cdn_base: str,
        aws_access_key: Optional[str] = None,
        aws_secret_key: Optional[str] = None,
        aws_region: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._bucket = bucket
        self._prefix = prefix.rstrip("/") + "/" if prefix else ""
        self._cdn_base = cdn_base.rstrip("/") + "/"
        self._aws_access_key = aws_access_key
        self._aws_secret_key = aws_secret_key
        self._aws_region = aws_region
        self._logger = logger or logging.getLogger(__name__)
        self._s3_client = None

    def _get_s3_client(self):
        """Lazy-load boto3 S3 client."""
        if self._s3_client is None:
            try:
                import boto3
                if self._aws_access_key and self._aws_secret_key:
                    self._s3_client = boto3.client(
                        "s3",
                        aws_access_key_id=self._aws_access_key,
                        aws_secret_access_key=self._aws_secret_key,
                        region_name=self._aws_region or "us-east-1",
                    )
                else:
                    # Use default credentials (IAM role, env vars, etc.)
                    self._s3_client = boto3.client("s3", region_name=self._aws_region or "us-east-1")
            except ImportError:
                self._logger.warning("boto3 not installed, S3 uploads will be simulated")
                return None
        return self._s3_client

    def store(self, *, audio: VoiceGenerationResult, filename: str) -> VoiceAsset:
        """Upload audio to S3 and return VoiceAsset with CDN URL."""
        object_key = f"{self._prefix}{filename}"
        s3_client = self._get_s3_client()

        if s3_client:
            try:
                s3_client.put_object(
                    Bucket=self._bucket,
                    Key=object_key,
                    Body=audio.audio_bytes,
                    ContentType=f"audio/{audio.format}",
                )
                self._logger.info("Uploaded voice asset to s3://%s/%s", self._bucket, object_key)
            except Exception as e:
                self._logger.error("Failed to upload to S3: %s", e)
        else:
            self._logger.warning("S3 client unavailable, simulating upload for %s", object_key)

        cdn_url = HttpUrl(f"{self._cdn_base}{object_key}")
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

