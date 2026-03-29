"""Document intelligence pipeline composed of OCR and parser adapters."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Iterable, List, Optional, Protocol, Sequence

import httpx

from app.domain.dto import (
    AttachmentDescriptor,
    DocInsights,
    Entity,
    EntityMap,
    SemanticChunk,
    StructuredJobRequest,
)
from app.domain.interfaces import DocumentIntelligencePipeline

if TYPE_CHECKING:
    from app.services.url_extractor import URLContentExtractor


@dataclass
class OCRExtraction:
    """Result of running OCR on a single attachment."""

    attachment: AttachmentDescriptor
    text: str
    language: Optional[str] = None
    metadata: dict | None = None


@dataclass
class ParserResult:
    """Structured interpretation of OCR extraction."""

    chunks: List[SemanticChunk]
    entities: List[Entity]
    summary: Optional[str] = None


class OCRAdapter(Protocol):
    """Adapter interface for converting attachments into text."""

    def can_process(self, attachment: AttachmentDescriptor) -> bool:
        ...

    def extract(self, attachment: AttachmentDescriptor) -> Optional[OCRExtraction]:
        ...


class ParserAdapter(Protocol):
    """Adapter interface for turning OCR text into structured artifacts."""

    def supports(self, extraction: OCRExtraction) -> bool:
        ...

    def parse(self, extraction: OCRExtraction) -> ParserResult:
        ...


class DefaultDocumentIntelligencePipeline(DocumentIntelligencePipeline):
    """Coordinate OCR adapters and parser adapters to build DocInsights."""

    def __init__(
        self,
        ocr_adapters: Sequence[OCRAdapter],
        parser_adapters: Sequence[ParserAdapter],
        url_extractor: Optional["URLContentExtractor"] = None,
    ) -> None:
        self._ocr_adapters = list(ocr_adapters)
        self._parser_adapters = list(parser_adapters)
        self._url_extractor = url_extractor

    def run(self, job_request: StructuredJobRequest) -> DocInsights:
        insights = DocInsights()
        logger = logging.getLogger(__name__)

        # Process URLs first (extract article content)
        if job_request.url_list and self._url_extractor:
            logger.warning(f"🔍 ===== DOCUMENT INTELLIGENCE: Processing {len(job_request.url_list)} URL(s) =====")
            logger.warning(f"🔍 URL List: {[str(url) for url in job_request.url_list]}")
            extraction_successful = False
            for url in job_request.url_list:
                url_str = str(url)
                logger.warning(f"🔍 ===== STARTING EXTRACTION FOR URL =====")
                logger.warning(f"🔍 URL: {url_str}")
                logger.warning(f"🔍 URL Extractor available: {self._url_extractor is not None}")
                try:
                    result = self._url_extractor.extract(url_str)
                    if result:
                        extraction_successful = True
                        # Validate that we got actual content
                        if not result.text or len(result.text.strip()) < 50:
                            logger.error(f"❌ Article extraction returned insufficient content for URL: {url_str} (text_length={len(result.text) if result.text else 0})")
                            logger.error(f"❌ Title extracted: {result.title[:100] if result.title else 'None'}")
                            continue
                        
                        # CRITICAL: Log extracted content to verify it matches the URL (using WARNING level so it shows in logs)
                        logger.warning(f"✅ Article extracted successfully:")
                        logger.warning(f"   URL: {url_str}")
                        logger.warning(f"   Title: {result.title[:100]}")
                        logger.warning(f"   Text length: {len(result.text)}")
                        logger.warning(f"   Summary length: {len(result.summary)}")
                        
                        chunks = self._url_extractor.to_semantic_chunks(result, url_str)
                        if chunks:
                            insights.semantic_chunks.extend(chunks)
                            logger.warning(f"✅ Added {len(chunks)} semantic chunk(s) from URL: {url_str}")
                        else:
                            logger.warning(f"⚠️ No semantic chunks created from URL: {url_str}")
                        
                        # Store article images in metadata for later use
                        if insights.metadata is None:
                            insights.metadata = {}
                        if "article_images" not in insights.metadata:
                            insights.metadata["article_images"] = []
                        if result.top_image_url:
                            insights.metadata["article_images"].append(result.top_image_url)
                        # Also store all images
                        if result.images:
                            insights.metadata["article_images"].extend(result.images[:5])  # Limit to 5
                    else:
                        # CRITICAL: If extraction returns None (validation failed), raise exception
                        error_msg = f"Article extraction FAILED or was REJECTED for URL: {url_str}. This usually means wrong content was extracted (e.g., chess URL but Delhi pollution content). Story generation ABORTED to prevent incorrect stories."
                        logger.error(f"❌ ===== CRITICAL: Article extraction returned None =====")
                        logger.error(f"❌ URL: {url_str}")
                        logger.error(f"❌ {error_msg}")
                        logger.error(f"❌ RAISING EXCEPTION to prevent wrong story generation!")
                        raise ValueError(error_msg)
                except ValueError:
                    # Re-raise ValueError (validation errors)
                    raise
                except Exception as e:
                    # Log error but continue processing for other exceptions
                    logger.error(f"❌ ===== CRITICAL: Failed to process URL =====")
                    logger.error(f"❌ URL: {url_str}")
                    logger.error(f"❌ Error: {e}", exc_info=True)
                    # For other exceptions, we continue, but for ValueError (validation), we raise
                    continue
            
            # Check if we got any semantic chunks from URLs
            if job_request.url_list and not insights.semantic_chunks:
                error_msg = f"CRITICAL ERROR: No content extracted from {len(job_request.url_list)} URL(s). URLs: {[str(url) for url in job_request.url_list]}. This will cause incorrect story generation. Please check the URLs and ensure article extraction is working."
                logger.error(f"❌ ===== CRITICAL ERROR =====")
                logger.error(f"❌ {error_msg}")
                logger.error(f"❌ URLs attempted: {[str(url) for url in job_request.url_list]}")
                logger.error(f"❌ RAISING EXCEPTION to prevent wrong story generation!")
                raise ValueError(error_msg)
            
            # Also check if extraction was attempted but failed
            if job_request.url_list and not extraction_successful:
                error_msg = f"CRITICAL ERROR: Article extraction failed for all {len(job_request.url_list)} URL(s). URLs: {[str(url) for url in job_request.url_list]}. Cannot generate story without content."
                logger.error(f"❌ ===== CRITICAL ERROR: EXTRACTION FAILED =====")
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)

        if job_request.text_input:
            insights.semantic_chunks.append(
                SemanticChunk(
                    id="payload:text",
                    text=job_request.text_input,
                    source_id="payload",
                    metadata={"source": "text_input"},
                )
            )

        for attachment in job_request.attachments:
            extraction = self._run_ocr(attachment)
            if extraction is None or not extraction.text.strip():
                continue

            parser = self._select_parser(extraction)
            if parser:
                result = parser.parse(extraction)
            else:
                result = self._default_parse(extraction)

            insights.semantic_chunks.extend(result.chunks)
            insights.entities.merge(result.entities)
            if result.summary:
                insights.summaries.append(result.summary)

        return insights

    def _run_ocr(self, attachment: AttachmentDescriptor) -> Optional[OCRExtraction]:
        for adapter in self._ocr_adapters:
            if adapter.can_process(attachment):
                return adapter.extract(attachment)
        return None

    def _select_parser(self, extraction: OCRExtraction) -> Optional[ParserAdapter]:
        for parser in self._parser_adapters:
            if parser.supports(extraction):
                return parser
        return None

    def _default_parse(self, extraction: OCRExtraction) -> ParserResult:
        chunk = SemanticChunk(
            id=f"{extraction.attachment.id}:chunk-1",
            text=extraction.text,
            source_id=extraction.attachment.id,
            metadata=extraction.metadata or {},
        )
        return ParserResult(
            chunks=[chunk],
            entities=[],
        )


class AzureDocumentIntelligenceAdapter:
    """Adapter that uses Azure Document Intelligence REST API for OCR."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        model_id: str = "prebuilt-layout",
        api_version: str = "2024-02-29-preview",
        attachment_loader: Callable[[AttachmentDescriptor], Optional[bytes]] | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._model_id = model_id
        self._api_version = api_version
        self._attachment_loader = attachment_loader or (lambda attachment: None)
        self._timeout = timeout
        self._logger = logging.getLogger(__name__)

    def can_process(self, attachment: AttachmentDescriptor) -> bool:
        return attachment.media_type in {"application/pdf", "image/png", "image/jpeg"}

    def extract(self, attachment: AttachmentDescriptor) -> Optional[OCRExtraction]:
        content = self._attachment_loader(attachment)
        if not content:
            self._logger.debug("Azure DI: no content available for attachment %s", attachment.id)
            return None

        analyze_url = (
            f"{self._endpoint}/documentanalysis:analyze"
            f"?modelId={self._model_id}&api-version={self._api_version}"
        )
        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key,
            "Content-Type": attachment.media_type or "application/octet-stream",
        }

        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(analyze_url, headers=headers, content=content)
            response.raise_for_status()
            operation_url = response.headers.get("operation-location")

        if not operation_url:
            self._logger.warning("Azure DI: missing operation-location header for %s", attachment.id)
            return None

        result = self._poll_operation(operation_url)
        full_text = self._extract_text(result)
        metadata = {"model_id": self._model_id, "api_version": self._api_version}
        language = result.get("documents", [{}])[0].get("language")
        return OCRExtraction(attachment=attachment, text=full_text, language=language, metadata=metadata)

    def _poll_operation(self, operation_url: str) -> dict[str, Any]:
        headers = {"Ocp-Apim-Subscription-Key": self._api_key}
        with httpx.Client(timeout=self._timeout) as client:
            for _ in range(10):
                response = client.get(operation_url, headers=headers)
                response.raise_for_status()
                payload = response.json()
                status = payload.get("status")
                if status in {"succeeded", "failed"}:
                    return payload
                time.sleep(1)
        raise RuntimeError("Azure Document Intelligence operation timed out.")

    def _extract_text(self, payload: dict[str, Any]) -> str:
        try:
            pages = payload["analyzeResult"]["pages"]
        except KeyError:
            return ""
        lines: List[str] = []
        for page in pages:
            for line in page.get("lines", []):
                content = line.get("content")
                if content:
                    lines.append(content)
        return "\n".join(lines)

