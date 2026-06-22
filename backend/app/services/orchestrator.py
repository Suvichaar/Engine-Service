"""Application service orchestrating the full story workflow."""

from __future__ import annotations

import re
import random
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, Sequence
from uuid import UUID, uuid4

import httpx

from app.domain.dto import (
    AnalysisReport,
    DocInsights,
    ImageAsset,
    IntakePayload,
    LanguageMetadata,
    Mode,
    RenderedPrompt,
    SlideDeck,
    StoryRecord,
    VoiceAsset,
)
from app.domain.interfaces import (
    AnalysisFacade,
    DocumentIntelligencePipeline,
    ImageAssetPipeline,
    IngestionAggregator,
    LanguageDetectionService,
    ModelRouter,
    PromptTemplateService,
    StoryRepository,
    UserInputService,
    VoiceSynthesisService,
)
from app.services.prompt_templates import PromptSelectionController
from app.services.html_renderer import HTMLTemplateRenderer
from app.api.schemas import StoryCreateRequest


@dataclass
class StoryOrchestrator:
    """Coordinate all services to create and retrieve stories."""

    user_input_service: UserInputService
    language_service: LanguageDetectionService
    ingestion_aggregator: IngestionAggregator
    doc_pipeline: DocumentIntelligencePipeline
    analysis_facade: AnalysisFacade
    prompt_controller: PromptSelectionController
    model_router: ModelRouter
    image_pipeline: ImageAssetPipeline
    voice_service: VoiceSynthesisService
    repository: StoryRepository
    html_renderer: Optional[HTMLTemplateRenderer] = None
    id_factory: Callable[[], UUID] = uuid4
    default_voice_provider: str = "azure_basic"
    story_base_url: Optional[str] = None
    save_to_database: bool = True  # Default to True - save stories to database

    def create_story(
        self,
        request: StoryCreateRequest,
        *,
        preset_story_id: Optional[UUID] = None,
    ) -> StoryRecord:
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            payload = self._build_intake_payload(request)
            logger.debug("Built intake payload")
        except Exception as e:
            logger.error("Failed to build intake payload: %s", e, exc_info=True)
            raise ValueError(f"Invalid request payload: {e}") from e
        
        try:
            language = self.language_service.detect(payload)
            logger.debug("Detected language: %s", language.language_code)
        except Exception as e:
            logger.error("Language detection failed: %s", e, exc_info=True)
            raise ValueError(f"Language detection failed: {e}") from e
        
        try:
            job_request = self.ingestion_aggregator.aggregate(payload, language)
            logger.debug("Aggregated job request")
        except Exception as e:
            logger.error("Job request aggregation failed: %s", e, exc_info=True)
            raise ValueError(f"Failed to aggregate job request: {e}") from e
        
        try:
            # CRITICAL LAYER 1: Create Curious mode-specific document pipeline with mode-specific URL extractor
            # This ensures Curious mode has its own isolated cache
            from app.services.url_extractor import URLContentExtractor
            from app.services.document_intelligence import DefaultDocumentIntelligencePipeline
            from app.core import get_settings
            import os
            
            # Get Serper API key from settings or environment variable
            settings = get_settings()
            serper_api_key = None
            if settings.serper and settings.serper.api_key:
                serper_api_key = settings.serper.api_key
            elif os.getenv("SERPER_API_KEY"):
                serper_api_key = os.getenv("SERPER_API_KEY")
            
            mode_str = payload.mode.value if hasattr(payload.mode, 'value') else str(payload.mode)
            mode_specific_extractor = URLContentExtractor(mode=mode_str, api_key=serper_api_key)
            
            # Create mode-specific doc pipeline for this request
            mode_doc_pipeline = DefaultDocumentIntelligencePipeline(
                ocr_adapters=self.doc_pipeline._ocr_adapters,
                parser_adapters=self.doc_pipeline._parser_adapters,
                url_extractor=mode_specific_extractor
            )
            
            logger.warning(f"🔍 Using mode-specific URL extractor for mode: {mode_str}")
            doc_insights = mode_doc_pipeline.run(job_request)
            logger.debug("Document intelligence completed, chunks: %d", len(doc_insights.semantic_chunks))
            
            # CRITICAL: Validate that we got content from URLs if URLs were provided
            if job_request.url_list and len(job_request.url_list) > 0:
                if not doc_insights.semantic_chunks or len(doc_insights.semantic_chunks) == 0:
                    error_msg = f"CRITICAL ERROR: No content extracted from {len(job_request.url_list)} URL(s). URLs: {[str(url) for url in job_request.url_list]}"
                    logger.error(f"❌ {error_msg}")
                    logger.error("❌ Story generation will fail or produce incorrect content!")
                    raise ValueError(error_msg + " Please check the URLs and ensure article extraction is working.")
                
                # CRITICAL FINAL VALIDATION: Check if extracted content matches URL
                # This is the LAST line of defense before story generation
                first_chunk = doc_insights.semantic_chunks[0]
                extracted_text = first_chunk.text.lower() if first_chunk.text else ""
                extracted_title = first_chunk.metadata.get("title", "").lower() if first_chunk.metadata else ""
                
                # LANGUAGE-AGNOSTIC: Check if content is in Hindi/Unicode (same logic as url_extractor.py)
                # Get original title (not lowercased) for Unicode detection
                original_title = first_chunk.metadata.get("title", "") if first_chunk.metadata else ""
                original_text = first_chunk.text[:1000] if first_chunk.text else ""  # Check first 1000 chars
                content_to_check = f"{original_title} {original_text}"  # Check BOTH title and text
                is_hindi_or_unicode = any(
                    '\u0900' <= char <= '\u097F' or  # Devanagari (Hindi, Marathi, etc.)
                    '\u0980' <= char <= '\u09FF' or  # Bengali
                    '\u0A00' <= char <= '\u0A7F' or  # Gurmukhi (Punjabi)
                    '\u0A80' <= char <= '\u0AFF' or  # Gujarati
                    '\u0B00' <= char <= '\u0B7F' or  # Oriya
                    '\u0B80' <= char <= '\u0BFF' or  # Tamil
                    '\u0C00' <= char <= '\u0C7F' or  # Telugu
                    '\u0C80' <= char <= '\u0CFF' or  # Kannada
                    '\u0D00' <= char <= '\u0D7F'     # Malayalam
                    for char in content_to_check
                )
                
                if is_hindi_or_unicode:
                    logger.warning("🌐 Final Validation: Detected Hindi/Unicode content - validation will be skipped")
                
                logger.warning(f"🔍 FINAL VALIDATION: Checking URL-content match")
                logger.warning(f"🔍 Extracted title: {extracted_title[:100]}")
                logger.warning(f"🔍 Extracted text preview: {extracted_text[:200]}")
                
                # Check each URL against extracted content
                for url in job_request.url_list:
                    url_str = str(url).lower()
                    logger.warning(f"🔍 Checking URL: {url_str}")
                    
                    # GENERAL validation: Check if URL path keywords match extracted content
                    # This is a general approach that works for ANY topic mismatch, not just specific cases
                    from urllib.parse import urlparse
                    parsed = urlparse(url_str if url_str.startswith('http') else f'https://{url_str}')
                    path_parts = parsed.path.split('/')
                    url_keywords = []
                    skip_words = {'article', 'news', 'story', 'com', 'org', 'www', 'http', 'https', 'indianexpress',
                                 'sports', 'cities', 'entertainment', 'technology', 'business', 'politics', 'world',
                                 'local', 'health', 'science', 'education', 'lifestyle', 'opinion', 'editorial', 'html'}
                    
                    for part in path_parts:
                        part = part.split('?')[0].split('#')[0].strip()
                        if not part or part == '/':
                            continue
                        words = part.split('-')
                        for word in words:
                            if len(word) > 3 and word not in skip_words and not word.isdigit():
                                url_keywords.append(word)
                    
                    # Check overlap: How many URL keywords appear in content?
                    if url_keywords:
                        top_url_keywords = sorted(set(url_keywords), key=len, reverse=True)[:10]
                        content_text = f"{extracted_title} {extracted_text}"
                        
                        # Count UNIQUE keyword matches (more accurate)
                        unique_matches = set()
                        for kw in top_url_keywords:
                            if kw in content_text:
                                unique_matches.add(kw)
                        actual_unique_matches = len(unique_matches)
                        match_ratio = actual_unique_matches / len(top_url_keywords) if top_url_keywords else 0
                        
                        # ADAPTIVE VALIDATION: Skip for Hindi/Unicode content, strict for English
                        if is_hindi_or_unicode:
                            # For Hindi/Unicode content: Skip validation entirely
                            # Hindi titles don't match English URL keywords
                            logger.warning("🌐 Final Validation: Hindi/Unicode content detected - skipping URL-content match check")
                            logger.warning("✅ Final Validation: Hindi/Unicode content accepted (validation skipped)")
                            continue  # Skip validation for this URL, move to next or proceed
                        
                        # STRICT VALIDATION: Require at least 2-3 unique keywords to match (only for English)
                        min_required_matches = max(2, min(3, len(top_url_keywords) // 3))
                        
                        logger.warning(f"🔍 Final Validation: URL keywords={top_url_keywords[:5]}")
                        logger.warning(f"🔍 Final Validation: Unique matches={actual_unique_matches}/{len(top_url_keywords)}, Match ratio={match_ratio*100:.1f}%, Required={min_required_matches}")
                        
                        # CRITICAL: Reject if match ratio is very low OR not enough unique matches (only for English)
                        if len(top_url_keywords) >= 3:
                            if match_ratio < 0.1 or actual_unique_matches < min_required_matches:
                                error_msg = f"CRITICAL MISMATCH DETECTED: URL keywords do not match extracted content. URL: {url_str}. Extracted title: {extracted_title[:100]}. URL keywords: {top_url_keywords}. Unique matches: {actual_unique_matches}/{len(top_url_keywords)} (required: {min_required_matches}). Match ratio: {match_ratio*100:.1f}% (expected >10%). This indicates wrong article was extracted. Story generation ABORTED."
                                logger.error(f"❌ ===== FINAL VALIDATION FAILED =====")
                                logger.error(f"❌ {error_msg}")
                                raise ValueError(error_msg)
                            else:
                                logger.warning(f"✅ Final validation passed (%.1f%% match, %d unique matches, required %d)", match_ratio * 100, actual_unique_matches, min_required_matches)
                        else:
                            logger.warning(f"⚠️ Too few URL keywords ({len(top_url_keywords)}) for strict validation, accepting")
                
                # Log first chunk to verify content (using WARNING level so it shows in logs)
                logger.warning(f"✅ Content extracted - First chunk preview: {first_chunk.text[:200] if first_chunk.text else 'Empty'}")
                logger.warning(f"✅ Final validation passed - URL and content match")
        except ValueError:
            # Re-raise ValueError (our validation error)
            raise
        except Exception as e:
            logger.error("Document intelligence pipeline failed: %s", e, exc_info=True)
            raise ValueError(f"Document processing failed: {e}") from e
        
        try:
            analysis = self.analysis_facade.analyze(doc_insights)
            self._apply_analysis(doc_insights, analysis)
            logger.debug("Analysis completed")
        except Exception as e:
            logger.error("Analysis failed: %s", e, exc_info=True)
            raise ValueError(f"Analysis failed: {e}") from e

        try:
            rendered_prompt = self.prompt_controller.select_prompt(
                mode=payload.mode.value,
                category=request.category or "Art",
                language=language.language_code,
                analysis=analysis,
                keywords=payload.prompt_keywords,
            )
            logger.debug("Prompt selected and rendered")
        except Exception as e:
            logger.error("Prompt selection/rendering failed: %s", e, exc_info=True)
            raise ValueError(f"Prompt rendering failed: {e}") from e

        try:
            model_client = self.model_router.route(payload.mode)
            # Narrative generation
            if hasattr(model_client, 'generate'):
                # For CuriousModelClient, pass slide_count if available
                # Note: CuriousModelClient may not support slide_count yet, but we pass it for future compatibility
                try:
                    narrative = model_client.generate(
                        rendered_prompt,
                        doc_insights,
                        slide_count=payload.slide_count,
                    )
                except TypeError:
                    # Fallback if slide_count parameter not supported yet
                    logger.debug("CuriousModelClient doesn't support slide_count yet, using default")
                    narrative = model_client.generate(rendered_prompt, doc_insights)
            else:
                narrative = model_client.generate(rendered_prompt, doc_insights)
            logger.debug("Narrative generated, slides: %d", len(narrative.slide_deck.slides))
        except Exception as e:
            logger.error("Narrative generation failed: %s", e, exc_info=True)
            raise ValueError(f"Narrative generation failed: {e}") from e

        # CRITICAL LAYER 3: Post-generation validation - check if generated story matches URL
        if job_request.url_list and len(job_request.url_list) > 0 and narrative.slide_deck.slides:
            story_title = narrative.slide_deck.slides[0].text if narrative.slide_deck.slides else ""
            url_str = str(job_request.url_list[0]).lower()
            
            # Extract URL keywords
            from urllib.parse import urlparse
            parsed = urlparse(url_str if url_str.startswith('http') else f'https://{url_str}')
            url_keywords = []
            skip_words = {'article', 'news', 'sports', 'cricket', 'football', 'cities', 
                         'entertainment', 'technology', 'business', 'politics', 'world'}
            
            for part in parsed.path.split('/')[-3:]:  # Last 3 path segments
                if not part or part == '/':
                    continue
                words = part.split('-')
                for word in words:
                    if len(word) > 3 and word.lower() not in skip_words:
                        url_keywords.append(word.lower())
            
            # Check if story title matches URL keywords
            if url_keywords and story_title:
                title_lower = story_title.lower()
                unique_keywords = list(dict.fromkeys(url_keywords[:5]))  # First 5 unique keywords
                matches = sum(1 for kw in unique_keywords if kw in title_lower)
                
                logger.warning(f"🔍 Post-generation validation: URL keywords={unique_keywords}, Story title={story_title[:100]}, Matches={matches}")
                
                # If less than 2 keywords match and we have 3+ keywords, regenerate
                if matches < 2 and len(unique_keywords) >= 3:
                    logger.error(f"❌ Generated story doesn't match URL! Title: {story_title[:100]}, URL keywords: {unique_keywords}, Matches: {matches}")
                    logger.error(f"❌ Regenerating with explicit URL context...")
                    
                    # Add URL keywords to doc_insights metadata for forced regeneration
                    if doc_insights.metadata is None:
                        doc_insights.metadata = {}
                    doc_insights.metadata["force_url_topic"] = " ".join(unique_keywords)
                    doc_insights.metadata["source_url"] = url_str
                    
                    # Regenerate narrative with URL context
                    try:
                        narrative = model_client.generate(rendered_prompt, doc_insights)
                        logger.warning(f"✅ Regenerated story with URL context: {narrative.slide_deck.slides[0].text[:100] if narrative.slide_deck.slides else 'None'}")
                    except Exception as regen_error:
                        logger.error(f"❌ Regeneration failed: {regen_error}, continuing with original narrative")
                else:
                    logger.warning(f"✅ Post-generation validation passed: {matches} keywords matched")

        # Extract article images from doc_insights metadata
        article_images = None
        if doc_insights.metadata and "article_images" in doc_insights.metadata:
            article_images = doc_insights.metadata["article_images"]

        # Extract article content from doc_insights for story generation
        # Combine all semantic chunks to get full article text
        article_content = None
        if doc_insights.semantic_chunks:
            article_content = " ".join([chunk.text for chunk in doc_insights.semantic_chunks if chunk.text])
            logger.debug(f"Extracted article content for image generation: {len(article_content)} characters")

        # For Curious mode, extract alt texts from narrative and pass to image pipeline
        
        
        try:
            logger.info("🖼️ Starting image pipeline: mode=%s image_source=%s slide_count=%d", 
                          payload.mode.value, payload.image_source, payload.slide_count)
            image_assets = self.image_pipeline.process(narrative.slide_deck, payload, article_images=article_images)
            logger.info("🖼️ Image assets processed: %d", len(image_assets))
        except Exception as e:
            logger.warning("❌ Image pipeline failed (non-critical): %s", e, exc_info=False)
            image_assets = []  # Continue without images
        
        try:
            voice_provider = payload.voice_engine or self.default_voice_provider
            logger.info("🔊 Voice synthesis requested: %s", voice_provider)
            
            if not voice_provider:
                logger.error("❌ No voice provider available! voice_provider=%s, default=%s", 
                            voice_provider, self.default_voice_provider)
                voice_assets = []
            else:
                logger.info("🎤 Starting voice synthesis for %d slides...", len(narrative.slide_deck.slides))
                voice_assets = self.voice_service.synthesize(narrative.slide_deck, language, voice_provider)
                logger.info("✅ Voice assets synthesized: count=%d", len(voice_assets))
                
                # Log each voice asset
                for idx, asset in enumerate(voice_assets):
                    logger.info("🎵 Voice asset %d: provider=%s, url=%s", idx, asset.provider, asset.audio_url)
        except Exception as e:
            logger.error("❌ Voice synthesis failed: %s", e, exc_info=True)
            voice_assets = []  # Continue without voice

        story_id = preset_story_id or self.id_factory()
        created_at = datetime.utcnow()

        # Get story title for URL generation (Curious mode uses title-based URLs)
        story_title = None
        if payload.mode == Mode.CURIOUS and narrative.slide_deck.slides:
            story_title = narrative.slide_deck.slides[0].text or None

        canurl, canurl1 = self._build_canurls(story_id, story_title=story_title, mode=payload.mode)

        og_image_url = None
        if image_assets:
            cover = image_assets[0]
            cover_key = getattr(cover, "original_object_key", None)
            if cover_key:
                try:
                    og_image_url = self.image_pipeline.generate_og_image(
                        source_s3_key=cover_key,
                        story_id=str(story_id),
                    )
                except Exception as e:
                    logger.warning("Failed to generate OG image for story %s: %s", story_id, e)

        record = StoryRecord(
            id=story_id,
            mode=payload.mode,
            category=request.category or narrative.mode.value.title(),
            input_language=language.language_code,
            slide_count=payload.slide_count,
            template_key=payload.template_key,
            doc_insights=doc_insights,
            slide_deck=narrative.slide_deck,
            image_assets=image_assets,
            voice_assets=voice_assets,
            prompt_curious=rendered_prompt.user,
            canurl=canurl,
            canurl1=canurl1,
            og_image_url=og_image_url,
            created_at=created_at,
        )

        # Save to database only if enabled
        if self.save_to_database:
            try:
                self.repository.save(record)
                logger.debug("Story saved to database successfully")
            except Exception as e:
                # Database save is non-critical - story generation should continue even if save fails
                logger.warning("Failed to save story to database (non-critical): %s", e)
                logger.debug("Database error details:", exc_info=True)
                # Continue without database save - story generation is still successful

        # Generate and save HTML if renderer is available
        html_file_path = None
        if self.html_renderer:
            try:
                html_content = self.html_renderer.render(
                    record=record,
                    template_key=payload.template_key,
                    template_source="file",
                    image_source=payload.image_source,
                )
                # Save HTML to file
                html_file_path = self.html_renderer.save_html_to_file(
                    html_content=html_content,
                    story_id=story_id,
                )
                import logging
                logger = logging.getLogger(__name__)
                logger.info("HTML saved to: %s", html_file_path)
                
                # For Curious mode, upload HTML to S3 bucket "suvichaarstories" with slug-based filename
                if record.canurl1:
                    try:
                        # Extract slug filename from canurl1: https://suvichaar.org/stories/slug_nano.html -> slug_nano.html
                        canurl1_str = str(record.canurl1)
                        if "suvichaar.org/stories/" in canurl1_str:
                            slug_filename = canurl1_str.split("suvichaar.org/stories/")[-1]
                            # slug_filename should be like "tragic-accident-near-navale-bridge-leaves-several-dead-and-injured-in-pune_KKd2kdX729_G.html"
                            
                            # Get AWS settings
                            from app.core import get_settings
                            settings = get_settings()
                            
                            # Upload to S3 bucket "suvichaarstories" with slug-based filename
                            import boto3
                            s3_client = boto3.client(
                                "s3",
                                aws_access_key_id=settings.aws.access_key,
                                aws_secret_access_key=settings.aws.secret_key,
                                region_name=settings.aws.region or "us-east-1",
                            )
                            
                            s3_client.put_object(
                                Bucket="suvichaarstories",
                                Key=slug_filename,  # Use slug-based filename (e.g., "slug_nano.html")
                                Body=html_content.encode("utf-8"),
                                ContentType="text/html; charset=utf-8",
                            )
                            
                            logger.info("Uploaded HTML to S3: s3://suvichaarstories/%s", slug_filename)
                    except ImportError:
                        logger.warning("boto3 not installed, S3 HTML upload skipped")
                    except Exception as e:
                        logger.warning("Failed to upload HTML to S3 (non-critical): %s", e)
                        logger.debug("S3 upload error details:", exc_info=True)
                        # Continue without S3 upload - story creation should succeed
                        
            except Exception as e:
                # Log error but don't fail story creation - HTML saving is optional
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("HTML rendering/saving failed (non-critical): %s", e)
                logger.debug("HTML error details:", exc_info=True)
                # Continue without HTML file - story creation should succeed

        return record

    def get_story(self, story_id: str) -> StoryRecord:
        return self.repository.get(story_id)

    def get_story_by_slug(self, slug: str) -> StoryRecord:
        """
        Get story by slug from URL.
        Handles both full URLs and just the slug part.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Extract slug from URL if full URL is provided
        # e.g., "https://suvichaar.org/stories/slug_nano" -> "slug_nano"
        # or "tragic-crash-near-navale-bridge-in-pune-leaves-several-dead-and-injured_PYDH_6ImHU_G"
        if "/" in slug:
            # Extract the last part after the last slash
            slug = slug.split("/")[-1]
            # Remove .html extension if present
            if slug.endswith(".html"):
                slug = slug[:-5]
        
        # Try to find by canurl (without .html)
        canurl = f"https://suvichaar.org/stories/{slug}"
        canurl1 = f"https://suvichaar.org/stories/{slug}.html"
        
        try:
            # First try exact match with canurl
            return self.repository.get_by_canurl(canurl)
        except KeyError:
            try:
                # Then try with canurl1
                return self.repository.get_by_canurl(canurl1)
            except KeyError:
                # Finally try with just the slug part
                try:
                    return self.repository.get_by_canurl(slug)
                except KeyError:
                    logger.error("Story not found for slug: %s (tried: %s, %s, %s)", slug, canurl, canurl1, slug)
                    raise KeyError(f"Story with slug {slug} not found.")

    def _build_intake_payload(self, request: StoryCreateRequest) -> IntakePayload:
        return self.user_input_service.build_payload(
            user_input=request.user_input,  # NEW: Unified input support
            text_prompt=request.text_prompt,
            notes=request.notes,
            urls=request.urls,
            attachments=request.attachments,
            prompt_keywords=request.prompt_keywords,
            mode=request.mode.value,
            template_key=request.template_key,
            slide_count=request.slide_count,
            category=request.category,
            image_source=request.image_source,
            voice_engine=request.voice_engine,
        )

    def _apply_analysis(self, doc_insights: DocInsights, analysis: AnalysisReport) -> None:
        if analysis.recommended_prompts:
            doc_insights.recommended_prompts = analysis.recommended_prompts
        if analysis.gaps:
            doc_insights.gaps = analysis.gaps
        if analysis.narrative_summary:
            doc_insights.summaries = [analysis.narrative_summary]

    def _build_canurls(self, story_id: UUID, story_title: Optional[str] = None, mode: Optional[Mode] = None) -> tuple[Optional[str], Optional[str]]:
        """
        Build canonical URLs for the story.
        
        For Curious mode: Uses title-based slug + date/time UUID format
        Matching JavaScript createSlugWithUUID function:
        - Slug from title (lowercase, hyphens, alphanumeric only)
        - UUID from date/time: ddmmyyhhminssms (14 digits)
        - Format: {slug}_{uuid}
        
        For other modes: Uses story_id format
        
        Args:
            story_id: UUID of the story
            story_title: Story title (used for slug generation)
            mode: Story mode (Curious)
        
        Returns:
            Tuple of (canurl, canurl1)
            - canurl: Primary URL (without .html) - https://suvichaar.org/stories/{slug}_{uuid}
            - canurl1: Secondary URL (with .html) - https://suvichaar.org/stories/{slug}_{uuid}.html
        """
        logger = logging.getLogger(__name__)
        
        # For Curious mode, ALWAYS use title-based slug + date/time UUID format
        if mode == Mode.CURIOUS:
            try:
                # Step 1: Generate slug from title
                if story_title and story_title.strip():
                    slug = self._slugify_title(story_title)
                    
                    # Double-check: Ensure slug is not empty (safety net)
                    if not slug or slug.strip() == '':
                        logger.warning("Slug is empty after slugification, using hash fallback")
                        title_hash = hashlib.md5(story_title.encode('utf-8')).hexdigest()[:8]
                        slug = f"story-{title_hash}"
                else:
                    # No title provided, use story_id as fallback slug
                    logger.warning("No story_title provided, using story_id as slug fallback")
                    slug = f"story-{str(story_id).replace('-', '')[:16]}"
                
                # Step 2: Generate UUID based on current date and time
                # Format: ddmmyyhhminssms (14 digits)
                # Matching JavaScript: dd + mm + yy + hh + min + ss + ms
                now = datetime.now()
                dd = f"{now.day:02d}"           # Day (2 digits, zero-padded)
                mm = f"{now.month:02d}"          # Month (2 digits, zero-padded)
                yy = f"{now.year % 100:02d}"     # Year (last 2 digits, zero-padded)
                hh = f"{now.hour:02d}"           # Hour (2 digits, zero-padded)
                min_str = f"{now.minute:02d}"    # Minute (2 digits, zero-padded)
                ss = f"{now.second:02d}"         # Second (2 digits, zero-padded)
                ms = f"{now.microsecond // 1000:03d}"  # Milliseconds (3 digits, zero-padded)
                
                uuid_str = f"{dd}{mm}{yy}{hh}{min_str}{ss}{ms}"
                
                # Step 3: Concatenate slug and UUID (no "_G" suffix)
                slug_uuid = f"{slug}_{uuid_str}"
                
                # ALWAYS use hardcoded base URL: https://suvichaar.org/stories
                base_url = "https://suvichaar.org/stories"
                
                # canurl: without .html extension (for display)
                canurl = f"{base_url}/{slug_uuid}"
                
                # canurl1: with .html extension (for S3 storage)
                canurl1 = f"{base_url}/{slug_uuid}.html"
                
                logger.info(f"✅ Generated URLs: canurl={canurl}, canurl1={canurl1}")
                return canurl, canurl1
                
            except Exception as e:
                logger.error("Failed to generate title-based URLs: %s", e, exc_info=True)
                # Even on exception, try to generate URLs with minimal info
                try:
                    now = datetime.now()
                    dd = f"{now.day:02d}"
                    mm = f"{now.month:02d}"
                    yy = f"{now.year % 100:02d}"
                    hh = f"{now.hour:02d}"
                    min_str = f"{now.minute:02d}"
                    ss = f"{now.second:02d}"
                    ms = f"{now.microsecond // 1000:03d}"
                    uuid_str = f"{dd}{mm}{yy}{hh}{min_str}{ss}{ms}"
                    
                    slug = f"story-{str(story_id).replace('-', '')[:16]}"
                    slug_uuid = f"{slug}_{uuid_str}"
                    base_url = "https://suvichaar.org/stories"
                    
                    canurl = f"{base_url}/{slug_uuid}"
                    canurl1 = f"{base_url}/{slug_uuid}.html"
                    
                    logger.warning(f"⚠️ Generated URLs with fallback: canurl={canurl}, canurl1={canurl1}")
                    return canurl, canurl1
                except Exception as e2:
                    logger.error("Complete failure in URL generation: %s", e2, exc_info=True)
                    return None, None
        
        # Fallback for other modes: use story_id format (if story_base_url is available)
        if self.story_base_url:
            base = self.story_base_url.rstrip("/")
            primary = f"{base}/{story_id}"
            secondary = f"{primary}?variant=alt"
            return primary, secondary
        
        return None, None
    
    def _slugify_title(self, title: str) -> str:
        """
        Slugify a title to create URL-friendly slug.
        Transliterates ANY non-English language to English if needed.
        NEVER raises exceptions - always returns a valid slug.
        Matches JavaScript slugify logic:
        - Convert to lowercase
        - Replace spaces with hyphens
        - Remove non-alphanumeric characters (except hyphens)
        - Remove leading/trailing hyphens
        """
        logger = logging.getLogger(__name__)
        
        try:
            if not title or not isinstance(title, str):
                logger.warning("Invalid title provided, using fallback")
                return "story-" + hashlib.md5(str(title).encode('utf-8')).hexdigest()[:8]
            
            original_title = title  # Keep original for fallback
            
            # Step 1: Check if title contains non-ASCII characters (any non-English language)
            # Count ASCII vs non-ASCII characters
            ascii_chars = sum(1 for c in title if ord(c) < 128)
            non_ascii_chars = len(title) - ascii_chars
            
            # If more than 30% non-ASCII, consider it non-English and transliterate
            total_chars = len(title.replace(' ', ''))  # Exclude spaces for calculation
            if total_chars > 0:
                non_ascii_ratio = non_ascii_chars / total_chars
                needs_transliteration = non_ascii_ratio > 0.3  # 30% threshold
            else:
                needs_transliteration = non_ascii_chars > 0
            
            # Step 2: If non-English, try to transliterate to English
            if needs_transliteration:
                try:
                    logger.info("🔄 Attempting transliteration for non-English text: %s", title[:50])
                    transliterated = self._transliterate_to_english(title)
                    if transliterated and transliterated.strip() and len(transliterated.strip()) > 3:
                        title = transliterated
                        logger.info("✅ Using transliterated title: %s", title[:50])
                    else:
                        logger.warning("⚠️ Transliteration failed or returned invalid result, using original with hash fallback")
                except Exception as e:
                    # Extra safety - catch any exception from transliteration
                    logger.warning("⚠️ Transliteration exception caught: %s, using original", str(e)[:100])
                    # Continue with original title
            
            # Step 3: Convert to lowercase
            slug = title.lower()
            
            # Step 4: Replace spaces with hyphens
            slug = re.sub(r'\s+', '-', slug)
            
            # Step 5: Remove non-alphanumeric characters (except hyphens)
            slug = re.sub(r'[^a-z0-9-]', '', slug)
            
            # Step 6: Remove leading or trailing hyphens
            slug = re.sub(r'^-+|-+$', '', slug)
            
            # Step 7: If slug is still empty, use hash-based fallback
            if not slug or slug.strip() == '':
                title_hash = hashlib.md5(original_title.encode('utf-8')).hexdigest()[:8]
                slug = f"story-{title_hash}"
                logger.warning("⚠️ Slug empty after processing, using hash fallback: %s", slug)
            
            return slug
            
        except Exception as e:
            # Ultimate fallback - should never reach here, but just in case
            logger.error("❌ Critical error in _slugify_title: %s", e, exc_info=True)
            fallback_hash = hashlib.md5(str(title).encode('utf-8')).hexdigest()[:8]
            return f"story-{fallback_hash}"
    
    def _transliterate_to_english(self, text: str) -> Optional[str]:
        """
        Translate ANY non-English language text to English using Azure OpenAI.
        Supports Hindi, Marathi, Tamil, Telugu, Bengali, Gujarati, Kannada, Punjabi, Urdu, Odia, Malayalam, and other languages.
        Returns proper English translation (not transliteration) for URL slug generation.
        Returns None if translation fails - never raises exceptions.
        This is non-blocking and will not break story creation if it fails.
        """
        logger = logging.getLogger(__name__)
        
        try:
            from app.core import get_settings
            
            settings = get_settings()
            
            # Check if Azure OpenAI is configured
            if not settings.azure_api or not settings.azure_api.api_key:
                logger.debug("Azure OpenAI not configured, skipping transliteration")
                return None
            
            # Limit text length for API call (reduced from 300 to 200 for faster calls)
            text_snippet = text[:200] if len(text) > 200 else text
            
            # Updated prompt to handle ALL languages - proper translation, not transliteration
            prompt = f"""Translate this text to English. Translate the meaning to proper English words, not just convert to Roman script.
The text may be in Hindi, Marathi, Tamil, Telugu, Bengali, Gujarati, Kannada, Punjabi, Urdu, Odia, Malayalam, or any other language.
Return only the English translation (use proper English words), no explanations:

{text_snippet}"""

            url = f"{settings.azure_api.endpoint.rstrip('/')}/openai/deployments/{settings.azure_api.deployment}/chat/completions"
            params = {"api-version": settings.azure_api.api_version}
            headers = {
                "api-key": settings.azure_api.api_key,
                "Content-Type": "application/json",
            }
            payload = {
                "messages": [
                    {"role": "system", "content": "You are a translator. Translate text from any language to proper English. Return only the translated English text, not transliteration."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 150,  # Reduced from 200
            }
            
            # Make API call with longer timeout and better error handling
            try:
                with httpx.Client(timeout=15.0) as client:  # Increased from 10.0 to 15.0
                    response = client.post(url, headers=headers, params=params, json=payload, timeout=15.0)
                    response.raise_for_status()
                    data = response.json()
                    
                    choices = data.get("choices", [])
                    if choices and choices[0].get("message"):
                        transliterated = choices[0]["message"].get("content", "").strip()
                        # Clean up any extra text that might be returned
                        transliterated = transliterated.split('\n')[0].strip()  # Take first line only
                        if transliterated and len(transliterated) > 0:
                            logger.info("✅ Transliteration successful: %s -> %s", text[:50], transliterated[:50])
                            return transliterated
                        else:
                            logger.warning("⚠️ Transliteration returned empty string")
            except httpx.TimeoutException:
                logger.warning("⚠️ Transliteration timeout (15s), using fallback")
                return None
            except httpx.HTTPStatusError as e:
                logger.warning("⚠️ Transliteration HTTP error %s: %s", e.response.status_code, e.response.text[:200] if hasattr(e.response, 'text') else str(e))
                return None
            except httpx.RequestError as e:
                logger.warning("⚠️ Transliteration request error: %s", str(e)[:200])
                return None
            
            return None
            
        except Exception as e:
            # Catch ALL exceptions to prevent breaking the story creation
            logger = logging.getLogger(__name__)
            logger.warning("⚠️ Transliteration failed with exception: %s (type: %s)", str(e)[:200], type(e).__name__)
            # Don't re-raise - return None to use fallback
            return None
