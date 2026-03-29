from __future__ import annotations

from dataclasses import dataclass

from app.domain.dto import DocInsights, Entity, RenderedPrompt, SemanticChunk
from app.services.model_clients import LanguageModel, NewsModelClient


@dataclass
class StubLanguageModel(LanguageModel):
    response: str

    def __post_init__(self):
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.response


def make_insights() -> DocInsights:
    doc_insights = DocInsights(
        semantic_chunks=[
            SemanticChunk(id="chunk-1", text="Chunk one content for context."),
            SemanticChunk(id="chunk-2", text="Chunk two additional details."),
        ]
    )
    doc_insights.entities.add(Entity(name="OpenAI", type="ORG"))
    doc_insights.entities.add(Entity(name="GPT-5", type="PRODUCT"))
    return doc_insights


def make_prompt() -> RenderedPrompt:
    return RenderedPrompt(
        system="news system",
        user="news user prompt",
        metadata={"mode": "news", "language": "en-IN"},
    )


def test_news_model_client_generates_news_narrative():
    lm = StubLanguageModel(
        response='{"slides":[{"title":"Major update announced","narration":"Point one"},{"title":"Policy shift","narration":"Point two"}],"storytitle":"Major update announced"}'
    )
    client = NewsModelClient(language_model=lm)

    narrative = client.generate(make_prompt(), make_insights(), slide_count=4, category="News")

    assert narrative.mode.value == "news"
    assert narrative.slide_deck.template_key == "news_default"
    assert narrative.headlines
    assert narrative.bullet_points
    assert lm.calls
