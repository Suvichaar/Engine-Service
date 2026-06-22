"""In-memory registry for asynchronous story generation jobs."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Literal, Optional
from uuid import UUID

from app.domain.dto import StoryRecord


JobStatus = Literal["pending", "processing", "completed", "failed"]


@dataclass
class StoryJob:
    id: UUID
    status: JobStatus = "pending"
    error: Optional[str] = None
    record: Optional[StoryRecord] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(IST))
    updated_at: datetime = field(default_factory=lambda: datetime.now(IST))


class StoryJobRegistry:
    """Thread-safe in-memory registry of in-flight story jobs.

    Jobs are dropped after they have been terminal (completed/failed) for
    longer than ``retention_seconds`` so the dict does not grow unbounded
    on a long-lived worker. Completed records still live in the SQL
    repository, so the status endpoint can fall back to that if the
    in-memory entry has been evicted.
    """

    def __init__(self, retention_seconds: int = 24 * 60 * 60) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, StoryJob] = {}
        self._retention_seconds = retention_seconds

    def create(self, story_id: UUID) -> StoryJob:
        job = StoryJob(id=story_id)
        with self._lock:
            self._sweep_locked()
            self._jobs[str(story_id)] = job
        return job

    def mark_processing(self, story_id: UUID) -> None:
        self._update(story_id, status="processing")

    def mark_completed(self, story_id: UUID, record: StoryRecord) -> None:
        self._update(story_id, status="completed", record=record)

    def mark_failed(self, story_id: UUID, error: str) -> None:
        self._update(story_id, status="failed", error=error)

    def get(self, story_id) -> Optional[StoryJob]:
        with self._lock:
            return self._jobs.get(str(story_id))

    def _update(self, story_id: UUID, **fields) -> None:
        with self._lock:
            job = self._jobs.get(str(story_id))
            if not job:
                return
            for key, value in fields.items():
                setattr(job, key, value)
            job.updated_at = datetime.now(IST)

    def _sweep_locked(self) -> None:
        now = datetime.now(IST)
        cutoff = self._retention_seconds
        stale = [
            key
            for key, job in self._jobs.items()
            if job.status in ("completed", "failed")
            and (now - job.updated_at).total_seconds() > cutoff
        ]
        for key in stale:
            self._jobs.pop(key, None)


_REGISTRY = StoryJobRegistry()


def get_job_registry() -> StoryJobRegistry:
    return _REGISTRY
IST = timezone(timedelta(hours=5, minutes=30))
