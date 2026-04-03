from __future__ import annotations

from pathlib import Path

import yaml

from app.services.prompt_management import PromptManagementService


def _write_prompt(path: Path, *, key: str, version: str, required_placeholders: str = "") -> None:
    content = "\n".join(
        [
            "---",
            f"key: {key}",
            f"version: {version}",
            f"required_placeholders: {required_placeholders}",
            "---",
            "[system]",
            f"System for {key} {version}",
            "",
            "[user]",
            "Hello",
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")


def test_prompt_management_lists_and_activates_versions(tmp_path: Path):
    root = tmp_path / "prompt_templates"
    text_dir = root / "text_prompts"
    image_dir = root / "image_prompts"
    text_dir.mkdir(parents=True)
    image_dir.mkdir(parents=True)

    (text_dir / "prompts.yml").write_text(
        yaml.safe_dump(
            {"prompts": [{"key": "news", "version": "v1", "file": "news.v1.prompt", "active": True}]},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (image_dir / "prompts.yml").write_text(yaml.safe_dump({"prompts": []}, sort_keys=False), encoding="utf-8")
    _write_prompt(text_dir / "news.v1.prompt", key="news", version="v1")
    _write_prompt(text_dir / "news.v2.prompt", key="news", version="v2")

    service = PromptManagementService(root=root)

    listing = service.list_prompts()
    text_prompts = listing["text_prompts"]
    assert text_prompts[0]["key"] == "news"
    assert any(version["is_active"] for version in text_prompts[0]["versions"])

    activated = service.activate_prompt(group="text_prompts", key="news", version="v2")
    assert activated["is_active"] is True

    manifest = yaml.safe_load((text_dir / "prompts.yml").read_text(encoding="utf-8"))
    assert manifest["prompts"][0]["version"] == "v2"


def test_prompt_management_create_update_delete(tmp_path: Path):
    root = tmp_path / "prompt_templates"
    for group in ("text_prompts", "image_prompts"):
        group_dir = root / group
        group_dir.mkdir(parents=True)
        (group_dir / "prompts.yml").write_text(
            yaml.safe_dump({"prompts": []}, sort_keys=False),
            encoding="utf-8",
        )

    service = PromptManagementService(root=root)

    created = service.create_prompt(
        group="image_prompts",
        key="english_fallback",
        version="v1",
        description="Fallback",
        status="active",
        allowed_categories=[],
        required_placeholders=["content"],
        system="Translate this",
        user_template="Content: {content}",
        active=True,
    )
    assert created["key"] == "english_fallback"
    assert created["is_active"] is True

    updated = service.update_prompt(
        group="image_prompts",
        key="english_fallback",
        version="v1",
        description="Updated fallback",
        status="draft",
        allowed_categories=[],
        required_placeholders=["content", "language"],
        system="Translate carefully",
        user_template="Content: {content}\nLanguage: {language}",
        active=None,
    )
    assert updated["status"] == "draft"
    assert updated["required_placeholders"] == ["content", "language"]

    service.delete_prompt(group="image_prompts", key="english_fallback", version="v1")
    listing = service.list_prompts()
    assert listing["image_prompts"] == []
