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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mode": "curious",
                "template_key": "curious-template-1",
                "slide_count": 4,
                "category": "History",
                "user_input": "Explain the history of the Pyramids of Giza.",
                "text_prompt": "",
                "notes": "",
                "urls": [],
                "attachments": [],
                "prompt_keywords": ["pyramids", "egypt"],
                "image_source": "ai",
                "voice_engine": "elevenlabs_pro"
            }
        }
    )


class StoryResponse(StoryRecord):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "mode": "curious",
                "category": "History",
                "input_language": "en",
                "slide_count": 4,
                "template_key": "curious-template-1",
                "doc_insights": {
                    "semantic_chunks": [],
                    "metadata": {}
                },
                "slide_deck": {
                    "slides": []
                },
                "image_assets": [],
                "voice_assets": [],
                "created_at": "2023-10-14T15:30:00Z",
                "canurl": "https://suvichaar.org/stories/history_of_pyramids_14102023153000",
                "canurl1": "https://suvichaar.org/stories/history_of_pyramids_14102023153000.html"
            }
        }
    )

