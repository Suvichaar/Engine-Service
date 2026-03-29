from __future__ import annotations

from typing import Optional

from app.domain.dto import AttachmentDescriptor, Entity, SemanticChunk, StructuredJobRequest
from app.services.document_intelligence import (
    DefaultDocumentIntelligencePipeline,
    OCRAdapter,
    OCRExtraction,
    ParserAdapter,
    ParserResult,
)


class StubOCRAdapter(OCRAdapter):
    def __init__(self, media_type: str, text: str):
        self.media_type = media_type
        self.text = text
        self.calls: list[str] = []

    def can_process(self, attachment: AttachmentDescriptor) -> bool:
        return attachment.media_type == self.media_type

    def extract(self, attachment: AttachmentDescriptor) -> Optional[OCRExtraction]:
        self.calls.append(attachment.id)
        return OCRExtraction(attachment=attachment, text=self.text, language="en", metadata={"media_type": self.media_type})


class StubParserAdapter(ParserAdapter):
    def supports(self, extraction: OCRExtraction) -> bool:
        return extraction.metadata and extraction.metadata.get("media_type") == "application/pdf"

    def parse(self, extraction: OCRExtraction) -> ParserResult:
        chunk = SemanticChunk(
            id=f"{extraction.attachment.id}:chunk-1",
            text=extraction.text.upper(),
            source_id=extraction.attachment.id,
            metadata={"parser": "stub"},
        )
        entity = Entity(name="Sample Entity", type="ORG", confidence=0.9)
        return ParserResult(chunks=[chunk], entities=[entity], summary="Stub summary")


def test_pipeline_runs_ocr_and_parser():
    ocr = StubOCRAdapter(media_type="application/pdf", text="hello world")
    parser = StubParserAdapter()
    pipeline = DefaultDocumentIntelligencePipeline([ocr], [parser])

    job_request = StructuredJobRequest(
        text_input="Base text",
        url_list=[],
        attachments=[
            AttachmentDescriptor(id="att-1", uri="s3://file.pdf", media_type="application/pdf", metadata={}),
        ],
        focus_keywords=[],
    )

    insights = pipeline.run(job_request)

    assert len(insights.semantic_chunks) == 2  # base text + parsed chunk
    assert insights.semantic_chunks[1].text == "HELLO WORLD"
    assert insights.summaries == ["Stub summary"]
    assert insights.entities.get("ORG")[0].name == "Sample Entity"
    assert ocr.calls == ["att-1"]


def test_pipeline_defaults_when_no_parser():
    ocr = StubOCRAdapter(media_type="image/png", text="image text")
    pipeline = DefaultDocumentIntelligencePipeline([ocr], [])

    job_request = StructuredJobRequest(
        text_input=None,
        url_list=[],
        attachments=[
            AttachmentDescriptor(id="att-2", uri="s3://image.png", media_type="image/png", metadata={}),
        ],
        focus_keywords=[],
    )

    insights = pipeline.run(job_request)

    assert len(insights.semantic_chunks) == 1
    assert insights.semantic_chunks[0].text == "image text"
    assert insights.summaries == []
    assert insights.entities.entities == {}

