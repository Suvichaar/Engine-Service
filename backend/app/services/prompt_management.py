"""CRUD operations for versioned prompt templates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.prompt_templates.loader import (
    load_prompt_file,
    manifest_path,
    load_prompt_manifest,
    load_prompt_registry,
)

PROMPT_GROUPS = ("text_prompts", "image_prompts")


class PromptManagementError(ValueError):
    """Raised when prompt management operations cannot be completed."""


@dataclass(frozen=True)
class PromptVersionRecord:
    group: str
    key: str
    version: str
    file_name: str
    description: str | None
    status: str | None
    allowed_categories: list[str]
    required_placeholders: list[str]
    system: str
    user_template: str
    is_active: bool


def _validate_group(group: str) -> str:
    if group not in PROMPT_GROUPS:
        allowed = ", ".join(PROMPT_GROUPS)
        raise PromptManagementError(f"Unsupported prompt group '{group}'. Allowed values: {allowed}")
    return group


def _group_dir(root: Path, group: str) -> Path:
    return root / group


def _prompt_path(root: Path, group: str, file_name: str) -> Path:
    return _group_dir(root, group) / file_name


def _serialize_csv(items: list[str]) -> str:
    return ", ".join(item.strip() for item in items if item.strip())


def _frontmatter_lines(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = ["---"]
    for key, value in payload.items():
        if value in (None, "", []):
            continue
        lines.append(f"{key}: {value}")
    lines.append("---")
    return lines


def _build_prompt_content(
    *,
    key: str,
    version: str,
    description: str | None,
    status: str | None,
    allowed_categories: list[str],
    required_placeholders: list[str],
    system: str,
    user_template: str,
) -> str:
    metadata = {
        "key": key,
        "version": version,
        "status": status,
        "description": description,
        "allowed_categories": _serialize_csv(allowed_categories),
        "required_placeholders": _serialize_csv(required_placeholders),
    }
    return "\n".join(
        [
            *_frontmatter_lines(metadata),
            "[system]",
            system.strip(),
            "",
            "[user]",
            user_template.strip(),
            "",
        ]
    )


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"prompts": []}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {"prompts": []}


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _clear_prompt_caches() -> None:
    manifest_path.cache_clear()
    load_prompt_manifest.cache_clear()
    load_prompt_registry.cache_clear()


class PromptManagementService:
    """Manage prompt template files and active versions."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path(__file__).resolve().parents[1] / "prompt_templates"

    def list_prompts(self) -> dict[str, list[dict[str, Any]]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for group in PROMPT_GROUPS:
            manifest_payload = _read_manifest(self._manifest_file(group))
            active_lookup = {
                str(item["key"]): (str(item["version"]), str(item["file"]))
                for item in manifest_payload.get("prompts", [])
                if item.get("active")
            }
            grouped: dict[str, list[PromptVersionRecord]] = {}
            for prompt_file in sorted(_group_dir(self._root, group).glob("*.prompt")):
                key, prompt = load_prompt_file(prompt_file)
                active_version = active_lookup.get(key)
                record = PromptVersionRecord(
                    group=group,
                    key=key,
                    version=prompt.version,
                    file_name=prompt_file.name,
                    description=prompt.description,
                    status=prompt.status,
                    allowed_categories=list(prompt.allowed_categories),
                    required_placeholders=list(prompt.required_placeholders),
                    system=prompt.system,
                    user_template=prompt.user_template,
                    is_active=bool(
                        active_version
                        and active_version[0] == prompt.version
                        and active_version[1] == prompt_file.name
                    ),
                )
                grouped.setdefault(key, []).append(record)

            groups[group] = [
                {
                    "key": key,
                    "versions": [
                        {
                            "group": version.group,
                            "key": version.key,
                            "version": version.version,
                            "file_name": version.file_name,
                            "description": version.description,
                            "status": version.status,
                            "allowed_categories": version.allowed_categories,
                            "required_placeholders": version.required_placeholders,
                            "system": version.system,
                            "user_template": version.user_template,
                            "is_active": version.is_active,
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
        return groups

    def create_prompt(
        self,
        *,
        group: str,
        key: str,
        version: str,
        description: str | None,
        status: str | None,
        allowed_categories: list[str],
        required_placeholders: list[str],
        system: str,
        user_template: str,
        active: bool,
    ) -> dict[str, Any]:
        group = _validate_group(group)
        file_name = f"{key}.{version}.prompt"
        path = _prompt_path(self._root, group, file_name)
        if path.exists():
            raise PromptManagementError(
                f"Prompt '{key}' version '{version}' already exists in '{group}'."
            )

        path.write_text(
            _build_prompt_content(
                key=key,
                version=version,
                description=description,
                status=status,
                allowed_categories=allowed_categories,
                required_placeholders=required_placeholders,
                system=system,
                user_template=user_template,
            ),
            encoding="utf-8",
        )

        if active:
            self._set_active_version(group=group, key=key, version=version, file_name=file_name)

        _clear_prompt_caches()
        return self._version_payload(group, key, version, file_name, active)

    def update_prompt(
        self,
        *,
        group: str,
        key: str,
        version: str,
        description: str | None,
        status: str | None,
        allowed_categories: list[str],
        required_placeholders: list[str],
        system: str,
        user_template: str,
        active: bool | None,
    ) -> dict[str, Any]:
        group = _validate_group(group)
        file_name = f"{key}.{version}.prompt"
        path = _prompt_path(self._root, group, file_name)
        if not path.exists():
            raise PromptManagementError(
                f"Prompt '{key}' version '{version}' does not exist in '{group}'."
            )

        path.write_text(
            _build_prompt_content(
                key=key,
                version=version,
                description=description,
                status=status,
                allowed_categories=allowed_categories,
                required_placeholders=required_placeholders,
                system=system,
                user_template=user_template,
            ),
            encoding="utf-8",
        )

        manifest_payload = _read_manifest(self._manifest_file(group))
        currently_active = self._is_active(manifest_payload, key, version, file_name)
        if active is True:
            self._set_active_version(group=group, key=key, version=version, file_name=file_name)
            currently_active = True
        elif active is False:
            self._deactivate_version(group=group, key=key, version=version, file_name=file_name)
            currently_active = False

        _clear_prompt_caches()
        return self._version_payload(group, key, version, file_name, currently_active)

    def activate_prompt(self, *, group: str, key: str, version: str) -> dict[str, Any]:
        group = _validate_group(group)
        file_name = f"{key}.{version}.prompt"
        path = _prompt_path(self._root, group, file_name)
        if not path.exists():
            raise PromptManagementError(
                f"Prompt '{key}' version '{version}' does not exist in '{group}'."
            )

        self._set_active_version(group=group, key=key, version=version, file_name=file_name)
        _clear_prompt_caches()
        return self._version_payload(group, key, version, file_name, True)

    def delete_prompt(self, *, group: str, key: str, version: str) -> None:
        group = _validate_group(group)
        file_name = f"{key}.{version}.prompt"
        path = _prompt_path(self._root, group, file_name)
        if not path.exists():
            raise PromptManagementError(
                f"Prompt '{key}' version '{version}' does not exist in '{group}'."
            )

        manifest_payload = _read_manifest(self._manifest_file(group))
        if self._is_active(manifest_payload, key, version, file_name):
            raise PromptManagementError("Cannot delete an active prompt version. Activate another version first.")

        path.unlink()
        _clear_prompt_caches()

    def _manifest_file(self, group: str) -> Path:
        return _group_dir(self._root, group) / "prompts.yml"

    def _set_active_version(self, *, group: str, key: str, version: str, file_name: str) -> None:
        manifest_file = self._manifest_file(group)
        payload = _read_manifest(manifest_file)
        prompts = payload.setdefault("prompts", [])

        updated = False
        for item in prompts:
            if item.get("key") == key:
                item["version"] = version
                item["file"] = file_name
                item["active"] = True
                updated = True
            elif item.get("active") and item.get("key") == key:
                item["active"] = False

        if not updated:
            prompts.append({"key": key, "version": version, "file": file_name, "active": True})

        _write_manifest(manifest_file, {"prompts": prompts})

    def _deactivate_version(self, *, group: str, key: str, version: str, file_name: str) -> None:
        manifest_file = self._manifest_file(group)
        payload = _read_manifest(manifest_file)
        prompts = payload.setdefault("prompts", [])

        for item in prompts:
            if (
                item.get("key") == key
                and str(item.get("version")) == version
                and str(item.get("file")) == file_name
            ):
                item["active"] = False

        _write_manifest(manifest_file, {"prompts": prompts})

    def _is_active(self, manifest_payload: dict[str, Any], key: str, version: str, file_name: str) -> bool:
        for item in manifest_payload.get("prompts", []):
            if (
                item.get("key") == key
                and str(item.get("version")) == version
                and str(item.get("file")) == file_name
                and bool(item.get("active"))
            ):
                return True
        return False

    def _version_payload(
        self, group: str, key: str, version: str, file_name: str, is_active: bool
    ) -> dict[str, Any]:
        _, prompt = load_prompt_file(_prompt_path(self._root, group, file_name))
        return {
            "group": group,
            "key": key,
            "version": version,
            "file_name": file_name,
            "description": prompt.description,
            "status": prompt.status,
            "allowed_categories": list(prompt.allowed_categories),
            "required_placeholders": list(prompt.required_placeholders),
            "system": prompt.system,
            "user_template": prompt.user_template,
            "is_active": is_active,
        }
