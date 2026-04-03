"""Compatibility wrapper around text prompt registry helpers."""

from app.prompt_templates.registry import (
    InvalidCategoryError,
    PromptNotFoundError,
    available_prompts,
    get_text_prompt_config,
    render_text_prompt,
)


def available_modes():
    return available_prompts("text_prompts")


def get_prompt_config(mode: str):
    return get_text_prompt_config(mode)


def render_prompt(mode: str, *, category: str, language: str, analysis: str, keywords):
    return render_text_prompt(
        mode,
        category=category,
        language=language,
        analysis=analysis,
        keywords=keywords,
    )


__all__ = [
    "InvalidCategoryError",
    "PromptNotFoundError",
    "available_modes",
    "get_prompt_config",
    "render_prompt",
]
