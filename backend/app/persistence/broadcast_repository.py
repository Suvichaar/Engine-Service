"""SQLAlchemy storage for broadcast events.

A broadcast is a single fan-out of one story to a list of recipients across
one or more channels (whatsapp, email). Each row captures the request, the
per-channel delivery outcome counts, and the recipient list so admins can
audit who got what.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, JSON, Integer, String, Text, inspect
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from .story_repository import Base


class BroadcastORM(Base):
    __tablename__ = "broadcasts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    story_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    channels: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    audience_tag: Mapped[str | None] = mapped_column(String(128))
    message: Mapped[str | None] = mapped_column(Text)
    recipients: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    outcomes: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    triggered_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_broadcasts_story_created", "story_id", "created_at"),
    )


def ensure_broadcast_schema(engine) -> None:
    """No-op safety net; create_all already creates the broadcasts table."""
    inspector = inspect(engine)
    if not inspector.has_table(BroadcastORM.__tablename__):
        return
    # Reserved for future column additions.


@dataclass(frozen=True)
class BroadcastEvent:
    id: UUID
    story_id: UUID
    channels: List[str]
    status: str
    audience_tag: Optional[str]
    message: Optional[str]
    recipients: List[Dict[str, Any]]
    outcomes: List[Dict[str, Any]]
    total_count: int
    sent_count: int
    failed_count: int
    triggered_by: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, orm: BroadcastORM) -> "BroadcastEvent":
        return cls(
            id=UUID(orm.id),
            story_id=UUID(orm.story_id),
            channels=list(orm.channels or []),
            status=orm.status,
            audience_tag=orm.audience_tag,
            message=orm.message,
            recipients=list(orm.recipients or []),
            outcomes=list(orm.outcomes or []),
            total_count=orm.total_count,
            sent_count=orm.sent_count,
            failed_count=orm.failed_count,
            triggered_by=orm.triggered_by,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )


class SqlAlchemyBroadcastRepository:
    """Persist and read broadcast events."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def record(
        self,
        *,
        story_id: UUID | str,
        channels: List[str],
        status: str,
        recipients: List[Dict[str, Any]],
        outcomes: List[Dict[str, Any]],
        total_count: int,
        sent_count: int,
        failed_count: int,
        triggered_by: str,
        audience_tag: Optional[str] = None,
        message: Optional[str] = None,
    ) -> BroadcastEvent:
        event_id = uuid4()
        now = datetime.now(tz=timezone.utc)
        with self._session_factory() as session:  # type: Session
            orm = BroadcastORM(
                id=str(event_id),
                story_id=str(story_id),
                channels=list(channels or []),
                status=status,
                audience_tag=audience_tag,
                message=message,
                recipients=list(recipients or []),
                outcomes=list(outcomes or []),
                total_count=total_count,
                sent_count=sent_count,
                failed_count=failed_count,
                triggered_by=triggered_by,
                created_at=now,
                updated_at=now,
            )
            session.add(orm)
            session.commit()
            session.refresh(orm)
            return BroadcastEvent.from_orm(orm)

    def list_for_story(self, story_id: UUID | str) -> List[BroadcastEvent]:
        with self._session_factory() as session:  # type: Session
            rows = (
                session.query(BroadcastORM)
                .filter(BroadcastORM.story_id == str(story_id))
                .order_by(BroadcastORM.created_at.desc())
                .all()
            )
            return [BroadcastEvent.from_orm(r) for r in rows]
