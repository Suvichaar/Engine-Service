from __future__ import annotations

from dataclasses import dataclass

from app.domain.dto import ImageAsset, IntakePayload, Mode, SlideBlock, SlideDeck
from app.services.image_pipeline import (
    AIImageProvider,
    DefaultImageAssetPipeline,
    ImageContent,
    ImageStorageService,
    PexelsImageProvider,
    S3ImageStorageService,
    UserUploadProvider,
)


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
        mode=Mode.CURIOUS,
        template_key="modern",
        slide_count=4,
        category="Art",
        image_source=image_source,
        voice_engine=None,
    )


def make_deck() -> SlideDeck:
    return SlideDeck(
        template_key="modern",
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

    assert len(contents) == 1
    assert contents[0].filename == "image1.png"


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

