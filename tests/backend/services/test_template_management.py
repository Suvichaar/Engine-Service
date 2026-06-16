from __future__ import annotations

from pathlib import Path

import yaml

from app.domain.dto import Mode
from app.services import template_management as template_management_module
from app.services import template_registry as template_registry_module
from app.services.template_management import TemplateManagementError, TemplateManagementService


def _write_template_manifest(manifest_path: Path, payload: dict) -> None:
    manifest_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_template_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_delete_active_template_promotes_latest_remaining_version(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "templates"
    manifest_path = root / "manifest.yml"
    _write_template_file(root / "news" / "hero.v1.html", "<html>v1</html>\n")
    _write_template_file(root / "news" / "hero.v2.html", "<html>v2</html>\n")

    _write_template_manifest(
        manifest_path,
        {
            "templates": [
                {
                    "key": "hero",
                    "version": "v1",
                    "mode": "news",
                    "file": "news/hero.v1.html",
                    "slide_generator": "hero",
                    "enabled": True,
                    "active": False,
                },
                {
                    "key": "hero",
                    "version": "v2",
                    "mode": "news",
                    "file": "news/hero.v2.html",
                    "slide_generator": "hero",
                    "enabled": True,
                    "active": True,
                },
            ]
        },
    )

    monkeypatch.setattr(template_management_module, "template_manifest_path", lambda: manifest_path)
    monkeypatch.setattr(template_registry_module, "template_manifest_path", lambda: manifest_path)
    monkeypatch.setattr(template_management_module, "clear_template_registry_caches", lambda: None)
    monkeypatch.setattr(template_registry_module, "clear_template_registry_caches", lambda: None)

    service = TemplateManagementService(mode=Mode.NEWS, root=root)

    service.delete_template(key="hero", version="v2")

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert [item["version"] for item in manifest["templates"]] == ["v1"]
    assert manifest["templates"][0]["active"] is True
    assert not (root / "news" / "hero.v2.html").exists()


def test_delete_only_active_template_requires_another_version(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "templates"
    manifest_path = root / "manifest.yml"
    _write_template_file(root / "news" / "solo.v1.html", "<html>solo</html>\n")

    _write_template_manifest(
        manifest_path,
        {
            "templates": [
                {
                    "key": "solo",
                    "version": "v1",
                    "mode": "news",
                    "file": "news/solo.v1.html",
                    "slide_generator": "solo",
                    "enabled": True,
                    "active": True,
                }
            ]
        },
    )

    monkeypatch.setattr(template_management_module, "template_manifest_path", lambda: manifest_path)
    monkeypatch.setattr(template_registry_module, "template_manifest_path", lambda: manifest_path)
    monkeypatch.setattr(template_management_module, "clear_template_registry_caches", lambda: None)
    monkeypatch.setattr(template_registry_module, "clear_template_registry_caches", lambda: None)

    service = TemplateManagementService(mode=Mode.NEWS, root=root)

    try:
        service.delete_template(key="solo", version="v1")
    except TemplateManagementError as exc:
        assert "Create or activate another version first" in str(exc)
    else:
        raise AssertionError("Expected deleting the only active template version to fail")

