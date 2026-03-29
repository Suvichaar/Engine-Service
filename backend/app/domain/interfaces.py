"""Interfaces (protocols/abstract base classes) for core domain services."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Protocol

from .dto import (
    AnalysisReport,
    DocInsights,
    EntityMap,
    Mode,
    NarrativeResponse,
    ImageAsset,
    IntakePayload,
    LanguageMetadata,
    SemanticChunk,
    SlideDeck,
    StoryRecord,
    StructuredJobRequest,
    VoiceAsset,
    PromptTemplateInfo,
    RenderedPrompt,
)


class UserInputService(ABC):
    """Collect and normalize user-provided inputs into an IntakePayload."""

    @abstractmethod
    def build_payload(self, **raw_inputs) -> IntakePayload:
        """Transform raw form inputs into an IntakePayload."""


class LanguageDetectionService(Protocol):
    """Detect the primary language used in user inputs."""

    def detect(self, payload: IntakePayload) -> LanguageMetadata:
        """Return language metadata for the provided payload."""


class IngestionAggregator(Protocol):
    """Prepare content for downstream pipelines."""

    def aggregate(self, payload: IntakePayload, language: LanguageMetadata) -> StructuredJobRequest:
        """Produce a structured job request from the payload and metadata."""


class DocumentIntelligencePipeline(Protocol):
    """Extract entities, summaries, and semantic chunks from attachments."""

    def run(self, job_request: StructuredJobRequest) -> DocInsights:
        """Execute the pipeline using the normalized job request."""


class AnalysisFacade(Protocol):
    """Higher-level aggregator for custom function calls and GPT analysis."""

    def analyze(self, insights: DocInsights) -> AnalysisReport:
        """Return an aggregated analysis report for downstream processes."""


class PromptTemplateService(Protocol):
    """Expose template and prompt catalogues."""

    def list_templates(self) -> Iterable["PromptTemplateInfo"]:
        """Return available prompt template descriptors."""

    def get_prompt(
        self,
        *,
        mode: str,
        category: str,
        language: str,
        analysis: str,
        keywords: Iterable[str],
    ) -> "RenderedPrompt":
        """Render a prompt for the given mode while keeping placeholders immutable."""


class ModelClient(Protocol):
    """Base interface for narrative models."""

    mode: Mode

    def generate(self, prompt: "RenderedPrompt", insights: DocInsights) -> NarrativeResponse:
        """Produce a narrative response given a rendered prompt and document insights."""


class ModelRouter(Protocol):
    """Route requests to the appropriate narrative model."""

    def route(self, mode: str) -> ModelClient:
        """Return the model client for the requested mode."""


class SlideAssemblyService(Protocol):
    """Combine narrative content with template placeholders."""

    def assemble(self, deck: SlideDeck) -> SlideDeck:
        """Return a slide deck with placeholders resolved."""


class ImageAssetPipeline(Protocol):
    """Generate or fetch slide images and upload them to storage."""

    def process(
        self, deck: SlideDeck, payload: IntakePayload, article_images: Optional[list[str]] = None
    ) -> list[ImageAsset]:
        """Return image assets keyed to slide placeholders."""


class VoiceSynthesisService(Protocol):
    """Produce narrated audio assets."""

    def synthesize(self, deck: SlideDeck, language: LanguageMetadata, provider: str) -> list[VoiceAsset]:
        """Return voice assets for the slide deck."""


class StoryRepository(Protocol):
    """Persist and retrieve story records."""

    def save(self, record: StoryRecord) -> StoryRecord:
        """Persist the story and return the saved record."""

    def get(self, story_id: str) -> StoryRecord:
        """Load a story record by its identifier."""

    def get_by_canurl(self, canurl: str) -> StoryRecord:
        """Load a story record by its canonical URL (slug)."""

