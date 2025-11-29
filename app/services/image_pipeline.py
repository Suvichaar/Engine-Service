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
    original_s3_key: Optional[str] = None  # Preserve original S3 key if image is already in S3


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
        result = payload.image_source == "ai"
        logger = logging.getLogger(__name__)
        logger.info(f"🔍 AIImageProvider.supports() - image_source: {payload.image_source}, result: {result}")
        return result

    def generate(self, deck: SlideDeck, payload: IntakePayload) -> Sequence[ImageContent]:
        contents: list[ImageContent] = []
        prompt_keywords = ", ".join(payload.prompt_keywords) or "story"
        
        # For News mode with custom cover, generate images based on slide_count
        # slide_count = cover (1) + middle slides + CTA (1)
        # So we need images for: cover (1) + middle slides + CTA (slide_count - 1 total slides after cover)
        logger = logging.getLogger(__name__)
        if payload.mode.value == "news" and payload.slide_count:
            logger.info("🎨 Generating AI images for News mode: slide_count=%d, deck_slides=%d", 
                       payload.slide_count, len(deck.slides))
            
            # Generate cover image (first slide)
            if deck.slides:
                cover_slide = deck.slides[0]
                if not cover_slide.image_url:
                    prompt = f"{cover_slide.text or 'News cover'} | keywords: {prompt_keywords}"
                    try:
                        contents.append(self._generate_image(cover_slide.placeholder_id, prompt))
                        logger.info("✅ Generated cover image (index 0)")
                    except Exception as exc:
                        logger.warning("❌ AI image generation failed for cover: %s", exc)
                else:
                    logger.info("⏭️ Skipping cover image (already has image_url)")
            else:
                logger.warning("⚠️ No slides in deck, cannot generate cover image")
            
            # Generate images for all remaining slides (middle + CTA)
            # Cover is index 0, so generate images for indices 1 to (slide_count - 1)
            # This includes both middle slides and the CTA slide
            max_idx = min(payload.slide_count, len(deck.slides))
            logger.info("🔄 Generating images for slides 1 to %d (indices 1 to %d)", max_idx, max_idx - 1)
            
            import time
            last_successful_image = None  # Fallback: use last successful image if one fails
            
            for idx in range(1, max_idx):
                slide = deck.slides[idx]
                if slide.image_url:
                    logger.debug("⏭️ Skipping slide %d (already has image_url)", idx)
                    continue
                
                # Create prompt - limit length to avoid API issues
                slide_text = (slide.text or 'Visual concept')[:200]  # Limit text length
                prompt = f"{slide_text} | keywords: {prompt_keywords}"
                
                # Add delay between requests to avoid rate limiting (except for first request)
                if idx > 1:
                    delay = 2.0  # 2 second delay between requests
                    logger.debug("⏳ Waiting %.1f seconds before next image generation...", delay)
                    time.sleep(delay)
                
                try:
                    image_content = self._generate_image(slide.placeholder_id, prompt)
                    contents.append(image_content)
                    last_successful_image = image_content
                    logger.info("✅ Generated image for slide %d (index %d)", idx + 1, idx)
                except Exception as exc:
                    logger.warning("❌ AI image generation failed for slide %d (index %d): %s", idx + 1, idx, exc)
                    # If we have a fallback image, use it (repeat last successful image)
                    if last_successful_image:
                        logger.info("🔄 Using last successful image as fallback for slide %d", idx + 1)
                        # Create a copy with different placeholder_id
                        from copy import deepcopy
                        fallback_content = deepcopy(last_successful_image)
                        fallback_content.placeholder_id = slide.placeholder_id
                        contents.append(fallback_content)
                    else:
                        logger.error("❌ No fallback available for slide %d, skipping", idx + 1)
            
            logger.info("📊 Total images generated: %d (expected: %d)", len(contents), payload.slide_count)
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

    def _generate_image(self, placeholder_id: str, prompt: str, retry_count: int = 3) -> ImageContent:
        import base64
        import logging
        import time
        logger = logging.getLogger(__name__)
        
        # Limit prompt length to avoid API issues (DALL-E has prompt length limits)
        max_prompt_length = 1000
        if len(prompt) > max_prompt_length:
            logger.warning("Prompt too long (%d chars), truncating to %d chars", len(prompt), max_prompt_length)
            prompt = prompt[:max_prompt_length]
        
        headers = {
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }
        body = {"prompt": prompt, "size": "1024x1024"}
        
        last_exception = None
        for attempt in range(retry_count):
            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(self._endpoint, headers=headers, json=body)
                    
                    if response.status_code == 400:
                        # Try to get error details
                        try:
                            error_data = response.json()
                            logger.warning("API returned 400 Bad Request. Error details: %s", error_data)
                        except:
                            logger.warning("API returned 400 Bad Request. Response text: %s", response.text[:200])
                    
                    response.raise_for_status()
                    data = response.json()
                    break  # Success, exit retry loop
            except httpx.HTTPStatusError as e:
                last_exception = e
                if e.response.status_code == 429:  # Rate limit
                    wait_time = (attempt + 1) * 5  # Exponential backoff: 5s, 10s, 15s
                    logger.warning("Rate limited (429), waiting %d seconds before retry %d/%d", wait_time, attempt + 1, retry_count)
                    time.sleep(wait_time)
                elif e.response.status_code == 400 and attempt < retry_count - 1:
                    # For 400 errors, try with a simpler prompt
                    logger.warning("400 Bad Request on attempt %d/%d, trying simpler prompt", attempt + 1, retry_count)
                    # Simplify prompt: remove keywords, use shorter text
                    simple_prompt = prompt.split("|")[0].strip()[:200]  # Take first part, limit length
                    body["prompt"] = simple_prompt
                    time.sleep(2)  # Wait before retry
                else:
                    # For other errors or last attempt, raise
                    if attempt == retry_count - 1:
                        raise
                    time.sleep(2)  # Wait before retry
            except Exception as e:
                last_exception = e
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning("Error on attempt %d/%d: %s. Retrying in %d seconds...", attempt + 1, retry_count, e, wait_time)
                    time.sleep(wait_time)
                else:
                    raise
        
        if last_exception:
            raise last_exception
        
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
            
            # Generate images for all remaining slides (middle + CTA)
            # Cover is index 0, so generate images for indices 1 to (slide_count - 1)
            # This includes both middle slides and the CTA slide
            for idx in range(1, min(payload.slide_count, len(deck.slides))):
                slide = deck.slides[idx]
                if slide.image_url:
                    continue
                try:
                    # Use different image_number for variety
                    contents.append(self._fetch_image(slide.placeholder_id, query[0], image_number=idx))
                except Exception as exc:
                    logging.getLogger(__name__).warning("Pexels fetch failed for slide %d: %s", idx, exc)
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
        
        # Graceful handling for all modes (News and Curious)
        import logging
        logger = logging.getLogger(__name__)
        
        # Validate attachment count for better handling
        num_slides = len(deck.slides)
        num_attachments = len(payload.attachments)
        
        if num_attachments != num_slides:
            logger.warning(
                f"Attachment count mismatch: {num_attachments} attachments "
                f"for {num_slides} slides. Using graceful handling."
            )
        
        # Process slides with graceful handling
        for idx, slide in enumerate(deck.slides):
            if slide.image_url:
                continue
            
            # Determine which attachment to use
            if idx < num_attachments:
                # Use corresponding attachment
                attachment = payload.attachments[idx]
            elif num_attachments > 0:
                # Use last attachment for remaining slides (repeat last image)
                attachment = payload.attachments[-1]
                logger.debug(f"Using last attachment for slide {idx} (repeating image)")
            else:
                # No attachments available, skip this slide
                logger.warning(f"No attachment available for slide {idx}")
                continue
            
            contents.append(self._to_content(slide.placeholder_id, attachment))
        
        return contents

    def _to_content(self, placeholder_id: str, attachment: str) -> ImageContent:
        """Convert attachment (URL, S3 URI, or file path) to ImageContent with actual bytes."""
        import logging
        from urllib.parse import urlparse
        logger = logging.getLogger(__name__)
        
        # Extract filename from attachment
        filename = attachment.split("/")[-1] or f"{placeholder_id}.upload"
        # Remove query parameters from filename if present
        if "?" in filename:
            filename = filename.split("?")[0]
        
        image_bytes = None
        original_s3_key = None  # Preserve original S3 key if attachment is S3 URI
        
        try:
            # Case 1: HTTP/HTTPS URL - download the image
            if attachment.startswith(("http://", "https://")):
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(attachment)
                    response.raise_for_status()
                    image_bytes = response.content
                    logger.info("Downloaded image from URL: %s (%d bytes)", attachment, len(image_bytes))
            
            # Case 2: S3 URI (s3://bucket/key) - extract key and optionally load from S3
            elif attachment.startswith("s3://"):
                # Extract S3 key from URI (preserve for CDN URL generation)
                parsed = urlparse(attachment)
                original_s3_key = parsed.path.lstrip("/")  # Remove leading slash
                logger.info("Detected S3 URI: %s, extracted key: %s", attachment, original_s3_key)
                
                # For S3 URIs, we don't need to download - the image is already in S3
                # We'll use the original key directly in storage service
                # But we still need some bytes for validation (minimal)
                # Actually, let's not download at all - just use empty bytes and let storage service handle it
                image_bytes = b""  # Empty bytes - storage service will skip upload if original_s3_key is provided
                logger.info("Skipping download for S3 URI (will use original key: %s)", original_s3_key)
            
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
        
        if image_bytes is None and original_s3_key is None:
            logger.warning("Could not load image bytes from attachment: %s", attachment)
            image_bytes = f"UPLOAD_FAILED:{attachment}".encode("utf-8")
        
        return ImageContent(
            placeholder_id=placeholder_id,
            content=image_bytes,
            filename=filename,
            description="User uploaded image",
            original_s3_key=original_s3_key,
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
        # If image is already in S3 (has original_s3_key), use that key instead of uploading
        if content.original_s3_key:
            object_key = content.original_s3_key
            self._logger.info("Using existing S3 key (skipping upload): s3://%s/%s", self._bucket, object_key)
        else:
            # Generate new object key and upload
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
        # Use base64 template format for CloudFront resize URLs (same as HTML renderer)
        from pydantic import HttpUrl
        import json
        resized_urls = []
        for suffix, dimensions in self._resize_variants.items():
            # Parse dimensions (e.g., "720x1280" -> width=720, height=1280)
            if "x" in dimensions:
                width, height = map(int, dimensions.split("x"))
            else:
                # Default dimensions if format is unexpected
                width, height = 720, 1280
            
            # Generate base64-encoded template URL (same format as HTML renderer)
            template = {
                "bucket": self._bucket,
                "key": object_key,
                "edits": {
                    "resize": {
                        "width": width,
                        "height": height,
                        "fit": "cover",
                    }
                },
            }
            encoded = base64.urlsafe_b64encode(json.dumps(template).encode()).decode()
            cdn_url = f"{self._cdn_base}{encoded}"
            self._logger.info("Generated CDN URL for variant %s: %s (S3 key: %s)", suffix, cdn_url[:100], object_key)
            resized_urls.append(HttpUrl(cdn_url))
        
        return ImageAsset(
            source=source,
            original_object_key=object_key,
            resized_variants=resized_urls,
            description=content.description,
        )

    def _cdn(self, object_key: str, variant: str) -> str:
        """Generate CDN URL for a variant (legacy method - now using base64 template in store())."""
        # This method is kept for backward compatibility but should not be used
        # The store() method now generates base64 template URLs directly
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

