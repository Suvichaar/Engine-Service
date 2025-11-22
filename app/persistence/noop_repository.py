"""No-op repository implementation that doesn't use database."""

from __future__ import annotations

from app.domain.dto import StoryRecord
from app.domain.interfaces import StoryRepository


class NoOpStoryRepository(StoryRepository):
    """Repository that doesn't persist anything (for when database is not used)."""

    def save(self, record: StoryRecord) -> StoryRecord:
        """No-op: just return the record without saving."""
        return record

    def get(self, story_id: str) -> StoryRecord:
        """No-op: raise error since we don't store anything."""
        raise KeyError(f"Story with id {story_id} not found (database not in use).")


__all__ = ["NoOpStoryRepository"]

