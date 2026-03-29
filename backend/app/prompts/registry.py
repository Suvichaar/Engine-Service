"""Registry for prompt templates keyed by narrative mode."""

from __future__ import annotations

from typing import Dict, Iterable, Mapping

from .base import PromptTemplate
from .curious import CURIOUS_TEMPLATE
from .news import NEWS_TEMPLATE


PROMPT_REGISTRY: Dict[str, PromptTemplate] = {
    "curious": CURIOUS_TEMPLATE,
    "news": NEWS_TEMPLATE,
}


class PromptNotFoundError(KeyError):
    """Raised when a prompt configuration cannot be located."""


class InvalidCategoryError(ValueError):
    """Raised when the requested category is not allowed for the prompt."""


def available_modes() -> Iterable[str]:
    """Return the set of registered prompt modes."""

    return PROMPT_REGISTRY.keys()


def get_prompt_config(mode: str) -> PromptTemplate:
    """Return the underlying prompt template for the specified mode."""

    try:
        return PROMPT_REGISTRY[mode]
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
        },
    }

