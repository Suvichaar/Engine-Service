from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.domain.dto import (
    Mode,
    CuriousNarrative,
    DocInsights,
    RenderedPrompt,
    SlideBlock,
    SlideDeck,
)
from app.domain.interfaces import ModelClient
from app.services.model_router import DefaultModelRouter, ModelRoutingError


@dataclass
class StubModelClient(ModelClient):
    name: str
    mode: Mode

    def generate(self, prompt: RenderedPrompt, insights: DocInsights):
        return CuriousNarrative(
            mode=self.mode,
            slide_deck=SlideDeck(template_key="stub", language_code="en", slides=[SlideBlock(placeholder_id="p", text="")]),
            raw_output=None,
            explainability_notes=[],
        )


def test_model_router_returns_registered_client():
    curious_client = StubModelClient("curious", mode=Mode.CURIOUS)
    news_client = StubModelClient("news", mode=Mode.NEWS)
    router = DefaultModelRouter({Mode.CURIOUS: curious_client, Mode.NEWS: news_client})

    assert router.route("curious") is curious_client
    assert router.route(Mode.NEWS) is news_client


def test_model_router_raises_for_unknown_mode():
    router = DefaultModelRouter({Mode.CURIOUS: StubModelClient("curious", mode=Mode.CURIOUS)})

    with pytest.raises(ModelRoutingError):
        router.route("news")

