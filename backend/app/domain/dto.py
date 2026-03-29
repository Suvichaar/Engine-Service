"""Pydantic DTOs that describe core domain concepts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, conint, constr


SlideCount = conint(strict=True, ge=4, le=10)


class Mode(str, Enum):
    CURIOUS = "curious"
    NEWS = "news"


class IntakePayload(BaseModel):
    """Normalized representation of all user-provided inputs."""

    text_prompt: Optional[str] = Field(default=None, description="Primary textual prompt.")
    notes: Optional[str] = Field(default=None, description="Supplementary notes.")
    urls: List[HttpUrl] = Field(default_factory=list, description="External references to pull context from.")
    attachments: List[str] = Field(  # references in object storage
        default_factory=list,
        description="Identifiers for uploaded assets (PDFs, images, documents).",
    )
    prompt_keywords: List[str] = Field(default_factory=list, description="Focus keywords extracted from UI.")
    mode: Mode = Field(..., description="Selected storytelling mode.")
    template_key: constr(min_length=1) = Field(..., description="Chosen template identifier.")
    slide_count: SlideCount = Field(..., description="Total number of slides requested.")
    category: Optional[str] = Field(default=None, description="Category chosen by the user, if applicable.")
    image_source: Optional[constr(pattern="^(ai|pexels|custom)$")] = Field(
        default=None, description="Preferred image pipeline source."
    )
    voice_engine: Optional[constr(pattern="^(elevenlabs_pro|azure_basic)$")] = Field(
        default=None, description="Selected text-to-speech provider."
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata for pipeline processing.")


class LanguageMetadata(BaseModel):
    """Result of the language detection stage."""

    language_code: constr(min_length=2) = Field(..., description="IETF language code (e.g., en, hi-IN).")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1.")
    source_text_preview: Optional[str] = Field(
        default=None, description="Optional snippet used for detection transparency."
    )


class Entity(BaseModel):
    """Represents a single extracted entity."""

    name: str = Field(..., description="Canonical entity name.")
    type: str = Field(..., description="Entity type (PERSON, ORG, LOCATION, etc.).")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence score when available.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific metadata.")


class EntityMap(BaseModel):
    """Mapping of entity types to lists of entities."""

    entities: Dict[str, List[Entity]] = Field(default_factory=dict)

    def add(self, entity: Entity) -> None:
        bucket = self.entities.setdefault(entity.type, [])
        bucket.append(entity)

    def get(self, entity_type: str) -> List[Entity]:
        return self.entities.get(entity_type, [])

    def merge(self, entities: List[Entity]) -> None:
        for entity in entities:
            self.add(entity)


class SemanticChunk(BaseModel):
    """Represents a chunk of text with optional metadata."""

    id: str = Field(..., description="Unique identifier for the chunk.")
    text: str = Field(..., description="Chunk text content.")
    source_id: Optional[str] = Field(default=None, description="Source attachment identifier.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata for routing or scoring.")


class DocInsights(BaseModel):
    """Insights extracted from documents and upstream analysis."""

    semantic_chunks: List[SemanticChunk] = Field(default_factory=list, description="Document segments ready for analysis.")
    summaries: List[str] = Field(default_factory=list, description="Generated summaries per attachment or chunk.")
    entities: EntityMap = Field(default_factory=EntityMap, description="Named entities discovered in the sources.")
    gaps: List[str] = Field(default_factory=list, description="Knowledge gaps identified by analyzers.")
    recommended_prompts: List[str] = Field(default_factory=list, description="Suggestions for downstream prompting.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata (e.g., article images).")


class TopicCluster(BaseModel):
    """Represents a cluster of related topics discovered during analysis."""

    title: str = Field(..., description="Title for the topic cluster.")
    keywords: List[str] = Field(default_factory=list, description="Keywords associated with the cluster.")
    summary: Optional[str] = Field(default=None, description="Brief description of the cluster.")


class AnalysisReport(BaseModel):
    """Aggregated analysis ready for downstream prompt selection."""

    narrative_summary: Optional[str] = Field(default=None, description="Overall summary generated by analyzers.")
    topic_clusters: List[TopicCluster] = Field(default_factory=list, description="List of discovered topic clusters.")
    recommended_prompts: List[str] = Field(default_factory=list, description="Suggested prompts tailored to the content.")
    gaps: List[str] = Field(default_factory=list, description="Identified knowledge gaps requiring attention.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata for debugging or audit.")


class PromptTemplateInfo(BaseModel):
    """Descriptor for a prompt template."""

    mode: str = Field(..., description="Mode identifier associated with the template.")
    description: Optional[str] = Field(default=None, description="Human-readable summary.")
    allowed_categories: List[str] = Field(default_factory=list, description="Allowed categories for the template.")
    user_template: str = Field(..., description="Raw user prompt template with placeholders.")


class RenderedPrompt(BaseModel):
    """Rendered prompt ready for LLM consumption."""

    system: str = Field(..., description="System prompt content.")
    user: str = Field(..., description="User prompt content with placeholders filled.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata. Placeholders remain immutable.")


class SlideBlock(BaseModel):
    """Single placeholder-content pair for slide assembly."""

    placeholder_id: constr(min_length=1) = Field(..., description="Template placeholder identifier.")
    text: Optional[str] = Field(default=None, description="Textual content to inject into the placeholder.")
    image_url: Optional[HttpUrl] = Field(default=None, description="Resolved image asset for the placeholder.")
    highlight_tags: List[str] = Field(default_factory=list, description="Optional tags to drive UI highlighting.")


class SlideDeck(BaseModel):
    """Assembled slide deck ready for rendering and persistence."""

    template_key: constr(min_length=1) = Field(..., description="Template identifier used for rendering.")
    language_code: Optional[str] = Field(default=None, description="Language used for the deck content.")
    slides: List[SlideBlock] = Field(..., description="Ordered slide blocks representing the final narrative.")


class AttachmentDescriptor(BaseModel):
    """Descriptor for an uploaded attachment."""

    id: str = Field(..., description="Internal identifier for the attachment.")
    uri: str = Field(..., description="Location or storage key for the attachment.")
    media_type: Optional[str] = Field(default=None, description="Mime type when known.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata used by adapters.")


class StructuredJobRequest(BaseModel):
    """Normalized request passed into document processing pipelines."""

    text_input: Optional[str] = Field(default=None, description="Concatenated textual content.")
    url_list: List[HttpUrl] = Field(default_factory=list, description="Normalized URLs to fetch additional context.")
    attachments: List[AttachmentDescriptor] = Field(default_factory=list, description="Attachments prepared for processing.")
    focus_keywords: List[str] = Field(default_factory=list, description="Normalized keyword list.")


class VoiceAsset(BaseModel):
    """Generated narration audio metadata."""

    provider: constr(min_length=1) = Field(..., description="Voice provider identifier.")
    voice_id: Optional[str] = Field(default=None, description="Provider-specific voice reference.")
    audio_url: HttpUrl = Field(..., description="Location of the rendered audio asset.")
    duration_seconds: Optional[float] = Field(default=None, gt=0, description="Length of audio when known.")


class ImageAsset(BaseModel):
    """Stored image asset metadata."""

    source: constr(min_length=1) = Field(..., description="Identifies whether the image is AI, Pexels, or user upload.")
    original_object_key: str = Field(..., description="S3 object key of the uploaded asset.")
    resized_variants: List[HttpUrl] = Field(default_factory=list, description="CloudFront URLs for resized variants.")
    description: Optional[str] = Field(default=None, description="Alt-text or caption associated with the image.")


class StoryRecord(BaseModel):
    """Aggregate persisted in Postgres representing the final story."""

    id: UUID = Field(..., description="Unique identifier for the story record.")
    mode: Mode = Field(..., description="Storytelling mode used to create the story.")
    category: str = Field(..., description="Story category, such as News or Art.")
    input_language: Optional[str] = Field(default=None, description="Detected or user-selected language code.")
    slide_count: SlideCount = Field(..., description="Number of slides in the final story.")
    template_key: constr(min_length=1) = Field(..., description="Template used for rendering.")
    doc_insights: DocInsights = Field(..., description="Document intelligence output stored for auditing.")
    slide_deck: SlideDeck = Field(..., description="Final slide deck representation.")
    image_assets: List[ImageAsset] = Field(default_factory=list, description="List of all resolved image assets.")
    voice_assets: List[VoiceAsset] = Field(default_factory=list, description="Narration assets linked to the story.")
    prompt_news: Optional[str] = Field(default=None, description="Prompt text used when generating news content.")
    prompt_curious: Optional[str] = Field(default=None, description="Prompt text used when generating curious content.")
    canurl: Optional[HttpUrl] = Field(default=None, description="Primary shareable URL.")
    canurl1: Optional[HttpUrl] = Field(default=None, description="Secondary shareable URL.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when the story was stored.")


class NarrativeResponse(BaseModel):
    """Base class for narrative model responses."""

    mode: Mode = Field(..., description="Mode that generated this narrative.")
    slide_deck: SlideDeck = Field(..., description="Generated slide deck for the narrative.")
    raw_output: Optional[str] = Field(default=None, description="Raw LLM output for auditing.")


class CuriousNarrative(NarrativeResponse):
    """Narrative response tailored for the Curious mode."""

    explainability_notes: List[str] = Field(default_factory=list, description="Explainability notes per slide or section.")
    reasoning_trace: Optional[str] = Field(default=None, description="Optional reasoning trace provided by the LLM.")


class NewsNarrative(NarrativeResponse):
    """Narrative response tailored for the News mode."""

    headlines: List[str] = Field(default_factory=list, description="Headline statements extracted from the output.")
    bullet_points: List[str] = Field(default_factory=list, description="Concise bullet points for the news story.")

