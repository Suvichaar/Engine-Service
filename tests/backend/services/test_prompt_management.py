from __future__ import annotations

from pathlib import Path

from app.services.prompt_management import PromptManagementService


def test_prompt_management_can_list_seeded_prompts():
    service = PromptManagementService()
    payload = service.list_prompts()

    assert "text_prompts" in payload
    assert payload["text_prompts"][0]["key"] == "curious"


def test_prompt_management_can_create_and_activate_prompt(tmp_path: Path):
    root = tmp_path / "prompt_templates"
    text_dir = root / "text_prompts"
    image_dir = root / "image_prompts"
    text_dir.mkdir(parents=True)
    image_dir.mkdir(parents=True)
    (text_dir / "prompts.yml").write_text("prompts: []\n", encoding="utf-8")
    (image_dir / "prompts.yml").write_text("prompts: []\n", encoding="utf-8")

    service = PromptManagementService(root=root)
    created = service.create_prompt(
        group="text_prompts",
        key="curious",
        version="v2",
        description="Updated curious prompt",
        status="active",
        allowed_categories=["Education"],
        required_placeholders=["category", "language", "keywords", "analysis"],
        system="System text",
        user_template="Category: {category}\nLanguage: {language}\nKeywords: {keywords}\n{analysis}",
        active=True,
    )

    assert created["key"] == "curious"
    assert created["version"] == "v2"
    assert created["is_active"] is True
    assert (text_dir / "curious.v2.prompt").exists()
