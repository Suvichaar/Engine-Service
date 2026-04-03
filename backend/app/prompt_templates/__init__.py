"""Versioned prompt templates for text and image generation."""

from .registry import (
    get_image_prompt_config,
    get_text_prompt_config,
    render_image_prompt,
    render_text_prompt,
)

__all__ = [
    "get_image_prompt_config",
    "get_text_prompt_config",
    "render_image_prompt",
    "render_text_prompt",
]
