"""HTML template rendering service for generating AMP Story HTML from StoryRecord."""

from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path
from typing import Optional
from uuid import UUID

import httpx
from pydantic import HttpUrl

from app.domain.dto import ImageAsset, Mode, SlideBlock, SlideDeck, StoryRecord, VoiceAsset
from app.services.template_slide_generators import get_slide_generator
from app.services.model_clients import LanguageModel


class TemplateLoader:
    """Load HTML templates from file system, S3, or URL."""

    def __init__(
        self,
        template_base_path: Optional[Path] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._template_base_path = template_base_path or Path(__file__).parent.parent / "news_template"
        self._logger = logger or logging.getLogger(__name__)

    def load(self, template_key: str, mode: Mode, source: str = "file") -> str:
        """Load template from file system, S3, or URL."""
        # If source is explicitly "file", always load from local file system
        # (even if template_key looks like a URL - extract name and load locally)
        if source == "file":
            return self._load_from_file(template_key, mode)
        
        # Auto-detect source only if not explicitly "file"
        if template_key.startswith(("http://", "https://")):
            return self._load_from_url(template_key)
        elif template_key.startswith("s3://"):
            return self._load_from_s3(template_key)
        else:
            return self._load_from_file(template_key, mode)

    def _load_from_file(self, template_key: str, mode: Mode) -> str:
        """Load template from file system."""
        # If template_key is a URL, extract template name
        original_key = template_key
        if template_key.startswith(("http://", "https://")):
            # Extract filename from URL: "https://example.com/test-news-1.html" → "test-news-1"
            template_key = template_key.split("/")[-1].replace(".html", "")
            self._logger.info("Extracted template name '%s' from URL: %s", template_key, original_key)
        
        # Try mode-specific template directory first
        mode_dir = self._template_base_path.parent / f"{mode.value}_template"
        if not mode_dir.exists():
            # Fallback: try news_template if mode-specific dir doesn't exist
            fallback_dir = self._template_base_path.parent / "news_template"
            if fallback_dir.exists():
                mode_dir = fallback_dir
                self._logger.warning("Mode-specific template dir not found, using fallback: %s", mode_dir)
            else:
                mode_dir = self._template_base_path  # Last resort

        template_path = mode_dir / f"{template_key}.html"
        if not template_path.exists():
            # Try without extension
            template_path = mode_dir / template_key
            if not template_path.exists():
                raise FileNotFoundError(f"Template not found: {template_path} (mode: {mode.value})")

        self._logger.info("Loading template from file: %s (mode: %s)", template_path, mode.value)
        return template_path.read_text(encoding="utf-8")

    def _load_from_url(self, url: str) -> str:
        """Load template from HTTP/HTTPS URL."""
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url)
                response.raise_for_status()
                self._logger.info("Loaded template from URL: %s", url)
                return response.text
        except Exception as e:
            self._logger.error("Failed to load template from URL %s: %s", url, e)
            raise

    def _load_from_s3(self, s3_uri: str) -> str:
        """Load template from S3 (requires boto3)."""
        try:
            import boto3
            from urllib.parse import urlparse

            parsed = urlparse(s3_uri)
            bucket = parsed.netloc
            key = parsed.path.lstrip("/")

            s3_client = boto3.client("s3")
            response = s3_client.get_object(Bucket=bucket, Key=key)
            content = response["Body"].read().decode("utf-8")
            self._logger.info("Loaded template from S3: %s", s3_uri)
            return content
        except ImportError:
            self._logger.error("boto3 not installed, cannot load from S3")
            raise
        except Exception as e:
            self._logger.error("Failed to load template from S3 %s: %s", s3_uri, e)
            raise


class PlaceholderMapper:
    """Map StoryRecord data to HTML template placeholders."""

    def __init__(
        self,
        default_bg_image: str = "https://media.suvichaar.org/upload/polaris/polarisslide.png",
        default_cover_image: str = "https://media.suvichaar.org/upload/polaris/polariscover.png",
        organization: str = "Suvichaar",
        cdn_prefix_media: str = "https://media.suvichaar.org/",
        aws_bucket: str = "suvichaarapp",
        language_model: Optional[LanguageModel] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._default_bg_image = default_bg_image
        self._default_cover_image = default_cover_image
        self._organization = organization
        self._cdn_prefix_media = cdn_prefix_media.rstrip("/") + "/"
        self._aws_bucket = aws_bucket
        self._language_model = language_model
        self._logger = logger or logging.getLogger(__name__)

    def map(self, record: StoryRecord, image_source: Optional[str] = None) -> dict[str, str]:
        """Convert StoryRecord to placeholder dictionary."""
        placeholders: dict[str, str] = {}

        # Story title (from first slide or fallback)
        storytitle = ""
        if record.slide_deck.slides:
            storytitle = record.slide_deck.slides[0].text or ""
        placeholders["storytitle"] = storytitle[:180] if storytitle else "Web Story"

        # Page title
        placeholders["pagetitle"] = f"{storytitle} | Suvichaar" if storytitle else "Suvichaar Story"

        # Slide paragraphs (s1paragraph1, s2paragraph1, etc.)
        for idx, slide in enumerate(record.slide_deck.slides, start=1):
            placeholders[f"s{idx}paragraph1"] = slide.text or ""

        # Images - Special handling for News mode with no image_source
        if record.mode == Mode.NEWS and not record.image_assets:
            # News mode + no image_source → use default polariscover.png
            default_cover = self._default_cover_image
            placeholders["image0"] = default_cover
            # Generate resized URLs for portrait cover (720x1280) and thumbnail (300x300)
            placeholders["potraitcoverurl"] = self._generate_resized_url(default_cover, 720, 1280)
            placeholders["portraitcoverurl"] = placeholders["potraitcoverurl"]  # Alternative spelling
            placeholders["msthumbnailcoverurl"] = self._generate_resized_url(default_cover, 300, 300)
        elif image_source == "custom" and record.image_assets and len(record.image_assets) > 0:
            # Custom image_source → use custom image for cover slide too
            asset = record.image_assets[0]  # Cover image is at index 0
            # Generate portrait resolution URL (720x1280) for cover
            if hasattr(asset, "original_object_key") and asset.original_object_key:
                cover_url = self._generate_resized_url_from_s3_key(asset.original_object_key, 720, 1280)
                placeholders["image0"] = cover_url
                placeholders["potraitcoverurl"] = cover_url
                placeholders["portraitcoverurl"] = cover_url
                placeholders["msthumbnailcoverurl"] = self._generate_resized_url_from_s3_key(asset.original_object_key, 300, 300)
            elif asset.resized_variants:
                cover_url = str(asset.resized_variants[0])
                placeholders["image0"] = cover_url
                placeholders["potraitcoverurl"] = cover_url
                placeholders["portraitcoverurl"] = cover_url
                # Generate thumbnail from first variant or use default
                placeholders["msthumbnailcoverurl"] = self._generate_resized_url(cover_url, 300, 300)
            else:
                # Fallback to default
                default_cover = self._default_cover_image
                placeholders["image0"] = default_cover
                placeholders["potraitcoverurl"] = self._generate_resized_url(default_cover, 720, 1280)
                placeholders["portraitcoverurl"] = placeholders["potraitcoverurl"]
                placeholders["msthumbnailcoverurl"] = self._generate_resized_url(default_cover, 300, 300)
        else:
            # Normal flow - use image assets or defaults
            cover_url = self._get_image_url(record.image_assets, 0, self._default_cover_image)
            placeholders["image0"] = cover_url
            
            # If we have an image asset, generate resized URLs
            if record.image_assets and len(record.image_assets) > 0:
                asset = record.image_assets[0]
                # Try to get S3 key from original_object_key to generate resize URLs
                s3_key = asset.original_object_key if hasattr(asset, "original_object_key") else None
                if s3_key:
                    placeholders["potraitcoverurl"] = self._generate_resized_url_from_s3_key(s3_key, 720, 1280)
                    placeholders["portraitcoverurl"] = placeholders["potraitcoverurl"]
                    placeholders["msthumbnailcoverurl"] = self._generate_resized_url_from_s3_key(s3_key, 300, 300)
                else:
                    # Fallback to default resized URLs
                    placeholders["potraitcoverurl"] = self._generate_resized_url(cover_url, 720, 1280)
                    placeholders["portraitcoverurl"] = placeholders["potraitcoverurl"]
                    placeholders["msthumbnailcoverurl"] = self._generate_resized_url(cover_url, 300, 300)
            else:
                # No assets, use default with resizing
                placeholders["potraitcoverurl"] = self._generate_resized_url(cover_url, 720, 1280)
                placeholders["portraitcoverurl"] = placeholders["potraitcoverurl"]
                placeholders["msthumbnailcoverurl"] = self._generate_resized_url(cover_url, 300, 300)

        # Slide images (s1image1, s2image1, etc.)
        # Special handling for News mode:
        # - If image_source is blank/null → use default polarisslide.png for all slides
        # - If image_source is "custom" → use image_assets mapped to s1image1, s2image1, etc.
        # - Otherwise → use image_assets or default
        if record.mode == Mode.NEWS and (image_source is None or image_source == ""):
            # News mode + blank image_source → use default polarisslide.png for all slides
            for idx in range(1, len(record.slide_deck.slides) + 1):
                placeholders[f"s{idx}image1"] = self._default_bg_image
        elif image_source == "custom" and record.image_assets:
            # Custom image_source → map image_assets to s1image1, s2image1, etc.
            # Note: image_assets are indexed by slide order (cover is index 0, first middle slide is index 1, etc.)
            for idx in range(1, len(record.slide_deck.slides) + 1):
                # s1image1 uses image_assets[0] (cover), s2image1 uses image_assets[1], etc.
                asset_idx = idx - 1
                if asset_idx < len(record.image_assets):
                    asset = record.image_assets[asset_idx]
                    # For custom images, generate portrait resolution (720x1280) from S3 key
                    if hasattr(asset, "original_object_key") and asset.original_object_key:
                        # Generate portrait resolution URL (720x1280) from S3 key
                        placeholders[f"s{idx}image1"] = self._generate_resized_url_from_s3_key(
                            asset.original_object_key, 720, 1280
                        )
                    elif asset.resized_variants:
                        # Fallback to first resized variant if available
                        placeholders[f"s{idx}image1"] = str(asset.resized_variants[0])
                    elif hasattr(asset, "original_object_key") and asset.original_object_key:
                        # Generate URL from S3 key (no resize)
                        placeholders[f"s{idx}image1"] = f"{self._cdn_prefix_media}{asset.original_object_key}"
                    else:
                        placeholders[f"s{idx}image1"] = self._default_bg_image
                else:
                    placeholders[f"s{idx}image1"] = self._default_bg_image
        else:
            # Normal flow - use image_assets or default (for both News and Curious)
            for idx in range(1, len(record.slide_deck.slides) + 1):
                # For curious mode, image_assets[0] is cover, image_assets[1] is slide 2, etc.
                # So s1image1 = image_assets[0], s2image1 = image_assets[1], etc.
                asset_idx = idx - 1  # Convert slide number to asset index
                if asset_idx < len(record.image_assets):
                    asset = record.image_assets[asset_idx]
                    # For Curious mode, generate portrait resolution (720x1280) from S3 key
                    if record.mode == Mode.CURIOUS and hasattr(asset, "original_object_key") and asset.original_object_key:
                        # Generate portrait resolution URL (720x1280) from S3 key for Curious mode
                        placeholders[f"s{idx}image1"] = self._generate_resized_url_from_s3_key(
                            asset.original_object_key, 720, 1280
                        )
                    elif asset.resized_variants:
                        placeholders[f"s{idx}image1"] = str(asset.resized_variants[0])
                    elif hasattr(asset, "original_object_key") and asset.original_object_key:
                        # Generate URL from S3 key (no resize)
                        placeholders[f"s{idx}image1"] = f"{self._cdn_prefix_media}{asset.original_object_key}"
                    else:
                        placeholders[f"s{idx}image1"] = self._default_bg_image
                else:
                    placeholders[f"s{idx}image1"] = self._default_bg_image

        # Audio URLs
        # s1audio1 for cover, s2audio1 for slide 2, etc.
        placeholders["storytitle_audiourl"] = self._get_audio_url(record.voice_assets, 0)
        for idx in range(1, len(record.slide_deck.slides) + 1):
            # s1audio1 = voice_assets[0] (cover), s2audio1 = voice_assets[1] (slide 2), etc.
            audio_idx = idx - 1  # Convert slide number to audio index
            placeholders[f"s{idx}audio_url"] = self._get_audio_url(record.voice_assets, audio_idx)
            placeholders[f"s{idx}audio1"] = placeholders[f"s{idx}audio_url"]  # Alias

        # Metadata
        placeholders["metadescription"] = self._generate_meta_description(record)
        placeholders["metakeywords"] = self._generate_meta_keywords(record)
        placeholders["category"] = record.category or "News"
        
        # Normalize language to en-US or hi-IN format
        lang = record.input_language or "en"
        if lang == "en" or lang.startswith("en"):
            placeholders["lang"] = "en-US"
        elif lang == "hi" or lang.startswith("hi"):
            placeholders["lang"] = "hi-IN"
        else:
            # If already in correct format (en-US, hi-IN) or other format, use as-is
            placeholders["lang"] = lang if "-" in lang else f"{lang}-US"
        
        # Content type: News for News mode, Article for Curious mode
        placeholders["contenttype"] = "News" if record.mode == Mode.NEWS else "Article"

        # URLs
        placeholders["canurl"] = str(record.canurl) if record.canurl else ""
        placeholders["canurl1"] = str(record.canurl1) if record.canurl1 else ""

        # Timestamps - ISO 8601 format with Z suffix (e.g., "2025-01-21T10:30:00.000000Z")
        iso_time = record.created_at.isoformat() + "Z"
        placeholders["publishedtime"] = iso_time
        placeholders["modifiedtime"] = iso_time

        # Branding
        logo_base = "https://media.suvichaar.org/filters:resize"
        placeholders["sitelogo32x32"] = f"{logo_base}/32x32/media/brandasset/suvichaariconblack.png"
        placeholders["sitelogo192x192"] = f"{logo_base}/192x192/media/brandasset/suvichaariconblack.png"
        placeholders["sitelogo180x180"] = f"{logo_base}/180x180/media/brandasset/suvichaariconblack.png"
        placeholders["sitelogo144x144"] = f"{logo_base}/144x144/media/brandasset/suvichaariconblack.png"
        placeholders["sitelogo96x96"] = f"{logo_base}/96x96/media/brandasset/suvichaariconblack.png"
        placeholders["organization"] = self._organization
        placeholders["publisher"] = self._organization
        placeholders["publisherlogosrc"] = "https://media.suvichaar.org/media/designasset/brandasset/icons/quaternary/whitequaternaryicon.png"

        # Additional placeholders (optional)
        placeholders["user"] = "Suvichaar Team"
        placeholders["userprofileurl"] = "https://suvichaar.org"
        placeholders["prevstorytitle"] = ""
        placeholders["prevstorylink"] = ""
        placeholders["nextstorytitle"] = ""
        placeholders["nextstorylink"] = ""
        # msthumbnailcoverurl is already set above in Images section

        return placeholders

    def _get_image_url(self, image_assets: list[ImageAsset], index: int, default: str) -> str:
        """Get image URL from assets, with fallback."""
        if index < len(image_assets):
            asset = image_assets[index]
            if asset.resized_variants:
                return str(asset.resized_variants[0])
            # Fallback: try to construct URL from original_object_key
            # This would require CDN base URL, for now return default
        return default

    def _get_audio_url(self, voice_assets: list[VoiceAsset], index: int) -> str:
        """Get audio URL from assets."""
        if index < len(voice_assets):
            return str(voice_assets[index].audio_url)
        return ""

    def _generate_resized_url(self, image_url: str, width: int, height: int) -> str:
        """Generate CloudFront resize URL from image URL using base64 template."""
        # If it's already a default URL, try to extract S3 key or use as-is
        # For default polariscover.png, we can still generate resize URL
        try:
            # Extract S3 key from URL if it's a CDN URL
            # For default images, we might need to construct the S3 key
            # For now, if it's a media.suvichaar.org URL, try to extract path
            if "media.suvichaar.org" in image_url:
                # Extract the path after the domain
                from urllib.parse import urlparse
                parsed = urlparse(image_url)
                s3_key = parsed.path.lstrip("/")
                return self._generate_resized_url_from_s3_key(s3_key, width, height)
            # If we can't extract, return original (fallback)
            return image_url
        except Exception as e:
            self._logger.warning("Failed to generate resized URL: %s", e)
            return image_url

    def _generate_resized_url_from_s3_key(self, s3_key: str, width: int, height: int) -> str:
        """Generate CloudFront resize URL from S3 key using base64 template."""
        try:
            template = {
                "bucket": self._aws_bucket,
                "key": s3_key,
                "edits": {
                    "resize": {
                        "width": width,
                        "height": height,
                        "fit": "cover",  # Cover fit to maintain aspect ratio
                    }
                },
            }
            encoded = base64.urlsafe_b64encode(json.dumps(template).encode()).decode()
            resized_url = f"{self._cdn_prefix_media}{encoded}"
            return resized_url
        except Exception as e:
            self._logger.warning("Failed to generate resized URL from S3 key: %s", e)
            # Fallback: try to construct a simple URL
            return f"{self._cdn_prefix_media}{s3_key}"

    def _generate_meta_description(self, record: StoryRecord) -> str:
        """Generate SEO meta description from story content using LLM if available, else fallback."""
        # Try LLM-based generation first
        if self._language_model and record.slide_deck.slides:
            try:
                story_title = record.slide_deck.slides[0].text or "Web Story"
                # Collect slide content for context (use first 5 slides)
                slide_contents = []
                for idx, slide in enumerate(record.slide_deck.slides[:5], start=1):
                    if slide.text:
                        slide_contents.append(f"Slide {idx}: {slide.text[:200]}")
                
                slides_text = "\n".join(slide_contents) if slide_contents else "No content available"
                language = record.input_language or "en"
                lang_code = language.split("-")[0] if "-" in language else language
                
                system_prompt = "You are an expert SEO assistant. Generate concise, engaging meta descriptions for web stories. Always respond with just the meta description text, no quotes or labels."
                user_prompt = f"""Generate a short SEO-friendly meta description (max 160 characters) for a web story.

Title: {story_title}
Content:
{slides_text}

Language: {lang_code}

Requirements:
- Maximum 160 characters
- Engaging and informative
- Include key topics
- Write in {lang_code} language
- No quotes or special formatting
- Just the description text, nothing else

Meta Description:"""

                meta_desc = self._language_model.complete(system_prompt, user_prompt)
                # Clean up the response (remove quotes, extra whitespace, labels)
                meta_desc = meta_desc.strip()
                # Remove quotes
                meta_desc = meta_desc.strip('"').strip("'")
                # Remove common prefixes/labels
                for prefix in ["Meta Description:", "Description:", "Description"]:
                    if meta_desc.startswith(prefix):
                        meta_desc = meta_desc[len(prefix):].strip().strip(":").strip()
                # Ensure it's within 160 characters
                if len(meta_desc) > 160:
                    meta_desc = meta_desc[:157] + "..."
                if meta_desc and len(meta_desc) > 20:  # Valid response
                    self._logger.info("Generated meta description using LLM: %s", meta_desc[:80])
                    return meta_desc
            except Exception as e:
                self._logger.warning("LLM meta description generation failed, using fallback: %s", e)
        
        # Fallback to simple text extraction
        if record.slide_deck.slides:
            first_slide = record.slide_deck.slides[0].text or ""
            if len(first_slide) > 160:
                return first_slide[:157] + "..."
            return first_slide
        return f"Explore this {record.category or 'story'} on Suvichaar."

    def _generate_meta_keywords(self, record: StoryRecord) -> str:
        """Generate SEO keywords using LLM if available, else fallback."""
        # Try LLM-based generation first
        if self._language_model and record.slide_deck.slides:
            try:
                story_title = record.slide_deck.slides[0].text or "Web Story"
                # Collect slide content for context (use first 5 slides)
                slide_contents = []
                for idx, slide in enumerate(record.slide_deck.slides[:5], start=1):
                    if slide.text:
                        slide_contents.append(f"Slide {idx}: {slide.text[:200]}")
                
                slides_text = "\n".join(slide_contents) if slide_contents else "No content available"
                language = record.input_language or "en"
                lang_code = language.split("-")[0] if "-" in language else language
                category = record.category or "Story"
                
                system_prompt = "You are an expert SEO assistant. Generate relevant keywords for web stories. Always respond with just comma-separated keywords, no quotes or labels."
                user_prompt = f"""Generate 8-12 relevant SEO keywords (comma-separated) for a web story.

Title: {story_title}
Category: {category}
Content:
{slides_text}

Language: {lang_code}

Requirements:
- 8-12 keywords
- Comma-separated
- Relevant to the content
- Include category and topic keywords
- Mix of broad and specific terms
- Write in {lang_code} language
- Just the keywords, nothing else

Keywords:"""

                keywords = self._language_model.complete(system_prompt, user_prompt)
                # Clean up the response (remove quotes, extra whitespace, labels)
                keywords = keywords.strip()
                # Remove quotes
                keywords = keywords.strip('"').strip("'")
                # Remove common prefixes/labels
                for prefix in ["Keywords:", "Keywords", "Meta Keywords:", "Meta Keywords", "Keyword:"]:
                    if keywords.startswith(prefix):
                        keywords = keywords[len(prefix):].strip().strip(":").strip()
                # Ensure reasonable length (max 200 chars for keywords)
                if len(keywords) > 200:
                    keywords = keywords[:200].rsplit(",", 1)[0]  # Cut at last comma before 200 chars
                if keywords and len(keywords) > 5:  # Valid response
                    self._logger.info("Generated meta keywords using LLM: %s", keywords[:100])
                    return keywords
            except Exception as e:
                self._logger.warning("LLM meta keywords generation failed, using fallback: %s", e)
        
        # Fallback to simple keyword generation
        keywords = [record.category or "story"]
        if record.input_language:
            keywords.append(record.input_language)
        keywords.append("web story")
        if record.mode == Mode.NEWS:
            keywords.append("news")
        elif record.mode == Mode.CURIOUS:
            keywords.append("education")
            keywords.append("curious")
        return ", ".join(keywords)


class HTMLTemplateRenderer:
    """Render HTML templates from StoryRecord."""

    def __init__(
        self,
        template_base_path: Optional[Path] = None,
        template_loader: Optional[TemplateLoader] = None,
        placeholder_mapper: Optional[PlaceholderMapper] = None,
        language_model: Optional[LanguageModel] = None,
        cdn_prefix_media: str = "https://media.suvichaar.org/",
        aws_bucket: str = "suvichaarapp",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._loader = template_loader or TemplateLoader(template_base_path=template_base_path)
        self._mapper = placeholder_mapper or PlaceholderMapper(
            cdn_prefix_media=cdn_prefix_media,
            aws_bucket=aws_bucket,
            language_model=language_model,
        )
        self._logger = logger or logging.getLogger(__name__)

    def render(
        self,
        record: StoryRecord,
        template_key: str,
        template_source: str = "file",
        image_source: Optional[str] = None,
    ) -> str:
        """Render HTML template from StoryRecord."""
        # 1. Load template
        template_html = self._loader.load(template_key, record.mode, template_source)

        # 2. Map StoryRecord to placeholders (pass image_source for proper image handling)
        placeholders = self._mapper.map(record, image_source=image_source)

        # 3. Replace basic placeholders
        filled_html = self._replace_placeholders(template_html, placeholders)

        # 4. Generate slides dynamically (pass template_key and image_source for template-specific generation)
        slides_html = self._generate_all_slides(record, template_key, placeholders, image_source=image_source)

        # 5. Insert slides at <!--INSERT_SLIDES_HERE-->
        filled_html = filled_html.replace("<!--INSERT_SLIDES_HERE-->", slides_html)

        # 6. Cleanup (remove stray curly braces from URLs)
        filled_html = self._cleanup_urls(filled_html)

        return filled_html

    def _replace_placeholders(self, template: str, data: dict[str, str]) -> str:
        """Replace {{key}} placeholders with values."""
        for key, value in data.items():
            # Clean markdown from values before replacing
            cleaned_value = self._clean_markdown(str(value))
            template = template.replace(f"{{{{{key}}}}}", cleaned_value)
            template = template.replace(f"{{{{{key}|safe}}}}", cleaned_value)
        return template

    def _clean_markdown(self, text: str) -> str:
        """Remove markdown formatting from text."""
        if not text:
            return ""
        # Remove **bold**
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        # Remove *italic*
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        # Remove # headers
        text = re.sub(r'#+\s*', '', text)
        # Remove `code blocks`
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # Remove [links](url)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        return text.strip()

    def _generate_all_slides(
        self, 
        record: StoryRecord, 
        template_key: str, 
        placeholders: dict[str, str],
        image_source: Optional[str] = None,
    ) -> str:
        """Generate slides based on slide_count using template-specific generator."""
        # For curious-template-1, it's a fixed 7-slide template, so don't generate dynamic slides
        if record.mode == Mode.CURIOUS and template_key == "curious-template-1":
            self._logger.info("curious-template-1 is a fixed template with all slides, skipping dynamic slide generation")
            return ""  # Return empty - template already has all slides hardcoded
        
        slides = []
        default_bg = "https://media.suvichaar.org/upload/polaris/polarisslide.png"

        # Get template-specific slide generator
        slide_generator = get_slide_generator(template_key)
        self._logger.debug("Using slide generator for template: %s", template_key)

        # Limit slides based on slide_count
        # Template structure:
        #   1. Cover slide (uses {{storytitle}} from slide_deck.slides[0]) - already in template
        #   2. Middle slides (inserted at <!--INSERT_SLIDES_HERE-->) - we generate these
        #   3. CTA slide - already in template
        # So if slide_count = 4:
        #   - Cover: 1 (template)
        #   - Middle: 4 - 2 = 2 slides (we generate)
        #   - CTA: 1 (template)
        #   Total = 4
        # We skip slide[0] (used in cover) and generate slide[1] to slide[slide_count-2]
        middle_slides_count = max(0, record.slide_count - 2)  # Exclude cover (1) and CTA (1)
        
        # Skip first slide (used in cover), take next middle_slides_count slides
        if len(record.slide_deck.slides) > 1:
            slides_to_generate = record.slide_deck.slides[1:1+middle_slides_count] if middle_slides_count > 0 else []
        else:
            slides_to_generate = []
        
        self._logger.debug("Generating %d slides (requested: %d, available: %d)", 
                          len(slides_to_generate), record.slide_count, len(record.slide_deck.slides))

        for idx, slide_block in enumerate(slides_to_generate, start=1):
            # Clean markdown from slide text
            clean_text = self._clean_markdown(slide_block.text or "")
            
            # Get image for this slide
            # Priority:
            # 1. If custom image_source, use placeholder s{idx}image1
            # 2. If blank image_source in news mode, use default polarisslide.png
            # 3. Otherwise, use image_assets or default
            slide_num = idx + 1  # idx starts at 1, but slides are numbered from 2 (s2image1, s3image1, etc.)
            image_url = default_bg
            
            if image_source == "custom":
                # Use placeholder s{slide_num}image1 (e.g., s2image1, s3image1)
                placeholder_key = f"s{slide_num}image1"
                if placeholder_key in placeholders:
                    image_url = placeholders[placeholder_key]
                else:
                    # Fallback to image_assets if placeholder not found
                    # idx=1 (first middle slide) → image_assets[1], idx=2 → image_assets[2], etc.
                    asset_idx = idx  # idx already starts at 1, so use directly (skip cover at index 0)
                    if asset_idx < len(record.image_assets):
                        img_asset = record.image_assets[asset_idx]
                        if img_asset.resized_variants:
                            image_url = str(img_asset.resized_variants[0])
            elif record.mode == Mode.NEWS and (image_source is None or image_source == ""):
                # News mode + blank image_source → use default polarisslide.png
                image_url = default_bg
            else:
                # Normal flow - use image_assets or default
                # idx=1 (first middle slide) → image_assets[1], idx=2 → image_assets[2], etc.
                asset_idx = idx  # idx already starts at 1, so use directly (skip cover at index 0)
                if asset_idx < len(record.image_assets):
                    img_asset = record.image_assets[asset_idx]
                    if img_asset.resized_variants:
                        image_url = str(img_asset.resized_variants[0])
                    else:
                        image_url = default_bg

            # Get audio for this slide
            # voice_assets are now generated per slide in order:
            # voice_assets[0] = cover slide (slide_deck.slides[0])
            # voice_assets[1] = first middle slide (slide_deck.slides[1])
            # voice_assets[2] = second middle slide (slide_deck.slides[2])
            # etc.
            # slides_to_generate[0] = slide_deck.slides[1] (first middle) → should use voice_assets[1]
            # slides_to_generate[1] = slide_deck.slides[2] (second middle) → should use voice_assets[2]
            # So: idx=1 → voice_assets[1], idx=2 → voice_assets[2]
            audio_url = ""
            audio_idx = idx  # idx starts at 1, which corresponds to voice_assets[1] (first middle slide)
            if audio_idx < len(record.voice_assets):
                audio_url = str(record.voice_assets[audio_idx].audio_url)

            # Generate slide HTML using template-specific generator
            slide_html = slide_generator.generate_slide(
                paragraph=clean_text,
                audio_url=audio_url,
                background_image_url=image_url,
                slide_id=f"slide-{idx}",
            )
            slides.append(slide_html)

        return "\n".join(slides)

    def _cleanup_urls(self, html: str) -> str:
        """Remove stray curly braces from URLs."""
        # Remove curly braces around URLs in various contexts
        html = re.sub(r'\{(\s*https?://[^\s"\'<>}]+)\}', r"\1", html)
        html = re.sub(r'(\s*https?://[^\s"\'<>}]+)\}', r"\1", html)
        html = re.sub(r'\{(\s*https?://[^\s"\'<>}]+)', r"\1", html)

        # Clean up in attribute values
        html = re.sub(
            r'(href|src|content|url|poster-portrait-src|publisher-logo-src)="\{([^"]+)\}"',
            r'\1="\2"',
            html,
        )
        html = re.sub(
            r"(href|src|content|url|poster-portrait-src|publisher-logo-src)='\{([^']+)\}'",
            r"\1='\2'",
            html,
        )

        # Clean up JSON-LD script content
        html = re.sub(r'"\{([^"]+)\}"', r'"\1"', html)
        html = re.sub(r':\s*"\{([^"]+)\}"', r': "\1"', html)

        return html

    def save_html_to_file(
        self,
        html_content: str,
        story_id: UUID,
        output_dir: Optional[Path] = None,
    ) -> Path:
        """Save rendered HTML to a local file."""
        try:
            if output_dir is None:
                output_dir = Path("output")
            
            # Create directory if it doesn't exist (handles Windows paths properly)
            output_dir = Path(output_dir).resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
            
            html_filename = f"{story_id}.html"
            output_path = output_dir / html_filename
            
            # Write file with proper error handling
            output_path.write_text(html_content, encoding="utf-8")
            self._logger.info("Saved HTML to file: %s", output_path)
            return output_path
        except PermissionError as e:
            self._logger.error("Permission denied saving HTML file: %s", e)
            raise
        except OSError as e:
            self._logger.error("OS error saving HTML file: %s", e)
            raise
        except Exception as e:
            self._logger.error("Failed to save HTML to file: %s", e, exc_info=True)
            raise

    def upload_html(
        self,
        html_content: str,
        story_id: UUID,
        template_key: str,
        bucket: str,
        prefix: str = "",
        cdn_base: str = "",
        aws_access_key: Optional[str] = None,
        aws_secret_key: Optional[str] = None,
        aws_region: Optional[str] = None,
    ) -> str:
        """Upload rendered HTML to S3 and return CDN URL."""
        try:
            import boto3

            s3_client = None
            if aws_access_key and aws_secret_key:
                s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region or "us-east-1",
                )
            else:
                s3_client = boto3.client("s3", region_name=aws_region or "us-east-1")

            html_filename = f"{story_id}.html"
            s3_key = f"{prefix.rstrip('/')}/{html_filename}" if prefix else html_filename

            s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=html_content.encode("utf-8"),
                ContentType="text/html; charset=utf-8",
            )

            self._logger.info("Uploaded HTML to s3://%s/%s", bucket, s3_key)

            if cdn_base:
                cdn_url = f"{cdn_base.rstrip('/')}/{s3_key}"
                return cdn_url
            return f"https://{bucket}.s3.amazonaws.com/{s3_key}"

        except ImportError:
            self._logger.warning("boto3 not installed, HTML upload skipped")
            return ""
        except Exception as e:
            self._logger.error("Failed to upload HTML to S3: %s", e)
            return ""


__all__ = ["HTMLTemplateRenderer", "TemplateLoader", "PlaceholderMapper"]

