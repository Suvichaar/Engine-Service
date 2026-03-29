"""API request/response schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

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


class StoryResponse(StoryRecord):
    model_config = ConfigDict(from_attributes=True)

