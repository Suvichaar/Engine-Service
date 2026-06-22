"""CRUD operations for versioned HTML templates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml

from app.domain.dto import Mode
from app.services.template_registry import (
    clear_template_registry_caches,
    list_template_versions,
    template_manifest_path,
)


class TemplateManagementError(ValueError):
    """Raised when template management operations cannot be completed."""


@dataclass(frozen=True)
class TemplateVersionRecord:
    key: str
    version: str
    mode: str
    file_name: str
    file_path: str
    slide_generator: str
    description: str | None
    enabled: bool
    is_active: bool
    html_content: str


_SAFE_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,118}[a-zA-Z0-9]$")


def _validate_name(label: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise TemplateManagementError(f"{label} is required.")
    if not _SAFE_NAME.match(normalized):
        raise TemplateManagementError(
            f"{label} '{value}' is invalid. Use letters, numbers, dots, underscores, or hyphens."
        )
    return normalized


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"templates": []}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {"templates": []}


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _version_sort_key(value: str) -> tuple[int, int | str]:
    normalized = str(value).strip().lower()
    if normalized.startswith("v") and normalized[1:].isdigit():
        return (1, int(normalized[1:]))
    return (0, normalized)


class TemplateManagementService:
    """Manage versioned HTML templates for a single mode."""

    def __init__(self, *, mode: Mode, root: Path | None = None) -> None:
        self._mode = mode
        self._root = root or Path(__file__).resolve().parents[1] / "templates"

    def list_templates(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[TemplateVersionRecord]] = {}
        for item in list_template_versions(mode=self._mode):
            file_path = self._root / item["file"]
            html_content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
            record = TemplateVersionRecord(
                key=str(item["key"]),
                version=str(item["version"]),
                mode=str(item["mode"]),
                file_name=file_path.name,
                file_path=str(item["file"]),
                slide_generator=str(item["slide_generator"]),
                description=item.get("description"),
                enabled=bool(item.get("enabled", True)),
                is_active=bool(item.get("active", False)),
                html_content=html_content,
            )
            grouped.setdefault(record.key, []).append(record)

        return {
            "templates": [
                {
                    "key": key,
                    "versions": [
                        {
                            "key": version.key,
                            "version": version.version,
                            "mode": version.mode,
                            "file_name": version.file_name,
                            "file_path": version.file_path,
                            "slide_generator": version.slide_generator,
                            "description": version.description,
                            "enabled": version.enabled,
                            "is_active": version.is_active,
                            "html_content": version.html_content,
                        }
                        for version in sorted(
                            versions,
                            key=lambda item: (item.version, item.file_name),
                            reverse=True,
                        )
                    ],
                }
                for key, versions in sorted(grouped.items())
            ]
        }

    def create_template(
        self,
        *,
        key: str,
        description: str | None,
        slide_generator: str,
        html_content: str,
        active: bool,
        enabled: bool,
    ) -> dict[str, Any]:
        key = _validate_name("Key", key)
        slide_generator = _validate_name("Slide generator", slide_generator)
        if not html_content.strip():
            raise TemplateManagementError("HTML content is required.")

        version = self._next_version_label(key)

        mode_dir = self._root / self._mode.value
        mode_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{key}.{version}.html"
        relative_path = f"{self._mode.value}/{file_name}"
        file_path = self._root / relative_path
        if file_path.exists():
            raise TemplateManagementError(f"Template '{key}' version '{version}' already exists.")

        file_path.write_text(html_content.strip() + "\n", encoding="utf-8")

        manifest_path = template_manifest_path()
        payload = _read_manifest(manifest_path)
        templates = payload.setdefault("templates", [])
        if active:
            for item in templates:
                if item.get("mode") == self._mode.value and item.get("key") == key:
                    item["active"] = False
        templates.append(
            {
                "key": key,
                "version": version,
                "mode": self._mode.value,
                "file": relative_path,
                "slide_generator": slide_generator,
                "description": description,
                "enabled": enabled,
                "active": active,
            }
        )
        _write_manifest(manifest_path, {"templates": templates})
        clear_template_registry_caches()
        return self._get_template_version(key=key, version=version)

    def update_template(
        self,
        *,
        key: str,
        version: str,
        description: str | None,
        slide_generator: str,
        html_content: str,
        active: bool | None,
        enabled: bool,
    ) -> dict[str, Any]:
        key = _validate_name("Key", key)
        version = _validate_name("Version", version)
        slide_generator = _validate_name("Slide generator", slide_generator)
        if not html_content.strip():
            raise TemplateManagementError("HTML content is required.")

        manifest_path = template_manifest_path()
        payload = _read_manifest(manifest_path)
        templates = payload.setdefault("templates", [])

        target: dict[str, Any] | None = None
        for item in templates:
            if (
                item.get("mode") == self._mode.value
                and item.get("key") == key
                and str(item.get("version")) == version
            ):
                target = item
                break

        if target is None:
            raise TemplateManagementError(f"Template '{key}' version '{version}' does not exist.")

        file_path = self._root / str(target["file"])
        file_path.write_text(html_content.strip() + "\n", encoding="utf-8")
        target["description"] = description
        target["slide_generator"] = slide_generator
        target["enabled"] = enabled

        if active is True:
            for item in templates:
                if item.get("mode") == self._mode.value and item.get("key") == key:
                    item["active"] = False
            target["active"] = True
        elif active is False:
            target["active"] = False

        _write_manifest(manifest_path, {"templates": templates})
        clear_template_registry_caches()
        return self._get_template_version(key=key, version=version)

    def activate_template(self, *, key: str, version: str) -> dict[str, Any]:
        key = _validate_name("Key", key)
        version = _validate_name("Version", version)

        manifest_path = template_manifest_path()
        payload = _read_manifest(manifest_path)
        templates = payload.setdefault("templates", [])
        found = False
        for item in templates:
            if item.get("mode") != self._mode.value or item.get("key") != key:
                continue
            if str(item.get("version")) == version:
                item["active"] = True
                found = True
            else:
                item["active"] = False

        if not found:
            raise TemplateManagementError(f"Template '{key}' version '{version}' does not exist.")

        _write_manifest(manifest_path, {"templates": templates})
        clear_template_registry_caches()
        return self._get_template_version(key=key, version=version)

    def delete_template(self, *, key: str, version: str) -> None:
        key = _validate_name("Key", key)
        version = _validate_name("Version", version)

        manifest_path = template_manifest_path()
        payload = _read_manifest(manifest_path)
        templates = payload.setdefault("templates", [])

        retained: list[dict[str, Any]] = []
        target: dict[str, Any] | None = None
        for item in templates:
            matches = (
                item.get("mode") == self._mode.value
                and item.get("key") == key
                and str(item.get("version")) == version
            )
            if matches:
                target = item
            else:
                retained.append(item)

        if target is None:
            raise TemplateManagementError(f"Template '{key}' version '{version}' does not exist.")
        if bool(target.get("active")):
            sibling_versions = [
                item
                for item in retained
                if item.get("mode") == self._mode.value and item.get("key") == key
            ]
            if not sibling_versions:
                raise TemplateManagementError(
                    "Cannot delete the only active template version. Create or activate another version first."
                )

            preferred_siblings = [item for item in sibling_versions if bool(item.get("enabled", True))]
            replacement = max(
                preferred_siblings or sibling_versions,
                key=lambda item: _version_sort_key(str(item.get("version", ""))),
            )
            for item in sibling_versions:
                item["active"] = False
            replacement["active"] = True

        file_path = self._root / str(target["file"])
        if file_path.exists():
            file_path.unlink()

        _write_manifest(manifest_path, {"templates": retained})
        clear_template_registry_caches()

    def _get_template_version(self, *, key: str, version: str) -> dict[str, Any]:
        listing = self.list_templates()
        for family in listing["templates"]:
            if family["key"] != key:
                continue
            for item in family["versions"]:
                if item["version"] == version:
                    return item
        raise TemplateManagementError(f"Template '{key}' version '{version}' does not exist.")

    def _next_version_label(self, key: str) -> str:
        versions: list[int] = []
        for item in list_template_versions(mode=self._mode):
            if str(item.get("key")) != key:
                continue
            version = str(item.get("version", ""))
            if version.startswith("v") and version[1:].isdigit():
                versions.append(int(version[1:]))
        next_number = max(versions, default=0) + 1
        return f"v{next_number}"
