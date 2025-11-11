from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.dto import (
    DocInsights,
    ImageAsset,
    Mode,
    SemanticChunk,
    SlideBlock,
    SlideDeck,
    StoryRecord,
    VoiceAsset,
)
from app.persistence.story_repository import Base, SqlAlchemyStoryRepository


def make_story_record() -> StoryRecord:
    return StoryRecord(
        id=uuid4(),
        mode=Mode.CURIOUS,
        category="Art",
        input_language="en",
        slide_count=4,
        template_key="modern",
        doc_insights=DocInsights(
            semantic_chunks=[SemanticChunk(id="chunk-1", text="Sample text")],
            summaries=["Summary"],
            gaps=[],
            recommended_prompts=[],
        ),
        slide_deck=SlideDeck(
            template_key="modern",
            language_code="en",
            slides=[SlideBlock(placeholder_id="title", text="Hello")],
        ),
        image_assets=[
            ImageAsset(
                source="ai",
                original_object_key="media/1.png",
                resized_variants=["https://cdn/img1.png"],
                description="desc",
            )
        ],
        voice_assets=[
            VoiceAsset(
                provider="elevenlabs",
                voice_id="voice",
                audio_url="https://cdn/audio.mp3",
                duration_seconds=10.0,
            )
        ],
        prompt_news="news prompt",
        prompt_curious="curious prompt",
        canurl="https://story/primary",
        canurl1="https://story/secondary",
        created_at=datetime.utcnow(),
    )


def make_repository():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
    return SqlAlchemyStoryRepository(session_factory), session_factory


def test_story_repository_save_and_get():
    repo, _ = make_repository()
    record = make_story_record()

    repo.save(record)
    fetched = repo.get(str(record.id))

    assert fetched.id == record.id
    assert fetched.category == "Art"
    assert fetched.slide_deck.template_key == "modern"
    assert fetched.image_assets[0].source == "ai"


def test_story_repository_updates_existing_record():
    repo, _ = make_repository()
    record = make_story_record()

    repo.save(record)
    updated = record.model_copy(update={"category": "History", "prompt_news": "updated news"})
    repo.save(updated)

    fetched = repo.get(str(record.id))
    assert fetched.category == "History"
    assert fetched.prompt_news == "updated news"

