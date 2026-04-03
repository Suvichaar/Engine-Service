"""File-backed prompt loader for versioned `.prompt` definitions."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .base import PromptTemplate


class PromptFileError(ValueError):
    """Raised when a `.prompt` file is malformed."""


PROMPT_ROOT = Path(__file__).resolve().parent


def _split_frontmatter(raw: str, source: Path) -> tuple[dict[str, str], str]:
    if not raw.startswith("---\n"):
        raise PromptFileError(f"{source.name}: missing frontmatter start delimiter.")

    try:
        _, frontmatter, body = raw.split("---\n", 2)
    except ValueError as exc:
        raise PromptFileError(f"{source.name}: invalid frontmatter block.") from exc

    metadata: dict[str, str] = {}
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if ":" not in stripped:
            raise PromptFileError(f"{source.name}: invalid metadata line '{line}'.")
        key, value = stripped.split(":", 1)
        metadata[key.strip()] = value.strip()

    return metadata, body.strip()


def _extract_section(body: str, section: str, next_section: str | None, source: Path) -> str:
    marker = f"[{section}]"
    if marker not in body:
        raise PromptFileError(f"{source.name}: missing [{section}] section.")

    start = body.index(marker) + len(marker)
    tail = body[start:]
    if next_section:
        next_marker = f"[{next_section}]"
        if next_marker not in tail:
            raise PromptFileError(f"{source.name}: missing [{next_section}] section.")
        content = tail[: tail.index(next_marker)]
    else:
        content = tail

    cleaned = content.strip()
    if not cleaned:
        raise PromptFileError(f"{source.name}: [{section}] section is empty.")
    return cleaned


def _parse_csv_field(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def load_prompt_file(path: str | Path) -> tuple[str, PromptTemplate]:
    source = Path(path)
    raw = source.read_text(encoding="utf-8")
    metadata, body = _split_frontmatter(raw, source)

    key = metadata.get("key") or metadata.get("mode") or metadata.get("name")
    if not key:
        raise PromptFileError(f"{source.name}: one of 'key', 'mode', or 'name' metadata is required.")

    version = metadata.get("version")
    if not version:
        raise PromptFileError(f"{source.name}: 'version' metadata is required.")

    system = _extract_section(body, "system", "user", source)
    user_template = _extract_section(body, "user", None, source)
    allowed_categories = _parse_csv_field(metadata.get("allowed_categories", ""))
    required_placeholders = _parse_csv_field(metadata.get("required_placeholders", ""))

    missing_fields = [field for field in required_placeholders if f"{{{field}}}" not in user_template]
    if missing_fields:
        fields = ", ".join(missing_fields)
        raise PromptFileError(f"{source.name}: user template missing placeholders: {fields}.")

    prompt = PromptTemplate(
        key=key,
        version=version,
        system=system,
        user_template=user_template,
        allowed_categories=allowed_categories,
        required_placeholders=required_placeholders,
        description=metadata.get("description") or None,
        status=metadata.get("status") or None,
        extra={"source_file": source.name},
    )
    return key, prompt


@lru_cache(maxsize=None)
def manifest_path(group: str) -> Path:
    return PROMPT_ROOT / group / "prompts.yml"


@lru_cache(maxsize=None)
def load_prompt_manifest(group: str) -> dict[str, dict[str, str | bool]]:
    path = manifest_path(group)
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    manifest: dict[str, dict[str, str | bool]] = {}
    for item in payload.get("prompts", []):
        key = item.get("key") or item.get("mode") or item.get("name")
        if not key:
            raise PromptFileError(f"{path.name}: every prompt entry requires 'key'.")
        if key in manifest:
            raise PromptFileError(f"{path.name}: duplicate prompt entry '{key}'.")
        manifest[key] = {
            "version": item.get("version", ""),
            "file": item.get("file", ""),
            "active": bool(item.get("active", False)),
        }
    return manifest


@lru_cache(maxsize=None)
def load_prompt_registry(group: str) -> dict[str, PromptTemplate]:
    registry: dict[str, PromptTemplate] = {}
    manifest = load_prompt_manifest(group)

    for key, item in manifest.items():
        if not item["active"]:
            continue
        prompt_file = PROMPT_ROOT / group / str(item["file"])
        loaded_key, prompt = load_prompt_file(prompt_file)
        if loaded_key != key:
            raise PromptFileError(
                f"{prompt_file.name}: key mismatch. Manifest='{key}', file='{loaded_key}'."
            )
        manifest_version = str(item["version"])
        if prompt.version != manifest_version:
            raise PromptFileError(
                f"{prompt_file.name}: version mismatch. Manifest='{manifest_version}', file='{prompt.version}'."
            )
        registry[key] = prompt

    return registry
