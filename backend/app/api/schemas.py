"""API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

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
    image_style: Optional[str] = Field(
        default=None,
        description="Optional AI image style: vector, realistic, cinematic, editorial, watercolor, or minimal.",
        examples=["realistic"],
    )
    image_model: Optional[str] = Field(
        default=None,
        description="Optional AI image model: flux_2, mai_2, or gpt_image_15. Defaults to flux_2.",
        examples=["flux_2"],
    )
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


# ── Auth ──────────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: str = Field(examples=["admin@suvichaar.org"])
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Seconds until the token expires.")
    user: "UserResponse"


class UserResponse(BaseModel):
    email: str
    role: str = "admin"


# ── Stories listing ───────────────────────────────────────────────────────────


class StoryListItem(BaseModel):
    id: UUID
    title: Optional[str] = None
    mode: str
    category: Optional[str] = None
    input_language: Optional[str] = None
    slide_count: int
    template_key: str
    canurl: Optional[str] = None
    created_at: datetime


class StoryListResponse(BaseModel):
    items: List[StoryListItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


# ── Publish ───────────────────────────────────────────────────────────────────


PublishTarget = Literal["suvichaar_live", "webhook"]
PublishStatus = Literal["success", "failed", "pending"]


class PublishRequest(BaseModel):
    target: PublishTarget
    webhook_url: Optional[str] = Field(
        default=None,
        description="Required when target is 'webhook'.",
        examples=["https://example.com/incoming/suvichaar"],
    )


class PublishHistoryItem(BaseModel):
    id: UUID
    story_id: UUID
    target: PublishTarget
    status: PublishStatus
    webhook_url: Optional[str] = None
    error: Optional[str] = None
    published_by: str
    published_at: datetime


class PublishResponse(PublishHistoryItem):
    """Response returned when a publish action succeeds."""

    pass


class PublishHistoryResponse(BaseModel):
    items: List[PublishHistoryItem] = Field(default_factory=list)


# ── StoryBoard ────────────────────────────────────────────────────────────────


StoryboardStatus = Literal["draft", "published", "archived"]
StoryboardSource = Literal["manual", "bulk_csv", "strapi", "api"]


class StoryboardMediaItem(BaseModel):
    url: str = Field(min_length=1)
    type: Literal["image", "video", "audio"] = "image"
    alt: Optional[str] = None
    caption: Optional[str] = None


class StoryboardBase(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    slug: str = Field(min_length=1, max_length=256, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
    category: Optional[str] = Field(default=None, max_length=128)
    tags: List[str] = Field(default_factory=list)
    cover_url: Optional[str] = None
    media_urls: List[StoryboardMediaItem] = Field(default_factory=list)
    language: Optional[str] = Field(default=None, max_length=16)
    mode: Optional[Literal["news", "curious"]] = None
    status: StoryboardStatus = "draft"
    external_id: Optional[str] = Field(default=None, max_length=128)
    notes: Optional[str] = None


class StoryboardCreateRequest(StoryboardBase):
    pass


class StoryboardUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=512)
    slug: Optional[str] = Field(
        default=None, min_length=1, max_length=256, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$"
    )
    category: Optional[str] = Field(default=None, max_length=128)
    tags: Optional[List[str]] = None
    cover_url: Optional[str] = None
    media_urls: Optional[List[StoryboardMediaItem]] = None
    language: Optional[str] = Field(default=None, max_length=16)
    mode: Optional[Literal["news", "curious"]] = None
    status: Optional[StoryboardStatus] = None
    external_id: Optional[str] = Field(default=None, max_length=128)
    notes: Optional[str] = None


class StoryboardItem(StoryboardBase):
    id: UUID
    source: StoryboardSource
    created_by: str
    created_at: datetime
    updated_at: datetime


class StoryboardListResponse(BaseModel):
    items: List[StoryboardItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class StoryboardBulkCreateRequest(BaseModel):
    items: List[StoryboardCreateRequest] = Field(min_length=1, max_length=500)


class StoryboardBulkCreateResponse(BaseModel):
    created: List[StoryboardItem] = Field(default_factory=list)
    errors: List[dict] = Field(default_factory=list)
    requested: int
    succeeded: int
    failed: int


# ── Broadcast ────────────────────────────────────────────────────────────────


BroadcastChannel = Literal["whatsapp", "email"]
BroadcastStatus = Literal["queued", "partial", "sent", "failed"]


class BroadcastRecipient(BaseModel):
    phone: Optional[str] = Field(default=None, max_length=32)
    email: Optional[str] = Field(default=None, max_length=255)
    name: Optional[str] = Field(default=None, max_length=255)
    tags: List[str] = Field(default_factory=list)

    @field_validator("phone", "email", mode="before")
    @classmethod
    def _strip(cls, value):
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class BroadcastRequest(BaseModel):
    channels: List[BroadcastChannel] = Field(min_length=1)
    recipients: List[BroadcastRecipient] = Field(default_factory=list)
    audience_tag: Optional[str] = Field(default=None, max_length=128)
    message: Optional[str] = Field(default=None, max_length=4000)


class BroadcastOutcome(BaseModel):
    channel: BroadcastChannel
    recipient: str
    status: Literal["sent", "failed", "queued"]
    error: Optional[str] = None


class BroadcastHistoryItem(BaseModel):
    id: UUID
    story_id: UUID
    channels: List[BroadcastChannel]
    status: BroadcastStatus
    audience_tag: Optional[str] = None
    message: Optional[str] = None
    total_count: int
    sent_count: int
    failed_count: int
    triggered_by: str
    created_at: datetime
    updated_at: datetime
    outcomes: List[BroadcastOutcome] = Field(default_factory=list)


class BroadcastResponse(BroadcastHistoryItem):
    pass


class BroadcastHistoryResponse(BaseModel):
    items: List[BroadcastHistoryItem] = Field(default_factory=list)


# ── Subscribers ──────────────────────────────────────────────────────────────


SubscriberStatus = Literal["active", "inactive", "cancelled"]
SubscriberSource = Literal["manual", "bulk_csv", "razorpay", "labs_subscribe", "api"]


class SubscriberBase(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=32)
    email: Optional[str] = Field(default=None, max_length=255)
    tags: List[str] = Field(default_factory=list)
    subscription: dict = Field(default_factory=dict)
    extra: dict = Field(default_factory=dict)
    status: SubscriberStatus = "active"

    @field_validator("phone", "email", "name", mode="before")
    @classmethod
    def _strip(cls, value):
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class SubscriberCreateRequest(SubscriberBase):
    pass


class SubscriberUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=32)
    email: Optional[str] = Field(default=None, max_length=255)
    tags: Optional[List[str]] = None
    subscription: Optional[dict] = None
    extra: Optional[dict] = None
    status: Optional[SubscriberStatus] = None


class SubscriberItem(SubscriberBase):
    id: UUID
    source: SubscriberSource
    created_at: datetime
    updated_at: datetime


class SubscriberListResponse(BaseModel):
    items: List[SubscriberItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class SubscriberBulkCreateRequest(BaseModel):
    items: List[SubscriberCreateRequest] = Field(min_length=1, max_length=1000)


class SubscriberBulkCreateResponse(BaseModel):
    created: List[SubscriberItem] = Field(default_factory=list)
    errors: List[dict] = Field(default_factory=list)
    requested: int
    succeeded: int
    failed: int


class SubscriberTagItem(BaseModel):
    tag: str
    count: int


class SubscriberTagsResponse(BaseModel):
    items: List[SubscriberTagItem] = Field(default_factory=list)
