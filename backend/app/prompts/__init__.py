"""Compatibility wrapper around `app.prompt_templates`."""

from app.prompt_templates import get_text_prompt_config


def get_prompt_config(mode: str):
    return get_text_prompt_config(mode)


__all__ = ["get_prompt_config"]
