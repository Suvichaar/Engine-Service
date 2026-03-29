"""Central registry for template metadata and file resolution."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import yaml

from app.domain.dto import Mode


@dataclass(frozen=True)
class TemplateDefinition:
    key: str
    mode: Mode
    file: str
    slide_generator: str
    description: str | None = None
    enabled: bool = True

    @property
    def file_path(self) -> Path:
        return registry_root() / self.file


def registry_root() -> Path:
    return Path(__file__).resolve().parents[1] / "templates"


def registry_path() -> Path:
    return registry_root() / "templates.yml"


def normalize_template_key(template_key: str) -> str:
    if template_key.startswith(("http://", "https://", "s3://")):
        parsed = urlparse(template_key)
        return Path(parsed.path).name.replace(".html", "")
    return Path(template_key).name.replace(".html", "")


@lru_cache(maxsize=1)
def load_template_registry() -> dict[str, TemplateDefinition]:
    config_path = registry_path()
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    definitions: dict[str, TemplateDefinition] = {}
    for item in payload.get("templates", []):
        definition = TemplateDefinition(
            key=item["key"],
            mode=Mode(item["mode"]),
            file=item["file"],
            slide_generator=item["slide_generator"],
            description=item.get("description"),
            enabled=bool(item.get("enabled", True)),
        )
        definitions[definition.key] = definition
    return definitions


def list_template_definitions(mode: Mode | None = None, *, enabled_only: bool = True) -> Iterable[TemplateDefinition]:
    for definition in load_template_registry().values():
        if enabled_only and not definition.enabled:
            continue
        if mode is not None and definition.mode != mode:
            continue
        yield definition


def get_template_definition(template_key: str) -> TemplateDefinition:
    normalized = normalize_template_key(template_key)
    definition = load_template_registry().get(normalized)
    if definition is None or not definition.enabled:
        raise KeyError(f"Template '{normalized}' is not registered.")
    if not definition.file_path.exists():
        raise FileNotFoundError(f"Registered template file not found: {definition.file_path}")
    return definition


def supported_template_keys(mode: Mode | None = None) -> set[str]:
    return {definition.key for definition in list_template_definitions(mode)}
