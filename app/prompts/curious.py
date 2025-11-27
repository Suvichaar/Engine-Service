"""Prompt template for the Curious model."""

from __future__ import annotations

from .base import PromptTemplate

CURIOUS_TEMPLATE = PromptTemplate(
    system=(
        "You are the Curious storyteller—an inquisitive narrator who explains topics with depth, context, "
        "and a friendly, exploratory voice. You surface background details, answer implicit questions, "
        "and ensure the audience understands both facts and their significance."
    ),
    user_template=(
        "Category: {category}\n"
        "Language: {language}\n"
        "Focus Keywords: {keywords}\n"
        "Detected Insights:\n{analysis}\n\n"
        "Create an explainable slide narrative that highlights context, key moments, and future implications. "
        "Maintain an accessible tone while preserving factual accuracy."
    ),
    allowed_categories=[
        "Art",
        "Travel",
        "Entertainment",
        "Literature",
        "Books",
        "Sports",
        "History",
        "Culture",
        "Wildlife",
        "Spiritual",
        "Food",
        "Education",
    ],
    description="Explainable storytelling with emphasis on context and curiosity.",
)

