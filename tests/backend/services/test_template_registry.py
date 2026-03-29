from __future__ import annotations

from app.domain.dto import Mode
from app.services.template_registry import (
    get_template_definition,
    list_template_definitions,
    normalize_template_key,
    supported_template_keys,
)


def test_supported_template_keys_loaded_from_registry():
    keys = supported_template_keys(Mode.NEWS)

    assert "test-news-1" in keys
    assert "test-news-3v1" in keys


def test_get_template_definition_returns_registered_metadata():
    definition = get_template_definition("test-news-3")

    assert definition.mode == Mode.NEWS
    assert definition.slide_generator == "test-news-3"
    assert definition.file_path.name == "test-news-3.html"


def test_normalize_template_key_handles_remote_paths():
    assert normalize_template_key("https://example.com/templates/test-news-1.html") == "test-news-1"
    assert normalize_template_key("s3://bucket/path/test-news-2.html") == "test-news-2"


def test_list_template_definitions_filters_by_mode():
    definitions = list(list_template_definitions(Mode.NEWS))

    assert definitions
    assert all(definition.mode == Mode.NEWS for definition in definitions)
