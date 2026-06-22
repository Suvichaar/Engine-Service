"""SQLAlchemy storage for publish events.

Each row records a single publish action against a story for a given target
(suvichaar_live or webhook). The table lets the admin UI show publish history
per story and prevents re-publishing the same target twice unintentionally.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, Text, inspect, text
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from .story_repository import Base


class PublishORM(Base):
    __tablename__ = "publishes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    story_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    webhook_url: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    published_by: Mapped[str] = mapped_column(String(255), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_publishes_story_target", "story_id", "target"),
    )


def ensure_publish_schema(engine) -> None:
    """No-op safety net; create_all already creates the publishes table."""
    inspector = inspect(engine)
    if not inspector.has_table(PublishORM.__tablename__):
        return
    # Reserved for future column additions, mirroring ensure_story_schema.


@dataclass(frozen=True)
class PublishEvent:
    id: UUID
    story_id: UUID
    target: str
    status: str
    webhook_url: Optional[str]
    error: Optional[str]
    published_by: str
    published_at: datetime


class SqlAlchemyPublishRepository:
    """Persist and read publish events."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def record(
        self,
        *,
        story_id: UUID | str,
        target: str,
        status: str,
        published_by: str,
        webhook_url: Optional[str] = None,
        error: Optional[str] = None,
    ) -> PublishEvent:
        event_id = uuid4()
        published_at = datetime.now(tz=timezone.utc)
        with self._session_factory() as session:  # type: Session
            orm = PublishORM(
                id=str(event_id),
                story_id=str(story_id),
                target=target,
                status=status,
                webhook_url=webhook_url,
                error=error,
                published_by=published_by,
                published_at=published_at,
            )
            session.add(orm)
            session.commit()

        return PublishEvent(
            id=event_id,
            story_id=UUID(str(story_id)),
            target=target,
            status=status,
            webhook_url=webhook_url,
            error=error,
            published_by=published_by,
            published_at=published_at,
        )

    def list_for_story(self, story_id: UUID | str) -> List[PublishEvent]:
        with self._session_factory() as session:  # type: Session
            rows = (
                session.query(PublishORM)
                .filter(PublishORM.story_id == str(story_id))
                .order_by(PublishORM.published_at.desc())
                .all()
            )
            return [_to_event(row) for row in rows]


def _to_event(orm: PublishORM) -> PublishEvent:
    return PublishEvent(
        id=UUID(orm.id),
        story_id=UUID(orm.story_id),
        target=orm.target,
        status=orm.status,
        webhook_url=orm.webhook_url,
        error=orm.error,
        published_by=orm.published_by,
        published_at=orm.published_at,
    )


__all__ = [
    "PublishEvent",
    "PublishORM",
    "SqlAlchemyPublishRepository",
    "ensure_publish_schema",
]
