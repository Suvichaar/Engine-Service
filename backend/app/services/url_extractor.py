"""URL content extraction service using Serper API."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional
from html import unescape
from urllib.parse import urlparse, urlunparse

import requests

from app.domain.dto import SemanticChunk


class ArticleExtractionResult:
    """Result of article extraction from URL."""

    def __init__(
        self,
        title: str,
        text: str,
        summary: str,
        top_image_url: Optional[str] = None,
        images: Optional[list[str]] = None,
    ):
        self.title = title
        self.text = text
        self.summary = summary
        self.top_image_url = top_image_url
        self.images = images or []


class URLContentExtractor:
    """Extract article content and images from URLs using Serper API."""

    def __init__(self, logger: Optional[logging.Logger] = None, mode: Optional[str] = None, api_key: Optional[str] = None):
        self._logger = logger or logging.getLogger(__name__)
        self._mode = mode  # Reserved for request-scoped extraction context.
        # Get API key from parameter, environment variable, or raise error
        # Priority: parameter > environment variable > error
        self._serper_api_key = api_key or os.getenv("SERPER_API_KEY")
        if not self._serper_api_key:
            raise ValueError(
                "Serper API key not provided. Set SERPER_API_KEY environment variable "
                "or pass api_key parameter to URLContentExtractor."
            )

    def _normalize_url(self, url: str) -> str:
        """Strip tracking query params and fragments before extraction."""
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    def _extract_with_serper(self, url: str) -> Optional[ArticleExtractionResult]:
        """Extract article content from URL using Serper API."""
        headers = {
            "X-API-KEY": self._serper_api_key,
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                "https://scrape.serper.dev/",
                json={"url": url},
                headers=headers,
                timeout=30,
            )
            if response.status_code != 200:
                self._logger.error(
                    "❌ Serper API returned status %d: %s",
                    response.status_code,
                    response.text[:200],
                )
                return None
            response_data = response.json()
        except requests.RequestException as exc:
            self._logger.error("❌ Serper HTTP request failed: %s", exc)
            return None

        title = response_data.get("title", "")
        text = response_data.get("text", "") or response_data.get("bodyText", "") or response_data.get("content", "")
        images = response_data.get("images", [])
        top_image_url = images[0] if images else None

        if not text and "html" in response_data:
            html_content = response_data.get("html", "")
            html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', html_content)
            text = re.sub(r'\s+', ' ', text).strip()

        if not title:
            title = "Untitled Article"
        if not text:
            text = "No article content available."

        summary = self._build_summary(text)
        return ArticleExtractionResult(
            title=title.strip(),
            text=text.strip(),
            summary=summary.strip(),
            top_image_url=top_image_url,
            images=images[:10] if images else [],
        )

    def _extract_with_newspaper(self, url: str) -> Optional[ArticleExtractionResult]:
        """Fallback extractor for when Serper returns mismatched or insufficient content."""
        try:
            from newspaper import Article
        except ImportError as exc:
            self._logger.warning("newspaper3k import failed (%s), using built-in HTML fallback", exc)
            return self._extract_with_basic_html(url)

        try:
            article = Article(url)
            article.download()
            article.parse()
            try:
                article.nlp()
            except Exception:
                pass

            text = (article.text or "").strip()
            title = (article.title or "").strip() or "Untitled Article"
            summary = (getattr(article, "summary", "") or "").strip() or self._build_summary(text or title)
            top_image_url = getattr(article, "top_image", None)
            images = list(getattr(article, "images", []) or [])

            if not text and not title:
                return None

            return ArticleExtractionResult(
                title=title,
                text=text or title,
                summary=summary,
                top_image_url=top_image_url,
                images=images[:10],
            )
        except Exception as exc:
            self._logger.warning("Direct article extraction failed for %s: %s", url, exc)
            return self._extract_with_basic_html(url)

    def _extract_with_basic_html(self, url: str) -> Optional[ArticleExtractionResult]:
        """Minimal dependency-free fallback for article pages."""
        try:
            response = requests.get(
                url,
                timeout=30,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/123.0.0.0 Safari/537.36"
                    )
                },
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            self._logger.warning("Basic HTML extraction request failed for %s: %s", url, exc)
            return None

        html = response.text or ""
        if not html.strip():
            return None

        title = self._extract_html_title(html) or "Untitled Article"
        text = self._extract_html_text(html)
        summary = self._build_summary(text or title)
        top_image_url = self._extract_og_image(html)

        if not text and not title:
            return None

        return ArticleExtractionResult(
            title=title.strip(),
            text=(text or title).strip(),
            summary=summary.strip(),
            top_image_url=top_image_url,
            images=[top_image_url] if top_image_url else [],
        )

    def _extract_html_title(self, html: str) -> str:
        patterns = [
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']',
            r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\'](.*?)["\']',
            r"<title[^>]*>(.*?)</title>",
            r'<h1[^>]*>(.*?)</h1>',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
            if match:
                return self._clean_html_text(match.group(1))
        return ""

    def _extract_og_image(self, html: str) -> Optional[str]:
        match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](.*?)["\']',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            return unescape(match.group(1).strip())
        return None

    def _extract_html_text(self, html: str) -> str:
        candidate_blocks = re.findall(
            r"<(?:article|main|section|div)[^>]*>(.*?)</(?:article|main|section|div)>",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        blocks_to_try = candidate_blocks if candidate_blocks else [html]

        best_text = ""
        for block in blocks_to_try:
            cleaned = re.sub(r"<script[^>]*>.*?</script>", " ", block, flags=re.IGNORECASE | re.DOTALL)
            cleaned = re.sub(r"<style[^>]*>.*?</style>", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
            cleaned = re.sub(r"<noscript[^>]*>.*?</noscript>", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
            cleaned = re.sub(r"<svg[^>]*>.*?</svg>", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
            cleaned = re.sub(r"</?(p|br|li|h1|h2|h3|h4|blockquote)[^>]*>", "\n", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"<[^>]+>", " ", cleaned)
            cleaned = self._clean_html_text(cleaned)
            if len(cleaned) > len(best_text):
                best_text = cleaned

        return best_text

    def _clean_html_text(self, text: str) -> str:
        text = unescape(text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _build_summary(self, text: str) -> str:
        sentences = re.split(r'[.!?]\s+', text)
        summary_parts = []
        for sent in sentences[:3]:
            if len(" ".join(summary_parts) + " " + sent) <= 300:
                summary_parts.append(sent)
            else:
                break
        return " ".join(summary_parts) if summary_parts else text[:300]

    def _is_valid_extraction(self, source_url: str, title: str, text: str) -> bool:
        """Validate extracted article content against the article URL."""
        url_lower = source_url.lower()
        title_lower = title.lower()
        text_lower = (text[:500].lower() if text else "")

        self._logger.warning("🔍 VALIDATION CHECK: URL=%s, Title=%s", url_lower[:100], title_lower[:100])

        parsed = urlparse(source_url)
        path_parts = parsed.path.split('/')
        url_keywords = []
        skip_words = {
            'article', 'news', 'story', 'com', 'org', 'www', 'http', 'https', 'indianexpress',
            'sports', 'cities', 'entertainment', 'technology', 'business', 'politics', 'world',
            'local', 'health', 'science', 'education', 'lifestyle', 'opinion', 'editorial', 'html',
            'quickest', 'latest', 'today', 'match', 'season', 'update'
        }

        for part in path_parts:
            part = part.split('?')[0].split('#')[0].strip()
            if not part or part == '/':
                continue
            words = part.split('-')
            for word in words:
                if len(word) > 3 and word not in skip_words and not word.isdigit():
                    url_keywords.append(word)

        content_to_check = f"{title} {text[:1000]}"
        is_hindi_or_unicode = any(
            '\u0900' <= char <= '\u097F' or
            '\u0980' <= char <= '\u09FF' or
            '\u0A00' <= char <= '\u0A7F' or
            '\u0A80' <= char <= '\u0AFF' or
            '\u0B00' <= char <= '\u0B7F' or
            '\u0B80' <= char <= '\u0BFF' or
            '\u0C00' <= char <= '\u0C7F' or
            '\u0C80' <= char <= '\u0CFF' or
            '\u0D00' <= char <= '\u0D7F'
            for char in content_to_check
        )
        text_is_empty = not text or len(text.strip()) < 50 or "no article content" in text.lower()

        if is_hindi_or_unicode:
            self._logger.warning("🌐 Detected Hindi/Unicode content - validation will be skipped")
        if text_is_empty:
            self._logger.warning("⚠️ Text is empty or too short - using relaxed validation")

        if not url_keywords:
            return True

        top_url_keywords = sorted(set(url_keywords), key=len, reverse=True)[:10]
        keyword_expansions = {}
        for kw in top_url_keywords:
            expansions = [kw]
            if kw == 'rbi':
                expansions.extend(['reserve bank', 'reserve bank of india'])
            elif kw == 'gst':
                expansions.extend(['goods and services tax', 'goods services tax'])
            elif kw in {'q1', 'q2', 'q3', 'q4'}:
                quarter_map = {
                    'q1': ['first quarter', 'quarter 1'],
                    'q2': ['second quarter', 'quarter 2'],
                    'q3': ['third quarter', 'quarter 3'],
                    'q4': ['fourth quarter', 'quarter 4'],
                }
                expansions.extend([kw, *quarter_map[kw]])
            keyword_expansions[kw] = expansions

        title_matches = 0
        text_matches = 0
        unique_matches = set()
        for kw in top_url_keywords:
            expansions = keyword_expansions.get(kw, [kw])
            if any(exp in title_lower for exp in expansions):
                title_matches += 1
            if any(exp in text_lower[:2000] for exp in expansions):
                text_matches += 1
            if any(exp in title_lower or exp in text_lower[:2000] for exp in expansions):
                unique_matches.add(kw)

        actual_unique_matches = len(unique_matches)
        match_ratio = actual_unique_matches / len(top_url_keywords) if top_url_keywords else 0

        if is_hindi_or_unicode:
            min_required_matches = 0
            match_ratio_threshold = 0.0
        elif text_is_empty:
            min_required_matches = 1
            match_ratio_threshold = 0.05
        else:
            sports_keywords = {'cricket', 'ipl', 'football', 'tennis', 'hockey', 'rohit', 'sharma', 'rickelton'}
            business_keywords = {'finance', 'economic', 'rbi', 'gdp', 'gst', 'credit', 'growth', 'policy', 'rate', 'q1', 'q2', 'q3', 'q4'}
            is_sports_article = any(sk in url_lower or sk in title_lower for sk in sports_keywords)
            is_business_article = any(bk in url_lower or bk in title_lower for bk in business_keywords)

            if is_sports_article:
                min_required_matches = 1
                match_ratio_threshold = 0.05
                self._logger.warning("🏏 Sports article detected - using relaxed validation")
            elif is_business_article:
                min_required_matches = max(1, min(2, len(top_url_keywords) // 4))
                match_ratio_threshold = 0.05
                self._logger.warning("📊 Business article detected - using relaxed validation")
            else:
                min_required_matches = max(2, min(3, len(top_url_keywords) // 3))
                match_ratio_threshold = 0.1

        self._logger.warning("🔍 VALIDATION: URL keywords=%s", top_url_keywords[:5])
        self._logger.warning(
            "🔍 VALIDATION: Title matches=%d, Text matches=%d, Unique matches=%d/%d",
            title_matches, text_matches, actual_unique_matches, len(top_url_keywords),
        )
        self._logger.warning(
            "🔍 VALIDATION: Match ratio=%.1f%%, Required=%d unique matches (threshold=%.1f%%)",
            match_ratio * 100, min_required_matches, match_ratio_threshold * 100,
        )

        if len(top_url_keywords) >= 3 and not is_hindi_or_unicode:
            if match_ratio < match_ratio_threshold or actual_unique_matches < min_required_matches:
                self._logger.error("❌ ===== IMMEDIATE REJECTION: URL-CONTENT MISMATCH =====")
                self._logger.error("❌ URL: %s", source_url)
                self._logger.error("❌ Extracted Title: %s", title[:100])
                self._logger.error("❌ Extracted Text Preview: %s", text[:300] if text else "None")
                self._logger.error("❌ URL keywords: %s", top_url_keywords)
                self._logger.error(
                    "❌ Title matches: %d, Text matches: %d, Unique matches: %d",
                    title_matches, text_matches, actual_unique_matches,
                )
                return False

        return True

    def extract(self, url: str) -> Optional[ArticleExtractionResult]:
        """Extract article content from URL using Serper API."""
        try:
            import hashlib
            normalized_url = self._normalize_url(url)

            # CRITICAL: Log the exact URL being processed (using WARNING level so it shows in logs)
            self._logger.warning("🔍 ===== STARTING ARTICLE EXTRACTION =====")
            self._logger.warning("🔍 Processing URL: %s", url)
            if normalized_url != url:
                self._logger.warning("🔍 Normalized URL for extraction: %s", normalized_url)
            self._logger.warning("🔍 URL hash: %s", hashlib.md5(url.encode()).hexdigest()[:8])
            
            # Use Serper API to scrape content
            self._logger.warning("🔍 Scraping content using Serper API...")

            try:
                result = self._extract_with_serper(normalized_url)
                self._logger.warning("✅ Content extracted successfully")
            except Exception as api_error:
                self._logger.error("❌ Failed to call Serper API: %s", api_error)
                result = None

            if result and not self._is_valid_extraction(normalized_url, result.title, result.text):
                self._logger.warning("⚠️ Serper extraction rejected. Trying direct article extraction fallback.")
                fallback_result = self._extract_with_newspaper(normalized_url)
                if fallback_result and self._is_valid_extraction(normalized_url, fallback_result.title, fallback_result.text):
                    result = fallback_result
                    self._logger.warning("✅ Direct extraction fallback accepted for URL: %s", normalized_url)
                else:
                    self._logger.error("❌ Direct extraction fallback also failed validation for URL: %s", normalized_url)
                    return None
            elif not result:
                self._logger.warning("⚠️ Serper extraction failed. Trying direct article extraction fallback.")
                fallback_result = self._extract_with_newspaper(normalized_url)
                if fallback_result and self._is_valid_extraction(normalized_url, fallback_result.title, fallback_result.text):
                    result = fallback_result
                    self._logger.warning("✅ Direct extraction fallback accepted for URL: %s", normalized_url)
                else:
                    return None

            title = result.title
            text = result.text
            images = result.images
            top_image_url = result.top_image_url

            self._logger.warning("🔍 Extracted Title: %s", title[:100] if title else "None")
            self._logger.warning("🔍 Extracted Text Length: %d characters", len(text) if text else 0)
            self._logger.warning("🔍 First 200 chars of text: %s", text[:200] if text else "None")
            
            # CRITICAL: Validate that we got actual content
            text_too_short = not text or text == "No article content available." or len(text.strip()) < 50
            
            if text_too_short:
                content_to_check = f"{title} {text[:1000]}"
                is_hindi_or_unicode = any(
                    '\u0900' <= char <= '\u097F' or
                    '\u0980' <= char <= '\u09FF' or
                    '\u0A00' <= char <= '\u0A7F' or
                    '\u0A80' <= char <= '\u0AFF' or
                    '\u0B00' <= char <= '\u0B7F' or
                    '\u0B80' <= char <= '\u0BFF' or
                    '\u0C00' <= char <= '\u0C7F' or
                    '\u0C80' <= char <= '\u0CFF' or
                    '\u0D00' <= char <= '\u0D7F'
                    for char in content_to_check
                )
                if is_hindi_or_unicode and title and len(title.strip()) > 20:
                    self._logger.warning("⚠️ Non-English article: Text extraction failed but title is valid, using title as content")
                    text = title
                elif title and len(title.strip()) > 30:
                    self._logger.warning("⚠️ Text extraction failed but title is valid (>30 chars), using title as content")
                    text = title
                else:
                    self._logger.error("❌ ===== ARTICLE EXTRACTION FAILED =====")
                    self._logger.error("❌ URL: %s", url)
                    self._logger.error("❌ Title extracted: %s", title[:100] if title else "None")
                    self._logger.error("❌ Text length: %d", len(text) if text else 0)
                    self._logger.error("❌ Both title and text are insufficient for story generation!")
                    return None
            
            summary = result.summary or self._build_summary(text)

            # CRITICAL: Final validation and logging
            self._logger.warning("✅ ===== ARTICLE EXTRACTION SUCCESSFUL =====")
            self._logger.warning("✅ URL: %s", url)
            self._logger.warning("✅ Title: %s", title[:100])
            self._logger.warning("✅ Text length: %d characters", len(text))
            self._logger.warning("✅ Summary length: %d characters", len(summary))
            self._logger.warning("✅ Images found: %d", len(images))

            return ArticleExtractionResult(
                title=title.strip(),
                text=text.strip(),
                summary=summary.strip(),
                top_image_url=top_image_url,
                images=images[:10] if images else [],  # Limit to first 10 images
            )
        except Exception as e:
            self._logger.error("Failed to extract article from URL %s: %s", url, e, exc_info=True)
            # Don't raise - return None to allow fallback
            return None

    def to_semantic_chunks(self, result: ArticleExtractionResult, url: str) -> list[SemanticChunk]:
        """Convert extraction result to semantic chunks."""
        chunks = []

        # Main content chunk
        if result.text:
            chunks.append(
                SemanticChunk(
                    id=f"url:{url}",
                    text=result.text,
                    source_id=url,
                    metadata={
                        "title": result.title,
                        "summary": result.summary,
                        "source": "url_extraction",
                        "top_image_url": result.top_image_url,
                        "image_count": len(result.images),
                    },
                )
            )

        return chunks
