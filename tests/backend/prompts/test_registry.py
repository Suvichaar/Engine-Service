from __future__ import annotations

import pytest

from app.prompt_templates.loader import load_prompt_file, load_prompt_manifest
from app.prompt_templates.registry import (
    IMAGE_PROMPT_GROUP,
    InvalidCategoryError,
    PromptNotFoundError,
    TEXT_PROMPT_GROUP,
    available_prompts,
    get_image_prompt_config,
    get_text_prompt_config,
    render_image_prompt,
    render_text_prompt,
)


def test_available_modes_contains_expected_entries():
    modes = set(available_prompts(TEXT_PROMPT_GROUP))
    assert "curious" in modes


def test_get_prompt_config_returns_template():
    template = get_text_prompt_config("curious")
    assert "Curious storyteller" in template.system
    assert template.version == "v1"
    assert template.extra["source_file"] == "curious.v1.prompt"


def test_load_prompt_file_parses_curious_prompt():
    mode, prompt = load_prompt_file("backend/app/prompt_templates/text_prompts/curious.v1.prompt")
    assert mode == "curious"
    assert prompt.version == "v1"
    assert "Education" in prompt.allowed_categories
    assert "{language}" in prompt.user_template


def test_load_prompt_manifest_returns_active_curious_prompt():
    manifest = load_prompt_manifest(TEXT_PROMPT_GROUP)
    assert manifest["curious"]["version"] == "v1"
    assert manifest["curious"]["file"] == "curious.v1.prompt"
    assert manifest["curious"]["active"] is True


def test_get_prompt_config_invalid_mode_raises():
    with pytest.raises(PromptNotFoundError):
        get_text_prompt_config("unknown")


def test_render_prompt_renders_user_template():
    prompt = render_text_prompt(
        "curious",
        category="Art",
        language="en-IN",
        analysis="Insightful analysis.",
        keywords=["creativity", "history"],
    )
    assert "creativity" in prompt["user"]
    assert "Insightful analysis." in prompt["user"]
    assert prompt["metadata"]["category"] == "Art"
    assert prompt["metadata"]["prompt_version"] == "v1"
    assert prompt["metadata"]["prompt_file"] == "curious.v1.prompt"


def test_render_prompt_disallows_invalid_category():
    with pytest.raises(InvalidCategoryError):
        render_text_prompt(
            "curious",
            category="InvalidCategory",
            language="en-IN",
            analysis="Some analysis",
            keywords=[],
        )


def test_image_prompt_manifest_contains_expected_entries():
    manifest = load_prompt_manifest(IMAGE_PROMPT_GROUP)
    assert manifest["alt_text_generation"]["version"] == "v1"
    assert manifest["english_fallback"]["active"] is True


def test_get_image_prompt_config_returns_template():
    template = get_image_prompt_config("alt_text_generation")
    assert "image prompts" in template.system
    assert template.version == "v1"
    assert template.extra["source_file"] == "alt_text_generation.v1.prompt"


def test_render_image_prompt_renders_user_template():
    prompt = render_image_prompt(
        "english_fallback",
        content="Namaste duniya",
        original_language="hi",
    )
    assert "Namaste duniya" in prompt["user"]
    assert prompt["metadata"]["prompt_version"] == "v1"
    assert prompt["metadata"]["prompt_file"] == "english_fallback.v1.prompt"
