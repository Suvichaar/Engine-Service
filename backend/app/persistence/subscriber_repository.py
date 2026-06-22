"""SQLAlchemy storage for Subscribers.

Subscribers come from two sources:

1. Razorpay payment webhook — `payment.captured` or `subscription.activated`
   creates/updates a subscriber by phone (and email when present), recording
   the payment id, amount, and a structured `subscription` blob.
2. Admin UI — manual single-add or bulk CSV upload from the admin panel.

Tags drive audience selection for broadcasts. A subscriber row stores the
chosen tags as a JSON array; broadcasts look up active subscribers whose
tags include the requested audience tag.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Index,
    JSON,
    String,
    Text,
    and_,
    func,
    inspect,
    or_,
    text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from .story_repository import Base


class SubscriberORM(Base):
    __tablename__ = "subscribers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32), index=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    tags: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    subscription: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    extra: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_subscribers_status_created", "status", "created_at"),
    )


def ensure_subscriber_schema(engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table(SubscriberORM.__tablename__):
        return
    existing = {c["name"] for c in inspector.get_columns(SubscriberORM.__tablename__)}
    additions: Dict[str, str] = {}
    missing = [(n, t) for n, t in additions.items() if n not in existing]
    if not missing:
        return
    with engine.begin() as conn:
        for name, column_type in missing:
            conn.execute(
                text(
                    f"ALTER TABLE {SubscriberORM.__tablename__} "
                    f"ADD COLUMN {name} {column_type}"
                )
            )


@dataclass(frozen=True)
class SubscriberRecord:
    id: UUID
    name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    tags: List[str]
    subscription: Dict[str, Any]
    extra: Dict[str, Any]
    status: str
    source: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, orm: SubscriberORM) -> "SubscriberRecord":
        return cls(
            id=UUID(orm.id),
            name=orm.name,
            phone=orm.phone,
            email=orm.email,
            tags=list(orm.tags or []),
            subscription=dict(orm.subscription or {}),
            extra=dict(orm.extra or {}),
            status=orm.status,
            source=orm.source,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )


class SubscriberNotFound(Exception):
    pass


class SqlAlchemySubscriberRepository:
    """CRUD + paginated listing + audience lookup for subscribers."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    # ── writes ─────────────────────────────────────────────────────────────

    def create(
        self,
        *,
        name: Optional[str],
        phone: Optional[str],
        email: Optional[str],
        tags: List[str],
        subscription: Optional[Dict[str, Any]],
        extra: Optional[Dict[str, Any]],
        status: str,
        source: str,
    ) -> SubscriberRecord:
        if not phone and not email:
            raise ValueError("subscriber needs phone or email")
        now = datetime.now(tz=timezone.utc)
        with self._session_factory() as session:  # type: Session
            orm = SubscriberORM(
                id=str(uuid4()),
                name=name,
                phone=phone,
                email=email,
                tags=list(tags or []),
                subscription=dict(subscription or {}),
                extra=dict(extra or {}),
                status=status,
                source=source,
                created_at=now,
                updated_at=now,
            )
            session.add(orm)
            session.commit()
            session.refresh(orm)
            return SubscriberRecord.from_orm(orm)

    def bulk_create(
        self,
        rows: List[Dict[str, Any]],
        *,
        source: str = "bulk_csv",
    ) -> Tuple[List[SubscriberRecord], List[Dict[str, Any]]]:
        created: List[SubscriberRecord] = []
        errors: List[Dict[str, Any]] = []
        now = datetime.now(tz=timezone.utc)
        with self._session_factory() as session:  # type: Session
            seen: set[str] = set()
            for idx, row in enumerate(rows):
                phone = (row.get("phone") or "").strip() or None
                email = (row.get("email") or "").strip() or None
                if not phone and not email:
                    errors.append({"row": idx, "error": "phone or email required"})
                    continue
                key = phone or email or ""
                if key in seen:
                    errors.append({"row": idx, "error": f"duplicate in upload: {key}"})
                    continue
                seen.add(key)
                orm = SubscriberORM(
                    id=str(uuid4()),
                    name=(row.get("name") or None),
                    phone=phone,
                    email=email,
                    tags=list(row.get("tags") or []),
                    subscription=dict(row.get("subscription") or {}),
                    extra=dict(row.get("extra") or {}),
                    status=(row.get("status") or "active"),
                    source=source,
                    created_at=now,
                    updated_at=now,
                )
                session.add(orm)
                session.flush()
                created.append(SubscriberRecord.from_orm(orm))
            session.commit()
        return created, errors

    def update(self, sub_id: UUID | str, *, updates: Dict[str, Any]) -> SubscriberRecord:
        with self._session_factory() as session:  # type: Session
            orm = session.get(SubscriberORM, str(sub_id))
            if not orm:
                raise SubscriberNotFound(str(sub_id))
            allowed = {"name", "phone", "email", "tags", "subscription", "extra", "status"}
            for key, value in updates.items():
                if key in allowed:
                    setattr(orm, key, value)
            orm.updated_at = datetime.now(tz=timezone.utc)
            session.commit()
            session.refresh(orm)
            return SubscriberRecord.from_orm(orm)

    def delete(self, sub_id: UUID | str) -> None:
        with self._session_factory() as session:  # type: Session
            orm = session.get(SubscriberORM, str(sub_id))
            if not orm:
                raise SubscriberNotFound(str(sub_id))
            session.delete(orm)
            session.commit()

    def upsert_from_payment(
        self,
        *,
        phone: Optional[str],
        email: Optional[str],
        name: Optional[str],
        tags: List[str],
        subscription: Dict[str, Any],
        source: str = "razorpay",
    ) -> SubscriberRecord:
        """Find existing subscriber by phone, else by email, else create.

        Tags are union-merged so a returning payer keeps prior selections;
        subscription dict is replaced with the latest payment payload so the
        most recent state wins.
        """
        if not phone and not email:
            raise ValueError("upsert_from_payment needs phone or email")
        now = datetime.now(tz=timezone.utc)
        with self._session_factory() as session:  # type: Session
            existing: Optional[SubscriberORM] = None
            if phone:
                existing = (
                    session.query(SubscriberORM)
                    .filter(SubscriberORM.phone == phone)
                    .first()
                )
            if existing is None and email:
                existing = (
                    session.query(SubscriberORM)
                    .filter(SubscriberORM.email == email)
                    .first()
                )

            if existing is None:
                orm = SubscriberORM(
                    id=str(uuid4()),
                    name=name,
                    phone=phone,
                    email=email,
                    tags=list(tags or []),
                    subscription=dict(subscription or {}),
                    extra={},
                    status="active",
                    source=source,
                    created_at=now,
                    updated_at=now,
                )
                session.add(orm)
            else:
                orm = existing
                # Merge tags as a deduplicated union; preserve order.
                merged_tags = list(orm.tags or [])
                for t in tags or []:
                    if t not in merged_tags:
                        merged_tags.append(t)
                orm.tags = merged_tags
                if name and not orm.name:
                    orm.name = name
                if phone and not orm.phone:
                    orm.phone = phone
                if email and not orm.email:
                    orm.email = email
                orm.subscription = dict(subscription or {})
                orm.status = "active"
                orm.source = source
                orm.updated_at = now
            session.commit()
            session.refresh(orm)
            return SubscriberRecord.from_orm(orm)

    # ── reads ──────────────────────────────────────────────────────────────

    def get(self, sub_id: UUID | str) -> SubscriberRecord:
        with self._session_factory() as session:  # type: Session
            orm = session.get(SubscriberORM, str(sub_id))
            if not orm:
                raise SubscriberNotFound(str(sub_id))
            return SubscriberRecord.from_orm(orm)

    def list(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        q: Optional[str] = None,
        tag: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[SubscriberRecord], int]:
        with self._session_factory() as session:  # type: Session
            query = session.query(SubscriberORM)
            conditions = []
            if status:
                conditions.append(SubscriberORM.status == status)
            if q:
                like = f"%{q}%"
                conditions.append(
                    or_(
                        SubscriberORM.name.ilike(like),
                        SubscriberORM.phone.ilike(like),
                        SubscriberORM.email.ilike(like),
                    )
                )
            if tag:
                conditions.append(
                    func.lower(func.cast(SubscriberORM.tags, String)).like(
                        f'%"{tag.lower()}"%'
                    )
                )
            if conditions:
                query = query.filter(and_(*conditions))
            total = query.with_entities(func.count(SubscriberORM.id)).scalar() or 0
            rows = (
                query.order_by(SubscriberORM.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            return [SubscriberRecord.from_orm(r) for r in rows], int(total)

    def find_by_tag(self, tag: str, *, status: str = "active") -> List[SubscriberRecord]:
        """Return active subscribers whose tags include `tag` (case-insensitive)."""
        with self._session_factory() as session:  # type: Session
            rows = (
                session.query(SubscriberORM)
                .filter(SubscriberORM.status == status)
                .filter(
                    func.lower(func.cast(SubscriberORM.tags, String)).like(
                        f'%"{tag.lower()}"%'
                    )
                )
                .all()
            )
            return [SubscriberRecord.from_orm(r) for r in rows]

    def distinct_tags(self) -> List[Tuple[str, int]]:
        """Aggregate (tag, count) across all subscribers — used for the audience picker.

        SQLite/Postgres-portable approach: pull all rows' tag lists into
        memory and count in Python. Cheap for the expected scale (≤ tens of
        thousands of subscribers); revisit when the table grows past that.
        """
        counts: Dict[str, int] = {}
        with self._session_factory() as session:  # type: Session
            rows = (
                session.query(SubscriberORM.tags)
                .filter(SubscriberORM.status == "active")
                .all()
            )
            for (tags,) in rows:
                for t in tags or []:
                    counts[t] = counts.get(t, 0) + 1
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
