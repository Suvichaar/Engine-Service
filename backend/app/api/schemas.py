"""API request/response schemas."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.domain.dto import Mode, SlideCount, StoryRecord
from app.services.template_registry import supported_template_keys


class StoryCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "mode": "news",
                    "template_key": "test-news-1",
                    "slide_count": 4,
                    "category": "News",
                    "user_input": "https://suvichaar.org/stories/trump-said-prefer-taking-oil-from-iran-possibility-of-seizing-kharg-island_300326094600956",
                    "notes": "make it in english",
                    "prompt_keywords": ["I want a good images"],
                    "image_source": "ai",
                    "voice_engine": "elevenlabs_pro",
                },
                {
                    "mode": "news",
                    "template_key": "test-news-1",
                    "slide_count": 4,
                    "category": "News",
                    "user_input": "https://indianexpress.com/article/sports/cricket/ipl-cameron-green-bowling-cricket-australia-ajinkya-rahane-kkr-10608515/?ref=rhs_mar_30_latest_news_world",
                    "notes": "I want it in english",
                    "prompt_keywords": ["news", "breaking"],
                    "image_source": "pexels",
                    "voice_engine": "elevenlabs_pro",
                },
                {
                    "mode": "news",
                    "template_key": "test-news-1",
                    "slide_count": 4,
                    "category": "News",
                    "user_input": "https://indianexpress.com/article/sports/cricket/ipl-cameron-green-bowling-cricket-australia-ajinkya-rahane-kkr-10608515/?ref=rhs_mar_30_latest_news_world",
                    "notes": "I want it english",
                    "image_source": "custom",
                    "voice_engine": "elevenlabs_pro",
                    "attachments": [
                        "s3://suvichaarapp/media/images/backgrounds/20260330/51d7eccb-2ce3-4de5-90af-ea7caba6f31f.JPG",
                        "s3://suvichaarapp/media/images/backgrounds/20260330/aca7c320-4a47-43c2-bb20-cecbc556e4bd.png",
                        "s3://suvichaarapp/media/images/backgrounds/20260330/dcc7adbd-1377-4776-85b4-18cfad7243ed.png",
                    ],
                },
            ]
        }
    )
    mode: Mode = Field(default=Mode.NEWS)
    template_key: str = Field(
        description="Registered HTML template key.",
        examples=["test-news-3"],
    )
    slide_count: SlideCount = Field(
        description="Number of slides to generate. Must be between 4 and 10.",
        examples=[4],
    )
    category: Optional[str] = Field(default=None, examples=["News"])
    
    # NEW: Unified input (ChatGPT-style) - auto-detects URLs, text, or files
    user_input: Optional[str] = Field(
        default=None,
        description="Unified input: text, URL(s), or file reference. Auto-detected. If provided, takes precedence over separate fields.",
        examples=[
            "https://indianexpress.com/article/world/donald-trump-iran-oil-kharg-island-seizure-10608749/?ref=breaking_hp"
        ],
    )
    
    # LEGACY: Keep for backward compatibility
    text_prompt: Optional[str] = Field(default=None, examples=["Create a factual short web story."])
    notes: Optional[str] = Field(default=None, examples=["Make it in Hindi"])
    input_mode: Optional[str] = Field(default=None, examples=["slideBySlide"])
    slide_inputs: List[str] = Field(default_factory=list)
    urls: List[HttpUrl] = Field(default_factory=list)
    attachments: List[str] = Field(default_factory=list)
    image_references: List[str] = Field(
        default_factory=list,
        description="Optional background reference images for custom upload or image-to-image AI generation.",
    )
    prompt_keywords: List[str] = Field(default_factory=list)
    image_source: Optional[str] = Field(default=None, examples=["ai"])
    voice_engine: Optional[str] = Field(default=None, examples=["elevenlabs_pro"])
    voice_id: Optional[str] = Field(default=None, examples=["yD0Zg2jxgfQLY8I2MEHO"])

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
