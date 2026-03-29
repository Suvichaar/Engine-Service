from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.domain.dto import IntakePayload
from app.services.language_detection import (
    DefaultLanguageDetectionService,
    FastTextLanguageDetectionStrategy,
    LanguageDetectionStrategy,
)


@dataclass
class StubStrategy(LanguageDetectionStrategy):
    language: str = "en"
    confidence: float = 0.9
    called_with: str | None = None

    def detect(self, text: str):
        self.called_with = text
        return self.language, self.confidence


def make_payload(**overrides):
    defaults = dict(
        text_prompt="Hello world",
        notes="Additional note",
        urls=["https://example.com"],
        attachments=[],
        prompt_keywords=["news", "update"],
        mode="news",
        template_key="modern",
        slide_count=4,
    )
    defaults.update(overrides)
    return IntakePayload(**defaults)


def test_default_service_combines_text_and_returns_metadata():
    strategy = StubStrategy(language="hi", confidence=0.75)
    service = DefaultLanguageDetectionService(strategy=strategy, default_language="en")

    payload = make_payload()
    metadata = service.detect(payload)

    assert metadata.language_code == "hi"
    assert pytest.approx(metadata.confidence, rel=1e-6) == 0.75
    assert strategy.called_with and "Hello world" in strategy.called_with
    assert "https://example.com" in strategy.called_with


def test_default_service_returns_default_when_empty():
    strategy = StubStrategy()
    service = DefaultLanguageDetectionService(strategy=strategy, default_language="en")

    payload = make_payload(text_prompt=None, notes=None, prompt_keywords=[], urls=[])

    metadata = service.detect(payload)

    assert metadata.language_code == "en"
    assert metadata.confidence == 0.0


def test_fasttext_strategy_removes_label_prefix():
    class DummyModel:
        def predict(self, text: str, k: int = 1):
            return ["__label__es"], [0.42]

    strategy = FastTextLanguageDetectionStrategy(
        model_path="dummy.bin",
        loader=lambda _: DummyModel(),
    )

    language_code, confidence = strategy.detect("Hola mundo")

    assert language_code == "es"
    assert pytest.approx(confidence, rel=1e-6) == 0.42

