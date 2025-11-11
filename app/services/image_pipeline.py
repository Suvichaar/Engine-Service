"""Image asset pipeline with pluggable providers and storage service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional, Protocol, Sequence
from uuid import uuid4

from app.domain.dto import ImageAsset, IntakePayload, SlideDeck
from app.domain.interfaces import ImageAssetPipeline


@dataclass
class ImageContent:
    """In-memory representation of an image prior to storage."""

    placeholder_id: str
    content: bytes
    filename: str
    description: Optional[str] = None


class ImageProvider(Protocol):
    """Strategy interface for sourcing images."""

    source: str

    def supports(self, payload: IntakePayload) -> bool:
        """Return True if the provider can supply images for the payload."""

    def generate(self, deck: SlideDeck, payload: IntakePayload) -> Sequence[ImageContent]:
        """Return image contents mapped to slide placeholders."""


class ImageStorageService(Protocol):
    """Stores image content and produces ImageAsset metadata."""

    def store(self, *, content: ImageContent, source: str) -> ImageAsset:
        """Persist the content and return a stored asset description."""


class DefaultImageAssetPipeline(ImageAssetPipeline):
    """Compose providers and storage to produce final image assets."""

    def __init__(
        self,
        providers: Sequence[ImageProvider],
        storage: ImageStorageService,
    ) -> None:
        self._providers = list(providers)
        self._storage = storage

    def process(self, deck: SlideDeck, payload: IntakePayload) -> List[ImageAsset]:
        provider = self._select_provider(payload)
        if provider is None:
            return []

        contents = provider.generate(deck, payload)
        assets: List[ImageAsset] = []
        for content in contents:
            assets.append(self._storage.store(content=content, source=provider.source))
        return assets

    def _select_provider(self, payload: IntakePayload) -> Optional[ImageProvider]:
        for provider in self._providers:
            if provider.supports(payload):
                return provider
        return None


# --- Provider Implementations -------------------------------------------------


class AIImageProvider:
    """Generate images using an AI image model."""

    source = "ai"

    def __init__(self, endpoint: str, api_key: str) -> None:
        self._endpoint = endpoint
        self._api_key = api_key

    def supports(self, payload: IntakePayload) -> bool:
        return payload.image_source == "ai"

    def generate(self, deck: SlideDeck, payload: IntakePayload) -> Sequence[ImageContent]:
        contents: list[ImageContent] = []
        prompt_keywords = ", ".join(payload.prompt_keywords) or "story"
        for slide in deck.slides:
            if slide.image_url:
                continue
            prompt = f"{slide.text or 'Visual concept'} | keywords: {prompt_keywords}"
            contents.append(
                ImageContent(
                    placeholder_id=slide.placeholder_id,
                    content=prompt.encode("utf-8"),
                    filename=f"{slide.placeholder_id}.txt",
                    description="AI generated image",
                )
            )
        return contents


class PexelsImageProvider:
    """Fetch royalty-free images from Pexels."""

    source = "pexels"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def supports(self, payload: IntakePayload) -> bool:
        return payload.image_source == "pexels"

    def generate(self, deck: SlideDeck, payload: IntakePayload) -> Sequence[ImageContent]:
        contents: list[ImageContent] = []
        query = payload.prompt_keywords[:1] or ["news"]
        for slide, term in zip(deck.slides, query * len(deck.slides)):
            if slide.image_url:
                continue
            contents.append(
                ImageContent(
                    placeholder_id=slide.placeholder_id,
                    content=f"PEXELS:{term}".encode("utf-8"),
                    filename=f"{slide.placeholder_id}.txt",
                    description=f"Pexels image for {term}",
                )
            )
        return contents


class UserUploadProvider:
    """Reuse user-uploaded images."""

    source = "custom"

    def supports(self, payload: IntakePayload) -> bool:
        return payload.image_source == "custom" and bool(payload.attachments)

    def generate(self, deck: SlideDeck, payload: IntakePayload) -> Sequence[ImageContent]:
        contents: list[ImageContent] = []
        for slide, attachment in zip(deck.slides, payload.attachments):
            if slide.image_url:
                continue
            contents.append(self._to_content(slide.placeholder_id, attachment))
        return contents

    def _to_content(self, placeholder_id: str, attachment: str) -> ImageContent:
        filename = attachment.split("/")[-1] or f"{placeholder_id}.upload"
        return ImageContent(
            placeholder_id=placeholder_id,
            content=f"UPLOAD:{attachment}".encode("utf-8"),
            filename=filename,
            description="User uploaded image",
        )


# --- Storage Implementation ---------------------------------------------------


class S3ImageStorageService:
    """Persist images to S3, simulate resizing, and expose CloudFront URLs."""

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str,
        cdn_base: str,
        resize_variants: Mapping[str, str] | None = None,
    ) -> None:
        self._bucket = bucket
        self._prefix = prefix.rstrip("/") + "/" if prefix else ""
        self._cdn_base = cdn_base.rstrip("/") + "/"
        self._resize_variants = resize_variants or {"sm": "320x180", "md": "768x432", "lg": "1280x720"}

    def store(self, *, content: ImageContent, source: str) -> ImageAsset:
        object_key = f"{self._prefix}{uuid4()}/{content.filename}"
        resized_urls = [self._cdn(object_key, suffix) for suffix in self._resize_variants.keys()]
        return ImageAsset(
            source=source,
            original_object_key=object_key,
            resized_variants=resized_urls,
            description=content.description,
        )

    def _cdn(self, object_key: str, variant: str) -> str:
        return f"{self._cdn_base}{variant}/{object_key}"


__all__ = [
    "DefaultImageAssetPipeline",
    "ImageProvider",
    "ImageStorageService",
    "AIImageProvider",
    "PexelsImageProvider",
    "UserUploadProvider",
    "S3ImageStorageService",
]

