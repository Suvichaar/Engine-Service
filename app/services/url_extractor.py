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

    def __init__(self, logger: Optional[logging.Logger] = None):
        self._logger = logger or logging.getLogger(__name__)

    def extract(self, url: str) -> Optional[ArticleExtractionResult]:
        """Extract article content from URL using newspaper3k and textblob."""
        try:
            from newspaper import Article
            from textblob import TextBlob

            self._logger.info("Starting article extraction from URL: %s", url)
            article = Article(url)
            
            self._logger.debug("Downloading article...")
            article.download()
            
            self._logger.debug("Parsing article...")
            article.parse()

            # Extract basic content
            title = article.title or "Untitled Article"
            text = article.text or "No article content available."
            
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

            self._logger.info(
                "Extracted article from URL: title=%s, text_length=%d, summary_length=%d, images=%d",
                title[:50],
                len(text),
                len(summary),
                len(images),
            )

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

