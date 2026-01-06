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
        
        # Filter out negative content - keep only positive/neutral (language-agnostic)
        article_text = self._filter_positive_content(article_text)
        
        # CRITICAL LAYER 2: Extract URL from insights and add URL context to force correct topic
        source_url = None
        url_context = ""
        if insights.semantic_chunks:
            first_chunk = insights.semantic_chunks[0]
            source_url = first_chunk.source_id  # URL is stored in source_id
            
            if source_url and str(source_url).startswith(('http://', 'https://')):
                from urllib.parse import urlparse
                parsed = urlparse(str(source_url))
                path_parts = [p for p in parsed.path.split('/') if p and len(p) > 3]
                url_keywords = []
                skip_words = {'article', 'news', 'sports', 'cricket', 'football', 'cities', 
                             'entertainment', 'technology', 'business', 'politics', 'world'}
                
                # Extract keywords from last 3 path segments
                for part in path_parts[-3:]:
                    words = part.split('-')
                    for word in words:
                        if len(word) > 3 and word.lower() not in skip_words:
                            url_keywords.append(word.lower())
                
                if url_keywords:
                    unique_keywords = list(dict.fromkeys(url_keywords[:5]))  # Remove duplicates, keep first 5
                    url_context = f"\n\nCRITICAL INSTRUCTION: The article URL contains these keywords: {', '.join(unique_keywords)}. The generated story MUST be about this topic. DO NOT generate about Delhi pollution, air quality, or any unrelated topic. The URL is: {source_url}. Ensure the story title and content match the URL topic."
                    logging.getLogger(__name__).warning(f"🔍 Added URL context to LLM: {unique_keywords}")
        
        # Add URL context to article text to force correct topic generation
        if url_context:
            article_text = article_text + url_context
        
        language = prompt.metadata.get("language", "en")
        # Extract base language code (e.g., "hi" from "hi-IN")
        lang_code = language.split("-")[0] if "-" in language else language
        
        # Map language codes to language names for prompts
        lang_name_map = {
            "hi": "Hindi",
            "mr": "Marathi",
            "gu": "Gujarati",
            "ta": "Tamil",
            "te": "Telugu",
            "kn": "Kannada",
            "bn": "Bengali",
            "pa": "Punjabi",
            "ur": "Urdu",
            "or": "Odia",
            "ml": "Malayalam",
        }
        content_language = lang_name_map.get(lang_code, "English")
        
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
        
        # Add storytitle as first slide - ensure it's never empty
        cleaned_storytitle = self._clean_markdown(storytitle).strip()
        if not cleaned_storytitle:
            # Fallback: use first line of article or default
            cleaned_storytitle = article_text.split("\n")[0].strip()[:80] if article_text else "Breaking News Story"
        narrations.append(cleaned_storytitle)
        
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

    def _filter_positive_content(self, text: str) -> str:
        """
        Language-agnostic filter: Remove negative content (war, attack, violence, etc.) 
        and keep only positive/neutral content.
        Works for ANY language by detecting script and using appropriate keywords.
        """
        if not text or len(text.strip()) < 50:
            return text
        
        import re
        logger = logging.getLogger(__name__)
        
        # MULTILINGUAL NEGATIVE KEYWORDS - Organized by script/language
        negative_keywords = {
            # English (Latin script)
            'latin': [
                'war', 'wars', 'warfare', 'battle', 'battles', 'attack', 'attacks', 'attacked', 'attacking',
                'violence', 'violent', 'kill', 'killed', 'killing', 'death', 'deaths', 'dead', 'died', 'dying',
                'bomb', 'bombs', 'bombing', 'bombed', 'explosion', 'explosions', 'exploded', 'terror', 'terrorist',
                'terrorism', 'shooting', 'shot', 'gun', 'guns', 'weapon', 'weapons', 'murder', 'murdered',
                'assassination', 'assassinated', 'riot', 'riots', 'protest', 'protests', 'blood', 'bloody',
                'casualties', 'casualty', 'injured', 'injury', 'injuries', 'wounded', 'destruction', 'destroyed',
                'destroy', 'destroys', 'damage', 'damaged', 'harm', 'harmed', 'crisis', 'crises', 'disaster',
                'disasters', 'tragedy', 'tragedies', 'accident', 'accidents', 'crash', 'crashes', 'crashed',
                'fire', 'fires', 'burning', 'burned', 'burnt', 'hate', 'hatred', 'hostile', 'hostility'
            ],
            # Hindi (Devanagari script) - Common negative words
            'devanagari': [
                'युद्ध', 'हिंसा', 'हत्या', 'मृत्यु', 'मौत', 'आतंक', 'आतंकवाद', 'हमला', 'हमले',
                'नष्ट', 'तबाही', 'दुर्घटना', 'दुर्घटनाएं', 'खून', 'खूनी', 'हताहत', 'घायल',
                'विनाश', 'नुकसान', 'क्षति', 'संकट', 'आपदा', 'त्रासदी', 'दुर्घटना', 'दुर्घटनाएं',
                'आग', 'जलना', 'जला', 'नफरत', 'शत्रुता', 'शत्रुतापूर्ण'
            ],
            # Bengali
            'bengali': [
                'যুদ্ধ', 'হিংসা', 'হত্যা', 'মৃত্যু', 'মৃত্যু', 'সন্ত্রাস', 'সন্ত্রাসবাদ', 'আক্রমণ',
                'ধ্বংস', 'বিপর্যয়', 'দুর্ঘটনা', 'রক্ত', 'রক্তাক্ত', 'হতাহত', 'আহত', 'ক্ষতি'
            ],
            # Tamil
            'tamil': [
                'போர்', 'வன்முறை', 'கொலை', 'மரணம்', 'பயங்கரவாதம்', 'தாக்குதல்', 'அழிவு',
                'விபத்து', 'இரத்தம்', 'காயம்', 'சேதம்', 'நெருக்கடி', 'விபத்து'
            ],
            # Telugu
            'telugu': [
                'యుద్ధం', 'హింస', 'హత్య', 'మరణం', 'భయోత్పాతం', 'దాడి', 'వినాశనం',
                'ప్రమాదం', 'రక్తం', 'గాయం', 'నష్టం', 'సంక్షోభం'
            ],
            # Gujarati
            'gujarati': [
                'યુદ્ધ', 'હિંસા', 'હત્યા', 'મૃત્યુ', 'આતંક', 'આતંકવાદ', 'હુમલો',
                'નાશ', 'તબાહી', 'દુર્ઘટના', 'રક્ત', 'ઘાયલ', 'નુકસાન'
            ],
            # Kannada
            'kannada': [
                'ಯುದ್ಧ', 'ಹಿಂಸೆ', 'ಕೊಲೆ', 'ಮರಣ', 'ಭಯೋತ್ಪಾದನೆ', 'ದಾಳಿ', 'ವಿನಾಶ',
                'ಅಪಘಾತ', 'ರಕ್ತ', 'ಗಾಯ', 'ನಷ್ಟ', 'ಸಂಕಷ್ಟ'
            ],
            # Malayalam
            'malayalam': [
                'യുദ്ധം', 'ഹിംസ', 'കൊല', 'മരണം', 'ഭീകരത', 'ആക്രമണം', 'വിനാശം',
                'അപകടം', 'രക്തം', 'ഗായം', 'നഷ്ടം', 'സംക്ഷോഭം'
            ],
            # Punjabi (Gurmukhi)
            'gurmukhi': [
                'ਯੁੱਧ', 'ਹਿੰਸਾ', 'ਹੱਤਿਆ', 'ਮੌਤ', 'ਆਤੰਕ', 'ਹਮਲਾ', 'ਨਾਸ਼',
                'ਤਬਾਹੀ', 'ਦੁਰਘਟਨਾ', 'ਖੂਨ', 'ਘਾਇਲ', 'ਨੁਕਸਾਨ'
            ],
            # Urdu (Arabic script) - Common negative words
            'arabic': [
                'جنگ', 'تشدد', 'قتل', 'موت', 'دہشت', 'دہشت گردی', 'حملہ', 'تباہی',
                'حادثہ', 'خون', 'زخمی', 'نقصان', 'بحران'
            ],
            # Marathi (Devanagari - same script as Hindi, different words)
            'marathi': [
                'युद्ध', 'हिंसा', 'हत्या', 'मृत्यू', 'दहशत', 'हल्ला', 'नाश',
                'तबाही', 'अपघात', 'रक्त', 'जखमी', 'नुकसान'
            ]
        }
        
        def detect_script(text: str) -> str:
            """Detect the primary script used in text."""
            script_counts = {
                'latin': 0,
                'devanagari': 0,
                'bengali': 0,
                'tamil': 0,
                'telugu': 0,
                'gujarati': 0,
                'kannada': 0,
                'malayalam': 0,
                'gurmukhi': 0,
                'arabic': 0
            }
            
            for char in text:
                code = ord(char)
                if '\u0000' <= char <= '\u007F':  # ASCII/Latin
                    script_counts['latin'] += 1
                elif '\u0900' <= char <= '\u097F':  # Devanagari
                    script_counts['devanagari'] += 1
                elif '\u0980' <= char <= '\u09FF':  # Bengali
                    script_counts['bengali'] += 1
                elif '\u0B80' <= char <= '\u0BFF':  # Tamil
                    script_counts['tamil'] += 1
                elif '\u0C00' <= char <= '\u0C7F':  # Telugu
                    script_counts['telugu'] += 1
                elif '\u0A80' <= char <= '\u0AFF':  # Gujarati
                    script_counts['gujarati'] += 1
                elif '\u0C80' <= char <= '\u0CFF':  # Kannada
                    script_counts['kannada'] += 1
                elif '\u0D00' <= char <= '\u0D7F':  # Malayalam
                    script_counts['malayalam'] += 1
                elif '\u0A00' <= char <= '\u0A7F':  # Gurmukhi
                    script_counts['gurmukhi'] += 1
                elif '\u0600' <= char <= '\u06FF':  # Arabic (Urdu)
                    script_counts['arabic'] += 1
            
            # Return script with highest count
            detected_script = max(script_counts.items(), key=lambda x: x[1])[0]
            return detected_script if script_counts[detected_script] > 0 else 'latin'
        
        # Detect primary script
        primary_script = detect_script(text)
        logger.info(f"🌐 Detected script: {primary_script}")
        
        # Get negative keywords for detected script + always include English (common in mixed content)
        keywords_to_check = set(negative_keywords.get(primary_script, []))
        keywords_to_check.update(negative_keywords['latin'])  # Always check English too
        
        # Split text into sentences (language-agnostic sentence splitting)
        # Works for: . ! ? । (Devanagari) | (Bengali) | (Tamil) | (Telugu) | (Gujarati) | (Kannada) | (Malayalam) | (Gurmukhi)
        sentence_endings = r'[.!?।।|॥]\s+'
        sentences = re.split(sentence_endings, text)
        
        filtered_sentences = []
        filtered_count = 0
        
        for sentence in sentences:
            sentence_stripped = sentence.strip()
            if not sentence_stripped or len(sentence_stripped) < 10:
                continue
            
            sentence_lower = sentence_stripped.lower()
            
            # Check if sentence contains any negative keywords
            contains_negative = any(
                keyword.lower() in sentence_lower 
                for keyword in keywords_to_check 
                if len(keyword) > 2  # Skip very short keywords to avoid false positives
            )
            
            if not contains_negative:
                filtered_sentences.append(sentence_stripped)
            else:
                filtered_count += 1
                logger.debug(f"🚫 Filtered negative sentence: {sentence_stripped[:80]}...")
        
        # Join filtered sentences
        filtered_text = '. '.join(filtered_sentences)
        
        # Safety check: If too much content was filtered (>70%), keep original (might be false positive)
        filter_ratio = len(filtered_text) / len(text) if len(text) > 0 else 1.0
        if filter_ratio < 0.3:  # Less than 30% remaining
            logger.warning(f"⚠️ Too much content filtered ({len(filtered_text)}/{len(text)} chars, {filter_ratio*100:.1f}%), keeping original to avoid false positives")
            return text
        
        if filtered_count > 0:
            logger.info(f"✅ Filtered {filtered_count} negative sentences: {len(text)} → {len(filtered_text)} chars ({filter_ratio*100:.1f}% kept)")
        else:
            logger.debug(f"✅ No negative content detected, keeping original text")
        
        return filtered_text if filtered_text else text

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
        
        # Use English for category detection (more reliable for JSON parsing)
        # But we'll generate content in the target language
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
        # CRITICAL: image_prompt must ALWAYS be in English for DALL-E, even if story content is in another language
        if content_language == "Hindi":
            language_clause = (
                "Write slide titles and summaries in Hindi (Devanagari script). "
                "IMPORTANT: image_prompt field MUST be in ENGLISH ONLY for image generation, even though other fields are in Hindi."
            )
        else:
            language_clause = (
                "Write all slide titles and prompts in English, even if the article text is in another language. "
                "IMPORTANT: image_prompt field MUST be in ENGLISH ONLY for image generation."
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
- Slide titles and summaries must be written in {content_language}.
- image_prompt field MUST ALWAYS be in English (for DALL-E image generation).

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
        
        # Map language names to script information for storytitle
        script_map_title = {
            "Hindi": "Devanagari script (हिंदी)",
            "Marathi": "Devanagari script (मराठी)",
            "Gujarati": "Gujarati script (ગુજરાતી)",
            "Tamil": "Tamil script (தமிழ்)",
            "Telugu": "Telugu script (తెలుగు)",
            "Kannada": "Kannada script (ಕನ್ನಡ)",
            "Bengali": "Bengali script (বাংলা)",
            "Punjabi": "Gurmukhi script (ਪੰਜਾਬੀ)",
            "Urdu": "Urdu script (اردو)",
            "Odia": "Odia script (ଓଡ଼ିଆ)",
            "Malayalam": "Malayalam script (മലയാളം)",
        }
        script_info_title = script_map_title.get(content_language, content_language)
        
        if content_language == "English":
            slide1_prompt = (
                f"Generate headline intro narration in English for: {headline}. "
                f"Maximum {slide1_limit} characters. Avoid greetings. Respond in English only, translating the source if necessary. "
                f"Do NOT use markdown formatting (no **, no *, no #). Use plain text only."
            )
        else:
            slide1_prompt = (
                f"Generate news headline narration in {content_language} for the story: {headline}. "
                f"Maximum {slide1_limit} characters. Avoid greetings. Respond in {content_language} language using {script_info_title} only. "
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
            # Ensure we always return a non-empty storytitle
            if not storytitle or not storytitle.strip():
                storytitle = headline[:slide1_limit] if headline else "Breaking News Story"
            return storytitle.strip()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Storytitle generation failed: %s, using fallback", e)
            # Always return a fallback - never empty
            return headline[:slide1_limit] if headline else "Breaking News Story"
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
        
        # Map language names to script information
        script_map = {
            "Hindi": "Devanagari script (हिंदी)",
            "Marathi": "Devanagari script (मराठी)",
            "Gujarati": "Gujarati script (ગુજરાતી)",
            "Tamil": "Tamil script (தமிழ்)",
            "Telugu": "Telugu script (తెలుగు)",
            "Kannada": "Kannada script (ಕನ್ನಡ)",
            "Bengali": "Bengali script (বাংলা)",
            "Punjabi": "Gurmukhi script (ਪੰਜਾਬੀ)",
            "Urdu": "Urdu script (اردو)",
            "Odia": "Odia script (ଓଡ଼ିଆ)",
            "Malayalam": "Malayalam script (മലയാളം)",
        }
        script_info = script_map.get(content_language, content_language)
        
        if content_language == "English":
            script_language = "English"
            language_requirement = "Deliver the narration strictly in English. Do not include words from other languages or transliteration."
        else:
            script_language = f"{content_language} (use {script_info})"
            language_requirement = f"Deliver the narration strictly in {content_language} language using {script_info}. Do not use English or transliteration."
        
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

