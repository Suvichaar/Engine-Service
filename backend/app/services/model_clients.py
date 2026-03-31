"""Narrative model client implementations for Curious and News modes."""

from __future__ import annotations

import json
import logging
import re
import textwrap
from typing import Iterable, Optional, Protocol

from app.domain.dto import (
    CuriousNarrative,
    DocInsights,
    Mode,
    NarrativeResponse,
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
    # Ensure we always have at least one slide with content
    if not content_sections:
        # Fallback: create a default slide instead of "No content generated"
        slides = [
            SlideBlock(
                placeholder_id="section_1",
                text="Breaking News Story",
            )
        ]
    else:
        # Filter out empty sections and ensure first slide is never empty
        filtered_sections = []
        for section in content_sections:
            if section and section.strip():
                filtered_sections.append(section.strip())
        
        # If all sections were empty, use fallback
        if not filtered_sections:
            filtered_sections = ["Breaking News Story"]
        
        # Ensure first slide (cover) is never empty
        if not filtered_sections[0] or not filtered_sections[0].strip():
            filtered_sections[0] = "Breaking News Story"
        
        slides = [
            SlideBlock(
                placeholder_id=f"section_{idx+1}",
                text=section,
            )
            for idx, section in enumerate(filtered_sections)
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
        # Example: slide_count=4 means 1 cover + 2 middle + 1 CTA = 4
        # Example: slide_count=7 means 1 cover + 5 middle + 1 CTA = 7
        # So middle_count = slide_count - 2
        # Ensure at least 1 middle slide, but respect the requested slide_count
        import logging
        logger = logging.getLogger(__name__)
        if slide_count:
            middle_count = max(1, slide_count - 2)  # At least 1 middle slide, but respect slide_count
            logger.info(f"Curious mode: slide_count={slide_count}, calculating middle_count={middle_count} (1 cover + {middle_count} middle + 1 CTA = {1 + middle_count + 1} total)")
        else:
            middle_count = 6  # Default fallback (for backward compatibility)
            logger.warning("Curious mode: slide_count not provided, using default middle_count=6")
        
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
        # Determine script/language name for better instructions
        lang_script_map = {
            "hi": "Devanagari script (हिंदी)",
            "mr": "Devanagari script (मराठी)",
            "gu": "Gujarati script (ગુજરાતી)",
            "ta": "Tamil script (தமிழ்)",
            "te": "Telugu script (తెలుగు)",
            "kn": "Kannada script (ಕನ್ನಡ)",
            "bn": "Bengali script (বাংলা)",
            "pa": "Gurmukhi script (ਪੰਜਾਬੀ)",
            "ur": "Urdu script (اردو)",
            "or": "Odia script (ଓଡ଼ିଆ)",
            "ml": "Malayalam script (മലയാളം)",
        }
        script_info = lang_script_map.get(target_lang, f"{target_lang} language")
        
        system_prompt = f"""
You are a multilingual teaching assistant.

INPUT:
- You will receive a topic or content to explain.

MANDATORY LANGUAGE REQUIREMENTS:
- Target language code = "{target_lang}".
- Story content (storytitle, s1paragraph1, s2paragraph1, etc.) MUST be written in {target_lang} language.
- If target_lang is "hi", "mr", "gu", "ta", "te", "kn", "bn", "pa", "or", "ml", or "ur", use the appropriate native script ({script_info}).
- Image prompts (s0alt1, s1alt1, s2alt1, etc.) MUST ALWAYS be in ENGLISH ONLY, regardless of story language.
- IMPORTANT: Do NOT use markdown formatting (no **, no *, no #). Use plain text only.
- Generate EXACTLY {middle_count} slides (s1paragraph1 through s{middle_count}paragraph1).

Your job:
1) Extract a short and catchy title → storytitle (≤ 80 characters, plain text only, in {target_lang} language).
2) Summarise the content into EXACTLY {middle_count} slides (s1paragraph1..s{middle_count}paragraph1), each within character limits:
   - All story content must be in {target_lang} language ({script_info}).
   - s1paragraph1: ≤ 500 characters
   - s2paragraph1: ≤ 450 characters
   - s3paragraph1: ≤ 400 characters
   - s4paragraph1: ≤ 350 characters
   - s5paragraph1: ≤ 300 characters
   - s6paragraph1: ≤ 250 characters
   - Additional slides: ≤ 250 characters each
3) For each slide, write a DALL·E image prompt in ENGLISH ONLY (for image generation):
   - Cover slide: s0alt1 (for the story title/cover) - MUST be in English
   - Middle slides: s1alt1..s{middle_count}alt1 (one for each content slide) - MUST be in English
   - Image prompts must be in ENGLISH, even if story content is in {target_lang}
   - Bright colors, clean lines, no text/captions/logos
   - Flat vector illustration style
   - Family-friendly and inclusive
4) Keep content factual, educational, and accessible.

SAFETY & POSITIVITY RULES:
- If input includes unsafe themes, reinterpret to safe, inclusive, family-friendly content.
- No markdown formatting - plain text only.
- Image prompts must be safe, no real-person likeness, no text in images.

CRITICAL: Respond strictly in this JSON format:
- Keys: Always in English
- Story content values (storytitle, s1paragraph1, etc.): In {target_lang} language ({script_info})
- Image prompt values (s0alt1, s1alt1, etc.): ALWAYS in English only

Include EXACTLY {middle_count} slides:

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
            
            # CRITICAL: Convert non-English title to English description for image prompt
            # Story title remains in original language, only image prompt is converted
            if target_lang != "en":
                try:
                    # Generate English description from non-English title for image prompt
                    title_desc_prompt = f"""Convert this story title to a brief English description for an image prompt (max 50 words).
Title: {title}
Original Language: {target_lang}

Return only the English description that captures the visual essence of the story, no quotes or labels."""
                    
                    title_desc = self._language_model.complete(
                        "You are a translator. Convert story titles to English descriptions for image generation.",
                        title_desc_prompt
                    ).strip().strip('"').strip("'")
                    
                    if title_desc and len(title_desc) > 10:
                        result["s0alt1"] = f"Cover illustration for story about {title_desc}: welcoming, abstract, educational motif — {GENERIC_ALT}"
                    else:
                        # Fallback if conversion fails
                        result["s0alt1"] = f"Educational story cover illustration, welcoming, abstract, positive theme — {GENERIC_ALT}"
                except Exception as e:
                    logger.warning(f"Failed to convert title to English for image prompt: {e}")
                    # Fallback if LLM fails
                    result["s0alt1"] = f"Educational story cover illustration, welcoming, abstract, positive theme — {GENERIC_ALT}"
            else:
                # English title - use directly
                result["s0alt1"] = f"Cover for the story titled '{title}': welcoming, abstract, educational motif — {GENERIC_ALT}"
        
        # Middle slide alts (s1alt1, s2alt1, etc.) - for slides[1], slides[2], etc.
        for i in range(1, middle_count + 1):
            if not result.get(f"s{i}alt1", "").strip():
                seed = (result.get(f"s{i}paragraph1") or result.get("storytitle", "")).strip()
                
                # CRITICAL: Convert non-English content to English description for image prompt
                # Story content (s{i}paragraph1) remains in original language, only image prompt is converted
                if target_lang != "en" and seed:
                    try:
                        # Generate English description from non-English content for image prompt
                        desc_prompt = f"""Convert this story content to a brief English description for an image prompt (max 30 words).
Content: {seed[:200]}
Original Language: {target_lang}

Return only the English description that captures the visual essence, no quotes or labels."""
                        
                        english_desc = self._language_model.complete(
                            "You are a translator. Convert story content to English descriptions for image generation.",
                            desc_prompt
                        ).strip().strip('"').strip("'")
                        
                        if english_desc and len(english_desc) > 10:
                            result[f"s{i}alt1"] = f"{english_desc} — {GENERIC_ALT}"
                        else:
                            # Fallback if conversion fails
                            result[f"s{i}alt1"] = GENERIC_ALT
                    except Exception as e:
                        logger.warning(f"Failed to convert slide {i} content to English for image prompt: {e}")
                        # Fallback if LLM fails
                        result[f"s{i}alt1"] = GENERIC_ALT
                else:
                    # English content - use directly
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


__all__ = ["CuriousModelClient", "LanguageModel"]

