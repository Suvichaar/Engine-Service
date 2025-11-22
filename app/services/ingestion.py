"""Service for constructing StructuredJobRequest objects."""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from app.domain.dto import AttachmentDescriptor, IntakePayload, LanguageMetadata, StructuredJobRequest
from app.domain.interfaces import IngestionAggregator


class DefaultIngestionAggregator(IngestionAggregator):
    """Aggregate user input and metadata into a StructuredJobRequest."""

    def __init__(self, text_joiner: str = "\n\n") -> None:
        self._text_joiner = text_joiner

    def aggregate(self, payload: IntakePayload, language: LanguageMetadata) -> StructuredJobRequest:
        segments = self._collect_text_segments(payload, language)
        text_input = self._join_non_empty(segments)
        return StructuredJobRequest(
            text_input=text_input or None,
            url_list=[str(url) for url in payload.urls],
            attachments=self._normalize_attachments(payload.attachments),
            focus_keywords=list(payload.prompt_keywords),
        )

    def _collect_text_segments(self, payload: IntakePayload, language: LanguageMetadata) -> list[str]:
        """
        Collect text segments with URL priority logic.
        If URLs are provided, skip text_prompt (URL content is primary source).
        Notes are used as additional context/guidance.
        """
        segments: list[str] = []
        
        # URL Priority Logic: If URLs are provided, skip text_prompt
        # (URL content will be extracted and used as primary source)
        if payload.urls:
            # URLs exist - skip text_prompt, use notes only as guidance
            if payload.notes:
                segments.append(f"[Additional Context]: {payload.notes.strip()}")
            # text_prompt is skipped when URLs are present
        else:
            # No URLs - use text_prompt and notes normally
            if payload.text_prompt:
                segments.append(payload.text_prompt.strip())
            if payload.notes:
                segments.append(payload.notes.strip())
        
        # Keywords are always included (for story angle/focus)
        if payload.prompt_keywords:
            segments.append(" ".join(payload.prompt_keywords))
        
        # Language preview (if available)
        if language.source_text_preview:
            segments.append(language.source_text_preview.strip())
        
        return segments

    def _normalize_attachments(self, attachments: Sequence[str]) -> list[AttachmentDescriptor]:
        descriptors: list[AttachmentDescriptor] = []
        for idx, attachment in enumerate(attachments):
            descriptor = AttachmentDescriptor(
                id=f"attachment-{idx+1}",
                uri=attachment,
                media_type=None,
                metadata={},
            )
            descriptors.append(descriptor)
        return descriptors

    def _join_non_empty(self, segments: Iterable[str]) -> str:
        cleaned = [segment for segment in segments if segment]
        return self._text_joiner.join(cleaned)

