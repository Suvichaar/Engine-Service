"""Common structures shared across prompt definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Mapping


@dataclass(frozen=True)
class PromptTemplate:
    """Structured representation of a prompt definition."""

    key: str
    version: str
    system: str
    user_template: str
    allowed_categories: List[str] = field(default_factory=list)
    required_placeholders: List[str] = field(default_factory=list)
    description: str | None = None
    status: str | None = None
    extra: Mapping[str, str] | None = None
