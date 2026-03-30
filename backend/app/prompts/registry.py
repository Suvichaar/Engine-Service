"""Registry for prompt templates keyed by narrative mode."""

from __future__ import annotations

from typing import Iterable, Mapping

from .base import PromptTemplate
from .loader import load_prompt_registry


class PromptNotFoundError(KeyError):
    """Raised when a prompt configuration cannot be located."""


class InvalidCategoryError(ValueError):
    """Raised when the requested category is not allowed for the prompt."""


def available_modes() -> Iterable[str]:
    """Return the set of registered prompt modes."""

    return load_prompt_registry().keys()


def get_prompt_config(mode: str) -> PromptTemplate:
    """Return the underlying prompt template for the specified mode."""

    try:
        return load_prompt_registry()[mode]
    except KeyError as exc:
        raise PromptNotFoundError(f"No prompt registered for mode '{mode}'.") from exc


def render_prompt(
    mode: str,
    *,
    category: str,
    language: str,
    analysis: str,
    keywords: Iterable[str],
) -> Mapping[str, str]:
    """Render a prompt for the given mode and contextual inputs."""

    prompt_template = get_prompt_config(mode)

    if prompt_template.allowed_categories and category not in prompt_template.allowed_categories:
        raise InvalidCategoryError(
            f"Category '{category}' is not allowed for mode '{mode}'. "
            f"Allowed categories: {prompt_template.allowed_categories}"
        )

    keyword_str = ", ".join(keyword.strip() for keyword in keywords if keyword.strip()) or "None"
    rendered_user = prompt_template.user_template.format(
        category=category,
        language=language,
        analysis=analysis.strip(),
        keywords=keyword_str,
    )
    return {
        "system": prompt_template.system,
        "user": rendered_user,
        "metadata": {
            "mode": mode,
            "category": category,
            "language": language,
            "prompt_version": prompt_template.version,
            "prompt_file": prompt_template.extra.get("source_file") if prompt_template.extra else None,
            "prompt_status": prompt_template.status,
        },
    }
