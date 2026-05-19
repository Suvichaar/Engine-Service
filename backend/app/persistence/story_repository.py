"""SQLAlchemy-based implementation of the StoryRepository."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import DateTime, Integer, JSON, String, Text, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.domain.dto import DocInsights, ImageAsset, Mode, SlideDeck, StoryRecord, VoiceAsset
from app.domain.interfaces import StoryRepository


class Base(DeclarativeBase):
    pass


class StoryORM(Base):
    __tablename__ = "stories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    input_language: Mapped[str | None] = mapped_column(String(16))
    slide_count: Mapped[int] = mapped_column(Integer, nullable=False)
    template_key: Mapped[str] = mapped_column(String(128), nullable=False)
    doc_insights: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    slide_deck: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    image_assets: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    voice_assets: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    prompt_news: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    prompt_file: Mapped[str | None] = mapped_column(String(255))
    canurl: Mapped[str | None] = mapped_column(Text)
    canurl1: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def ensure_story_schema(engine) -> None:
    """Add columns introduced after the initial stories table was created."""

    inspector = inspect(engine)
    if not inspector.has_table(StoryORM.__tablename__):
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns(StoryORM.__tablename__)
    }
    required_columns = {
        "prompt_news": "TEXT",
        "prompt_version": "VARCHAR(32)",
        "prompt_file": "VARCHAR(255)",
        "canurl": "TEXT",
        "canurl1": "TEXT",
    }
    missing_columns = [
        (name, column_type)
        for name, column_type in required_columns.items()
        if name not in existing_columns
    ]
    if not missing_columns:
        return

    with engine.begin() as connection:
        for name, column_type in missing_columns:
            connection.execute(
                text(f"ALTER TABLE {StoryORM.__tablename__} ADD COLUMN {name} {column_type}")
            )


class SqlAlchemyStoryRepository(StoryRepository):
    """Persist StoryRecord aggregates using SQLAlchemy."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def save(self, record: StoryRecord) -> StoryRecord:
        from sqlalchemy.orm import Session

        with self._session_factory() as session:  # type: Session
            existing = session.get(StoryORM, str(record.id))
            payload = self._serialize(record)

            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
                orm = existing
            else:
                orm = StoryORM(**payload)
                session.add(orm)

            session.commit()
            return record

    def get(self, story_id: str) -> StoryRecord:
        from sqlalchemy.orm import Session

        with self._session_factory() as session:  # type: Session
            orm = session.get(StoryORM, story_id)
            if orm is None:
                raise KeyError(f"Story with id {story_id} not found.")
            return self._deserialize(orm)

    def get_by_canurl(self, canurl: str) -> StoryRecord:
        """Load a story record by its canonical URL (slug)."""
        from sqlalchemy.orm import Session
        from sqlalchemy import or_

        with self._session_factory() as session:  # type: Session
            # Search in both canurl and canurl1 fields
            orm = session.query(StoryORM).filter(
                or_(
                    StoryORM.canurl == canurl,
                    StoryORM.canurl1 == canurl,
                    StoryORM.canurl.like(f"%{canurl}%"),
                    StoryORM.canurl1.like(f"%{canurl}%")
                )
            ).first()
            
            if orm is None:
                raise KeyError(f"Story with URL {canurl} not found.")
            return self._deserialize(orm)

    def _serialize(self, record: StoryRecord) -> Dict[str, Any]:
        return {
            "id": str(record.id),
            "mode": record.mode.value,
            "category": record.category,
            "input_language": record.input_language,
            "slide_count": record.slide_count,
            "template_key": record.template_key,
            "doc_insights": record.doc_insights.model_dump(mode="json"),
            "slide_deck": record.slide_deck.model_dump(mode="json"),
            "image_assets": [asset.model_dump(mode="json") for asset in record.image_assets],
            "voice_assets": [asset.model_dump(mode="json") for asset in record.voice_assets],
            "prompt_news": record.prompt_news,
            "prompt_version": record.prompt_version,
            "prompt_file": record.prompt_file,
            "canurl": str(record.canurl) if record.canurl else None,
            "canurl1": str(record.canurl1) if record.canurl1 else None,
            "created_at": record.created_at,
        }

    def _deserialize(self, orm: StoryORM) -> StoryRecord:
        return StoryRecord(
            id=UUID(orm.id),
            mode=Mode(orm.mode),
            category=orm.category,
            input_language=orm.input_language,
            slide_count=orm.slide_count,
            template_key=orm.template_key,
            doc_insights=DocInsights(**orm.doc_insights),
            slide_deck=SlideDeck(**orm.slide_deck),
            image_assets=[ImageAsset(**item) for item in orm.image_assets],
            voice_assets=[VoiceAsset(**item) for item in orm.voice_assets],
            prompt_news=orm.prompt_news,
            prompt_version=orm.prompt_version,
            prompt_file=orm.prompt_file,
            canurl=orm.canurl,
            canurl1=orm.canurl1,
            created_at=orm.created_at,
        )


__all__ = ["SqlAlchemyStoryRepository", "StoryORM", "Base", "ensure_story_schema"]
