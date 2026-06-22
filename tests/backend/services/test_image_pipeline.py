from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import pytest
from PIL import Image

from app.domain.dto import ImageAsset, IntakePayload, Mode, SlideBlock, SlideDeck
from app.services.image_pipeline import (
    AI_IMAGE_HEIGHT,
    AI_IMAGE_WIDTH,
    AIImageProvider,
    DefaultImageAssetPipeline,
    ImageContent,
    ImageStorageService,
    PexelsImageProvider,
    S3ImageStorageService,
    UserUploadProvider,
)
from app.services.image_prompts import generate_news_slide_prompt, is_sensitive_news_topic


@dataclass
class StubStorage(ImageStorageService):
    stored: list[ImageContent]

    def __init__(self):
        self.stored = []

    def store(self, *, content: ImageContent, source: str) -> ImageAsset:
        self.stored.append(content)
        return ImageAsset(
            source=source,
            original_object_key=f"mock/{content.filename}",
            resized_variants=[f"https://cdn.test/{content.filename}"],
            description=content.description,
        )


class StubProvider:
    source = "stub"

    def __init__(self, supports: bool, contents: list[ImageContent]):
        self._supports = supports
        self._contents = contents

    def supports(self, payload: IntakePayload) -> bool:
        return self._supports

    def generate(self, deck: SlideDeck, payload: IntakePayload):
        return self._contents


def make_payload(image_source: str, attachments: list[str] | None = None) -> IntakePayload:
    return IntakePayload(
        text_prompt="",
        notes=None,
        urls=[],
        attachments=attachments or [],
        prompt_keywords=["innovation"],
        mode=Mode.NEWS,
        template_key="test-news-1",
        slide_count=4,
        category="News",
        image_source=image_source,
        voice_engine=None,
    )


def make_deck() -> SlideDeck:
    return SlideDeck(
        template_key="test-news-1",
        language_code="en",
        slides=[
            SlideBlock(placeholder_id="title", text="AI Revolution"),
            SlideBlock(placeholder_id="body", text="Impact on industries"),
        ],
    )


def test_pipeline_uses_matching_provider_and_storage():
    provider = StubProvider(
        supports=True,
        contents=[
            ImageContent(placeholder_id="title", content=b"a", filename="title.jpg"),
            ImageContent(placeholder_id="body", content=b"b", filename="body.jpg"),
        ],
    )
    storage = StubStorage()
    pipeline = DefaultImageAssetPipeline([provider], storage)

    assets = pipeline.process(make_deck(), make_payload("ai"))

    assert len(assets) == 2
    assert storage.stored[0].placeholder_id == "title"
    assert str(assets[0].resized_variants[0]).startswith("https://cdn.test/")


def test_pipeline_returns_empty_when_no_provider_supports():
    storage = StubStorage()
    pipeline = DefaultImageAssetPipeline([StubProvider(False, [])], storage)

    assets = pipeline.process(make_deck(), make_payload("ai"))

    assert assets == []
    assert storage.stored == []


def test_user_upload_provider_converts_attachments():
    provider = UserUploadProvider()
    payload = make_payload("custom", attachments=["s3://bucket/image1.png"])
    contents = provider.generate(make_deck(), payload)

    assert len(contents) == 2
    assert contents[0].filename == "image1.png"
    assert contents[1].filename == "image1.png"


def test_s3_storage_service_generates_cloudfront_urls():
    storage = S3ImageStorageService(
        bucket="bucket",
        prefix="media",
        cdn_base="https://cdn.example.com",
        resize_variants={"sm": "320x180", "md": "768x432"},
    )
    asset = storage.store(
        content=ImageContent(placeholder_id="p", content=b"bytes", filename="image.jpg"),
        source="ai",
    )

    assert asset.source == "ai"
    assert asset.original_object_key.startswith("media/")
    assert len(asset.resized_variants) == 2
    assert all(str(url).startswith("https://cdn.example.com") for url in asset.resized_variants)


def test_sensitive_news_topic_uses_safe_editorial_prompt():
    article_content = (
        "A national leader hinted at the possibility of seizing a strategic island "
        "near a major oil export hub as military tensions rose around shipping lanes."
    )

    assert is_sensitive_news_topic(article_content)

    prompt = generate_news_slide_prompt(
        "Leader comments on energy route control",
        slide_index=0,
        is_cover=True,
        article_content=article_content,
    )
    lowered = prompt.lower()

    assert "professional news cover illustration" in lowered
    assert "calm informative mood" in lowered
    assert "seizing" not in lowered
    assert "military" not in lowered
    assert "oil" not in lowered
    assert "text-free image" in lowered
    assert "readable words" in lowered
    assert "typography" in lowered


def test_news_ai_prompt_forbids_rendered_text():
    prompt = generate_news_slide_prompt(
        "New education policy improves student learning",
        slide_index=0,
        is_cover=True,
        article_content="Education policy update about learning outcomes.",
    )

    lowered = prompt.lower()
    assert "text-free image" in lowered
    assert "readable words" in lowered
    assert "typography" in lowered
    assert "app icons" in lowered
    assert "signage" in lowered


def test_news_ai_prompt_applies_requested_style():
    realistic_prompt = generate_news_slide_prompt(
        "New airport terminal opens for passengers",
        slide_index=1,
        image_style="realistic",
    )
    vector_prompt = generate_news_slide_prompt(
        "New airport terminal opens for passengers",
        slide_index=1,
        image_style="vector",
    )

    assert "realistic editorial photography style" in realistic_prompt
    assert "clean vector illustration" in vector_prompt


def test_ai_provider_requests_portrait_dimensions():
    provider = AIImageProvider(
        endpoint="https://example.services.ai.azure.com/models/providers/blackforestlabs/flux-2-pro/images/generations",
        api_key="test-key",
    )

    body = provider._build_request_body("portrait image", reference_image_bytes=None)

    assert body["width"] == AI_IMAGE_WIDTH
    assert body["height"] == AI_IMAGE_HEIGHT


def test_ai_provider_normalizes_image_bytes_to_story_portrait_size():
    provider = AIImageProvider(endpoint="https://example.test/openai/images", api_key="test-key")
    source = Image.new("RGB", (1024, 1024), color="red")
    buffer = BytesIO()
    source.save(buffer, format="PNG")

    normalized = provider._normalize_image_bytes(buffer.getvalue())

    with Image.open(BytesIO(normalized)) as img:
        assert img.size == (AI_IMAGE_WIDTH, AI_IMAGE_HEIGHT)


@pytest.mark.parametrize(
    "text",
    [
        "A national leader hinted at seizing a strategic island near a major energy terminal.",
        "Military forces deployed near a border waterway after weeks of regional tension.",
        "The government announced sanctions affecting oil tankers near a strategic strait.",
        "Naval patrols increased around a shipping lane after officials discussed a blockade.",
        "A commander said forces may occupy a port that handles gas pipeline exports.",
    ],
)
def test_sensitive_news_topic_detects_geopolitical_security_edges(text):
    assert is_sensitive_news_topic(text)


@pytest.mark.parametrize(
    "text",
    [
        "A technology company launched a new AI service for education customers.",
        "Oil prices rose as tankers moved through a busy shipping lane without disruption.",
        "The president opened a clean energy terminal with local business leaders.",
        "A travel guide named the island one of the best destinations for families.",
        "A sports team leader praised defensive discipline after a tournament win.",
        "A government digital payments initiative expanded to rural markets.",
    ],
)
def test_sensitive_news_topic_avoids_common_news_false_positives(text):
    assert not is_sensitive_news_topic(text)
