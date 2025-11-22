"""Narrative model client implementations for Curious and News modes."""

from __future__ import annotations

import json
import re
import textwrap
from typing import Iterable, Optional, Protocol

from app.domain.dto import (
    CuriousNarrative,
    DocInsights,
    Mode,
    NarrativeResponse,
    NewsNarrative,
    RenderedPrompt,
    SemanticChunk,
    SlideBlock,
    SlideDeck,
)
from app.domain.interfaces import ModelClient

# Character limits per slide (matching Streamlit app)
SLIDE_CHAR_LIMITS = {
    1: 80,   # Cover/title
    2: 500,  # First middle slide
    3: 450,  # Second middle slide
    4: 250,  # Third middle slide
    5: 200,  # Fourth middle slide
    "default": 200,
}


class LanguageModel(Protocol):
    """Protocol describing minimal LLM behavior required by model clients."""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return generated text given system and user prompts."""


def _aggregate_chunks(chunks: Iterable[SemanticChunk], limit: int = 3) -> str:
    selected = []
    for chunk in chunks:
        if not chunk.text:
            continue
        selected.append(f"- {chunk.text.strip()}")
        if len(selected) >= limit:
            break
    return "\n".join(selected)


def _build_slide_deck(content_sections: list[str], template_key: str, language_code: str | None) -> SlideDeck:
    slides = [
        SlideBlock(
            placeholder_id=f"section_{idx+1}",
            text=section,
        )
        for idx, section in enumerate(content_sections)
    ] or [
        SlideBlock(placeholder_id="section_1", text="No content generated.")
    ]
    return SlideDeck(template_key=template_key, language_code=language_code, slides=slides)


class CuriousModelClient(ModelClient):
    """Curious mode model client using Streamlit-style structured JSON generation."""

    mode: Mode = Mode.CURIOUS

    def __init__(self, language_model: LanguageModel, template_key: str = "curious_default") -> None:
        self._language_model = language_model
        self._template_key = template_key

    def generate(
        self,
        prompt: RenderedPrompt,
        insights: DocInsights,
        slide_count: Optional[int] = None,
    ) -> NarrativeResponse:
        """
        Generate curious narrative using structured JSON format (like streamlit app).
        Returns exactly slide_count slides (1 cover + middle slides).
        """
        # Extract source text from semantic chunks
        source_text = self._extract_source_text(insights)
        language = prompt.metadata.get("language", "en")
        target_lang = language.split("-")[0] if "-" in language else language
        
        # Calculate middle slides count (slide_count - 1 cover - 1 CTA = middle slides)
        # For curious-template-1: slide_count=7 means 1 cover + 5 middle + 1 CTA = 7
        # So middle_count = slide_count - 2
        middle_count = max(1, slide_count - 2) if slide_count else 6
        
        # Generate structured JSON
        result_json = self._generate_structured_json(source_text, target_lang, middle_count, prompt)
        
        # Build slide deck from JSON
        slide_deck = self._build_slide_deck_from_json(result_json, middle_count)
        
        # Build explainability notes
        explainability = self._build_explainability_notes(insights, slide_deck.slides)
        
        return CuriousNarrative(
            mode=self.mode,
            slide_deck=slide_deck,
            raw_output=json.dumps(result_json, ensure_ascii=False, indent=2),
            explainability_notes=explainability,
            reasoning_trace=json.dumps(result_json, ensure_ascii=False),
        )

    def _extract_source_text(self, insights: DocInsights) -> str:
        """Extract text from semantic chunks."""
        chunks = []
        for chunk in insights.semantic_chunks:
            if chunk.text and chunk.text.strip():
                chunks.append(chunk.text.strip())
        return "\n\n".join(chunks) or "No content provided."

    def _generate_structured_json(
        self,
        source_text: str,
        target_lang: str,
        middle_count: int,
        prompt: RenderedPrompt,
    ) -> dict:
        """Generate structured JSON like streamlit app."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Build system prompt similar to streamlit app
        system_prompt = f"""
You are a multilingual teaching assistant.

INPUT:
- You will receive a topic or content to explain.

MANDATORY:
- Target language = "{target_lang}".
- Produce ALL text fields strictly in the Target language.
- IMPORTANT: Do NOT use markdown formatting (no **, no *, no #). Use plain text only.
- Generate EXACTLY {middle_count} slides (s1paragraph1 through s{middle_count}paragraph1).

Your job:
1) Extract a short and catchy title → storytitle (≤ 80 characters, plain text only).
2) Summarise the content into EXACTLY {middle_count} slides (s1paragraph1..s{middle_count}paragraph1), each within character limits:
   - s1paragraph1: ≤ 500 characters
   - s2paragraph1: ≤ 450 characters
   - s3paragraph1: ≤ 400 characters
   - s4paragraph1: ≤ 350 characters
   - s5paragraph1: ≤ 300 characters
   - s6paragraph1: ≤ 250 characters
   - Additional slides: ≤ 250 characters each
3) For each slide, write a DALL·E image prompt for a 1024x1024 flat vector illustration:
   - Cover slide: s0alt1 (for the story title/cover)
   - Middle slides: s1alt1..s{middle_count}alt1 (one for each content slide)
   - Bright colors, clean lines, no text/captions/logos
   - Flat vector illustration style
   - Family-friendly and inclusive
4) Keep content factual, educational, and accessible.

SAFETY & POSITIVITY RULES:
- If input includes unsafe themes, reinterpret to safe, inclusive, family-friendly content.
- No markdown formatting - plain text only.
- Image prompts must be safe, no real-person likeness, no text in images.

Respond strictly in this JSON format (keys in English; values in Target language). Include EXACTLY {middle_count} slides:

{{
  "language": "{target_lang}",
  "storytitle": "...",
  "s0alt1": "...",
  "s1paragraph1": "...",
  "s2paragraph1": "...",
  "s3paragraph1": "...",
  "s4paragraph1": "...",
  "s5paragraph1": "...",
  "s6paragraph1": "...",
  "s1alt1": "...",
  "s2alt1": "...",
  "s3alt1": "...",
  "s4alt1": "...",
  "s5alt1": "...",
  "s6alt1": "..."
}}
""".strip()
        
        # Add additional slide fields if needed
        if middle_count > 6:
            additional_paras = ",\n".join([f'  "s{i}paragraph1": "..."' for i in range(7, middle_count + 1)])
            additional_alts = ",\n".join([f'  "s{i}alt1": "..."' for i in range(7, middle_count + 1)])
            system_prompt = system_prompt.replace('  "s6paragraph1": "..."', f'  "s6paragraph1": "...",\n{additional_paras}')
            system_prompt = system_prompt.replace('  "s6alt1": "..."', f'  "s6alt1": "...",\n{additional_alts}')
        
        # Ensure s0alt1 is always in the prompt (for cover slide)
        if '"s0alt1": "..."' not in system_prompt:
            # Insert s0alt1 after storytitle
            system_prompt = system_prompt.replace('  "storytitle": "...",', '  "storytitle": "...",\n  "s0alt1": "...",')
        
        # Ensure s0alt1 is mentioned in the prompt for cover slide
        if 's0alt1' not in system_prompt:
            # Already added above in the JSON format, but ensure it's clear in instructions
            pass
        
        # Build user prompt
        user_prompt = f"""SOURCE INPUT:\n{source_text[:3000]}\n\nReturn only the JSON object described above. No markdown, no code fences, just valid JSON. Include EXACTLY {middle_count} slides."""

        # Generate JSON
        try:
            raw_output = self._language_model.complete(system_prompt, user_prompt)
            logger.debug(f"Curious mode raw output length: {len(raw_output)}")
        except Exception as e:
            logger.error(f"Language model completion failed: {e}")
            raw_output = ""
        
        # Parse JSON
        result = self._parse_json_response(raw_output)
        
        # If parsing failed, log and create minimal structure
        if not result or not isinstance(result, dict):
            logger.warning(f"JSON parsing failed for Curious mode. Raw output preview: {raw_output[:500]}")
            result = {
                "language": target_lang,
                "storytitle": source_text[:80] if source_text else "Educational Story",
            }
            for i in range(1, middle_count + 1):
                result[f"s{i}paragraph1"] = ""
        
        # Ensure all required fields exist
        result.setdefault("language", target_lang)
        result.setdefault("storytitle", "")
        result.setdefault("s0alt1", "")  # Cover slide alt text
        for i in range(1, middle_count + 1):
            result.setdefault(f"s{i}paragraph1", "")
            result.setdefault(f"s{i}alt1", "")  # Ensure alt texts exist
        
        # Clean markdown from paragraph fields only (not alt texts)
        result["storytitle"] = self._clean_markdown(result.get("storytitle", ""))
        for i in range(1, middle_count + 1):
            key = f"s{i}paragraph1"
            result[key] = self._clean_markdown(result.get(key, ""))
        
        # Fallbacks for paragraphs
        if not result["storytitle"].strip():
            first_slide = result.get("s1paragraph1", "")[:60].strip(" .,-")
            result["storytitle"] = first_slide or "Educational Story"
        
        if not result.get("s1paragraph1", "").strip():
            result["s1paragraph1"] = result["storytitle"][:500]
        
        # Generate fallback alt texts if missing
        GENERIC_ALT = (
            "Flat vector illustration of the slide's idea; clean geometric shapes, "
            "smooth gradients, harmonious palette; inclusive, family-friendly; "
            "no text/logos/watermarks; no real-person likeness."
        )
        
        # Cover alt (s0alt1) - for cover slide (slides[0])
        if not result.get("s0alt1", "").strip():
            title = (result.get("storytitle") or "Educational Story").strip()
            result["s0alt1"] = f"Cover for the story titled '{title}': welcoming, abstract, educational motif — {GENERIC_ALT}"
        
        # Middle slide alts (s1alt1, s2alt1, etc.) - for slides[1], slides[2], etc.
        for i in range(1, middle_count + 1):
            if not result.get(f"s{i}alt1", "").strip():
                seed = (result.get(f"s{i}paragraph1") or result.get("storytitle", "")).strip()
                result[f"s{i}alt1"] = f"{seed} — {GENERIC_ALT}" if seed else GENERIC_ALT
        
        # Log final result
        logger.info(f"Curious mode generated {middle_count} middle slides + 1 cover = {middle_count + 1} total slides")
        logger.debug(f"Alt texts generated: {sum(1 for i in range(1, middle_count + 1) if result.get(f's{i}alt1'))} slides")
        
        return result

    def _parse_json_response(self, raw_output: str) -> dict:
        """Parse JSON from model response, handling code fences and extra text."""
        # Try direct JSON parse
        try:
            return json.loads(raw_output)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from code fences
        json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", raw_output)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON object in text
        json_match = re.search(r"\{[\s\S]*\}", raw_output)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Fallback: return empty structure
        return {}

    def _clean_markdown(self, text: str) -> str:
        """Remove markdown formatting from text."""
        if not text:
            return ""
        # Remove **bold**
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        # Remove *italic*
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        # Remove # headers
        text = re.sub(r'#+\s*', '', text)
        # Remove `code blocks`
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # Remove [links](url)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # Remove --- separators
        text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
        # Clean up extra whitespace
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        return text.strip()

    def _build_slide_deck_from_json(self, result_json: dict, middle_count: int) -> SlideDeck:
        """Build SlideDeck from structured JSON.
        
        Note: Template uses s2paragraph1, s3paragraph1, etc. (starting from 2).
        PlaceholderMapper maps:
        - slides[0] → storytitle (cover)
        - slides[1] → s2paragraph1 (first middle slide)
        - slides[2] → s3paragraph1 (second middle slide)
        - etc.
        
        So we create:
        - slides[0] = cover (storytitle)
        - slides[1] = first middle (s1paragraph1 → will map to s2paragraph1)
        - slides[2] = second middle (s2paragraph1 → will map to s3paragraph1)
        - etc.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        slides = []
        
        # Cover slide (uses storytitle) - this becomes slides[0]
        storytitle = result_json.get("storytitle", "Educational Story")
        slides.append(
            SlideBlock(
                placeholder_id="cover",  # Changed from "section_1" to avoid old code path
                text=storytitle[:180],  # Limit cover text
            )
        )
        
        # Middle slides (s1paragraph1 through s{middle_count}paragraph1)
        # These will be mapped to s2paragraph1, s3paragraph1, etc. by PlaceholderMapper
        for i in range(1, middle_count + 1):
            key = f"s{i}paragraph1"
            paragraph = result_json.get(key, "").strip()
            slides.append(
                SlideBlock(
                    placeholder_id=f"slide_{i}",  # Changed from f"section_{i+1}" to avoid old code path
                    text=paragraph if paragraph else f"Slide {i} content",
                )
            )
        
        # Ensure we have exactly middle_count + 1 slides (cover + middle)
        expected_count = middle_count + 1
        if len(slides) != expected_count:
            logger.warning(f"Expected {expected_count} slides, got {len(slides)}. Adjusting...")
            # Trim or pad to exact count
            slides = slides[:expected_count]
            while len(slides) < expected_count:
                slides.append(
                    SlideBlock(
                        placeholder_id=f"slide_{len(slides)}",
                        text="",
                    )
                )
        
        logger.info(f"Built slide deck with {len(slides)} slides: 1 cover + {middle_count} middle")
        
        return SlideDeck(
            template_key=self._template_key,
            language_code=result_json.get("language", "en"),
            slides=slides,
        )

    def _build_explainability_notes(self, insights: DocInsights, slides: list[SlideBlock]) -> list[str]:
        """Build explainability notes from slides."""
        notes = []
        for idx, slide in enumerate(slides):
            source_chunk = ""
            if idx < len(insights.semantic_chunks):
                source_chunk = insights.semantic_chunks[idx].text[:120] if insights.semantic_chunks[idx].text else ""
            notes.append(f"Slide {idx+1}: {slide.text[:120]} (Source: {source_chunk})")
        return notes


class NewsModelClient(ModelClient):
    """News mode model client using Streamlit-style two-phase generation."""

    mode: Mode = Mode.NEWS

    def __init__(self, language_model: LanguageModel, template_key: str = "news_default") -> None:
        self._language_model = language_model
        self._template_key = template_key

    def generate(
        self,
        prompt: RenderedPrompt,
        insights: DocInsights,
        slide_count: Optional[int] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        emotion: Optional[str] = None,
    ) -> NarrativeResponse:
        """
        Generate news narrative using Streamlit-style two-phase approach:
        1. Generate slide structure (JSON format)
        2. Generate individual narrations for each slide
        """
        # Extract article text from semantic chunks
        article_text = self._extract_article_text(insights)
        language = prompt.metadata.get("language", "en")
        content_language = "Hindi" if language.startswith("hi") else "English"
        
        # Detect category, subcategory, emotion if not provided
        if not category or not subcategory or not emotion:
            detected_category, detected_subcategory, detected_emotion = self._detect_category_subcategory_emotion(
                article_text, content_language
            )
            category = category or detected_category
            subcategory = subcategory or detected_subcategory
            emotion = emotion or detected_emotion
        
        # Calculate middle slides count
        middle_count = max(1, slide_count - 2) if slide_count else 5
        
        # Phase 1: Generate slide structure (JSON format)
        slides_structure = self._generate_slide_structure(
            article_text, category, subcategory, emotion, content_language, middle_count
        )
        
        # Phase 2: Generate storytitle (cover slide)
        storytitle = self._generate_storytitle(article_text, content_language, slide_count)
        
        # Phase 3: Generate individual narrations for each slide
        narrations = []
        slide_char_limits = SLIDE_CHAR_LIMITS.copy()
        default_limit = slide_char_limits.get("default", 200)
        
        # Add storytitle as first slide
        narrations.append(self._clean_markdown(storytitle))
        
        # Generate narrations for middle slides
        for idx, slide_data in enumerate(slides_structure[:middle_count], start=1):
            slide_index = idx + 1  # +1 because storytitle is slide 1
            target_limit = slide_char_limits.get(slide_index, default_limit)
            narration = self._generate_slide_narration(
                slide_data, slide_index, content_language, target_limit
            )
            narrations.append(self._clean_markdown(narration))
        
        # Build slide deck
        slide_deck = _build_slide_deck(narrations, self._template_key, language)
        
        return NewsNarrative(
            mode=self.mode,
            slide_deck=slide_deck,
            raw_output=f"Generated {len(narrations)} slides",
            headlines=[storytitle],
            bullet_points=narrations[1:] if len(narrations) > 1 else [],
        )

    def _extract_article_text(self, insights: DocInsights) -> str:
        """Extract full article text from semantic chunks."""
        text_parts = []
        for chunk in insights.semantic_chunks:
            if chunk.text:
                text_parts.append(chunk.text.strip())
        return "\n\n".join(text_parts) or "No article content available."

    def _detect_category_subcategory_emotion(self, article_text: str, content_language: str) -> tuple[str, str, str]:
        """Detect category, subcategory, and emotion from article text (like Streamlit app)."""
        if not article_text or len(article_text.strip()) < 50:
            return ("News", "General", "Neutral")
        
        if content_language == "Hindi":
            prompt = f"""
आप एक समाचार विश्लेषण विशेषज्ञ हैं।

इस समाचार लेख का विश्लेषण करें और नीचे तीन बातें बताएं:

1. category (श्रेणी)
2. subcategory (उपश्रेणी)
3. emotion (भावना)

लेख:
\"\"\"{article_text[:3000]}\"\"\"

जवाब केवल JSON में दें:
{{
  "category": "...",
  "subcategory": "...",
  "emotion": "..."
}}
"""
        else:
            prompt = f"""
You are an expert news analyst.

Analyze the following news article and return:

1. category
2. subcategory
3. emotion

Article:
\"\"\"{article_text[:3000]}\"\"\"

Return ONLY as JSON:
{{
  "category": "...",
  "subcategory": "...",
  "emotion": "..."
}}
"""
        
        try:
            system_prompt = "Classify the news into category, subcategory, and emotion. Return only valid JSON."
            response = self._language_model.complete(system_prompt, prompt.strip())
            content = response.strip()
            content = content.strip("```json").strip("```").strip()
            
            result = json.loads(content)
            if all(k in result for k in ["category", "subcategory", "emotion"]):
                return (result["category"], result["subcategory"], result["emotion"])
        except Exception:
            pass
        
        return ("News", "General", "Neutral")

    def _generate_slide_structure(
        self,
        article_text: str,
        category: Optional[str],
        subcategory: Optional[str],
        emotion: Optional[str],
        content_language: str,
        middle_count: int,
    ) -> list[dict]:
        """Phase 1: Generate slide structure in JSON format."""
        guidance_map = {
            2: "detail the core development with precise names, locations, and the headline claim.",
            3: "explain earlier context, build-up, or precedent events that shaped the story.",
            4: "highlight supporting evidence—quotes, data points, documents, or eyewitness accounts.",
            5: "capture reactions from officials, experts, or the public and note immediate fallout.",
            6: "examine broader implications such as geopolitical, economic, or social impact.",
            7: "surface remaining questions, unresolved angles, or investigative threads still open.",
        }
        
        guidance_lines = []
        for story_slide in range(2, middle_count + 2):
            description = guidance_map.get(
                story_slide,
                "add further factual detail, supporting evidence, or expert insight while staying concise."
            )
            guidance_lines.append(f"- Content Slide {story_slide - 1} (≤ 200 characters): {description}")
        
        guidance_text = "\n".join(guidance_lines) or "- Provide factual narrative for each slide."
        language_clause = (
            "Write all slide titles and prompts in Hindi (Devanagari script)."
            if content_language == "Hindi"
            else "Write all slide titles and prompts in English, even if the article text is in another language."
        )
        
        system_prompt = f"""
Create an engaging Google Web Story based on the news article provided below.

Objectives:
- Extract the key highlights, timelines, verified facts, and impactful quotes.
- Summarize the complete story visually across {middle_count} slides.
- Keep the tone informative, balanced, and visually compelling.
- Provide slide-wise captions and background image suggestions that align with each phase of the story.
- Maintain chronological flow: introduction → build-up → evidence → reactions → implications → outlook.
- Avoid repetition; each slide must surface fresh details pulled from different portions of the article.
- IMPORTANT: Do NOT use markdown formatting (no **, no *, no #). Use plain text only.

Language requirements:
- {language_clause}
- All fields must be written in {content_language}.

Return JSON strictly in this format (NO markdown, NO code fences):
{{
  "slides": [
    {{
      "title": "<concise slide caption (≤ 90 characters, plain text only)>",
      "summary": "<two or three sentences covering the facts for narration, plain text only>",
      "image_prompt": "<background or visual suggestion relevant to this slide>"
    }},
    ...
  ]
}}
"""
        
        user_prompt = f"""
Category: {category or "News"}
Subcategory: {subcategory or "General"}
Emotion: {emotion or "Neutral"}

Article:
\"\"\"{article_text[:3000]}\"\"\"

Guidance:
{guidance_text}
"""
        
        try:
            raw_output = self._language_model.complete(system_prompt, user_prompt)
            # Clean JSON response
            raw_output = raw_output.strip()
            raw_output = raw_output.strip("```json").strip("```").strip()
            
            # Parse JSON
            parsed = json.loads(raw_output)
            slides_raw = parsed.get("slides", [])
            
            if not slides_raw:
                # Fallback: generate simple slides from article text
                return self._fallback_slide_generation(article_text, middle_count)
            
            return slides_raw
        except (json.JSONDecodeError, KeyError, Exception) as e:
            # Fallback if JSON parsing fails
            return self._fallback_slide_generation(article_text, middle_count)

    def _fallback_slide_generation(self, article_text: str, middle_count: int) -> list[dict]:
        """Fallback: Generate simple slides from article text."""
        sentences = article_text.split(". ")
        slides = []
        sentences_per_slide = max(1, len(sentences) // middle_count)
        
        for i in range(middle_count):
            start_idx = i * sentences_per_slide
            end_idx = min(start_idx + sentences_per_slide, len(sentences))
            slide_text = ". ".join(sentences[start_idx:end_idx])
            if slide_text:
                slides.append({
                    "title": slide_text[:90],
                    "summary": slide_text[:300],
                    "image_prompt": "News story background"
                })
        
        return slides[:middle_count]

    def _generate_storytitle(self, article_text: str, content_language: str, slide_count: Optional[int]) -> str:
        """Generate storytitle (cover slide narration)."""
        headline = article_text.split("\n")[0].strip().replace('"', '')
        if not headline:
            headline = article_text[:100].strip()
        
        slide1_limit = SLIDE_CHAR_LIMITS.get(1, 80)
        
        if content_language == "Hindi":
            slide1_prompt = (
                f"Generate news headline narration in Hindi for the story: {headline}. "
                f"Maximum {slide1_limit} characters. Avoid greetings. Respond in Hindi (Devanagari script) only. "
                f"Do NOT use markdown formatting (no **, no *, no #). Use plain text only."
            )
        else:
            slide1_prompt = (
                f"Generate headline intro narration in English for: {headline}. "
                f"Maximum {slide1_limit} characters. Avoid greetings. Respond in English only, translating the source if necessary. "
                f"Do NOT use markdown formatting (no **, no *, no #). Use plain text only."
            )
        
        try:
            system_prompt = "You are a news presenter generating opening lines. Always respond with plain text only, no markdown."
            response = self._language_model.complete(system_prompt, slide1_prompt)
            storytitle = textwrap.shorten(
                self._clean_markdown(response.strip()),
                width=slide1_limit,
                placeholder="…"
            )
            return storytitle if storytitle else headline[:80]
        except Exception:
            return headline[:80]

    def _generate_slide_narration(
        self,
        slide_data: dict,
        slide_index: int,
        content_language: str,
        target_limit: int,
    ) -> str:
        """Phase 2: Generate individual narration for a slide."""
        caption = (slide_data.get("title") or "").strip()
        summary_brief = (slide_data.get("summary") or slide_data.get("caption") or "").strip()
        image_prompt = (slide_data.get("image_prompt") or "").strip()
        
        if not summary_brief:
            summary_brief = caption or "Provide factual narration for this segment."
        
        script_language = f"{content_language} (use Devanagari script)" if content_language == "Hindi" else content_language
        language_requirement = (
            "Deliver the narration strictly in Hindi (Devanagari script)."
            if content_language == "Hindi"
            else "Deliver the narration strictly in English. Do not include Hindi words or transliteration."
        )
        
        character_sketch = (
            f"Polaris is a sincere and articulate {content_language} news anchor. "
            "They present facts clearly, concisely, and warmly, connecting deeply with their audience."
        )
        
        narration_prompt = f"""
Write a narration in {script_language} (max {target_limit} characters),
in the voice of Polaris (factual, vivid, and neutral). {language_requirement}

IMPORTANT: Do NOT use markdown formatting (no **, no *, no #). Use plain text only.

Key points to cover:
{summary_brief}

Visual inspiration:
{image_prompt or 'Use a neutral newsroom-inspired background.'}

Character sketch:
{character_sketch}
"""
        
        try:
            system_prompt = "You write concise narrations for web story slides. Always respond with plain text only, no markdown formatting."
            response = self._language_model.complete(system_prompt, narration_prompt.strip())
            narration = textwrap.shorten(
                self._clean_markdown(response.strip()),
                width=target_limit,
                placeholder="…"
            )
            return narration if narration else summary_brief[:target_limit]
        except Exception:
            return summary_brief[:target_limit] if summary_brief else "Unable to generate narration for this slide."

    def _clean_markdown(self, text: str) -> str:
        """Remove markdown formatting from text."""
        if not text:
            return ""
        
        # Remove **bold**
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        # Remove *italic*
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        # Remove # headers
        text = re.sub(r'#+\s*', '', text)
        # Remove `code blocks`
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # Remove [links](url)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text


__all__ = ["CuriousModelClient", "NewsModelClient", "LanguageModel"]

