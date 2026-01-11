"""URL content extraction service using Serper API."""

from __future__ import annotations

import http.client
import json
import logging
import os
import re
from typing import Optional
from urllib.parse import urlparse

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
        self._mode = mode  # "news" or "curious" for mode-specific isolation
        # Get API key from parameter, environment variable, or raise error
        # Priority: parameter > environment variable > error
        self._serper_api_key = api_key or os.getenv("SERPER_API_KEY")
        if not self._serper_api_key:
            raise ValueError(
                "Serper API key not provided. Set SERPER_API_KEY environment variable "
                "or pass api_key parameter to URLContentExtractor."
            )

    def extract(self, url: str) -> Optional[ArticleExtractionResult]:
        """Extract article content from URL using Serper API."""
        try:
            import hashlib

            # CRITICAL: Log the exact URL being processed (using WARNING level so it shows in logs)
            self._logger.warning("🔍 ===== STARTING ARTICLE EXTRACTION =====")
            self._logger.warning("🔍 Processing URL: %s", url)
            self._logger.warning("🔍 URL hash: %s", hashlib.md5(url.encode()).hexdigest()[:8])
            
            # Use Serper API to scrape content
            self._logger.warning("🔍 Scraping content using Serper API...")
            
            conn = http.client.HTTPSConnection("scrape.serper.dev")
            payload = json.dumps({"url": url})
            headers = {
                'X-API-KEY': self._serper_api_key,
                'Content-Type': 'application/json'
            }
            
            try:
                conn.request("POST", "/", payload, headers)
                res = conn.getresponse()
                data = res.read()
                
                if res.status != 200:
                    self._logger.error("❌ Serper API returned status %d: %s", res.status, data.decode("utf-8")[:200])
                    return None
                
                response_data = json.loads(data.decode("utf-8"))
                conn.close()
                
                # Extract content from Serper response
                # Serper API response structure may vary, so we handle different formats
                title = response_data.get("title", "")
                text = response_data.get("text", "") or response_data.get("bodyText", "") or response_data.get("content", "")
                
                # Extract images
                images = response_data.get("images", [])
                top_image_url = images[0] if images else None
                
                # If text is not in main response, try other fields
                if not text and "html" in response_data:
                    # Try to extract text from HTML (simple extraction)
                    html_content = response_data.get("html", "")
                    # Remove script and style tags
                    html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                    html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                    # Remove HTML tags
                    text = re.sub(r'<[^>]+>', ' ', html_content)
                    # Clean up whitespace
                    text = re.sub(r'\s+', ' ', text).strip()
                
                self._logger.warning("✅ Content extracted successfully")
                
            except Exception as api_error:
                self._logger.error("❌ Failed to call Serper API: %s", api_error)
                return None

            # Extract basic content
            if not title:
                title = "Untitled Article"
            if not text:
                text = "No article content available."
            
            # CRITICAL: IMMEDIATE validation - check for obvious mismatches BEFORE processing
            url_lower = url.lower()
            title_lower = title.lower()
            text_lower = (text[:500].lower() if text else "")
            
            # DEBUG: Log what we're checking (using WARNING level so it shows in logs)
            self._logger.warning("🔍 VALIDATION CHECK: URL=%s, Title=%s", url_lower[:100], title_lower[:100])
            
            # GENERAL validation: Check if URL path keywords match extracted content
            # Extract meaningful keywords from URL path (skip common words and domains)
            parsed = urlparse(url)
            path_parts = parsed.path.split('/')
            url_keywords = []
            skip_words = {'article', 'news', 'story', 'com', 'org', 'www', 'http', 'https', 'indianexpress', 
                         'sports', 'cities', 'entertainment', 'technology', 'business', 'politics', 'world', 
                         'local', 'health', 'science', 'education', 'lifestyle', 'opinion', 'editorial', 'html'}
            
            for part in path_parts:
                # Remove query params and get meaningful words
                part = part.split('?')[0].split('#')[0].strip()
                if not part or part == '/':
                    continue
                words = part.split('-')
                for word in words:
                    # Keep words longer than 3 chars, skip common words and numbers
                    if len(word) > 3 and word not in skip_words and not word.isdigit():
                        url_keywords.append(word)
            
            # Extract meaningful keywords from title and text
            content_text = f"{title_lower} {text_lower[:2000]}"  # Check first 2000 chars of text
            
            # Check if content is in Hindi/Unicode (Devanagari and other Indian scripts)
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
                for char in title
            )
            
            # Check if text is actually extracted (not just placeholder)
            text_is_empty = not text or len(text.strip()) < 50 or "no article content" in text.lower()
            
            if is_hindi_or_unicode:
                self._logger.warning("🌐 Detected Hindi/Unicode content - validation will be skipped")
            if text_is_empty:
                self._logger.warning("⚠️ Text is empty or too short - using relaxed validation")
            
            # Check overlap: How many URL keywords appear in content?
            if url_keywords:
                # Get top 10 most relevant URL keywords (longer words are more specific)
                top_url_keywords = sorted(set(url_keywords), key=len, reverse=True)[:10]
                
                # Create keyword synonyms/expansions for better matching
                keyword_expansions = {}
                for kw in top_url_keywords:
                    expansions = [kw]  # Always include original
                    # Common abbreviations
                    if kw == 'rbi':
                        expansions.extend(['reserve bank', 'reserve bank of india'])
                    elif kw == 'gst':
                        expansions.extend(['goods and services tax', 'goods services tax'])
                    elif kw == 'q3':
                        expansions.extend(['third quarter', 'q3', 'quarter 3'])
                    elif kw == 'q4':
                        expansions.extend(['fourth quarter', 'q4', 'quarter 4'])
                    elif kw == 'q1':
                        expansions.extend(['first quarter', 'q1', 'quarter 1'])
                    elif kw == 'q2':
                        expansions.extend(['second quarter', 'q2', 'quarter 2'])
                    keyword_expansions[kw] = expansions
                
                # Count matches in title and text separately for better debugging
                title_matches = 0
                text_matches = 0
                for kw in top_url_keywords:
                    expansions = keyword_expansions.get(kw, [kw])
                    if any(exp in title_lower for exp in expansions):
                        title_matches += 1
                    if any(exp in text_lower[:2000] for exp in expansions):
                        text_matches += 1
                
                # CRITICAL: Count UNIQUE keywords that match (not duplicates)
                unique_matches = set()
                for kw in top_url_keywords:
                    expansions = keyword_expansions.get(kw, [kw])
                    if any(exp in title_lower or exp in text_lower[:2000] for exp in expansions):
                        unique_matches.add(kw)
                actual_unique_matches = len(unique_matches)
                
                # Match ratio based on unique matches (more accurate)
                match_ratio = actual_unique_matches / len(top_url_keywords) if top_url_keywords else 0
                
                # ADAPTIVE VALIDATION: Adjust requirements based on content language and text availability
                if is_hindi_or_unicode:
                    min_required_matches = 0
                    match_ratio_threshold = 0.0
                    self._logger.warning("🌐 Hindi content: Validation disabled (accepting article)")
                elif text_is_empty:
                    min_required_matches = 1
                    match_ratio_threshold = 0.05
                    self._logger.warning("⚠️ Empty text: Using relaxed validation (1 match required)")
                else:
                    business_keywords = {'business', 'finance', 'economic', 'rbi', 'gdp', 'gst', 'credit', 'growth', 'policy', 'rate', 'q1', 'q2', 'q3', 'q4'}
                    is_business_article = any(bk in url_lower or bk in title_lower for bk in business_keywords)
                    
                    if is_business_article:
                        min_required_matches = max(1, min(2, len(top_url_keywords) // 4))
                        match_ratio_threshold = 0.05
                        self._logger.warning("📊 Business article detected - using relaxed validation")
                    else:
                        min_required_matches = max(2, min(3, len(top_url_keywords) // 3))
                        match_ratio_threshold = 0.1
                
                self._logger.warning("🔍 VALIDATION: URL keywords=%s", top_url_keywords[:5])
                self._logger.warning("🔍 VALIDATION: Title matches=%d, Text matches=%d, Unique matches=%d/%d", 
                                   title_matches, text_matches, actual_unique_matches, len(top_url_keywords))
                self._logger.warning("🔍 VALIDATION: Match ratio=%.1f%%, Required=%d unique matches (threshold=%.1f%%)", 
                                   match_ratio * 100, min_required_matches, match_ratio_threshold * 100)
                
                # CRITICAL: Reject only for English content if validation fails
                if len(top_url_keywords) >= 3 and not is_hindi_or_unicode:
                    if match_ratio < match_ratio_threshold or actual_unique_matches < min_required_matches:
                        self._logger.error("❌ ===== IMMEDIATE REJECTION: URL-CONTENT MISMATCH =====")
                        self._logger.error("❌ URL: %s", url)
                        self._logger.error("❌ Extracted Title: %s", title[:100])
                        self._logger.error("❌ Extracted Text Preview: %s", text[:300] if text else "None")
                        self._logger.error("❌ URL keywords: %s", top_url_keywords)
                        self._logger.error("❌ Title matches: %d, Text matches: %d, Unique matches: %d", 
                                         title_matches, text_matches, actual_unique_matches)
                        self._logger.error("❌ Match ratio: %.1f%% (expected >%.1f%%), Required: %d unique matches (got %d)", 
                                         match_ratio * 100, match_ratio_threshold * 100, min_required_matches, actual_unique_matches)
                        self._logger.error("❌ This indicates wrong article was extracted (caching/mismatch issue)")
                        self._logger.error("❌ REJECTING to prevent wrong story generation")
                        return None
                    else:
                        self._logger.warning("✅ URL-content validation passed (%.1f%% match, %d unique matches, required %d)", 
                                           match_ratio * 100, actual_unique_matches, min_required_matches)
                else:
                    if is_hindi_or_unicode:
                        self._logger.warning("✅ Hindi/Unicode content - validation skipped, accepting article")
                    else:
                        self._logger.warning("⚠️ Too few URL keywords (%d) for strict validation, accepting", len(top_url_keywords))
            
            # CRITICAL: Log extracted content for debugging
            self._logger.warning("🔍 Extracted Title: %s", title[:100] if title else "None")
            self._logger.warning("🔍 Extracted Text Length: %d characters", len(text) if text else 0)
            self._logger.warning("🔍 First 200 chars of text: %s", text[:200] if text else "None")
            
            # CRITICAL: Validate that we got actual content
            text_too_short = not text or text == "No article content available." or len(text.strip()) < 50
            
            if text_too_short:
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
            
            # Generate summary (first 3 sentences or first 300 chars)
            # Simple sentence splitting for summary
            sentences = re.split(r'[.!?]\s+', text)
            summary_parts = []
            for sent in sentences[:3]:
                if len(" ".join(summary_parts) + " " + sent) <= 300:
                    summary_parts.append(sent)
                else:
                    break
            summary = " ".join(summary_parts) if summary_parts else text[:300]

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
