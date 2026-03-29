from __future__ import annotations

import pytest

from app.domain.dto import AnalysisReport, TopicCluster
from app.services.prompt_templates import DefaultPromptTemplateService, PromptSelectionController, PromptSelectionError


def test_list_templates_returns_modes():
    service = DefaultPromptTemplateService()

    templates = {info.mode: info for info in service.list_templates()}

    assert "curious" in templates
    assert "news" in templates
    assert "{analysis}" in templates["curious"].user_template


def test_get_prompt_renders_user_content():
    service = DefaultPromptTemplateService()

    prompt = service.get_prompt(
        mode="news",
        category="News",
        language="en-IN",
        analysis="Headline summary here.",
        keywords=["economy", "policy"],
    )

    assert "Headline summary here." in prompt.user
    assert "economy" in prompt.user
    assert prompt.metadata["mode"] == "news"


def test_prompt_selection_controller_composes_analysis_text():
    service = DefaultPromptTemplateService()
    controller = PromptSelectionController(service)

    analysis = AnalysisReport(
        narrative_summary="AI adoption increases.",
        topic_clusters=[
            TopicCluster(title="Adoption", keywords=["AI", "automation"], summary="Companies embracing AI."),
        ],
    )

    prompt = controller.select_prompt(
        mode="curious",
        category="Art",
        language="en-IN",
        analysis=analysis,
        keywords=["innovation"],
    )

    assert "AI adoption increases." in prompt.user
    assert "automation" in prompt.user
    assert prompt.metadata["mode"] == "curious"


def test_prompt_selection_invalid_category_raises():
    service = DefaultPromptTemplateService()
    controller = PromptSelectionController(service)

    analysis = AnalysisReport()

    with pytest.raises(PromptSelectionError):
        controller.select_prompt(
            mode="news",
            category="Art",
            language="en-IN",
            analysis=analysis,
            keywords=[],
        )

