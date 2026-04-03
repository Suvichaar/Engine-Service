"""Compatibility wrapper around text prompt loading."""

from app.prompt_templates.loader import PromptFileError, load_prompt_file
from app.prompt_templates.loader import load_prompt_manifest as _load_prompt_manifest
from app.prompt_templates.loader import load_prompt_registry as _load_prompt_registry
from app.prompt_templates.registry import TEXT_PROMPT_GROUP


def load_prompt_manifest():
    return _load_prompt_manifest(TEXT_PROMPT_GROUP)


def load_prompt_registry():
    return _load_prompt_registry(TEXT_PROMPT_GROUP)


__all__ = ["PromptFileError", "load_prompt_file", "load_prompt_manifest", "load_prompt_registry"]
