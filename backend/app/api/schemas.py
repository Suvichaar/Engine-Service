"""API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.domain.dto import Mode, SlideCount, StoryRecord
from app.services.template_registry import supported_template_keys


class StoryCreateRequest(BaseModel):
    mode: Mode = Field(default=Mode.CURIOUS)
    template_key: str = Field(
        description="Registered HTML template key.",
        examples=["curious-template-1"],
    )
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
            "examples": [
                {
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
            ]
        }
    )

    @field_validator("template_key")
    @classmethod
    def validate_template_key(cls, value: str) -> str:
        allowed_keys = supported_template_keys(Mode.CURIOUS)
        if value not in allowed_keys:
            allowed = ", ".join(sorted(allowed_keys))
            raise ValueError(f"Unsupported template_key '{value}'. Allowed values: {allowed}")
        return value


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


StoryJobStatus = Literal["pending", "processing", "completed", "failed"]


class StoryJobAck(BaseModel):
    id: UUID
    status: StoryJobStatus = "pending"


class StoryJobStatusResponse(BaseModel):
    id: UUID
    status: StoryJobStatus
    error: Optional[str] = None
    story: Optional[StoryResponse] = None
    created_at: datetime
    updated_at: datetime


PromptGroup = Literal["text_prompts", "image_prompts"]


class PromptVersionResponse(BaseModel):
    group: PromptGroup
    key: str
    version: str
    file_name: str
    description: Optional[str] = None
    status: Optional[str] = None
    allowed_categories: List[str] = Field(default_factory=list)
    required_placeholders: List[str] = Field(default_factory=list)
    system: str
    user_template: str
    is_active: bool


class PromptGroupResponse(BaseModel):
    key: str
    versions: List[PromptVersionResponse] = Field(default_factory=list)


class PromptListingResponse(BaseModel):
    text_prompts: List[PromptGroupResponse] = Field(default_factory=list)
    image_prompts: List[PromptGroupResponse] = Field(default_factory=list)


class PromptCreateRequest(BaseModel):
    group: PromptGroup
    key: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    description: Optional[str] = None
    status: Optional[str] = None
    allowed_categories: List[str] = Field(default_factory=list)
    required_placeholders: List[str] = Field(default_factory=list)
    system: str = Field(min_length=1)
    user_template: str = Field(min_length=1)
    active: bool = True


class PromptUpdateRequest(BaseModel):
    description: Optional[str] = None
    status: Optional[str] = None
    allowed_categories: List[str] = Field(default_factory=list)
    required_placeholders: List[str] = Field(default_factory=list)
    system: str = Field(min_length=1)
    user_template: str = Field(min_length=1)
    active: Optional[bool] = None


class PromptActivateRequest(BaseModel):
    group: PromptGroup
    key: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)


class TemplateVersionResponse(BaseModel):
    key: str
    version: str
    mode: str
    file_name: str
    file_path: str
    slide_generator: str
    description: Optional[str] = None
    enabled: bool
    is_active: bool
    html_content: str


class TemplateFamilyResponse(BaseModel):
    key: str
    versions: List[TemplateVersionResponse] = Field(default_factory=list)


class TemplateListingResponse(BaseModel):
    templates: List[TemplateFamilyResponse] = Field(default_factory=list)


class TemplateCreateRequest(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    slide_generator: str = Field(min_length=1, max_length=120)
    description: Optional[str] = None
    enabled: bool = True
    active: bool = True
    html_content: str = Field(min_length=1)


class TemplateUpdateRequest(BaseModel):
    slide_generator: str = Field(min_length=1, max_length=120)
    description: Optional[str] = None
    enabled: bool = True
    active: Optional[bool] = None
    html_content: str = Field(min_length=1)


class TemplateActivateRequest(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
