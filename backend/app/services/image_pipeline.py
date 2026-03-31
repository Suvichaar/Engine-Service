"""Image asset pipeline with pluggable providers and storage service."""

from __future__ import annotations

import base64
import logging
import mimetypes
from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional, Protocol, Sequence
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from app.domain.dto import ImageAsset, IntakePayload, SlideDeck
from app.domain.interfaces import ImageAssetPipeline
from app.utils import is_placeholder_value
from app.services.image_prompts import (
    extract_positive_keywords,
    generate_content_related_safe_prompt,
    generate_news_slide_prompt,
    generate_safe_news_prompt,
    sanitize_prompt,
    sanitize_revised_prompt,
)


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
        logger = logging.getLogger(__name__)
        # Use both print and logging to ensure visibility
        print(f"\n{'='*60}")
        print(f"🖼️ IMAGE PIPELINE CALLED")
        print(f"Mode: {getattr(payload.mode, 'value', str(payload.mode))}")
        print(f"Image Source: {payload.image_source}")
        print(f"Slide Count: {payload.slide_count}")
        print(f"Article Images: {len(article_images) if article_images else 0}")
        print(f"{'='*60}\n")
        logger.warning(
            "🖼️ Image pipeline called: mode=%s image_source=%s slide_count=%s article_images=%s",
            getattr(payload.mode, "value", str(payload.mode)),
            payload.image_source,
            payload.slide_count,
            len(article_images) if article_images else 0,
        )
        # ALWAYS respect user's image_source selection (like before)
        # Article images are NOT used automatically - they're just metadata
        # User's explicit choice (ai, pexels, custom) takes priority
        provider = self._select_provider(payload)

        if provider is None:
            print(f"\n❌ NO IMAGE PROVIDER SELECTED for image_source={payload.image_source}\n")
            logger.warning("🖼️ No image provider selected for image_source=%s", payload.image_source)
            return []

        provider_name = getattr(provider, "source", type(provider).__name__)
        print(f"✅ Using image provider: {provider_name}")
        logger.warning("🖼️ Using image provider: %s", provider_name)
        try:
            contents = provider.generate(deck, payload)
        except Exception as exc:
            logger.warning(
                "🖼️ Provider %s failed during image generation: %s",
                provider_name,
                exc,
                exc_info=True,
            )
            contents = []

        if provider_name == "ai" and not contents:
            fallback_provider = self._find_provider_by_source("pexels")
            if fallback_provider is not None:
                logger.warning(
                    "🖼️ AI image generation produced no assets. Falling back to Pexels for this story."
                )
                fallback_payload = payload.model_copy(update={"image_source": "pexels"})
                try:
                    contents = fallback_provider.generate(deck, fallback_payload)
                    provider = fallback_provider
                    provider_name = getattr(provider, "source", type(provider).__name__)
                except Exception as exc:
                    logger.warning(
                        "🖼️ Pexels fallback also failed after AI generation failure: %s",
                        exc,
                        exc_info=True,
                    )
                    contents = []

        print(f"✅ Provider {provider_name} generated {len(contents)} image contents\n")
        logger.warning("🖼️ Provider %s generated %d image contents", provider_name, len(contents))
        assets: List[ImageAsset] = []
        for content in contents:
            try:
                # Avoid letting a single failed store wipe all images
                assets.append(self._storage.store(content=content, source=provider.source))
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "🖼️ Failed to store image for placeholder_id=%s source=%s: %s",
                    getattr(content, "placeholder_id", "unknown"),
                    getattr(provider, "source", "unknown"),
                    exc,
                    exc_info=True,
                )
        return assets

    def _select_provider(self, payload: IntakePayload) -> Optional[ImageProvider]:
        logger = logging.getLogger(__name__)
        logger.warning(
            "🖼️ Selecting image provider for image_source=%s mode=%s",
            payload.image_source,
            getattr(payload.mode, "value", str(payload.mode)),
        )
        for provider in self._providers:
            try:
                supports = provider.supports(payload)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "🖼️ Provider %s.supports() raised %s: %s",
                    getattr(provider, "source", type(provider).__name__),
                    type(exc).__name__,
                    exc,
                )
                continue
            logger.warning(
                "🖼️ Provider %s.supports(image_source=%s) -> %s",
                getattr(provider, "source", type(provider).__name__),
                payload.image_source,
                supports,
            )
            if supports:
                return provider
        return None

    def _find_provider_by_source(self, source: str) -> Optional[ImageProvider]:
        for provider in self._providers:
            if getattr(provider, "source", None) == source:
                return provider
        return None


# --- Provider Implementations -------------------------------------------------


class AIImageProvider:
    """Generate images using an AI image model."""

    source = "ai"
    
    # Class-level rate limiter: track last request time
    _last_request_time = None
    _min_cooldown_seconds = 5.0  # Minimum 5 seconds between requests

    def __init__(self, endpoint: str, api_key: str, cooldown_seconds: float = 5.0, language_model=None) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._min_cooldown_seconds = cooldown_seconds  # Configurable cooldown
        self._language_model = language_model  # For automatic alt_text generation

    def _uses_foundry_provider_api(self) -> bool:
        return "/providers/blackforestlabs/" in self._endpoint or ".services.ai.azure.com/" in self._endpoint

    def _build_headers(self) -> dict[str, str]:
        if self._uses_foundry_provider_api():
            return {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }

        return {
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }

    def _build_request_body(self, prompt: str, reference_image_bytes: Optional[bytes]) -> dict[str, object]:
        if self._uses_foundry_provider_api():
            body: dict[str, object] = {
                "prompt": prompt,
                "width": 1024,
                "height": 1024,
                "n": 1,
                "model": "FLUX.2-pro",
            }
            if reference_image_bytes:
                body["input_image"] = base64.b64encode(reference_image_bytes).decode("utf-8")
            return body

        return {"prompt": prompt, "size": "1024x1024"}

    def _get_reference_image_refs(self, payload: IntakePayload) -> list[str]:
        metadata = payload.metadata or {}
        references = metadata.get("image_references")
        if isinstance(references, list):
            return [str(item) for item in references if item]
        return []

    def _pick_reference_image_ref(self, payload: IntakePayload, slide_index: int) -> Optional[str]:
        references = self._get_reference_image_refs(payload)
        if not references:
            return None
        if slide_index < len(references):
            return references[slide_index]
        return references[-1]

    def _load_reference_image_bytes(self, reference: str) -> Optional[bytes]:
        logger = logging.getLogger(__name__)

        if reference.startswith("data:"):
            header, _, data = reference.partition(",")
            if ";base64" not in header.lower():
                logger.warning("Skipping unsupported data URL reference image format")
                return None
            mime_type = header[5:].split(";")[0].lower()
            if not mime_type.startswith("image/"):
                logger.info("Skipping non-image data URL reference: %s", mime_type or "unknown")
                return None
            return base64.b64decode(data)

        if reference.startswith(("http://", "https://")):
            mime_type, _ = mimetypes.guess_type(reference)
            if mime_type and not mime_type.startswith("image/"):
                logger.info("Skipping non-image reference URL: %s", reference)
                return None
            with httpx.Client(timeout=60.0) as client:
                response = client.get(reference)
                response.raise_for_status()
                return response.content

        if reference.startswith("s3://"):
            try:
                import boto3
                from app.core import get_settings

                settings = get_settings()
                parsed = urlparse(reference)
                bucket = parsed.netloc
                key = parsed.path.lstrip("/")
                s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=settings.aws.access_key,
                    aws_secret_access_key=settings.aws.secret_key,
                    region_name=settings.aws.region,
                )
                response = s3_client.get_object(Bucket=bucket, Key=key)
                return response["Body"].read()
            except Exception as exc:
                logger.warning("Failed to load S3 reference image %s: %s", reference, exc)
                return None

        mime_type, _ = mimetypes.guess_type(reference)
        if mime_type and not mime_type.startswith("image/"):
            logger.info("Skipping non-image local reference: %s", reference)
            return None

        try:
            from pathlib import Path

            path = Path(reference)
            if path.exists():
                return path.read_bytes()
        except Exception as exc:
            logger.warning("Failed to load local reference image %s: %s", reference, exc)

        return None

    def supports(self, payload: IntakePayload) -> bool:
        result = payload.image_source == "ai"
        logger = logging.getLogger(__name__)
        logger.info(f"🔍 AIImageProvider.supports() - image_source: {payload.image_source}, result: {result}")
        return result

    def _wait_for_cooldown(self):
        """Wait if needed to respect rate limits."""
        import time
        logger = logging.getLogger(__name__)
        
        if AIImageProvider._last_request_time is not None:
            elapsed = time.time() - AIImageProvider._last_request_time
            if elapsed < self._min_cooldown_seconds:
                wait_time = self._min_cooldown_seconds - elapsed
                logger.info(f"⏳ Rate limiting: waiting {wait_time:.1f} seconds before next request...")
                time.sleep(wait_time)
        
        AIImageProvider._last_request_time = time.time()

    # Prompt generation methods now delegate to image_prompts module
    def _sanitize_prompt(self, text: str) -> str:
        """Sanitize prompt by extracting only positive keywords and concepts."""
        logger = logging.getLogger(__name__)
        result = sanitize_prompt(text, fallback_fn=lambda: generate_safe_news_prompt())
        if extract_positive_keywords(text):
            logger.info(f"Extracted positive keywords: {extract_positive_keywords(text)}")
        return result
    
    def _generate_safe_news_prompt(self, topic: str = None, slide_index: int = None) -> str:
        """Generate a very simple, safe, positive news-related image prompt."""
        return generate_safe_news_prompt(topic, slide_index)

    def _generate_content_related_safe_prompt(self, topic: str = None, original_prompt: str = None, simpler: bool = False) -> str:
        """Generate a safe, positive prompt that's still related to the original content."""
        return generate_content_related_safe_prompt(topic, original_prompt, simpler)

    def _generate_alt_texts_for_slides(self, slides, payload) -> dict[int, str]:
        """Generate alt_texts automatically from slide content using LLM if available.
        
        Args:
            slides: List of slides to generate alt_texts for
            payload: IntakePayload with mode and category info
            
        Returns:
            Dictionary mapping slide index to alt_text
        """
        alt_texts = {}
        logger = logging.getLogger(__name__)
        
        if not self._language_model:
            logger.debug("Language model not available, skipping automatic alt_text generation")
            return alt_texts
        
        logger.info(f"🔄 Generating alt_texts automatically for {len(slides)} slides using LLM...")
        
        for idx, slide in enumerate(slides):
            try:
                # Generate alt_text from slide content
                # CRITICAL: Image prompts must ALWAYS be in English, regardless of story language
                system_prompt = """You are an expert at creating visual image prompts for AI image generation. 
Generate concise, descriptive alt text (image prompts) that are:
- Visual and descriptive (1-2 sentences)
- Suitable for AI image generation (DALL-E 3)
- Focus on visual elements, colors, style, composition
- Safe, positive, and family-friendly
- No text, logos, or watermarks mentioned
- Professional and modern aesthetic
- ALWAYS in English (regardless of the story content language)

IMPORTANT: The image prompt must be in English only, even if the slide content is in another language."""
                
                mode_context = "news story"
                category_context = f"Category: {payload.category}" if payload.category else ""
                
                user_prompt = f"""Generate a descriptive image prompt (alt text) in ENGLISH ONLY for this slide content.

Slide Content: {slide.text or 'Visual concept'}
Mode: {mode_context}
{category_context}

Requirements:
- Descriptive and visual (1-2 sentences max)
- Suitable for AI image generation
- Focus on visual elements, colors, style
- Safe, positive, family-friendly
- Professional and modern

Alt Text:"""
                
                alt_text = self._language_model.complete(system_prompt, user_prompt)
                # Clean up the response
                alt_text = alt_text.strip().strip('"').strip("'").strip()
                
                if alt_text:
                    alt_texts[idx] = alt_text
                    logger.info(f"✅ Generated alt_text for slide {idx}: {alt_text[:80]}...")
                else:
                    # Fallback: Convert non-English slide text to English description
                    fallback_text = slide.text or "Visual concept"
                    alt_texts[idx] = self._convert_to_english_fallback(fallback_text, payload)
                    logger.warning(f"⚠️ Empty alt_text generated for slide {idx}, using converted fallback")
                    
            except Exception as e:
                logger.warning(f"⚠️ Failed to generate alt_text for slide {idx}: {e}, using converted fallback")
                # Fallback: Convert non-English slide text to English description
                fallback_text = slide.text or "Visual concept"
                alt_texts[idx] = self._convert_to_english_fallback(fallback_text, payload)
        
        logger.info(f"✅ Generated {len(alt_texts)} alt_texts automatically")
        return alt_texts
    
    def _convert_to_english_fallback(self, text: str, payload) -> str:
        """Convert non-English text to English description for image prompt fallback."""
        if not text or text == "Visual concept":
            return "Visual concept"
        
        # Check if we need to convert (get language from payload metadata if available)
        lang_code = "en"
        if payload.metadata and "language" in payload.metadata:
            lang_code = payload.metadata["language"].split("-")[0] if "-" in payload.metadata["language"] else payload.metadata["language"]
        elif hasattr(payload, "language") and payload.language:
            lang_code = payload.language.split("-")[0] if "-" in payload.language else payload.language
        
        # If English or no language model, return as is
        if lang_code == "en" or not self._language_model:
            return text
        
        # Convert non-English content to English description
        try:
            convert_prompt = f"""Convert this content to a brief English description for an image prompt (max 30 words).
Content: {text[:200]}
Original Language: {lang_code}

Return only the English description that captures the visual essence, no quotes or labels."""
            
            english_desc = self._language_model.complete(
                "You are a translator. Convert content to English descriptions for image generation.",
                convert_prompt
            ).strip().strip('"').strip("'")
            
            if english_desc and len(english_desc) > 10:
                return english_desc
            else:
                return "Visual concept"
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to convert fallback text to English: {e}")
            return "Visual concept"

    def generate(self, deck: SlideDeck, payload: IntakePayload) -> Sequence[ImageContent]:
        contents: list[ImageContent] = []
        logger = logging.getLogger(__name__)
        max_idx = min(payload.slide_count or len(deck.slides), len(deck.slides))
        logger.info("🎨 Generating AI images for news mode: requested=%d deck_slides=%d", max_idx, len(deck.slides))

        import time
        last_successful_image = None
        article_content = payload.metadata.get("article_content") if payload.metadata else None

        for idx in range(max_idx):
            slide = deck.slides[idx]
            if slide.image_url:
                logger.debug("⏭️ Skipping slide %d (already has image_url)", idx)
                continue

            if idx > 0:
                delay = 3.0 if idx == 1 else 6.0
                logger.info("⏳ Waiting %.1f seconds before generating image for slide %d...", delay, idx)
                time.sleep(delay)

            slide_text = (slide.text or "Visual concept")[:200]
            prompt = generate_news_slide_prompt(
                slide_text,
                idx,
                is_cover=(idx == 0),
                is_cta=(idx == max_idx - 1),
                article_content=article_content,
            )

            try:
                reference_image = self._load_reference_image_bytes(
                    self._pick_reference_image_ref(payload, idx)
                ) if self._pick_reference_image_ref(payload, idx) else None
                image_content = self._generate_image(slide.placeholder_id, prompt, reference_image_bytes=reference_image)
                contents.append(image_content)
                last_successful_image = image_content
                logger.info("✅ Generated image for slide %d (index %d)", idx + 1, idx)
            except Exception as exc:
                logger.warning("❌ AI image generation failed for slide %d (index %d): %s", idx + 1, idx, exc)
                try:
                    fallback_prompt = (
                        generate_news_slide_prompt(
                            slide_text,
                            idx,
                            is_cover=(idx == 0),
                            is_cta=(idx == max_idx - 1),
                            article_content=article_content[:400] if article_content else None,
                        )
                        if article_content
                        else self._generate_safe_news_prompt(slide_text, slide_index=idx)
                    )
                    reference_image = self._load_reference_image_bytes(
                        self._pick_reference_image_ref(payload, idx)
                    ) if self._pick_reference_image_ref(payload, idx) else None
                    fallback_content = self._generate_image(
                        slide.placeholder_id,
                        fallback_prompt,
                        reference_image_bytes=reference_image,
                    )
                    contents.append(fallback_content)
                    last_successful_image = fallback_content
                    logger.info("✅ Generated fallback image for slide %d", idx + 1)
                except Exception as fallback_exc:
                    logger.warning("❌ Fallback generation failed for slide %d: %s", idx + 1, fallback_exc)
                    if last_successful_image:
                        from copy import deepcopy

                        fallback_content = deepcopy(last_successful_image)
                        fallback_content.placeholder_id = slide.placeholder_id
                        contents.append(fallback_content)
                    else:
                        logger.error("❌ All fallback options exhausted for slide %d; skipping image", idx + 1)

        logger.info("📊 Total AI images generated: %d", len(contents))
        return contents

    def _generate_image(
        self,
        placeholder_id: str,
        prompt: str,
        retry_count: int = 3,
        reference_image_bytes: Optional[bytes] = None,
    ) -> ImageContent:
        import base64
        import logging
        import time
        logger = logging.getLogger(__name__)
        
        # Wait for cooldown before making request
        self._wait_for_cooldown()
        
        # Limit prompt length to avoid API issues (DALL-E has prompt length limits)
        max_prompt_length = 1000
        if len(prompt) > max_prompt_length:
            logger.warning("Prompt too long (%d chars), truncating to %d chars", len(prompt), max_prompt_length)
            prompt = prompt[:max_prompt_length]
        
        headers = self._build_headers()
        body = self._build_request_body(prompt, reference_image_bytes)
        
        last_exception = None
        for attempt in range(retry_count):
            try:
                with httpx.Client(timeout=120.0) as client:
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
                    # Longer exponential backoff for 429 errors: 10s, 20s, 30s
                    wait_time = (attempt + 1) * 10  # Increased from 5s to 10s
                    logger.warning("⚠️ Rate limited (429), waiting %d seconds before retry %d/%d", wait_time, attempt + 1, retry_count)
                    time.sleep(wait_time)
                    # Update last request time after waiting
                    AIImageProvider._last_request_time = time.time() + wait_time
                elif e.response.status_code == 400 and attempt < retry_count - 1:
                    # Check if it's content policy violation
                    error_code = None
                    revised_prompt = None
                    try:
                        error_data = e.response.json()
                        error_code = error_data.get("error", {}).get("code", "")
                        # Try to extract revised_prompt from error response (Azure provides this)
                        inner_error = error_data.get("error", {}).get("inner_error", {})
                        revised_prompt = inner_error.get("revised_prompt")
                    except:
                        pass
                    
                    if error_code == "content_policy_violation":
                        # Progressive fallback: use revised_prompt first, then content-related safe prompts
                        if attempt == 0:
                            if revised_prompt:
                                # Use Azure's revised prompt (sanitize and shorten it first)
                                logger.warning(
                                    "Content policy violation detected (attempt %d/%d), using sanitized Azure revised prompt",
                                    attempt + 1,
                                    retry_count,
                                )
                                body["prompt"] = sanitize_revised_prompt(revised_prompt)
                            else:
                                # Generate safe prompt related to original content
                                logger.warning("Content policy violation detected (attempt %d/%d), generating content-related safe prompt", attempt + 1, retry_count)
                                # Extract topic from original prompt for context
                                original_topic = prompt.split(",")[0].strip()[:50] if prompt else None
                                safe_prompt = self._generate_content_related_safe_prompt(original_topic, prompt)
                                body = self._build_request_body(safe_prompt, reference_image_bytes)
                        elif attempt == 1:
                            # Second retry: use simpler content-related prompt
                            logger.warning("Content policy violation still occurring (attempt %d/%d), using simpler content-related prompt", attempt + 1, retry_count)
                            original_topic = prompt.split(",")[0].strip()[:30] if prompt else None
                            safe_prompt = self._generate_content_related_safe_prompt(original_topic, prompt, simpler=True)
                            body = self._build_request_body(safe_prompt, reference_image_bytes)
                        else:
                            # Last retry: use minimal but still content-aware prompt
                            logger.warning("Content policy violation persists (attempt %d/%d), using minimal content-aware prompt", attempt + 1, retry_count)
                            original_topic = prompt.split(",")[0].strip()[:20] if prompt else None
                            if original_topic:
                                body = self._build_request_body(
                                    f"professional illustration about {original_topic}, clean, modern, positive",
                                    reference_image_bytes,
                                )
                            else:
                                body = self._build_request_body(
                                    "professional news illustration, clean, modern, positive",
                                    reference_image_bytes,
                                )
                    else:
                        # For other 400 errors, try with a simpler prompt
                        logger.warning("400 Bad Request on attempt %d/%d, trying simpler prompt", attempt + 1, retry_count)
                        simple_prompt = prompt.split("|")[0].strip()[:100]  # Take first part, limit length more aggressively
                        body = self._build_request_body(simple_prompt, reference_image_bytes)
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
    _pexel_tags: List[str] = []  # Class variable to store Pexels tags
    _tags_loaded: bool = False  # Flag to track if tags are loaded

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        # Load Pexels tags on first initialization
        if not PexelsImageProvider._tags_loaded:
            self._load_pexel_tags()

    def supports(self, payload: IntakePayload) -> bool:
        return payload.image_source == "pexels"

    def _translate_to_english(self, text: str) -> Optional[str]:
        """Translate non-English text to English using Azure OpenAI.
        
        Works for ANY language (Hindi, Marathi, Tamil, Telugu, Bengali, Gujarati, 
        Kannada, Malayalam, Punjabi, Urdu, Odia, Japanese, Chinese, Arabic, etc.)
        
        Args:
            text: Text in any language
            
        Returns:
            Translated English text, or None if translation fails
        """
        logger = logging.getLogger(__name__)
        
        try:
            from app.core import get_settings
            settings = get_settings()
            
            # Check if Azure OpenAI is configured
            if not settings.azure_api or not settings.azure_api.api_key:
                logger.debug("Azure OpenAI not configured, skipping translation")
                return None
            
            # Limit text length for API call (first 200 chars for faster processing)
            text_snippet = text[:200] if len(text) > 200 else text
            
            # Translation prompt - works for ANY language
            prompt = f"""Translate this text to English. The text may be in any language (Hindi, Marathi, Tamil, Telugu, Bengali, Gujarati, Kannada, Malayalam, Punjabi, Urdu, Odia, Japanese, Chinese, Arabic, French, Spanish, or any other language).
Return only the English translation, no explanations:

{text_snippet}"""

            url = f"{settings.azure_api.endpoint.rstrip('/')}/openai/deployments/{settings.azure_api.deployment}/chat/completions"
            params = {"api-version": settings.azure_api.api_version}
            headers = {
                "api-key": settings.azure_api.api_key,
                "Content-Type": "application/json",
            }
            payload = {
                "messages": [
                    {"role": "system", "content": "You are a translator. Translate text from any language to English. Return only the translated text."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 200,
            }
            
            import httpx
            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, params=params, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                
                choices = data.get("choices", [])
                if choices:
                    translated = choices[0]["message"].get("content", "").strip()
                    # Clean up: take first line only, remove quotes
                    translated = translated.split('\n')[0].strip().strip('"').strip("'")
                    if translated and len(translated) > 5:
                        logger.info(f"✅ Translation successful: {text[:50]}... → {translated[:50]}...")
                        return translated
            
            logger.warning("Translation returned empty result")
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Translation failed: {e}", exc_info=False)
            return None

    def _load_pexel_tags(self) -> None:
        """Load Pexels tags from the backend data directory."""
        import os
        logger = logging.getLogger(__name__)
        
        try:
            # Try multiple locations for pexel_tags.txt
            possible_paths = []
            
            # 1. Backend data directory (3 levels up from app/services/image_pipeline.py)
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
            possible_paths.append(os.path.join(project_root, "data", "pexel_tags.txt"))

            # 2. Current working directory
            possible_paths.append(os.path.join(os.getcwd(), "data", "pexel_tags.txt"))
            possible_paths.append(os.path.join(os.getcwd(), "pexel_tags.txt"))

            # 3. Same directory as this file
            possible_paths.append(os.path.join(os.path.dirname(current_file), "pexel_tags.txt"))
            
            tags_file = None
            for path in possible_paths:
                if os.path.exists(path):
                    tags_file = path
                    break
            
            if tags_file:
                with open(tags_file, 'r', encoding='utf-8') as f:
                    PexelsImageProvider._pexel_tags = [line.strip().lower() for line in f if line.strip()]
                PexelsImageProvider._tags_loaded = True
                logger.info(f"✅ Loaded {len(PexelsImageProvider._pexel_tags)} Pexels tags from {tags_file}")
            else:
                logger.warning(f"⚠️ pexel_tags.txt not found in any of these locations: {possible_paths}, will use direct keyword matching")
                PexelsImageProvider._pexel_tags = []
                PexelsImageProvider._tags_loaded = True  # Mark as loaded to avoid repeated attempts
        except Exception as e:
            logger.error(f"❌ Failed to load pexel_tags.txt: {e}", exc_info=True)
            PexelsImageProvider._pexel_tags = []
            PexelsImageProvider._tags_loaded = True  # Mark as loaded to avoid repeated attempts

    def _match_keywords_with_pexel_tags(self, keywords: List[str], max_matches: int = 10) -> List[str]:
        """Match extracted keywords with Pexels tags using relevance scoring.
        
        CRITICAL: Filters out generic keywords and tags to avoid generic images.
        
        Args:
            keywords: List of keywords extracted from slide text
            max_matches: Maximum number of matched tags to return
            
        Returns:
            List of matched Pexels tags sorted by relevance score (generic tags excluded)
        """
        logger = logging.getLogger(__name__)
        
        if not PexelsImageProvider._pexel_tags:
            logger.debug("No Pexels tags loaded, returning filtered keywords")
            # Filter generic keywords even if tags not loaded
            generic_keywords_to_exclude = {
                "news", "article", "story", "media", "report", "update", "world", 
                "today", "latest", "information", "newspaper", "magazine", "journalism"
            }
            filtered = [kw for kw in keywords if kw.lower() not in generic_keywords_to_exclude]
            return filtered[:max_matches] if filtered else keywords[:max_matches]
        
        # CRITICAL FIX: Filter out generic keywords that lead to generic images
        generic_keywords_to_exclude = {
            "news", "article", "story", "media", "report", "update", "world", 
            "today", "latest", "information", "newspaper", "magazine", "journalism"
        }
        
        # Filter: Keep only specific, meaningful keywords (at least 4 chars)
        specific_keywords = [
            kw for kw in keywords 
            if kw.lower() not in generic_keywords_to_exclude and len(kw) >= 4
        ]
        
        if not specific_keywords:
            logger.warning(f"⚠️ All keywords are generic: {keywords[:5]}..., skipping tag matching to avoid generic images")
            return []  # Return empty to force fallback
        
        logger.info(f"🔍 Filtered {len(keywords)} → {len(specific_keywords)} specific keywords: {specific_keywords[:5]}...")
        
        scored_matches = []
        
        # Only match specific keywords
        for keyword in specific_keywords:
            keyword_lower = keyword.lower()
            
            for tag in PexelsImageProvider._pexel_tags:
                tag_lower = tag.lower()
                
                # CRITICAL: Also exclude generic tags from results
                if tag_lower in generic_keywords_to_exclude:
                    continue  # Skip generic tags
                
                score = 0
                
                # Exact match: highest score
                if keyword_lower == tag_lower:
                    score = 100
                # Keyword is substring of tag (e.g., "cricket" in "cricket field")
                elif keyword_lower in tag_lower:
                    score = 80 - (len(tag_lower) - len(keyword_lower)) * 2  # Penalize longer tags
                # Tag is substring of keyword (e.g., "sport" in "sports")
                elif tag_lower in keyword_lower:
                    score = 70 - (len(keyword_lower) - len(tag_lower)) * 2
                # Word overlap: check if words match
                elif any(word == tag_lower for word in keyword_lower.split()) or \
                     any(word == keyword_lower for word in tag_lower.split()):
                    score = 60
                # Partial match: check if significant portion matches
                elif len(keyword_lower) >= 4 and keyword_lower[:4] in tag_lower:
                    score = 40
                elif len(tag_lower) >= 4 and tag_lower[:4] in keyword_lower:
                    score = 40
                else:
                    continue  # Skip if no match
                
                # Avoid duplicates
                if tag not in [m[1] for m in scored_matches]:
                    scored_matches.append((score, tag))
        
        # Sort by score (descending) and return top matches
        scored_matches.sort(key=lambda x: x[0], reverse=True)
        matched_tags = [tag for score, tag in scored_matches[:max_matches]]
        
        # If we have matched tags, use them; otherwise use filtered specific keywords
        if matched_tags:
            logger.info(f"🎯 Matched {len(matched_tags)} specific Pexels tags: {matched_tags[:5]}...")
            return matched_tags
        else:
            logger.warning(f"⚠️ No specific tag matches found, using filtered keywords")
            return specific_keywords[:max_matches] if specific_keywords else []

    def _extract_keywords_from_text(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extract multiple keywords from slide text for Pexels search.
        
        CRITICAL FIX: Translates non-English text to English first, then extracts keywords.
        Works for ANY language (Hindi, Marathi, Tamil, Telugu, Bengali, Gujarati, etc.)
        
        Args:
            text: Slide text content (can be in any language)
            max_keywords: Maximum number of keywords to extract (default: 10)
            
        Returns:
            List of specific keywords (generic keywords filtered out) for Pexels search
        """
        logger = logging.getLogger(__name__)
        
        # Default fallback keywords (only used if translation fails completely)
        generic_fallbacks = ["news", "article", "story", "media", "report", "update", "world", "today", "latest", "information"]
        
        if not text:
            logger.info("📝 No text provided")
            return []  # Return empty, let matching logic handle fallback
        
        import re
        
        # Check if text is primarily non-English (any language: Hindi, Tamil, Japanese, Arabic, etc.)
        # Count ASCII letters vs total word characters
        ascii_letters = len(re.findall(r'[a-zA-Z]', text))
        total_word_chars = len(re.findall(r'\w', text))  # All word characters (letters, digits, underscore)
        
        # CRITICAL FIX: Translate non-English text to English first
        is_non_english = total_word_chars > 0 and (ascii_letters / total_word_chars) < 0.5
        
        if is_non_english:
            ascii_ratio = (ascii_letters / total_word_chars) * 100
            logger.info("🌐 Non-English text detected (%.1f%% ASCII), translating to English for keyword extraction...", ascii_ratio)
            
            # Translate to English
            translated_text = self._translate_to_english(text)
            
            if translated_text and len(translated_text) > 10:
                logger.info(f"✅ Translation successful: {text[:50]}... → {translated_text[:100]}...")
                text = translated_text  # Use translated text for keyword extraction
            else:
                logger.warning("⚠️ Translation failed or returned empty, will try to extract from original text")
                # Continue with original text - might have some English words
        
        # For English text: Extract meaningful keywords
        # Comprehensive stop words list (expanded)
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by",
            "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
            "will", "would", "should", "could", "may", "might", "must", "can", "this", "that", "these", "those",
            "it", "its", "they", "them", "their", "we", "our", "you", "your", "he", "she", "his", "her",
            "from", "as", "if", "when", "where", "why", "how", "what", "which", "who", "whom", "whose",
            "not", "no", "yes", "also", "just", "only", "more", "less", "very", "much", "many", "few",
            "some", "any", "all", "both", "each", "every", "most", "other", "such", "than", "too",
            "about", "after", "before", "between", "during", "through", "into", "over", "under",
            "said", "says", "according", "based", "made", "make", "get", "got", "take", "took",
            "come", "came", "give", "gave", "know", "knew", "think", "thought", "see", "saw",
            "want", "need", "use", "used", "find", "found", "tell", "told", "ask", "asked",
            "seem", "seems", "seemed", "become", "became", "begin", "began", "keep", "kept",
            "let", "put", "run", "say", "try", "tried", "turn", "turned", "show", "showed",
            "like", "new", "first", "last", "long", "great", "little", "own", "same", "right",
            "big", "high", "different", "small", "large", "next", "early", "young", "important"
        }
        
        # Extract all words (at least 3 chars)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Filter out stop words and get unique words
        unique_keywords = []
        seen = set()
        for w in words:
            if w not in stop_words and w not in seen and len(w) >= 3:
                unique_keywords.append(w)
                seen.add(w)
        
        # Sort by word length (longer = more specific = better for search)
        unique_keywords.sort(key=len, reverse=True)
        
        # Get top keywords (don't add generic fallbacks - let matching logic handle it)
        keywords = unique_keywords[:max_keywords]
        
        logger.info(f"📝 Extracted {len(keywords)} keywords: {keywords[:5]}...")
        
        # Match extracted keywords with Pexels tags for better relevance
        # This will filter out generic keywords and return specific tags
        matched_tags = self._match_keywords_with_pexel_tags(keywords, max_matches=max_keywords)
        
        # If we got matched tags, use them; otherwise use filtered keywords
        if matched_tags:
            logger.info(f"✅ Using {len(matched_tags)} matched Pexels tags: {matched_tags[:5]}...")
            return matched_tags
        else:
            # Return filtered keywords (generic ones already filtered in _match_keywords_with_pexel_tags)
            logger.debug("No Pexels tag matches, using filtered keywords")
            # Filter generic keywords here too as fallback
            generic_keywords_to_exclude = {
                "news", "article", "story", "media", "report", "update", "world", 
                "today", "latest", "information", "newspaper", "magazine", "journalism"
            }
            filtered = [kw for kw in keywords if kw.lower() not in generic_keywords_to_exclude and len(kw) >= 4]
            return filtered[:max_keywords] if filtered else []

    def _fetch_image_with_retry(self, placeholder_id: str, keywords: List[str], image_number: int = 0) -> Optional[ImageContent]:
        """Fetch image from Pexels, trying multiple keywords until successful.
        
        FIX: Uses different image_number for each keyword attempt to ensure variety.
        This prevents same images when multiple slides use same keywords.
        
        Args:
            placeholder_id: Unique identifier for the slide
            keywords: List of keywords to try (will try each until one works)
            image_number: Base index of image to fetch from search results
            
        Returns:
            ImageContent if successful, None if all keywords failed
        """
        logger = logging.getLogger(__name__)
        
        for idx, keyword in enumerate(keywords):
            try:
                # CRITICAL FIX: Use image_number + keyword_index to ensure different images
                # This ensures even if same keyword is used, different slides get different images
                # Multiply by 3 to create gaps between keyword attempts
                unique_image_number = image_number + (idx * 3)
                
                logger.info(f"🔍 Pexels: Trying keyword {idx+1}/{len(keywords)}: '{keyword}' (image_number={unique_image_number})")
                result = self._fetch_image(placeholder_id, keyword, unique_image_number)
                logger.info(f"✅ Pexels: Success with keyword '{keyword}' (got image #{unique_image_number})")
                return result
            except Exception as exc:
                logger.warning(f"⚠️ Pexels: Keyword '{keyword}' failed: {exc}")
                continue
        
        logger.error(f"❌ Pexels: All {len(keywords)} keywords failed for {placeholder_id}")
        return None

    def generate(self, deck: SlideDeck, payload: IntakePayload) -> Sequence[ImageContent]:
        contents: list[ImageContent] = []
        logger = logging.getLogger(__name__)
        
        # Priority: User-provided prompt_keywords > Automatic extraction
        user_provided_keywords = payload.prompt_keywords and len(payload.prompt_keywords) > 0
        if user_provided_keywords:
            logger.info(f"📝 User provided prompt_keywords: {payload.prompt_keywords}, will use them for Pexels search")
        else:
            logger.info("🔄 No user keywords provided, will extract keywords automatically from slide content")
        
        if payload.slide_count:
            logger.info("Generating Pexels images for %s mode: slide_count=%d, deck_slides=%d", 
                       payload.mode.value, payload.slide_count, len(deck.slides))
            
            # Generate cover image (first slide)
            if deck.slides:
                cover_slide = deck.slides[0]
                if not cover_slide.image_url:
                    # Priority: User keywords > Automatic extraction (with 10+ keywords)
                    if user_provided_keywords:
                        keywords = list(payload.prompt_keywords)  # Use user keywords as list
                        logger.info(f"📝 Pexels cover: Using user-provided keywords: {keywords[:5]}")
                    else:
                        # Extract 10+ keywords from cover slide content automatically
                        keywords = self._extract_keywords_from_text(cover_slide.text, max_keywords=10)
                        logger.info(f"📸 Pexels cover: Extracted {len(keywords)} keywords from slide text")
                    
                    # Try all keywords until one works
                    result = self._fetch_image_with_retry(cover_slide.placeholder_id, keywords, image_number=0)
                    if result:
                        contents.append(result)
                        logger.info("✅ Generated Pexels cover image (index 0)")
                    else:
                        logger.warning("⚠️ Pexels: All keywords failed for cover slide")
            
            # Generate images for all remaining slides (middle + CTA)
            # Cover is index 0, so generate images for indices 1 to (slide_count - 1)
            # This includes both middle slides and the CTA slide
            for idx in range(1, min(payload.slide_count, len(deck.slides))):
                slide = deck.slides[idx]
                if slide.image_url:
                    continue
                
                # Priority: User keywords > Automatic extraction (with 10+ keywords)
                if user_provided_keywords:
                    # Use user keywords, cycle through them for variety
                    keywords = list(payload.prompt_keywords)
                    # Rotate keywords for variety: start from different position for each slide
                    rotated_keywords = keywords[(idx-1) % len(keywords):] + keywords[:(idx-1) % len(keywords)]
                    logger.info(f"📝 Pexels slide {idx}: Using user-provided keywords (rotated): {rotated_keywords[:3]}")
                else:
                    # Extract 10+ keywords from slide content automatically
                    keywords = self._extract_keywords_from_text(slide.text, max_keywords=10)
                    rotated_keywords = keywords
                    logger.info(f"📸 Pexels slide {idx}: Extracted {len(keywords)} keywords from slide text")
                
                # Try all keywords until one works, use different image_number for variety
                result = self._fetch_image_with_retry(slide.placeholder_id, rotated_keywords, image_number=idx)
                if result:
                    contents.append(result)
                    logger.info("✅ Generated Pexels image for slide %d (index %d)", idx + 1, idx)
                else:
                    # Fallback: use last successful image if available
                    if contents:
                        from copy import deepcopy
                        fallback_image = deepcopy(contents[-1])
                        fallback_image.placeholder_id = slide.placeholder_id
                        contents.append(fallback_image)
                        logger.info("🔄 Using fallback (last successful) image for slide %d", idx + 1)
                    else:
                        logger.warning("⚠️ Pexels: No images available for slide %d", idx + 1)
            
        else:
            # Fallback: Original behavior for other modes (if slide_count not provided)
            logger.warning("slide_count not provided, using fallback behavior with retry logic")
            for idx, slide in enumerate(deck.slides):
                if slide.image_url:
                    continue
                
                # Priority: User keywords > Automatic extraction (with 10+ keywords)
                if user_provided_keywords:
                    keywords = list(payload.prompt_keywords)
                    # Rotate for variety
                    rotated_keywords = keywords[idx % len(keywords):] + keywords[:idx % len(keywords)]
                    logger.info(f"📝 Pexels slide {idx}: Using user-provided keywords (rotated): {rotated_keywords[:3]}")
                else:
                    # Extract 10+ keywords from slide content
                    keywords = self._extract_keywords_from_text(slide.text, max_keywords=10)
                    rotated_keywords = keywords
                    logger.info(f"📸 Pexels slide {idx}: Extracted {len(keywords)} keywords from slide text")
                
                # Try all keywords until one works
                result = self._fetch_image_with_retry(slide.placeholder_id, rotated_keywords, image_number=idx)
                if result:
                    contents.append(result)
                    logger.info("✅ Generated Pexels image for slide %d", idx + 1)
                else:
                    # Fallback: use last successful image
                    if contents:
                        from copy import deepcopy
                        fallback_image = deepcopy(contents[-1])
                        fallback_image.placeholder_id = slide.placeholder_id
                        contents.append(fallback_image)
                        logger.info("🔄 Using fallback (last successful) image for slide %d", idx + 1)
                    else:
                        logger.warning("⚠️ Pexels: No images available for slide %d", idx + 1)
        
        expected_count = payload.slide_count if payload.slide_count else len(deck.slides)
        logger.info("📊 Total Pexels images generated: %d (expected: %d)", len(contents), expected_count)
        return contents

    def _fetch_image(self, placeholder_id: str, keyword: str, image_number: int = 0) -> ImageContent:
        """Fetch image from Pexels API matching the user's implementation pattern.
        
        Args:
            placeholder_id: Unique identifier for the slide
            keyword: Search keyword for Pexels
            image_number: Index of image to fetch from search results (0 = first, 1 = second, etc.)
                          This ensures different images for different slides.
        """
        headers = {"Authorization": self._api_key}
        # Request a larger set of results (15 images) to ensure variety
        # Then use image_number to select different images from this set
        # This ensures each slide gets a different image even if we make multiple calls
        params = {
            "query": keyword,
            "per_page": 15,  # Request 15 images to have enough variety (Pexels allows up to 80)
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

        # Use image_number to get different images for different slides
        # If image_number is beyond available photos, use modulo to cycle through
        if len(photos) > image_number:
            photo = photos[image_number]
        else:
            # If not enough photos, cycle through available ones
            photo = photos[image_number % len(photos)]

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
        image_references = (payload.metadata or {}).get("image_references") or []
        return payload.image_source == "custom" and bool(image_references or payload.attachments)

    def generate(self, deck: SlideDeck, payload: IntakePayload) -> Sequence[ImageContent]:
        contents: list[ImageContent] = []
        
        import logging
        logger = logging.getLogger(__name__)
        
        # Validate attachment count for better handling
        image_references = (payload.metadata or {}).get("image_references") or []
        attachments = image_references or payload.attachments
        num_slides = len(deck.slides)
        num_attachments = len(attachments)
        
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
                attachment = attachments[idx]
            elif num_attachments > 0:
                # Use last attachment for remaining slides (repeat last image)
                attachment = attachments[-1]
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
        logger = logging.getLogger(__name__)
        
        # Extract filename from attachment
        filename = attachment.split("/")[-1] or f"{placeholder_id}.upload"
        # Remove query parameters from filename if present
        if "?" in filename:
            filename = filename.split("?")[0]
        
        image_bytes = None
        original_s3_key = None  # Preserve original S3 key if attachment is S3 URI
        
        try:
            # Case 1: data URL from browser uploads
            if attachment.startswith("data:"):
                header, _, data = attachment.partition(",")
                if ";base64" not in header.lower():
                    raise ValueError("Unsupported data URL format")
                image_bytes = base64.b64decode(data)
                mime_type = header[5:].split(";")[0].lower()
                extension = mimetypes.guess_extension(mime_type) or ".png"
                filename = f"{placeholder_id}{extension}"
                logger.info("Loaded image from data URL (%d bytes)", len(image_bytes))

            # Case 2: HTTP/HTTPS URL - download the image
            elif attachment.startswith(("http://", "https://")):
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(attachment)
                    response.raise_for_status()
                    image_bytes = response.content
                    logger.info("Downloaded image from URL: %s (%d bytes)", attachment, len(image_bytes))
            
            # Case 3: S3 URI (s3://bucket/key) - extract key and optionally load from S3
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
            
            # Case 4: Local file path - read from filesystem
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
        if is_placeholder_value(self._aws_access_key) or is_placeholder_value(self._aws_secret_key):
            self._logger.info("Skipping S3 image client initialization because placeholder credentials are configured")
            return None

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
