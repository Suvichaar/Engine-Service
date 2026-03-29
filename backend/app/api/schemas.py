"""API request/response schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.domain.dto import Mode, SlideCount, StoryRecord
from app.services.template_registry import supported_template_keys


class StoryCreateRequest(BaseModel):
    mode: Mode = Field(default=Mode.NEWS)
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

    @field_validator("template_key")
    @classmethod
    def validate_template_key(cls, value: str) -> str:
        allowed_keys = supported_template_keys(Mode.NEWS)
        if value not in allowed_keys:
            allowed = ", ".join(sorted(allowed_keys))
            raise ValueError(f"Unsupported template_key '{value}'. Allowed values: {allowed}")
        return value


class StoryResponse(StoryRecord):
    model_config = ConfigDict(from_attributes=True)
