from __future__ import annotations

import json
from dataclasses import dataclass

from app.domain.dto import CuriousNarrative, DocInsights, Entity, RenderedPrompt, SemanticChunk
from app.services.model_clients import CuriousModelClient, LanguageModel


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
    # Provide a valid JSON response as expected by CuriousModelClient
    mock_json = {
        "language": "en",
        "storytitle": "Test Story Title",
        "s0alt1": "Cover Alt Text",
        "s1paragraph1": "Slide 1 Content",
        "s1alt1": "Slide 1 Alt Text",
        "s2paragraph1": "Slide 2 Content",
        "s2alt1": "Slide 2 Alt Text",
        "s3paragraph1": "Slide 3 Content",
        "s3alt1": "Slide 3 Alt Text",
        "s4paragraph1": "Slide 4 Content",
        "s4alt1": "Slide 4 Alt Text",
        "s5paragraph1": "Slide 5 Content",
        "s5alt1": "Slide 5 Alt Text",
        "s6paragraph1": "Slide 6 Content",
        "s6alt1": "Slide 6 Alt Text"
    }
    lm = StubLanguageModel(response=json.dumps(mock_json))
    client = CuriousModelClient(language_model=lm)
    insights = make_insights()
    prompt = make_prompt("curious")

    narrative = client.generate(prompt, insights, slide_count=6)

    assert isinstance(narrative, CuriousNarrative)
    assert narrative.slide_deck.template_key == "curious_default"
    # 1 cover + 4 middle (since slide_count=6 means 1 cover + 4 middle + 1 CTA, 
    # but build_slide_deck_from_json builds cover + middle_count)
    # Wait, CuriousModelClient.generate: middle_count = max(1, slide_count - 2)
    # If slide_count=6, middle_count=4. Total slides = 1 (cover) + 4 (middle) = 5.
    assert len(narrative.slide_deck.slides) == 5
    assert lm.calls[0][0].startswith("You are a multilingual teaching assistant.")
    assert "SOURCE INPUT:" in lm.calls[0][1]
