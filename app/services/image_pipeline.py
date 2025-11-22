"""Image asset pipeline with pluggable providers and storage service."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional, Protocol, Sequence
from uuid import uuid4

import httpx

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

    def process(
        self, deck: SlideDeck, payload: IntakePayload, article_images: Optional[list[str]] = None
    ) -> List[ImageAsset]:
        # Prioritize article images if available
        if article_images:
            # ArticleImageProvider is defined later in this file, so we reference it directly
            # Since it's in the same module, we can use it without import
            provider = ArticleImageProvider(article_images)  # type: ignore[name-defined]
        else:
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
        
        # For News mode with custom cover, generate images based on slide_count
        # slide_count = cover (1) + middle slides + CTA (1)
        # So we need images for: cover (1) + middle slides (slide_count - 2)
        if payload.mode.value == "news" and payload.slide_count:
            # Generate cover image (first slide)
            if deck.slides:
                cover_slide = deck.slides[0]
                if not cover_slide.image_url:
                    prompt = f"{cover_slide.text or 'News cover'} | keywords: {prompt_keywords}"
                    try:
                        contents.append(self._generate_image(cover_slide.placeholder_id, prompt))
                    except Exception as exc:
                        logging.getLogger(__name__).warning("AI image generation failed for cover: %s", exc)
            
            # Generate middle slide images (slide_count - 2)
            middle_slides_count = max(1, payload.slide_count - 2)
            for idx in range(1, min(middle_slides_count + 1, len(deck.slides))):
                slide = deck.slides[idx]
                if slide.image_url:
                    continue
                prompt = f"{slide.text or 'Visual concept'} | keywords: {prompt_keywords}"
                try:
                    contents.append(self._generate_image(slide.placeholder_id, prompt))
                except Exception as exc:
                    logging.getLogger(__name__).warning("AI image generation failed: %s", exc)
        else:
            # For Curious mode, extract alt text from narrative JSON in payload metadata
            # For other modes, use slide text
            alt_texts = {}
            logger = logging.getLogger(__name__)
            if payload.mode.value == "curious":
                logger.debug(f"Curious mode: metadata exists={bool(payload.metadata)}, image_source={payload.image_source}")
                if payload.metadata:
                    narrative_json = payload.metadata.get("narrative_json")
                    logger.debug(f"Narrative JSON exists: {bool(narrative_json)}, type: {type(narrative_json)}")
                    if narrative_json and isinstance(narrative_json, dict):
                        logger.debug(f"Narrative JSON keys: {list(narrative_json.keys())[:20]}")
                        # Extract alt texts: s0alt1 (cover), s1alt1, s2alt1, etc.
                        # Map: slide index 0 → s0alt1 (cover), slide index 1 → s1alt1, etc.
                        for i in range(len(deck.slides)):
                            if i == 0:
                                # Cover slide uses s0alt1
                                alt_key = "s0alt1"
                            else:
                                # Middle slides use s1alt1, s2alt1, etc. (note: slide index 1 → s1alt1)
                                alt_key = f"s{i}alt1"
                            if alt_key in narrative_json and narrative_json[alt_key]:
                                alt_texts[i] = narrative_json[alt_key]
                                logger.debug(f"Extracted alt text for slide {i} ({alt_key}): {narrative_json[alt_key][:80]}...")
                            else:
                                logger.debug(f"Alt text not found for slide {i} (key: {alt_key})")
                        logger.info(f"Extracted {len(alt_texts)} alt texts for {len(deck.slides)} slides")
                    else:
                        logger.warning("Narrative JSON is not a dict or is None")
                else:
                    logger.warning("Payload metadata is empty or None for Curious mode")
            
            # Generate images for all slides in the deck
            for idx, slide in enumerate(deck.slides):
                if slide.image_url:
                    continue
                
                # For Curious mode, prioritize alt text from narrative JSON
                if payload.mode.value == "curious":
                    if idx in alt_texts and alt_texts[idx]:
                        # Use extracted alt text
                        prompt = alt_texts[idx]
                        logger.info(f"✅ Using alt text for slide {idx} ({slide.placeholder_id}): {prompt[:100]}...")
                    else:
                        # Fallback: generate prompt from slide content
                        if idx == 0:
                            # Cover slide fallback
                            prompt = f"Cover for educational story: {slide.text or 'Learning'} — flat vector illustration, clean geometric shapes, smooth gradients, harmonious palette; inclusive, family-friendly; no text/logos/watermarks; no real-person likeness."
                        else:
                            # Middle slide fallback
                            prompt = f"{slide.text or 'Visual concept'} — flat vector illustration, clean geometric shapes, smooth gradients, harmonious palette; inclusive, family-friendly; no text/logos/watermarks; no real-person likeness. | keywords: {prompt_keywords}"
                        logger.warning(f"⚠️ Alt text not found for slide {idx} ({slide.placeholder_id}), using fallback prompt")
                else:
                    # For other modes, use slide text with keywords
                    prompt = f"{slide.text or 'Visual concept'} | keywords: {prompt_keywords}"
                
                try:
                    logger.debug(f"🖼️ Generating image for slide {idx} with prompt: {prompt[:150]}...")
                    contents.append(self._generate_image(slide.placeholder_id, prompt))
                    logger.info(f"✅ Successfully generated image for slide {idx} ({slide.placeholder_id})")
                except Exception as exc:
                    logger.error(f"❌ AI image generation failed for slide {idx} ({slide.placeholder_id}): {exc}", exc_info=True)
        return contents

    def _generate_image(self, placeholder_id: str, prompt: str) -> ImageContent:
        import base64
        import logging
        logger = logging.getLogger(__name__)
        
        headers = {
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }
        body = {"prompt": prompt, "size": "1024x1024"}
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(self._endpoint, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
        
        logger.debug(f"DALL-E API response keys: {list(data.keys())}")
        
        images = data.get("data") or []
        if not images:
            logger.error(f"No image data in response. Full response: {data}")
            raise ValueError("No image data returned from AI provider.")
        
        image_data = images[0]
        logger.debug(f"Image data keys: {list(image_data.keys())}")
        
        # Try to get base64 first (OpenAI format)
        b64 = image_data.get("b64_json")
        if b64:
            logger.debug("Using base64 image data (OpenAI format)")
            image_bytes = base64.b64decode(b64)
        else:
            # Azure DALL-E returns URL instead of base64
            image_url = image_data.get("url")
            if not image_url:
                logger.error(f"No b64_json or url in image data. Available keys: {list(image_data.keys())}")
                logger.error(f"Full image data: {image_data}")
                raise ValueError("Missing base64 image payload or URL.")
            
            # Download image from URL
            logger.info(f"Downloading image from URL: {image_url}")
            with httpx.Client(timeout=30.0) as client:
                img_response = client.get(image_url)
                img_response.raise_for_status()
                image_bytes = img_response.content
        
        filename = f"{placeholder_id}.png"
        return ImageContent(
            placeholder_id=placeholder_id,
            content=image_bytes,
            filename=filename,
            description="AI generated image",
        )


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
        
        # For News mode with custom cover, generate images based on slide_count
        if payload.mode.value == "news" and payload.slide_count:
            # Generate cover image (first slide)
            if deck.slides:
                cover_slide = deck.slides[0]
                if not cover_slide.image_url:
                    try:
                        contents.append(self._fetch_image(cover_slide.placeholder_id, query[0], image_number=0))
                    except Exception as exc:
                        logging.getLogger(__name__).warning("Pexels fetch failed for cover: %s", exc)
            
            # Generate middle slide images (slide_count - 2)
            middle_slides_count = max(1, payload.slide_count - 2)
            for idx in range(1, min(middle_slides_count + 1, len(deck.slides))):
                slide = deck.slides[idx]
                if slide.image_url:
                    continue
                try:
                    # Use different image_number for variety
                    contents.append(self._fetch_image(slide.placeholder_id, query[0], image_number=idx))
                except Exception as exc:
                    logging.getLogger(__name__).warning("Pexels fetch failed: %s", exc)
        else:
            # Original behavior for other modes
            for slide, term in zip(deck.slides, query * len(deck.slides)):
                if slide.image_url:
                    continue
                try:
                    contents.append(self._fetch_image(slide.placeholder_id, term))
                except Exception as exc:
                    logging.getLogger(__name__).warning("Pexels fetch failed: %s", exc)
        return contents

    def _fetch_image(self, placeholder_id: str, keyword: str, image_number: int = 0) -> ImageContent:
        """Fetch image from Pexels API matching the user's implementation pattern."""
        headers = {"Authorization": self._api_key}
        params = {
            "query": keyword,
            "per_page": image_number + 1,
            "orientation": "portrait",
            "size": "medium",
        }
        with httpx.Client(timeout=15.0) as client:
            response = client.get("https://api.pexels.com/v1/search", headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

        photos = data.get("photos") or []
        if not photos:
            raise ValueError("No photos returned from Pexels.")

        # Match user's logic: use image_number if available, otherwise first photo
        if len(photos) > image_number:
            photo = photos[image_number]
        else:
            photo = photos[0]

        src = photo.get("src", {}).get("original")
        if not src:
            raise ValueError("Missing original image URL.")

        with httpx.Client(timeout=30.0) as client:
            image_response = client.get(src)
            image_response.raise_for_status()
            content = image_response.content

        filename = f"{placeholder_id}.jpg"
        return ImageContent(
            placeholder_id=placeholder_id,
            content=content,
            filename=filename,
            description=f"Pexels image for {keyword}",
        )


class UserUploadProvider:
    """Reuse user-uploaded images."""

    source = "custom"

    def supports(self, payload: IntakePayload) -> bool:
        return payload.image_source == "custom" and bool(payload.attachments)

    def generate(self, deck: SlideDeck, payload: IntakePayload) -> Sequence[ImageContent]:
        contents: list[ImageContent] = []
        
        # For News mode with custom cover, use uploaded image for all slides based on slide_count
        if payload.mode.value == "news" and payload.slide_count and payload.attachments:
            # Use first attachment for cover and all middle slides
            attachment = payload.attachments[0]
            
            # Generate cover image (first slide)
            if deck.slides:
                cover_slide = deck.slides[0]
                if not cover_slide.image_url:
                    contents.append(self._to_content(cover_slide.placeholder_id, attachment))
            
            # Generate middle slide images (slide_count - 2)
            middle_slides_count = max(1, payload.slide_count - 2)
            for idx in range(1, min(middle_slides_count + 1, len(deck.slides))):
                slide = deck.slides[idx]
                if slide.image_url:
                    continue
                # Use same attachment for all slides (or cycle through if multiple)
                attachment_to_use = attachment
                if len(payload.attachments) > idx:
                    attachment_to_use = payload.attachments[idx]
                contents.append(self._to_content(slide.placeholder_id, attachment_to_use))
        else:
            # Original behavior for other modes
            for slide, attachment in zip(deck.slides, payload.attachments):
                if slide.image_url:
                    continue
                contents.append(self._to_content(slide.placeholder_id, attachment))
        return contents

    def _to_content(self, placeholder_id: str, attachment: str) -> ImageContent:
        """Convert attachment (URL, S3 URI, or file path) to ImageContent with actual bytes."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Extract filename from attachment
        filename = attachment.split("/")[-1] or f"{placeholder_id}.upload"
        # Remove query parameters from filename if present
        if "?" in filename:
            filename = filename.split("?")[0]
        
        image_bytes = None
        
        try:
            # Case 1: HTTP/HTTPS URL - download the image
            if attachment.startswith(("http://", "https://")):
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(attachment)
                    response.raise_for_status()
                    image_bytes = response.content
                    logger.info("Downloaded image from URL: %s (%d bytes)", attachment, len(image_bytes))
            
            # Case 2: S3 URI (s3://bucket/key) - load from S3
            elif attachment.startswith("s3://"):
                image_bytes = self._load_from_s3(attachment, logger)
            
            # Case 3: Local file path - read from filesystem
            else:
                from pathlib import Path
                path = Path(attachment)
                if path.exists():
                    image_bytes = path.read_bytes()
                    logger.info("Loaded image from local file: %s (%d bytes)", attachment, len(image_bytes))
                else:
                    logger.warning("Attachment path does not exist: %s", attachment)
        
        except Exception as e:
            logger.error("Failed to load image from attachment %s: %s", attachment, e)
            # Fallback: return placeholder content (will fail gracefully later)
            image_bytes = f"UPLOAD_FAILED:{attachment}".encode("utf-8")
        
        if image_bytes is None:
            logger.warning("Could not load image bytes from attachment: %s", attachment)
            image_bytes = f"UPLOAD_FAILED:{attachment}".encode("utf-8")
        
        return ImageContent(
            placeholder_id=placeholder_id,
            content=image_bytes,
            filename=filename,
            description="User uploaded image",
        )
    
    def _load_from_s3(self, s3_uri: str, logger: logging.Logger) -> Optional[bytes]:
        """Load image from S3 URI (s3://bucket/key)."""
        try:
            import boto3
            from urllib.parse import urlparse
            
            parsed = urlparse(s3_uri)
            bucket = parsed.netloc
            key = parsed.path.lstrip("/")
            
            # Try to use default AWS credentials (IAM role, env vars, etc.)
            s3_client = boto3.client("s3")
            response = s3_client.get_object(Bucket=bucket, Key=key)
            image_bytes = response["Body"].read()
            logger.info("Loaded image from S3: %s (%d bytes)", s3_uri, len(image_bytes))
            return image_bytes
        except ImportError:
            logger.warning("boto3 not installed, cannot load from S3")
            return None
        except Exception as e:
            logger.error("Failed to load from S3 %s: %s", s3_uri, e)
            return None


class NewsDefaultImageProvider:
    """Default image provider for News mode when no image_source is specified."""

    source = "news_default"

    def supports(self, payload: IntakePayload) -> bool:
        """Only for NEWS mode when image_source is None/not provided."""
        from app.domain.dto import Mode

        return payload.mode == Mode.NEWS and payload.image_source is None

    def generate(self, deck: SlideDeck, payload: IntakePayload) -> Sequence[ImageContent]:
        """Return empty list - default images will be handled in HTML renderer."""
        # For News mode with no image_source, we use default URLs directly in HTML renderer
        # No actual image generation/upload needed
        return []


class ArticleImageProvider:
    """Provider that uses images extracted from article URLs."""

    source = "article"

    def __init__(self, article_images: list[str], logger: Optional[logging.Logger] = None):
        self._article_images = article_images
        self._logger = logger or logging.getLogger(__name__)

    def supports(self, payload: IntakePayload) -> bool:
        """Always supports if article images are available."""
        return bool(self._article_images)

    def generate(self, deck: SlideDeck, payload: IntakePayload) -> Sequence[ImageContent]:
        """Download and return article images."""
        contents: list[ImageContent] = []
        
        for idx, slide in enumerate(deck.slides):
            if slide.image_url:
                continue
            
            # Use article image if available
            if idx < len(self._article_images):
                image_url = self._article_images[idx]
                try:
                    # Download image
                    with httpx.Client(timeout=30.0) as client:
                        response = client.get(image_url)
                        response.raise_for_status()
                        image_bytes = response.content
                    
                    # Determine filename from URL
                    from urllib.parse import urlparse
                    parsed = urlparse(image_url)
                    filename = parsed.path.split("/")[-1] or f"article_{idx}.jpg"
                    if not filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                        filename = f"article_{idx}.jpg"
                    
                    contents.append(
                        ImageContent(
                            placeholder_id=slide.placeholder_id,
                            content=image_bytes,
                            filename=filename,
                            description=f"Article image {idx + 1}",
                        )
                    )
                except Exception as e:
                    self._logger.warning("Failed to download article image %s: %s", image_url, e)
                    continue
        
        return contents


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
        aws_access_key: Optional[str] = None,
        aws_secret_key: Optional[str] = None,
        aws_region: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._bucket = bucket
        self._prefix = prefix.rstrip("/") + "/" if prefix else ""
        self._cdn_base = cdn_base.rstrip("/") + "/"
        self._resize_variants = resize_variants or {"sm": "320x180", "md": "768x432", "lg": "1280x720"}
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

    def store(self, *, content: ImageContent, source: str) -> ImageAsset:
        """Upload image to S3 and return ImageAsset with CDN URLs."""
        object_key = f"{self._prefix}{uuid4()}/{content.filename}"
        s3_client = self._get_s3_client()

        if s3_client:
            try:
                # Determine content type from filename
                content_type = "image/png"
                if content.filename.lower().endswith((".jpg", ".jpeg")):
                    content_type = "image/jpeg"
                elif content.filename.lower().endswith(".webp"):
                    content_type = "image/webp"

                s3_client.put_object(
                    Bucket=self._bucket,
                    Key=object_key,
                    Body=content.content,
                    ContentType=content_type,
                )
                self._logger.info("Uploaded image to s3://%s/%s", self._bucket, object_key)
            except Exception as e:
                self._logger.error("Failed to upload image to S3: %s", e)
        else:
            self._logger.warning("S3 client unavailable, simulating upload for %s", object_key)

        # Generate CDN URLs for resized variants (resizing would be done by Lambda/CloudFront)
        from pydantic import HttpUrl
        resized_urls = [HttpUrl(self._cdn(object_key, suffix)) for suffix in self._resize_variants.keys()]
        return ImageAsset(
            source=source,
            original_object_key=object_key,
            resized_variants=resized_urls,
            description=content.description,
        )

    def _cdn(self, object_key: str, variant: str) -> str:
        """Generate CDN URL for a variant."""
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

