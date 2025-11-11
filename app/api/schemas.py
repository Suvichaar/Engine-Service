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
    text_prompt: Optional[str] = None
    notes: Optional[str] = None
    urls: List[HttpUrl] = Field(default_factory=list)
    attachments: List[str] = Field(default_factory=list)
    prompt_keywords: List[str] = Field(default_factory=list)
    image_source: Optional[str] = None
    voice_engine: Optional[str] = None


class StoryResponse(StoryRecord):
    model_config = ConfigDict(from_attributes=True)

