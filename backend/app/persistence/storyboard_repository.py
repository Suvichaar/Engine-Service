"""SQLAlchemy storage for StoryBoard entries.

StoryBoard is the admin-curated content bank: each row captures a story idea
or pre-produced asset (title, cover, media URLs from the CDN, tags) that the
production pipeline later picks up. Unlike the `stories` table — which stores
fully-generated AMP stories — StoryBoard rows are lightweight metadata records
ingested manually (single form) or in bulk (CSV upload), and optionally
mirrored from external sources (e.g. Strapi).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
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


class StoryboardORM(Base):
    __tablename__ = "storyboards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    slug: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(128))
    tags: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    cover_url: Mapped[str | None] = mapped_column(Text)
    media_urls: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    language: Mapped[str | None] = mapped_column(String(16))
    mode: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    external_id: Mapped[str | None] = mapped_column(String(128), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_storyboards_status_created", "status", "created_at"),
        Index("ix_storyboards_category", "category"),
    )


def ensure_storyboard_schema(engine) -> None:
    """Create or back-fill columns on the storyboards table on startup."""

    inspector = inspect(engine)
    if not inspector.has_table(StoryboardORM.__tablename__):
        return

    existing = {c["name"] for c in inspector.get_columns(StoryboardORM.__tablename__)}
    additions = {
        "external_id": "VARCHAR(128)",
        "notes": "TEXT",
        "language": "VARCHAR(16)",
        "mode": "VARCHAR(32)",
    }
    missing = [(n, t) for n, t in additions.items() if n not in existing]
    if not missing:
        return
    with engine.begin() as conn:
        for name, column_type in missing:
            conn.execute(
                text(
                    f"ALTER TABLE {StoryboardORM.__tablename__} "
                    f"ADD COLUMN {name} {column_type}"
                )
            )


@dataclass(frozen=True)
class StoryboardRecord:
    id: UUID
    title: str
    slug: str
    category: Optional[str]
    tags: List[str]
    cover_url: Optional[str]
    media_urls: List[Dict[str, Any]]
    language: Optional[str]
    mode: Optional[str]
    status: str
    source: str
    external_id: Optional[str]
    notes: Optional[str]
    created_by: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, orm: StoryboardORM) -> "StoryboardRecord":
        return cls(
            id=UUID(orm.id),
            title=orm.title,
            slug=orm.slug,
            category=orm.category,
            tags=list(orm.tags or []),
            cover_url=orm.cover_url,
            media_urls=list(orm.media_urls or []),
            language=orm.language,
            mode=orm.mode,
            status=orm.status,
            source=orm.source,
            external_id=orm.external_id,
            notes=orm.notes,
            created_by=orm.created_by,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )


class StoryboardNotFound(Exception):
    pass


class StoryboardSlugTaken(Exception):
    pass


class SqlAlchemyStoryboardRepository:
    """CRUD + paginated listing for StoryBoard entries."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    # ── writes ─────────────────────────────────────────────────────────────

    def create(
        self,
        *,
        title: str,
        slug: str,
        category: Optional[str],
        tags: List[str],
        cover_url: Optional[str],
        media_urls: List[Dict[str, Any]],
        language: Optional[str],
        mode: Optional[str],
        status: str,
        source: str,
        external_id: Optional[str],
        notes: Optional[str],
        created_by: str,
    ) -> StoryboardRecord:
        now = datetime.now(tz=timezone.utc)
        new_id = uuid4()
        with self._session_factory() as session:  # type: Session
            if self._slug_exists(session, slug, exclude_id=None):
                raise StoryboardSlugTaken(slug)
            orm = StoryboardORM(
                id=str(new_id),
                title=title,
                slug=slug,
                category=category,
                tags=list(tags or []),
                cover_url=cover_url,
                media_urls=list(media_urls or []),
                language=language,
                mode=mode,
                status=status,
                source=source,
                external_id=external_id,
                notes=notes,
                created_by=created_by,
                created_at=now,
                updated_at=now,
            )
            session.add(orm)
            session.commit()
            session.refresh(orm)
            return StoryboardRecord.from_orm(orm)

    def bulk_create(
        self,
        rows: List[Dict[str, Any]],
        *,
        created_by: str,
        source: str = "bulk_csv",
    ) -> Tuple[List[StoryboardRecord], List[Dict[str, Any]]]:
        """Insert many rows. Returns (created_records, errors). Skips bad rows."""
        created: List[StoryboardRecord] = []
        errors: List[Dict[str, Any]] = []
        now = datetime.now(tz=timezone.utc)
        with self._session_factory() as session:  # type: Session
            seen_slugs = set()
            for idx, row in enumerate(rows):
                slug = (row.get("slug") or "").strip()
                title = (row.get("title") or "").strip()
                if not title or not slug:
                    errors.append({"row": idx, "error": "title and slug are required"})
                    continue
                if slug in seen_slugs:
                    errors.append({"row": idx, "error": f"duplicate slug in upload: {slug}"})
                    continue
                if self._slug_exists(session, slug, exclude_id=None):
                    errors.append({"row": idx, "error": f"slug already exists: {slug}"})
                    continue
                seen_slugs.add(slug)
                orm = StoryboardORM(
                    id=str(uuid4()),
                    title=title,
                    slug=slug,
                    category=(row.get("category") or None),
                    tags=list(row.get("tags") or []),
                    cover_url=(row.get("cover_url") or None),
                    media_urls=list(row.get("media_urls") or []),
                    language=(row.get("language") or None),
                    mode=(row.get("mode") or None),
                    status=(row.get("status") or "draft"),
                    source=source,
                    external_id=(row.get("external_id") or None),
                    notes=(row.get("notes") or None),
                    created_by=created_by,
                    created_at=now,
                    updated_at=now,
                )
                session.add(orm)
                session.flush()
                created.append(StoryboardRecord.from_orm(orm))
            session.commit()
        return created, errors

    def update(
        self,
        board_id: UUID | str,
        *,
        updates: Dict[str, Any],
    ) -> StoryboardRecord:
        with self._session_factory() as session:  # type: Session
            orm = session.get(StoryboardORM, str(board_id))
            if not orm:
                raise StoryboardNotFound(str(board_id))
            new_slug = updates.get("slug")
            if new_slug and new_slug != orm.slug and self._slug_exists(
                session, new_slug, exclude_id=orm.id
            ):
                raise StoryboardSlugTaken(new_slug)
            allowed = {
                "title",
                "slug",
                "category",
                "tags",
                "cover_url",
                "media_urls",
                "language",
                "mode",
                "status",
                "external_id",
                "notes",
            }
            for key, value in updates.items():
                if key in allowed:
                    setattr(orm, key, value)
            orm.updated_at = datetime.now(tz=timezone.utc)
            session.commit()
            session.refresh(orm)
            return StoryboardRecord.from_orm(orm)

    def delete(self, board_id: UUID | str) -> None:
        with self._session_factory() as session:  # type: Session
            orm = session.get(StoryboardORM, str(board_id))
            if not orm:
                raise StoryboardNotFound(str(board_id))
            session.delete(orm)
            session.commit()

    # ── reads ──────────────────────────────────────────────────────────────

    def get(self, board_id: UUID | str) -> StoryboardRecord:
        with self._session_factory() as session:  # type: Session
            orm = session.get(StoryboardORM, str(board_id))
            if not orm:
                raise StoryboardNotFound(str(board_id))
            return StoryboardRecord.from_orm(orm)

    def list(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        category: Optional[str] = None,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        q: Optional[str] = None,
    ) -> Tuple[List[StoryboardRecord], int]:
        with self._session_factory() as session:  # type: Session
            query = session.query(StoryboardORM)
            conditions = []
            if category:
                conditions.append(StoryboardORM.category == category)
            if status:
                conditions.append(StoryboardORM.status == status)
            if q:
                like = f"%{q}%"
                conditions.append(
                    or_(StoryboardORM.title.ilike(like), StoryboardORM.slug.ilike(like))
                )
            if tag:
                # JSON contains across SQLite/Postgres — best-effort LIKE on serialized form.
                conditions.append(func.lower(func.cast(StoryboardORM.tags, String)).like(
                    f'%"{tag.lower()}"%'
                ))
            if conditions:
                query = query.filter(and_(*conditions))

            total = query.with_entities(func.count(StoryboardORM.id)).scalar() or 0
            rows = (
                query.order_by(StoryboardORM.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            return [StoryboardRecord.from_orm(r) for r in rows], int(total)

    # ── helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _slug_exists(session: Session, slug: str, *, exclude_id: Optional[str]) -> bool:
        query = session.query(StoryboardORM.id).filter(StoryboardORM.slug == slug)
        if exclude_id:
            query = query.filter(StoryboardORM.id != exclude_id)
        return session.query(query.exists()).scalar() or False
