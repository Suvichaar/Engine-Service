"""API request/response schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.domain.dto import Mode, SlideCount, StoryRecord


class StoryCreateRequest(BaseModel):
    mode: Mode
    template_key: str
    slide_count: SlideCount
    category: Optional[str] = None
    
    # NEW: Unified input (ChatGPT-style) - auto-detects URLs, text, or files
    user_input: Optional[str] = Field(
        default=None,
        description="Unified input: text, URL(s), or file reference. Auto-detected. If provided, takes precedence over separate fields."
    )
    
    # LEGACY: Keep for backward compatibility
    text_prompt: Optional[str] = None
    notes: Optional[str] = None
    urls: List[HttpUrl] = Field(default_factory=list)
    attachments: List[str] = Field(default_factory=list)
    prompt_keywords: List[str] = Field(default_factory=list)
    image_source: Optional[str] = None
    voice_engine: Optional[str] = None
    slide_texts: Optional[List[str]] = Field(
        default=None,
        description="Optional per-slide text content. When provided, must have exactly slide_count non-empty strings. Overrides LLM generation for News mode."
    )

    @model_validator(mode='after')
    def _validate_slide_texts(self) -> StoryCreateRequest:
        if self.slide_texts is not None:
            if len(self.slide_texts) != self.slide_count:
                raise ValueError("slide_texts length must equal slide_count")
            self.slide_texts = [s.strip() for s in self.slide_texts]
        return self


class StoryResponse(StoryRecord):
    model_config = ConfigDict(from_attributes=True)

