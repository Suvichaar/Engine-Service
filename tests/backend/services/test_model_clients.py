from __future__ import annotations

from dataclasses import dataclass

from app.domain.dto import CuriousNarrative, DocInsights, Entity, RenderedPrompt, SemanticChunk
from app.services.model_clients import CuriousModelClient, LanguageModel, NewsModelClient


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


def make_prompt(mode: str) -> RenderedPrompt:
    return RenderedPrompt(
        system=f"{mode} system",
        user=f"{mode} user prompt",
        metadata={"mode": mode, "language": "en-IN"},
    )


def test_curious_model_client_generates_narrative():
    lm = StubLanguageModel(response="Slide A\n\nSlide B")
    client = CuriousModelClient(language_model=lm)
    insights = make_insights()
    prompt = make_prompt("curious")

    narrative = client.generate(prompt, insights)

    assert isinstance(narrative, CuriousNarrative)
    assert narrative.slide_deck.template_key == "curious_default"
    assert len(narrative.slide_deck.slides) == 2
    assert lm.calls[0][0] == prompt.system
    assert "Contextual Highlights" in lm.calls[0][1]


def test_news_model_client_generates_headlines_and_bullets():
    lm = StubLanguageModel(response="Major update announced\n- Point one\n- Point two")
    client = NewsModelClient(language_model=lm)
    insights = make_insights()
    prompt = make_prompt("news")

    narrative = client.generate(prompt, insights)

    assert narrative.headlines == ["Major update announced"]
    assert narrative.bullet_points == ["Point one", "Point two"]
    assert narrative.slide_deck.template_key == "news_default"
    assert "Context:" in lm.calls[0][1]

