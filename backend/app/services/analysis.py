"""Analysis facade that combines function-style analyzers and LLM analyzers."""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from collections import Counter
from typing import Iterable, List, Optional, Protocol, Sequence

from app.domain.dto import AnalysisReport, DocInsights, Entity, EntityMap, SemanticChunk, TopicCluster
from app.domain.interfaces import AnalysisFacade


class AnalyzerStrategy(Protocol):
    """Protocol for strategies that augment an AnalysisReport."""

    def analyze(self, insights: DocInsights) -> AnalysisReport:
        """Produce a partial analysis report derived from the provided insights."""


class BaseAnalyzerStrategy(ABC):
    """Convenience abstract base class implementing AnalyzerStrategy."""

    @abstractmethod
    def analyze(self, insights: DocInsights) -> AnalysisReport:
        raise NotImplementedError


def _flatten_chunks(insights: DocInsights) -> str:
    return "\n".join(chunk.text for chunk in insights.semantic_chunks if chunk.text)


def _extract_keywords(text: str, limit: int = 10) -> List[str]:
    tokens = [
        token.strip(".,!?()[]{}\"'").lower()
        for token in text.split()
        if token and token.isalpha() and len(token) > 3
    ]
    most_common = Counter(tokens).most_common(limit)
    return [word for word, _ in most_common]


class HeuristicFunctionAnalyzer(BaseAnalyzerStrategy):
    """Lightweight analyzer that derives topics and gaps heuristically."""

    def analyze(self, insights: DocInsights) -> AnalysisReport:
        text = _flatten_chunks(insights)
        keywords = _extract_keywords(text)

        topic = TopicCluster(
            title="Key Themes",
            keywords=keywords[:5],
            summary=insights.summaries[0] if insights.summaries else None,
        )

        gaps = insights.gaps or self._infer_gaps(keywords)
        return AnalysisReport(
            narrative_summary=insights.summaries[0] if insights.summaries else None,
            topic_clusters=[topic] if topic.keywords else [],
            gaps=gaps,
        )

    def _infer_gaps(self, keywords: List[str]) -> List[str]:
        if not keywords:
            return ["Insufficient content detected; request more detailed inputs."]
        return []


class PromptRecommendationAnalyzer(BaseAnalyzerStrategy):
    """Generate recommended prompts based on entities and keywords."""

    def __init__(self, base_prompt: str = "Explore the relationship between {entity} and {keyword}.") -> None:
        self._base_prompt = base_prompt

    def analyze(self, insights: DocInsights) -> AnalysisReport:
        keywords = _extract_keywords(_flatten_chunks(insights), limit=5)
        entities = list(self._iter_entities(insights.entities))

        prompts: List[str] = []
        if entities:
            for entity in entities[:3]:
                for keyword in keywords[:3]:
                    prompts.append(self._base_prompt.format(entity=entity.name, keyword=keyword))
        else:
            prompts.extend([f"Explore deeper insights about {keyword}." for keyword in keywords[:3]])

        return AnalysisReport(recommended_prompts=prompts)

    def _iter_entities(self, entity_map: EntityMap) -> Iterable[Entity]:
        for entity_list in entity_map.entities.values():
            for entity in entity_list:
                yield entity


class CompositeAnalysisFacade(AnalysisFacade):
    """Compose multiple analyzer strategies into a single facade."""

    def __init__(self, strategies: Sequence[AnalyzerStrategy]) -> None:
        if not strategies:
            raise ValueError("At least one AnalyzerStrategy must be provided.")
        self._strategies = list(strategies)

    def analyze(self, insights: DocInsights) -> AnalysisReport:
        merged = AnalysisReport()
        for strategy in self._strategies:
            partial = strategy.analyze(insights)
            merged = self._merge_reports(merged, partial)
        return merged

    def _merge_reports(self, base: AnalysisReport, addition: AnalysisReport) -> AnalysisReport:
        summary = base.narrative_summary or addition.narrative_summary

        clusters = self._merge_clusters(base.topic_clusters, addition.topic_clusters)
        prompts = list(dict.fromkeys(itertools.chain(base.recommended_prompts, addition.recommended_prompts)))
        gaps = list(dict.fromkeys(itertools.chain(base.gaps, addition.gaps)))

        metadata = {**base.metadata, **addition.metadata}
        return AnalysisReport(
            narrative_summary=summary,
            topic_clusters=clusters,
            recommended_prompts=prompts,
            gaps=gaps,
            metadata=metadata,
        )

    def _merge_clusters(self, existing: List[TopicCluster], incoming: List[TopicCluster]) -> List[TopicCluster]:
        if not existing:
            return incoming
        titles = {cluster.title: cluster for cluster in existing}
        for cluster in incoming:
            if cluster.title in titles:
                merged_keywords = list(dict.fromkeys([*titles[cluster.title].keywords, *cluster.keywords]))
                titles[cluster.title].keywords = merged_keywords
                if cluster.summary:
                    titles[cluster.title].summary = cluster.summary
            else:
                titles[cluster.title] = cluster
        return list(titles.values())


__all__ = [
    "CompositeAnalysisFacade",
    "HeuristicFunctionAnalyzer",
    "PromptRecommendationAnalyzer",
    "AnalyzerStrategy",
]

