"""URL content extraction service using newspaper3k."""

from __future__ import annotations

import logging
from typing import Optional

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
    """Extract article content and images from URLs."""

    def __init__(self, logger: Optional[logging.Logger] = None, mode: Optional[str] = None):
        self._logger = logger or logging.getLogger(__name__)
        self._mode = mode  # "news" or "curious" for mode-specific isolation

    def extract(self, url: str) -> Optional[ArticleExtractionResult]:
        """Extract article content from URL using newspaper3k and textblob."""
        try:
            from newspaper import Article
            from textblob import TextBlob
            import hashlib

            # CRITICAL: Log the exact URL being processed (using WARNING level so it shows in logs)
            self._logger.warning("🔍 ===== STARTING ARTICLE EXTRACTION =====")
            self._logger.warning("🔍 Processing URL: %s", url)
            self._logger.warning("🔍 URL hash: %s", hashlib.md5(url.encode()).hexdigest()[:8])
            
            # CRITICAL: Clear newspaper3k cache to prevent wrong article extraction
            # Add cache-busting parameter to URL to force fresh download
            import time
            cache_buster = int(time.time() * 1000)  # Milliseconds timestamp
            url_with_cache_bust = f"{url}{'&' if '?' in url else '?'}_cb={cache_buster}"
            self._logger.warning("🔍 Cache-busted URL: %s", url_with_cache_bust[:150])
            
            # Create article object with explicit configuration to avoid caching issues
            # Use original URL (cache-busting is just for logging/debugging)
            article = Article(url, language='en', memoize_articles=False)  # Disable memoization
            
            # CRITICAL: Mode-specific user agent for cache isolation
            user_agent = (
                "NewsBot/1.0 (News Mode)" if self._mode == "news"
                else "CuriousBot/1.0 (Curious Mode)" if self._mode == "curious"
                else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            
            # CRITICAL: Try to clear any existing cache for this URL
            try:
                # Clear article cache if it exists
                if hasattr(article, 'config'):
                    article.config.memoize_articles = False
                    article.config.browser_user_agent = user_agent
                    self._logger.warning("🔍 Mode-specific user agent: %s", user_agent)
            except Exception as cache_error:
                self._logger.debug("Cache clearing attempt (non-critical): %s", cache_error)
            
            self._logger.warning("🔍 Downloading article from: %s", url)
            try:
                article.download()
                self._logger.warning("✅ Article downloaded successfully")
            except Exception as download_error:
                self._logger.error("❌ Failed to download article from %s: %s", url, download_error)
                return None
            
            self._logger.warning("🔍 Parsing article...")
            try:
                article.parse()
                self._logger.warning("✅ Article parsed successfully")
            except Exception as parse_error:
                self._logger.error("❌ Failed to parse article from %s: %s", url, parse_error)
                return None

            # Extract basic content
            title = article.title or "Untitled Article"
            text = article.text or "No article content available."
            
            # CRITICAL: IMMEDIATE validation - check for obvious mismatches BEFORE processing
            url_lower = url.lower()
            title_lower = title.lower()
            text_lower = (text[:500].lower() if text else "")
            
            # DEBUG: Log what we're checking (using WARNING level so it shows in logs)
            self._logger.warning("🔍 VALIDATION CHECK: URL=%s, Title=%s", url_lower[:100], title_lower[:100])
            
            # GENERAL validation: Check if URL path keywords match extracted content
            # This is a general approach that works for ANY topic mismatch, not just specific cases
            # Extract meaningful keywords from URL path (skip common words and domains)
            from urllib.parse import urlparse
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
            # IMPORTANT: Check BOTH title AND text content (first 2000 chars) for better validation
            # This catches cases where title might be in English but content is wrong
            content_text = f"{title_lower} {text_lower[:2000]}"  # Check first 2000 chars of text
            
            # Check if content is in Hindi/Unicode (Devanagari and other Indian scripts)
            # This is important because Hindi titles won't match English URL keywords
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
                
                # Count matches in title and text separately for better debugging
                title_matches = sum(1 for kw in top_url_keywords if kw in title_lower)
                text_matches = sum(1 for kw in top_url_keywords if kw in text_lower[:2000])
                
                # CRITICAL: Count UNIQUE keywords that match (not duplicates)
                # A keyword can appear in both title and text, but we count it only once
                unique_matches = set()
                for kw in top_url_keywords:
                    if kw in title_lower or kw in text_lower[:2000]:
                        unique_matches.add(kw)
                actual_unique_matches = len(unique_matches)
                
                # Match ratio based on unique matches (more accurate)
                match_ratio = actual_unique_matches / len(top_url_keywords) if top_url_keywords else 0
                
                # ADAPTIVE VALIDATION: Adjust requirements based on content language and text availability
                if is_hindi_or_unicode:
                    # For Hindi/Unicode content: Skip validation entirely
                    # Hindi titles don't match English URL keywords
                    min_required_matches = 0  # Don't require any matches for Hindi
                    match_ratio_threshold = 0.0  # No threshold for Hindi (accept all)
                    self._logger.warning("🌐 Hindi content: Validation disabled (accepting article)")
                elif text_is_empty:
                    # If text is empty, rely more on title and be lenient
                    min_required_matches = 1  # Require only 1 match
                    match_ratio_threshold = 0.05  # 5% threshold
                    self._logger.warning("⚠️ Empty text: Using relaxed validation (1 match required)")
                else:
                    # For English content with proper text: Use strict validation
                    min_required_matches = max(2, min(3, len(top_url_keywords) // 3))
                    match_ratio_threshold = 0.1  # 10% threshold
                
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
            
            # CRITICAL: Log extracted content for debugging (using WARNING level so it shows in logs)
            self._logger.warning("🔍 Extracted Title: %s", title[:100] if title else "None")
            self._logger.warning("🔍 Extracted Text Length: %d characters", len(text) if text else 0)
            self._logger.warning("🔍 First 200 chars of text: %s", text[:200] if text else "None")
            
            # CRITICAL: Validate that we got actual content
            # LANGUAGE-AGNOSTIC: For non-English content, text extraction often fails due to encoding/JS rendering
            # If text is empty or too short, check if we can use title as fallback
            text_too_short = not text or text == "No article content available." or len(text.strip()) < 50
            
            if text_too_short:
                # For Hindi/Unicode content with a valid title, use title as text fallback
                # This handles cases where newspaper3k can't extract body text from dynamic sites
                if is_hindi_or_unicode and title and len(title.strip()) > 20:
                    self._logger.warning("⚠️ Non-English article: Text extraction failed but title is valid, using title as content")
                    # Use title as text - LLM will generate story based on title
                    text = title
                    # Continue processing with title as text
                elif title and len(title.strip()) > 30:
                    # For English content with good title but no text, also try title fallback
                    self._logger.warning("⚠️ Text extraction failed but title is valid (>30 chars), using title as content")
                    text = title
                else:
                    # No valid title or title too short - reject completely
                    self._logger.error("❌ ===== ARTICLE EXTRACTION FAILED =====")
                    self._logger.error("❌ URL: %s", url)
                    self._logger.error("❌ Title extracted: %s", title[:100] if title else "None")
                    self._logger.error("❌ Text length: %d", len(text) if text else 0)
                    self._logger.error("❌ Both title and text are insufficient for story generation!")
                    return None  # Return None instead of empty result
            
            # Use textblob for better text processing and summary
            try:
                self._logger.debug("Processing text with TextBlob...")
                blob = TextBlob(text)
                
                # Get better summary using textblob's sentence extraction
                # Take first 3 sentences as summary if available
                sentences = blob.sentences
                if len(sentences) > 0:
                    # Use first 2-3 sentences for summary (up to 300 chars)
                    summary_parts = []
                    for sent in sentences[:3]:
                        if len(" ".join(summary_parts) + " " + str(sent)) <= 300:
                            summary_parts.append(str(sent))
                        else:
                            break
                    summary = " ".join(summary_parts) if summary_parts else text[:300]
                else:
                    summary = text[:300]
                
                # Extract keywords using noun phrases
                try:
                    keywords = [str(np) for np in blob.noun_phrases[:10]]
                    self._logger.debug("Extracted keywords: %s", keywords[:5])
                except Exception:
                    keywords = []
                
            except Exception as textblob_error:
                self._logger.debug("TextBlob processing failed (non-critical): %s", textblob_error)
                # Fallback to newspaper3k NLP or simple truncation
                try:
                    article.nlp()  # Try newspaper3k NLP
                    summary = article.summary or text[:300]
                except Exception:
                    summary = text[:300]

            # Extract images
            top_image = article.top_image
            images = list(article.images) if hasattr(article, "images") else []

            # CRITICAL: Final validation and logging (using WARNING level so it shows in logs)
            self._logger.warning("✅ ===== ARTICLE EXTRACTION SUCCESSFUL =====")
            self._logger.warning("✅ URL: %s", url)
            self._logger.warning("✅ Title: %s", title[:100])
            self._logger.warning("✅ Text length: %d characters", len(text))
            self._logger.warning("✅ Summary length: %d characters", len(summary))
            self._logger.warning("✅ Images found: %d", len(images))
            
            # NOTE: URL-content validation already done above (lines 78-126)
            # No need for duplicate validation here

            return ArticleExtractionResult(
                title=title.strip(),
                text=text.strip(),
                summary=summary.strip(),
                top_image_url=top_image,
                images=images[:10],  # Limit to first 10 images
            )
        except ImportError as import_error:
            self._logger.error("newspaper3k not installed. Install with: pip install newspaper3k")
            self._logger.error("Import error details: %s", import_error)
            # Don't raise - return None to allow graceful fallback
            return None
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

