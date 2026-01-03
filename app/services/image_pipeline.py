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
from app.services.image_prompts import (
    extract_positive_keywords,
    generate_content_related_safe_prompt,
    generate_cta_prompt,
    generate_curious_slide_prompt,
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
        contents = provider.generate(deck, payload)
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
                
                mode_context = "educational story" if payload.mode.value == "curious" else "news story"
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
        prompt_keywords = ", ".join(payload.prompt_keywords) or "story"
        
        # For News mode with custom cover, generate images based on slide_count
        # slide_count = cover (1) + middle slides + CTA (1)
        # So we need images for: cover (1) + middle slides + CTA (slide_count - 1 total slides after cover)
        logger = logging.getLogger(__name__)
        if payload.mode.value == "news" and payload.slide_count:
            logger.info("🎨 Generating AI images for News mode: slide_count=%d, deck_slides=%d", 
                       payload.slide_count, len(deck.slides))
            
            import time
            last_successful_image = None  # Track last successful image for fallback
            
            # Generate images for ALL slides including cover (0) and CTA (last)
            # Loop through all slides from 0 to slide_count-1
            max_idx = min(payload.slide_count, len(deck.slides))
            logger.info("🔄 Generating images for all slides 0 to %d (including cover and CTA)", max_idx - 1)
            
            for idx in range(max_idx):
                slide = deck.slides[idx]
                if slide.image_url:
                    logger.debug("⏭️ Skipping slide %d (already has image_url)", idx)
                    continue
                
                # Add delay between requests (except first)
                # Reduced delays slightly but kept enough for rate limiting
                if idx > 0:
                    if idx == 1:
                        delay = 3.0  # Delay after cover (reduced from 5.0)
                    else:
                        delay = 6.0  # Delay between subsequent requests (reduced from 8.0)
                    logger.info("⏳ Waiting %.1f seconds before generating image for slide %d...", delay, idx)
                    time.sleep(delay)
                
                # Create prompt using prompts module
                slide_text = (slide.text or 'Visual concept')[:200]
                is_cover = (idx == 0)
                is_cta = (idx == max_idx - 1)
                
                # Get article content from payload metadata if available (for News mode)
                article_content = None
                if payload.metadata and "article_content" in payload.metadata:
                    article_content = payload.metadata["article_content"]
                    logger.info(f"📰 Using article content for slide {idx} image generation ({len(article_content)} chars)")
                
                prompt = generate_news_slide_prompt(
                    slide_text, 
                    idx, 
                    is_cover=is_cover, 
                    is_cta=is_cta,
                    article_content=article_content
                )
                
                try:
                    image_content = self._generate_image(slide.placeholder_id, prompt)
                    contents.append(image_content)
                    last_successful_image = image_content
                    logger.info("✅ Generated image for slide %d (index %d)", idx + 1, idx)
                except Exception as exc:
                    logger.warning("❌ AI image generation failed for slide %d (index %d): %s", idx + 1, idx, exc)
                    # ALWAYS try to generate a unique fallback image first
                    # Only use last_successful_image if fallback generation also fails
                    logger.info("🔄 Generating unique safe fallback image for slide %d (index %d)", idx + 1, idx)
                    try:
                        # Use content-related fallback that still uses article content for theme relevance
                        # This ensures fallback images are still related to the article theme
                        # and negative content is converted to positive (via generate_news_slide_prompt)
                        if article_content:
                            # Use shorter article snippet for fallback (400 chars) to keep it simple
                            # generate_news_slide_prompt will handle negative-to-positive conversion
                            fallback_article_snippet = article_content[:400]
                            safe_prompt = generate_news_slide_prompt(
                                slide_text,
                                idx,
                                is_cover=is_cover,
                                is_cta=is_cta,
                                article_content=fallback_article_snippet  # Shorter snippet for fallback
                            )
                            logger.info(f"🔄 Using article content in fallback for slide {idx} (theme-based)")
                        else:
                            # Fallback to simple safe prompt if no article content
                            safe_prompt = self._generate_safe_news_prompt(slide_text, slide_index=idx)
                            logger.info(f"🔄 Using generic safe prompt for slide {idx} (no article content)")
                        
                        fallback_content = self._generate_image(slide.placeholder_id, safe_prompt)
                        contents.append(fallback_content)
                        last_successful_image = fallback_content
                        logger.info("✅ Generated unique fallback image for slide %d", idx + 1)
                    except Exception as fallback_exc:
                        logger.warning("❌ Unique fallback generation failed for slide %d: %s", idx + 1, fallback_exc)
                        # Only now use last successful image as last resort
                        if last_successful_image:
                            logger.info("🔄 Using last successful image as final fallback for slide %d", idx + 1)
                            from copy import deepcopy
                            fallback_content = deepcopy(last_successful_image)
                            fallback_content.placeholder_id = slide.placeholder_id
                            contents.append(fallback_content)
                        else:
                            # Last resort: skip this slide (don't append empty bytes that can break storage)
                            logger.error("❌ All fallback options exhausted for slide %d; skipping image", idx + 1)
            
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
            
            # If alt_texts not found (for both News and Curious modes), generate them automatically
            # BUT: Only if user hasn't provided prompt_keywords (user input takes priority)
            if not alt_texts and self._language_model:
                # Check if user provided prompt_keywords - if yes, we'll use them in prompts instead
                user_provided_keywords = payload.prompt_keywords and len(payload.prompt_keywords) > 0
                if not user_provided_keywords:
                    logger.info("🔄 Alt texts not found in narrative_json and no user keywords provided, generating automatically from slide content...")
                    alt_texts = self._generate_alt_texts_for_slides(deck.slides, payload)
                else:
                    logger.info("📝 User provided prompt_keywords, will use them in prompts instead of auto-generated alt_texts")
            
            # Generate images for all slides in the deck (including cover and CTA)
            import time
            last_successful_image = None  # Track for fallback
            
            # Calculate total slides needed (deck slides + CTA if in Curious mode)
            total_slides_needed = len(deck.slides)
            if payload.mode.value == "curious":
                # In Curious mode, CTA slide is not in deck.slides, so we need to generate it separately
                # Total = deck.slides (cover + middle) + 1 CTA
                total_slides_needed = len(deck.slides) + 1
                logger.info(f"🔄 Curious mode: Generating images for {len(deck.slides)} deck slides + 1 CTA slide = {total_slides_needed} total")
            
            for idx, slide in enumerate(deck.slides):
                if slide.image_url:
                    continue
                
                # Add cooldown delay between requests (except first)
                if idx > 0:
                    delay = 8.0
                    logger.info(f"⏳ Waiting {delay:.1f} seconds before generating image for slide {idx} (rate limit protection)...")
                    time.sleep(delay)
                
                # Priority order:
                # 1. User-provided prompt_keywords (if available) - user input takes priority
                # 2. Auto-generated alt_texts (if available)
                # 3. Fallback to slide.text + prompt_keywords
                
                user_provided_keywords = payload.prompt_keywords and len(payload.prompt_keywords) > 0
                
                if user_provided_keywords:
                    # User provided keywords - use them in prompt (user preference)
                    if payload.mode.value == "curious":
                        # Convert non-English slide text to English first, then add keywords
                        english_desc = self._convert_to_english_fallback(slide.text or 'Learning', payload)
                        if english_desc == "Visual concept" or not english_desc or len(english_desc) < 10:
                            base_prompt = generate_curious_slide_prompt('Learning', is_cover=(idx == 0))
                        else:
                            base_prompt = f"{english_desc} — flat vector illustration, clean geometric shapes, smooth gradients, harmonious palette; inclusive, family-friendly; no text/logos/watermarks; no real-person likeness."
                        prompt = f"{base_prompt} | keywords: {prompt_keywords}"
                    else:
                        # For News mode, use slide text with user keywords
                        prompt = f"{slide.text or 'Visual concept'} | keywords: {prompt_keywords}"
                    logger.info(f"📝 Using user-provided keywords for slide {idx} ({slide.placeholder_id}): {prompt_keywords}")
                elif idx in alt_texts and alt_texts[idx]:
                    # Auto-generated alt_texts available - use them
                    prompt = alt_texts[idx]
                    logger.info(f"✅ Using auto-generated alt text for slide {idx} ({slide.placeholder_id}): {prompt[:100]}...")
                else:
                    # Fallback: convert non-English content to English description for image prompt
                    fallback_text = slide.text or 'Learning'
                    if payload.mode.value == "curious":
                        # For Curious mode, convert non-English slide text to English description
                        prompt = self._convert_to_english_fallback(fallback_text, payload)
                        if prompt == "Visual concept" or not prompt:
                            # If conversion failed, use generic safe prompt
                            prompt = generate_curious_slide_prompt('Learning', is_cover=(idx == 0))
                    else:
                        # For News mode, use slide text only (no keywords if not provided)
                        prompt = f"{fallback_text or 'Visual concept'}"
                    logger.warning(f"⚠️ Alt text not found for slide {idx} ({slide.placeholder_id}), using converted fallback prompt")
                
                try:
                    logger.debug(f"🖼️ Generating image for slide {idx} with prompt: {prompt[:150]}...")
                    image_content = self._generate_image(slide.placeholder_id, prompt)
                    contents.append(image_content)
                    last_successful_image = image_content
                    logger.info(f"✅ Successfully generated image for slide {idx} ({slide.placeholder_id})")
                except Exception as exc:
                    logger.error(f"❌ AI image generation failed for slide {idx} ({slide.placeholder_id}): {exc}", exc_info=True)
                    # ALWAYS provide fallback
                    if last_successful_image:
                        logger.info(f"🔄 Using last successful image as fallback for slide {idx}")
                        from copy import deepcopy
                        fallback_content = deepcopy(last_successful_image)
                        fallback_content.placeholder_id = slide.placeholder_id
                        contents.append(fallback_content)
                    else:
                        # Generate safe fallback with unique prompt for this slide
                        logger.info(f"🔄 Generating unique safe fallback image for slide {idx}")
                        try:
                            # Use slide index to ensure unique prompt
                            safe_prompt = self._generate_safe_news_prompt(slide.text, slide_index=idx)
                            fallback_content = self._generate_image(slide.placeholder_id, safe_prompt)
                            contents.append(fallback_content)
                            last_successful_image = fallback_content
                            logger.info(f"✅ Generated unique fallback image for slide {idx}")
                        except Exception as fallback_exc:
                            logger.warning(f"❌ Unique fallback generation failed for slide {idx}: {fallback_exc}")
                            # Only use last successful if available
                            if last_successful_image:
                                logger.info(f"🔄 Using last successful image as final fallback for slide {idx}")
                                from copy import deepcopy
                                fallback_content = deepcopy(last_successful_image)
                                fallback_content.placeholder_id = slide.placeholder_id
                                contents.append(fallback_content)
                            else:
                                # Last resort: skip (don't append empty bytes that can break storage)
                                logger.error(f"❌ All fallback options exhausted for slide {idx}; skipping image")
            
            # For Curious mode, generate CTA slide image separately (CTA is not in deck.slides)
            if payload.mode.value == "curious":
                cta_placeholder_id = "cta-slide"  # Match the template's CTA slide ID
                logger.info(f"🎯 Generating CTA slide image for Curious mode (placeholder: {cta_placeholder_id})")
                
                # Add delay before CTA image generation
                delay = 8.0
                logger.info(f"⏳ Waiting {delay:.1f} seconds before generating CTA image (rate limit protection)...")
                time.sleep(delay)
                
                # Generate CTA-specific prompt using prompts module
                cta_prompt = generate_cta_prompt(mode=payload.mode.value)
                
                try:
                    logger.debug(f"🖼️ Generating CTA image with prompt: {cta_prompt[:150]}...")
                    cta_image_content = self._generate_image(cta_placeholder_id, cta_prompt)
                    contents.append(cta_image_content)
                    last_successful_image = cta_image_content
                    logger.info(f"✅ Successfully generated CTA slide image ({cta_placeholder_id})")
                except Exception as cta_exc:
                    logger.error(f"❌ AI image generation failed for CTA slide ({cta_placeholder_id}): {cta_exc}", exc_info=True)
                    # Use last successful image as fallback for CTA
                    if last_successful_image:
                        logger.info(f"🔄 Using last successful image as fallback for CTA slide")
                        from copy import deepcopy
                        cta_fallback_content = deepcopy(last_successful_image)
                        cta_fallback_content.placeholder_id = cta_placeholder_id
                        contents.append(cta_fallback_content)
                    else:
                        # Generate safe fallback for CTA
                        logger.info(f"🔄 Generating unique safe fallback image for CTA slide")
                        try:
                            # Use a high index to ensure unique prompt
                            safe_cta_prompt = self._generate_safe_news_prompt("call to action learning", slide_index=len(deck.slides))
                            cta_fallback_content = self._generate_image(cta_placeholder_id, safe_cta_prompt)
                            contents.append(cta_fallback_content)
                            logger.info(f"✅ Generated unique fallback image for CTA slide")
                        except Exception as cta_fallback_exc:
                            logger.error(f"❌ CTA fallback generation also failed: {cta_fallback_exc}")
                            # Last resort: skip (template will fall back to default image)
                            logger.error("❌ CTA fallback exhausted; skipping CTA image")
            
            logger.info(f"📊 Total images generated: {len(contents)} (expected: {total_slides_needed} for {payload.mode.value} mode)")
        return contents

    def _generate_image(self, placeholder_id: str, prompt: str, retry_count: int = 3) -> ImageContent:
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
                                body["prompt"] = safe_prompt
                        elif attempt == 1:
                            # Second retry: use simpler content-related prompt
                            logger.warning("Content policy violation still occurring (attempt %d/%d), using simpler content-related prompt", attempt + 1, retry_count)
                            original_topic = prompt.split(",")[0].strip()[:30] if prompt else None
                            safe_prompt = self._generate_content_related_safe_prompt(original_topic, prompt, simpler=True)
                            body["prompt"] = safe_prompt
                        else:
                            # Last retry: use minimal but still content-aware prompt
                            logger.warning("Content policy violation persists (attempt %d/%d), using minimal content-aware prompt", attempt + 1, retry_count)
                            original_topic = prompt.split(",")[0].strip()[:20] if prompt else None
                            if original_topic:
                                body["prompt"] = f"professional illustration about {original_topic}, clean, modern, positive"
                            else:
                                body["prompt"] = "professional news illustration, clean, modern, positive"
                    else:
                        # For other 400 errors, try with a simpler prompt
                        logger.warning("400 Bad Request on attempt %d/%d, trying simpler prompt", attempt + 1, retry_count)
                        simple_prompt = prompt.split("|")[0].strip()[:100]  # Take first part, limit length more aggressively
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

    def _extract_keywords_from_text(self, text: str, max_keywords: int = 2) -> List[str]:
        """Extract 1-2 main keywords from slide text for Pexels search.
        
        Args:
            text: Slide text content
            max_keywords: Maximum number of keywords to extract
            
        Returns:
            List of keywords (1-2 words) for Pexels search
        """
        if not text:
            return ["news"]  # Default fallback
        
        import re
        
        # Simple approach: Extract first 1-2 meaningful words
        # Remove common stop words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by",
            "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
            "will", "would", "should", "could", "may", "might", "must", "can", "this", "that", "these", "those",
            "it", "its", "they", "them", "their", "we", "our", "you", "your", "he", "she", "his", "her",
            "from", "as", "if", "when", "where", "why", "how", "what", "which", "who", "whom", "whose"
        }
        
        # Split text into words, remove punctuation, lowercase
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Filter out stop words and get unique words
        keywords = [w for w in words if w not in stop_words]
        
        # Return first max_keywords or fallback
        if keywords:
            return keywords[:max_keywords]
        else:
            # Fallback: use first word from text (if available)
            first_words = text.split()
            if first_words:
                # Take first word, remove punctuation, lowercase
                first_word = re.sub(r'[^\w]', '', first_words[0].lower())
                if first_word and len(first_word) >= 3:
                    return [first_word]
            return ["news"]  # Ultimate fallback

    def generate(self, deck: SlideDeck, payload: IntakePayload) -> Sequence[ImageContent]:
        contents: list[ImageContent] = []
        logger = logging.getLogger(__name__)
        
        # Priority: User-provided prompt_keywords > Automatic extraction
        user_provided_keywords = payload.prompt_keywords and len(payload.prompt_keywords) > 0
        if user_provided_keywords:
            logger.info(f"📝 User provided prompt_keywords: {payload.prompt_keywords}, will use them for Pexels search")
        else:
            logger.info("🔄 No user keywords provided, will extract keywords automatically from slide content")
        
        # For both News and Curious modes, generate different images for each slide
        if payload.slide_count:
            logger.info("Generating Pexels images for %s mode: slide_count=%d, deck_slides=%d", 
                       payload.mode.value, payload.slide_count, len(deck.slides))
            
            # Generate cover image (first slide)
            if deck.slides:
                cover_slide = deck.slides[0]
                if not cover_slide.image_url:
                    try:
                        # Priority: User keywords > Automatic extraction
                        if user_provided_keywords:
                            query = payload.prompt_keywords[0]
                            logger.info(f"📝 Pexels cover: Using user-provided keyword: '{query}'")
                        else:
                            # Extract keywords from cover slide content automatically
                            keywords = self._extract_keywords_from_text(cover_slide.text)
                            query = keywords[0] if keywords else "news"
                            logger.info(f"📸 Pexels cover: Extracted keywords '{keywords}' from slide text: {cover_slide.text[:50] if cover_slide.text else 'N/A'}...")
                        contents.append(self._fetch_image(cover_slide.placeholder_id, query, image_number=0))
                        logger.info("✅ Generated Pexels cover image (index 0)")
                    except Exception as exc:
                        logger.warning("Pexels fetch failed for cover: %s", exc)
            
            # Generate images for all remaining slides (middle + CTA)
            # Cover is index 0, so generate images for indices 1 to (slide_count - 1)
            # This includes both middle slides and the CTA slide
            for idx in range(1, min(payload.slide_count, len(deck.slides))):
                slide = deck.slides[idx]
                if slide.image_url:
                    continue
                try:
                    # Priority: User keywords > Automatic extraction
                    if user_provided_keywords:
                        # Use user keywords, but cycle through them for variety
                        keyword_idx = (idx - 1) % len(payload.prompt_keywords)
                        query = payload.prompt_keywords[keyword_idx]
                        logger.info(f"📝 Pexels slide {idx}: Using user-provided keyword: '{query}'")
                    else:
                        # Extract keywords from slide content automatically
                        keywords = self._extract_keywords_from_text(slide.text)
                        query = keywords[0] if keywords else "news"
                        logger.info(f"📸 Pexels slide {idx}: Extracted keywords '{keywords}' from slide text: {slide.text[:50] if slide.text else 'N/A'}...")
                    # Use different image_number for variety (idx = 1, 2, 3, etc.)
                    # This ensures each slide gets a different image from Pexels search results
                    contents.append(self._fetch_image(slide.placeholder_id, query, image_number=idx))
                    logger.info("✅ Generated Pexels image for slide %d (index %d, image_number=%d)", idx + 1, idx, idx)
                except Exception as exc:
                    logger.warning("Pexels fetch failed for slide %d: %s", idx, exc)
            
            # For Curious mode, generate CTA slide image separately (CTA is not in deck.slides)
            if payload.mode.value == "curious":
                cta_placeholder_id = "cta-slide"
                logger.info("🎯 Generating Pexels CTA slide image for Curious mode (placeholder: %s)", cta_placeholder_id)
                try:
                    # Priority: User keywords > Automatic extraction
                    if user_provided_keywords:
                        # Use last keyword from user list, or first if only one
                        query = payload.prompt_keywords[-1] if len(payload.prompt_keywords) > 1 else payload.prompt_keywords[0]
                        logger.info(f"📝 Pexels CTA: Using user-provided keyword: '{query}'")
                    else:
                        # Extract keywords from last slide or use category
                        if deck.slides:
                            last_slide = deck.slides[-1]
                            keywords = self._extract_keywords_from_text(last_slide.text)
                        else:
                            keywords = [payload.category.lower()] if payload.category else ["news"]
                        query = keywords[0] if keywords else "news"
                        logger.info(f"📸 Pexels CTA: Extracted keywords '{keywords}' for CTA slide")
                    # Use a high image_number to get a different image for CTA
                    cta_image_number = len(deck.slides)  # Use deck.slides length to ensure unique image
                    contents.append(self._fetch_image(cta_placeholder_id, query, image_number=cta_image_number))
                    logger.info("✅ Generated Pexels CTA slide image (image_number=%d)", cta_image_number)
                except Exception as exc:
                    logger.warning("Pexels fetch failed for CTA slide: %s", exc)
                    # Fallback: use last successful image if available
                    if contents:
                        from copy import deepcopy
                        last_image = deepcopy(contents[-1])
                        last_image.placeholder_id = cta_placeholder_id
                        contents.append(last_image)
                        logger.info("🔄 Using last Pexels image as fallback for CTA slide")
        else:
            # Fallback: Original behavior for other modes (if slide_count not provided)
            logger.warning("slide_count not provided, using fallback behavior")
            for idx, slide in enumerate(deck.slides):
                if slide.image_url:
                    continue
                try:
                    # Priority: User keywords > Automatic extraction
                    if user_provided_keywords:
                        keyword_idx = idx % len(payload.prompt_keywords)
                        query = payload.prompt_keywords[keyword_idx]
                        logger.info(f"📝 Pexels slide {idx}: Using user-provided keyword: '{query}'")
                    else:
                        # Extract keywords from slide content automatically
                        keywords = self._extract_keywords_from_text(slide.text)
                        query = keywords[0] if keywords else "news"
                        logger.info(f"📸 Pexels slide {idx}: Extracted keywords '{keywords}' from slide text")
                    # Use image_number=idx to get different images
                    contents.append(self._fetch_image(slide.placeholder_id, query, image_number=idx))
                except Exception as exc:
                    logger.warning("Pexels fetch failed: %s", exc)
        
        expected_count = payload.slide_count if payload.slide_count else len(deck.slides)
        if payload.mode.value == "curious" and payload.slide_count:
            # In Curious mode, add 1 for CTA slide
            expected_count = len(deck.slides) + 1
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
        
        # For Curious mode, generate CTA slide image separately (CTA is not in deck.slides)
        if payload.mode.value == "curious":
            cta_placeholder_id = "cta-slide"
            logger.info("🎯 Generating custom CTA slide image for Curious mode (placeholder: %s)", cta_placeholder_id)
            
            # Use last attachment for CTA slide
            if num_attachments > 0:
                cta_attachment = payload.attachments[-1]
                try:
                    contents.append(self._to_content(cta_placeholder_id, cta_attachment))
                    logger.info("✅ Generated custom CTA slide image using last attachment")
                except Exception as exc:
                    logger.warning("Failed to generate custom CTA image: %s", exc)
                    # Fallback: use last successful image if available
                    if contents:
                        from copy import deepcopy
                        last_image = deepcopy(contents[-1])
                        last_image.placeholder_id = cta_placeholder_id
                        contents.append(last_image)
                        logger.info("🔄 Using last custom image as fallback for CTA slide")
            else:
                logger.warning("No attachments available for CTA slide in Curious mode")
        
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

