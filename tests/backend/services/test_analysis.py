from __future__ import annotations

from app.domain.dto import DocInsights, Entity, EntityMap, SemanticChunk
from app.services.analysis import CompositeAnalysisFacade, HeuristicFunctionAnalyzer, PromptRecommendationAnalyzer


def make_insights(text: str, entities: list[Entity] | None = None) -> DocInsights:
    entity_map = EntityMap()
    for entity in entities or []:
        entity_map.add(entity)

    return DocInsights(
        semantic_chunks=[SemanticChunk(id="chunk-1", text=text)],
        summaries=["Summary of the document"],
        entities=entity_map,
    )


def test_composite_facade_combines_strategies():
    insights = make_insights(
        "Artificial intelligence and machine learning drive innovation in healthcare and finance.",
        entities=[Entity(name="OpenAI", type="ORG"), Entity(name="Innovation Lab", type="ORG")],
    )

    facade = CompositeAnalysisFacade(
        [
            HeuristicFunctionAnalyzer(),
            PromptRecommendationAnalyzer(),
        ]
    )

    report = facade.analyze(insights)

    assert report.narrative_summary == "Summary of the document"
    assert any(cluster.keywords for cluster in report.topic_clusters)
    assert len(report.recommended_prompts) > 0
    assert report.gaps == []


def test_facade_merges_clusters_and_prompts():
    class CustomAnalyzer(HeuristicFunctionAnalyzer):
        def analyze(self, insights: DocInsights):
            base_report = super().analyze(insights)
            base_report.topic_clusters.append(
                base_report.topic_clusters[0].model_copy(update={"title": "Secondary", "keywords": ["growth"]})
            )
            base_report.recommended_prompts.append("Discuss the impact of regulation.")
            base_report.gaps.append("Need statistics on adoption rate.")
            return base_report

    insights = make_insights(
        "Data privacy and cybersecurity remain critical challenges.",
        entities=[Entity(name="GlobalTech", type="ORG")],
    )

    facade = CompositeAnalysisFacade(
        [
            CustomAnalyzer(),
            PromptRecommendationAnalyzer(base_prompt="How does {entity} align with {keyword}?"),
        ]
    )

    report = facade.analyze(insights)

    titles = {cluster.title for cluster in report.topic_clusters}
    assert "Key Themes" in titles
    assert "Secondary" in titles
    assert "Need statistics on adoption rate." in report.gaps
    assert any(prompt.startswith("How does") for prompt in report.recommended_prompts)

