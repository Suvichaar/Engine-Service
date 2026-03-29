from __future__ import annotations

import pytest

from app.prompts.registry import InvalidCategoryError, PromptNotFoundError, available_modes, get_prompt_config, render_prompt


def test_available_modes_contains_expected_entries():
    modes = set(available_modes())
    assert "news" in modes
    assert "curious" in modes


def test_get_prompt_config_returns_template():
    template = get_prompt_config("news")
    assert "News model" in template.system


def test_get_prompt_config_invalid_mode_raises():
    with pytest.raises(PromptNotFoundError):
        get_prompt_config("unknown")


def test_render_prompt_renders_user_template():
    prompt = render_prompt(
        "curious",
        category="Art",
        language="en-IN",
        analysis="Insightful analysis.",
        keywords=["creativity", "history"],
    )
    assert "creativity" in prompt["user"]
    assert "Insightful analysis." in prompt["user"]
    assert prompt["metadata"]["category"] == "Art"


def test_render_prompt_disallows_invalid_category():
    with pytest.raises(InvalidCategoryError):
        render_prompt(
            "news",
            category="Art",
            language="en-IN",
            analysis="Some analysis",
            keywords=[],
        )

