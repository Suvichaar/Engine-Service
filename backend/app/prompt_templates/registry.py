"""Registry helpers for text and image prompt templates."""

from __future__ import annotations

from typing import Iterable, Mapping

from .base import PromptTemplate
from .loader import load_prompt_registry

TEXT_PROMPT_GROUP = "text_prompts"
IMAGE_PROMPT_GROUP = "image_prompts"


class PromptNotFoundError(KeyError):
    """Raised when a prompt configuration cannot be located."""


class InvalidCategoryError(ValueError):
    """Raised when the requested category is not allowed for the prompt."""


def available_prompts(group: str) -> Iterable[str]:
    """Return the set of active prompt keys for a group."""

    return load_prompt_registry(group).keys()


def get_prompt_config(group: str, key: str) -> PromptTemplate:
    """Return the underlying prompt template for the specified group and key."""

    try:
        return load_prompt_registry(group)[key]
    except KeyError as exc:
        raise PromptNotFoundError(f"No prompt registered for group '{group}' and key '{key}'.") from exc


def get_text_prompt_config(mode: str) -> PromptTemplate:
    """Return the configured text prompt for a narrative mode."""

    return get_prompt_config(TEXT_PROMPT_GROUP, mode)


def get_image_prompt_config(name: str) -> PromptTemplate:
    """Return the configured image prompt template."""

    return get_prompt_config(IMAGE_PROMPT_GROUP, name)


def render_text_prompt(
    mode: str,
    *,
    category: str,
    language: str,
    analysis: str,
    keywords: Iterable[str],
) -> Mapping[str, str]:
    """Render a text-generation prompt for the given mode and context."""

    prompt_template = get_text_prompt_config(mode)

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
            "prompt_group": TEXT_PROMPT_GROUP,
        },
    }


def render_image_prompt(name: str, **kwargs: str) -> Mapping[str, str]:
    """Render an image-generation prompt template."""

    prompt_template = get_image_prompt_config(name)
    rendered_user = prompt_template.user_template.format(**kwargs)
    return {
        "system": prompt_template.system,
        "user": rendered_user,
        "metadata": {
            "name": name,
            "prompt_version": prompt_template.version,
            "prompt_file": prompt_template.extra.get("source_file") if prompt_template.extra else None,
            "prompt_status": prompt_template.status,
            "prompt_group": IMAGE_PROMPT_GROUP,
        },
    }
