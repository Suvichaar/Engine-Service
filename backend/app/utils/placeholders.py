"""Helper utilities for detecting placeholder configuration values."""

from __future__ import annotations


def is_placeholder_value(value: str | None) -> bool:
    if not value:
        return True
    normalized = value.strip().lower()
    placeholders = [
        "replace-with",
        "your-",
        "example",
        "stub",
        "dummy",
    ]
    return any(token in normalized for token in placeholders)

