"""Narrative model client implementation for the news backend."""

from __future__ import annotations

import json
import logging
import re
import textwrap
from typing import Iterable, Optional, Protocol

from app.domain.dto import DocInsights, Mode, NarrativeResponse, NewsNarrative, RenderedPrompt, SemanticChunk, SlideBlock, SlideDeck
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


__all__ = ["NewsModelClient", "LanguageModel"]
