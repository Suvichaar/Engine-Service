"""Common structures shared across prompt definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping


@dataclass(frozen=True)
class PromptTemplate:
    """Structured representation of a prompt definition."""

    system: str
    user_template: str
    allowed_categories: List[str]
    description: str | None = None
    extra: Mapping[str, str] | None = None

