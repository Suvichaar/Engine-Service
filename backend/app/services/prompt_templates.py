"""Prompt template service and selection controller."""

from __future__ import annotations

from typing import Iterable, Sequence

from app.domain.dto import AnalysisReport, PromptTemplateInfo, RenderedPrompt
from app.domain.interfaces import PromptTemplateService
from app.prompts import get_prompt_config
from app.prompts.registry import InvalidCategoryError, PromptNotFoundError, available_modes, render_prompt


class DefaultPromptTemplateService(PromptTemplateService):
    """Serve prompt templates from the prompts registry."""

    def list_templates(self) -> Iterable[PromptTemplateInfo]:
        for mode in available_modes():
            config = get_prompt_config(mode)
            yield PromptTemplateInfo(
                mode=mode,
                description=getattr(config, "description", None),
                allowed_categories=list(config.allowed_categories),
                user_template=config.user_template,
            )

    def get_prompt(
        self,
        *,
        mode: str,
        category: str,
        language: str,
        analysis: str,
        keywords: Iterable[str],
    ) -> RenderedPrompt:
        result = render_prompt(
            mode,
            category=category,
            language=language,
            analysis=analysis,
            keywords=list(keywords),
        )
        return RenderedPrompt(
            system=result["system"],
            user=result["user"],
            metadata=result.get("metadata", {}),
        )


class PromptSelectionError(Exception):
    """Raised when prompt selection fails."""


class PromptSelectionController:
    """Encapsulate selection logic for choosing prompts."""

    def __init__(self, service: PromptTemplateService) -> None:
        self._service = service

    def select_prompt(
        self,
        *,
        mode: str,
        category: str,
        language: str,
        analysis: AnalysisReport,
        keywords: Sequence[str],
    ) -> RenderedPrompt:
        analysis_text = self._build_analysis_text(analysis)
        try:
            return self._service.get_prompt(
                mode=mode,
                category=category,
                language=language,
                analysis=analysis_text,
                keywords=keywords,
            )
        except (PromptNotFoundError, InvalidCategoryError) as exc:  # pragma: no cover - defensive
            raise PromptSelectionError(str(exc)) from exc

    def _build_analysis_text(self, report: AnalysisReport) -> str:
        segments: list[str] = []
        if report.narrative_summary:
            segments.append(f"Summary: {report.narrative_summary}")
        for cluster in report.topic_clusters:
            keyword_str = ", ".join(cluster.keywords) if cluster.keywords else ""
            cluster_lines = [f"Cluster: {cluster.title}"]
            if keyword_str:
                cluster_lines.append(f"Keywords: {keyword_str}")
            if cluster.summary:
                cluster_lines.append(f"Details: {cluster.summary}")
            segments.append(" | ".join(cluster_lines))
        if not segments:
            segments.append("No analysis available.")
        return "\n".join(segments)


__all__ = ["DefaultPromptTemplateService", "PromptSelectionController", "PromptSelectionError"]

