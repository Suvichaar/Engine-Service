"""AI Image Prompt Generation Utilities.

This module contains all prompt generation logic for AI image providers.
Separated for easy management and editing of prompts.
"""

import re
import random
from typing import Optional


# ============================================================================
# Safe Prompt Templates
# ============================================================================

SIMPLE_SAFE_PROMPTS = [
    "abstract geometric shapes in blue and white",
    "modern minimalist design with soft colors",
    "professional business illustration",
    "clean abstract composition with warm tones",
    "contemporary design elements in neutral colors",
    "simple geometric patterns in pastel colors",
    "minimalist abstract art with professional aesthetic",
    "modern design with clean lines and soft lighting",
    "abstract composition with vibrant but safe colors",
    "professional graphic design with geometric elements",
    "contemporary illustration with positive energy",
    "clean modern aesthetic with balanced composition",
    "abstract visual design with professional quality",
    "minimalist art with contemporary style",
    "simple geometric design with harmonious colors"
]

VARIATION_MODIFIERS = [
    "with blue color scheme",
    "with warm lighting",
    "with modern design elements",
    "with professional atmosphere",
    "with clean minimalist style",
    "with contemporary aesthetics",
    "with vibrant colors",
    "with soft natural lighting"
]

SLIDE_VARIATIONS = [
    "with blue and white color scheme",
    "with warm orange and yellow tones",
    "with green and teal accents",
    "with purple and blue gradient",
    "with red and orange highlights",
    "with cool gray and blue palette",
    "with vibrant multicolor design",
    "with soft pastel colors",
    "with bold primary colors",
    "with elegant monochrome style"
]

# Positive keywords for extraction
POSITIVE_KEYWORDS = [
    "technology", "innovation", "development", "progress", "growth", "success", 
    "achievement", "discovery", "research", "science", "education", "learning", 
    "knowledge", "information", "news", "media", "journalism", "reporting", 
    "story", "article", "update", "announcement", "event", "meeting", 
    "conference", "launch", "release", "product", "service", "business", 
    "economy", "market", "trade", "investment", "finance", "health", 
    "wellness", "sports", "entertainment", "culture", "art", "music", 
    "travel", "food", "nature", "environment", "city", "country", 
    "world", "global", "local", "community", "people", "team", 
    "organization", "company", "industry", "project", "program", 
    "initiative", "improvement", "advancement", "breakthrough", 
    "celebration", "award", "recognition", "support", "cooperation", 
    "collaboration", "partnership", "agreement", "peace", "harmony"
]

# Safe terms for content-related prompts
SAFE_TERMS = [
    "news", "story", "article", "report", "update", "information", 
    "education", "learning", "knowledge", "science", "technology",
    "business", "economy", "sports", "culture", "art", "history",
    "health", "environment", "innovation", "development", "progress"
]

# Negative patterns to remove from prompts
NEGATIVE_PATTERNS = [
    r'\b(violence|attack|death|kill|murder|crime|war|conflict|disaster|tragedy|accident|injury|harm|danger|threat|fear|panic|chaos|destruction|damage|loss|failure|error|mistake|problem|issue|complaint|protest|riot|strike|dispute|scandal|corruption|fraud|theft|robbery|assault|abuse|exploitation|discrimination|hate|anger|rage|fury|outrage|controversy|criticism|blame|fault|guilt|shame|embarrassment|humiliation|insult|offense|disrespect|disgrace|shameful|disgusting|horrible|terrible|awful|bad|evil|wicked|sinful|immoral|unethical|illegal|unlawful|criminal|violent|aggressive|hostile|dangerous|harmful|toxic|poisonous|deadly|fatal|lethal|destructive|damaging|negative|pessimistic|depressing|sad|unhappy|miserable|hopeless|desperate|despair|grief|sorrow|pain|suffering|agony|torment|torture|oppression|injustice|inequality|prejudice|bias|racism|sexism|homophobia|xenophobia|hatred|intolerance|bigotry|extremism|terrorism|radicalism|fanaticism|fundamentalism|defeating|defeat|striking|battlefield|battle|fighting|fight|combat|weapon|weapons|bow|arrow|arrows|sword|swords|spear|spears|dagger|knife|blade|blades|shooting|aiming|firing|attacking|hitting|hit|punching|punch|kicking|kick|throwing|throw|hurting|hurt|wounding|wound|injuring|injure|killing|killed|murdering|murdered|destroying|destroyed|damaging|damaged|breaking|broken|crushing|crushed|exploding|exploded|burning|burned|fire|flames|smoke|blood|bloody|gore|gory|action pose|action stance|combat pose|fighting stance|epic battle|war scene|battle scene|conflict scene|violence scene|being struck|falling backward|multiple faces|fierce expressions|dark tones)\b',
]


# ============================================================================
# Prompt Generation Functions
# ============================================================================

def extract_positive_keywords(text: str) -> list[str]:
    """Extract only positive, safe keywords from text.
    
    Args:
        text: Input text to extract keywords from
        
    Returns:
        List of positive keywords found (max 5)
    """
    if not text:
        return []
    
    # Extract words that match positive keywords
    words = re.findall(r'\b\w+\b', text.lower())
    positive_words = [word for word in words if word in POSITIVE_KEYWORDS]
    
    # Remove duplicates and limit to top 5
    unique_words = list(dict.fromkeys(positive_words))[:5]
    
    return unique_words


def sanitize_prompt(text: str, fallback_fn=None) -> str:
    """Sanitize prompt by extracting only positive keywords and concepts.
    
    Args:
        text: Input text to sanitize
        fallback_fn: Optional function to call if sanitization fails
        
    Returns:
        Sanitized prompt string
    """
    if not text:
        return "professional news illustration"
    
    # Extract positive keywords first
    positive_keywords = extract_positive_keywords(text)
    
    # Remove ALL negative/problematic words and phrases
    sanitized = text
    for pattern in NEGATIVE_PATTERNS:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    # Clean up extra spaces
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    # If we have positive keywords, use them
    if positive_keywords:
        safe_prompt = f"{', '.join(positive_keywords)}, professional news illustration, positive, informative, clean, modern"
        return safe_prompt
    
    # If too much was removed or no positive keywords, use generic safe prompt
    if len(sanitized) < len(text) * 0.3 or not sanitized:
        if fallback_fn:
            return fallback_fn()
        return generate_safe_news_prompt()
    
    # Use sanitized text with safe modifiers
    return f"{sanitized[:100]}, professional news illustration, positive, informative, clean, modern"


def generate_safe_news_prompt(topic: Optional[str] = None, slide_index: Optional[int] = None) -> str:
    """Generate a very simple, safe, positive news-related image prompt.
    
    Args:
        topic: Optional topic to incorporate (will be sanitized)
        slide_index: Optional slide index to ensure variation
        
    Returns:
        Safe prompt string
    """
    # Use slide_index to select different prompts for different slides
    # This ensures each slide gets a different image even with safe prompts
    if slide_index is not None:
        prompt_idx = slide_index % len(SIMPLE_SAFE_PROMPTS)
        base_prompt = SIMPLE_SAFE_PROMPTS[prompt_idx]
    else:
        base_prompt = random.choice(SIMPLE_SAFE_PROMPTS)
    
    # Add variation based on slide position to ensure different images
    if slide_index is not None:
        variation = VARIATION_MODIFIERS[slide_index % len(VARIATION_MODIFIERS)]
    else:
        variation = random.choice(VARIATION_MODIFIERS)
    
    # Don't add topic if it might cause issues - keep it very simple
    return f"{base_prompt}, {variation}, professional, clean, modern, positive, informative, high quality"


def generate_content_related_safe_prompt(
    topic: Optional[str] = None, 
    original_prompt: Optional[str] = None, 
    simpler: bool = False
) -> str:
    """Generate a safe, positive prompt that's still related to the original content.
    
    Args:
        topic: Main topic/keyword from original content (will be sanitized)
        original_prompt: Full original prompt for context
        simpler: If True, use even simpler version
        
    Returns:
        Safe, content-related prompt string
    """
    # Extract safe keywords from topic or original prompt
    safe_keywords = []
    if topic:
        # Remove problematic words and keep safe ones
        topic_lower = topic.lower()
        for term in SAFE_TERMS:
            if term in topic_lower:
                safe_keywords.append(term)
                break
    
    # If no safe keywords found, extract first safe word from original prompt
    if not safe_keywords and original_prompt:
        words = re.findall(r'\b[a-zA-Z]{4,}\b', original_prompt.lower())
        for word in words[:3]:  # Check first 3 words
            if word in SAFE_TERMS:
                safe_keywords.append(word)
                break
    
    # Build safe prompt that's still content-related (avoid negative terms)
    if simpler:
        # Very simple but still related
        if safe_keywords:
            base = f"professional {safe_keywords[0]} themed illustration, clean, modern, uplifting"
        else:
            base = "professional news themed illustration, clean, modern, uplifting"
    else:
        # More detailed but safe
        if safe_keywords:
            base = f"professional {safe_keywords[0]} themed editorial illustration, informative, uplifting, clean design, modern aesthetic, warm colors"
        else:
            base = "professional news themed editorial illustration, informative, uplifting, clean design, modern aesthetic"
    
    # Add safe modifiers (keep positive phrasing; avoid 'no ...' patterns)
    modifiers = "family-friendly, calm, optimistic mood, professional quality, clean composition"
    return f"{base}, {modifiers}"


def generate_news_slide_prompt(
    slide_text: str, 
    slide_index: int, 
    is_cover: bool = False, 
    is_cta: bool = False,
    article_content: Optional[str] = None
) -> str:
    """Generate prompt for a news mode slide.
    
    Args:
        slide_text: Text content of the slide
        slide_index: Index of the slide (0-based)
        is_cover: Whether this is the cover slide
        is_cta: Whether this is the CTA slide
        article_content: Optional full article content for better context
        
    Returns:
        Formatted prompt string
    """
    # If article content is available, use it to generate content-related prompts
    if article_content:
        # Combine slide text with article content for better context
        # Use first 800 chars of article + slide text to get good context while keeping processing fast
        # This ensures we capture key concepts from the article without excessive processing time
        article_snippet = article_content[:800] if len(article_content) > 800 else article_content
        combined_content = f"{slide_text}. {article_snippet}"
        
        # Use editorial style prompt which extracts key concepts from article
        # This ensures images are relevant to the actual article content
        try:
            prompt = generate_editorial_style_prompt(
                input_text=combined_content,
                topic_title=slide_text[:50] if slide_text else None,
                content_type="news",
            )
            
            # Add slide-specific modifiers
            variation = SLIDE_VARIATIONS[slide_index % len(SLIDE_VARIATIONS)]
            if is_cover:
                return f"{prompt}, professional news cover illustration, {variation}"
            elif is_cta:
                return f"{prompt}, professional news CTA illustration, {variation}, call-to-action"
            else:
                return f"{prompt}, professional news illustration for slide {slide_index + 1}, {variation}"
        except Exception:
            # Fallback to simple prompt if editorial style fails
            pass
    
    # Fallback: Use simple sanitized prompt (original behavior)
    safe_text = sanitize_prompt(slide_text, fallback_fn=lambda: generate_safe_news_prompt())
    
    # Get slide-specific variation
    variation = SLIDE_VARIATIONS[slide_index % len(SLIDE_VARIATIONS)]
    
    if is_cover:
        return f"{safe_text}, professional news cover illustration, {variation}, positive, informative, clean, modern, unique design"
    elif is_cta:
        return f"{safe_text}, professional news CTA illustration, {variation}, positive, informative, clean, modern, call-to-action, unique design"
    else:
        return f"{safe_text}, professional news illustration for slide {slide_index + 1}, {variation}, positive, informative, clean, modern, unique design"


def generate_curious_slide_prompt(slide_text: str, is_cover: bool = False) -> str:
    """Generate prompt for a curious mode slide.
    
    Args:
        slide_text: Text content of the slide
        is_cover: Whether this is the cover slide
        
    Returns:
        Formatted prompt string
    """
    if is_cover:
        return f"Cover for educational story: {slide_text or 'Learning'} — flat vector illustration, clean geometric shapes, smooth gradients, harmonious palette; inclusive, family-friendly; no text/logos/watermarks; no real-person likeness."
    else:
        return f"{slide_text or 'Visual concept'} — flat vector illustration, clean geometric shapes, smooth gradients, harmonious palette; inclusive, family-friendly; no text/logos/watermarks; no real-person likeness."


def generate_cta_prompt(mode: str = "curious") -> str:
    """Generate prompt for CTA slide.
    
    Args:
        mode: Story mode (curious or news)
        
    Returns:
        CTA prompt string
    """
    if mode == "curious":
        return "Educational story call-to-action slide — flat vector illustration, clean geometric shapes, smooth gradients, harmonious palette, positive learning theme, inclusive, family-friendly; no text/logos/watermarks; no real-person likeness"
    else:
        return "Professional news call-to-action illustration, clean, modern, positive, informative, engaging"


def sanitize_revised_prompt(revised_prompt: str, max_length: int = 200) -> str:
    """Sanitize and shorten Azure's revised_prompt for retry.
    
    Args:
        revised_prompt: The revised prompt from Azure error response
        max_length: Maximum length for the sanitized prompt
        
    Returns:
        Sanitized and shortened prompt
    """
    # Step 1: Convert negative words to positive FIRST
    sanitized = convert_negative_to_positive_imagery(revised_prompt)
    
    # Step 2: Remove ALL violence-related phrases (more aggressive)
    violence_phrases = [
        "defeating", "striking", "battlefield", "battle", "fighting", "combat",
        "bow and arrow", "action pose", "epic battle", "war scene", "conflict scene",
        "being struck", "falling backward", "multiple faces", "fierce expressions",
        "dark tones", "weapons", "combat pose", "fighting stance", "struck by",
        "defeating ravana", "lord rama defeating", "ravana being struck"
    ]
    for phrase in violence_phrases:
        sanitized = re.sub(re.escape(phrase), '', sanitized, flags=re.IGNORECASE)
    
    # Step 3: Remove any remaining problematic patterns
    for pattern in NEGATIVE_PATTERNS:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    # Step 4: Replace mythological violence with peaceful concepts
    sanitized = re.sub(r'\b(defeating|striking|battlefield|battle)\b', 'epic moment', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'\b(bow|arrow|arrows|weapon|weapons)\b', 'divine symbol', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'\b(action pose|combat pose|fighting stance)\b', 'heroic stance', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'\b(epic battle|war scene|battle scene)\b', 'epic scene', sanitized, flags=re.IGNORECASE)
    
    # Step 5: Clean up extra spaces
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    # Step 6: If still too violent, use generic safe prompt
    violence_keywords = ["violence", "attack", "strike", "defeat", "battle", "combat", "weapon", "fighting", "war"]
    if any(word in sanitized.lower() for word in violence_keywords):
        return "peaceful mythological illustration, divine hero in heroic stance, sacred ground, bright colors, clean lines, family-friendly"
    
    # Step 7: Truncate if too long
    if len(sanitized) > max_length:
        truncated = sanitized[:max_length]
        last_comma = truncated.rfind(',')
        last_period = truncated.rfind('.')
        last_break = max(last_comma, last_period)
        if last_break > max_length * 0.7:
            sanitized = truncated[:last_break + 1]
        else:
            sanitized = truncated
    
    return sanitized


def convert_negative_to_positive_imagery(text: str) -> str:
    """Convert negative concepts in text to positive visual representations.
    
    Args:
        text: Input text that may contain negative concepts
    
    Returns:
        Text with negative concepts converted to positive visual equivalents
    """
    # Mapping of negative concepts to positive visual representations
    conversion_map = {
        # Problems → Solutions
        "problem": "solution approach",
        "issue": "resolution process",
        "challenge": "overcoming obstacle",
        "difficulty": "learning journey",
        "obstacle": "pathway forward",
        
        # Conflicts → Harmony
        "conflict": "dialogue and understanding",
        "dispute": "collaborative discussion",
        "disagreement": "diverse perspectives",
        "tension": "balanced approach",
        
        # Crises → Response
        "crisis": "effective response",
        "emergency": "preparedness and action",
        "disaster": "recovery and resilience",
        "catastrophe": "rebuilding efforts",
        
        # Failures → Growth
        "failure": "learning opportunity",
        "mistake": "improvement process",
        "error": "correction and refinement",
        "defeat": "resilience and comeback",
        
        # Loss → Transformation
        "loss": "transformation and renewal",
        "decline": "renewal and growth",
        "reduction": "optimization",
        "decrease": "efficiency improvement",
        
        # Threats → Preparedness
        "threat": "preparedness and protection",
        "danger": "safety measures",
        "risk": "careful planning",
        "hazard": "preventive action",
        
        # Negative emotions → Positive outcomes
        "fear": "courage and action",
        "worry": "preparation and care",
        "anxiety": "mindfulness and calm",
        "stress": "balance and resilience",
        
        # Criticism → Constructive feedback
        "slam": "constructive analysis",
        "critic": "analyst perspective",
        "critics": "analyst perspectives",
        "criticism": "constructive feedback",
        "criticize": "analyze and improve",
        "blame": "accountability and improvement",
        "attack": "constructive dialogue",
    }
    
    # Convert text
    converted = text.lower()
    for negative, positive in conversion_map.items():
        # Replace whole words only
        pattern = r'\b' + re.escape(negative) + r'\b'
        converted = re.sub(pattern, positive, converted, flags=re.IGNORECASE)
    
    return converted


def generate_editorial_style_prompt(
    input_text: str,
    topic_title: Optional[str] = None,
    content_type: str = "general",  # "education", "news", "general", etc.
    mood_adjectives: Optional[str] = None,
    color_palette: Optional[str] = None,
) -> str:
    """Generate a serious, intellectual editorial-style image prompt.
    
    This function:
    - Extracts key concepts from input text
    - Converts negative content to positive representation
    - Generates comprehensive visual descriptions
    - Works for any content type (education, news, general)
    
    Args:
        input_text: The content to visualize
        topic_title: Optional title for the topic (will be auto-extracted if not provided)
        content_type: Type of content ("education", "news", "general")
        mood_adjectives: Optional mood descriptors (auto-generated if not provided)
        color_palette: Optional color palette (auto-selected if not provided)
    
    Returns:
        Formatted prompt string ready for image generation
    """
    # Step 1: Convert negative to positive and sanitize
    positive_text = convert_negative_to_positive_imagery(input_text)
    sanitized_text = sanitize_prompt(positive_text, fallback_fn=lambda: "informative content")
    
    # Step 2: Extract topic title if not provided
    # IMPORTANT: Use positive_text (not input_text) to avoid negative words in title
    if not topic_title:
        # Extract first meaningful phrase or sentence from POSITIVE text
        sentences = re.split(r'[.!?]\s+', positive_text)
        if sentences:
            topic_title = sentences[0].strip()[:50]
            # Clean up title and ensure it's positive
            topic_title = re.sub(r'[^\w\s-]', '', topic_title)
            # Convert any remaining negative words in title
            topic_title = convert_negative_to_positive_imagery(topic_title)
            if not topic_title:
                topic_title = "Key Concept"
        else:
            topic_title = "Key Concept"
    else:
        # If topic_title provided, convert it to positive as well
        topic_title = convert_negative_to_positive_imagery(topic_title)
    
    # Step 3: Generate positive visual description
    # Extract key concepts and convert to positive imagery
    words = re.findall(r'\b[a-zA-Z]{4,}\b', sanitized_text.lower())
    
    # Map negative concepts to positive visual representations
    positive_mappings = {
        "problem": "solution approach",
        "challenge": "overcoming obstacle",
        "difficulty": "learning process",
        "conflict": "resolution discussion",
        "crisis": "response and recovery",
        "failure": "growth opportunity",
        "loss": "transformation",
        "decline": "renewal",
        "threat": "preparedness",
        "risk": "careful planning"
    }
    
    visual_concepts = []
    for word in words[:10]:  # Take top 10 meaningful words
        if word in positive_mappings:
            visual_concepts.append(positive_mappings[word])
        elif word in SAFE_TERMS:
            visual_concepts.append(word)
    
    # Build comprehensive visual description
    if visual_concepts:
        visual_description = f"depicting {', '.join(visual_concepts[:5])}, with elements representing knowledge, understanding, and positive progression"
    else:
        visual_description = "depicting key concepts and ideas in an informative, educational manner"
    
    # Step 4: Auto-generate mood adjectives if not provided
    if not mood_adjectives:
        if content_type == "education":
            mood_adjectives = "intellectual, clear, inspiring, scholarly, accessible"
        elif content_type == "news":
            mood_adjectives = "informative, professional, balanced, engaging, credible"
        else:
            mood_adjectives = "professional, clear, engaging, informative, positive"
    
    # Step 5: Auto-select color palette if not provided
    if not color_palette:
        color_palettes = [
            "muted blue and gray watercolor wash",
            "soft earth tones with warm sepia accents",
            "gentle teal and cream watercolor wash",
            "subtle indigo and white watercolor wash",
            "warm amber and soft gray watercolor wash"
        ]
        color_palette = random.choice(color_palettes)
    
    # Step 6: Build the final prompt
    topic_title_upper = topic_title.upper()[:40]  # Limit title length
    
    prompt = (
        f"A serious, intellectual editorial illustration in distinctive ink line art and "
        f"{color_palette} style. The concept visualizes {topic_title}. "
        f"{visual_description}, with detailed elements representing the core ideas and concepts. "
        f"The mood is {mood_adjectives}. Isolated on a pure, clean white background. "
        f"The specific concept title '{topic_title_upper}' is rendered in small, elegant, "
        f"understated ink typography in a single horizontal line integrated into the upper left corner. "
        f"Professional quality, family-friendly, no negative imagery, positive representation only. "
        f"--ar 9:16"
    )
    
    return prompt


def generate_sequential_topics_prompt(
    input_text: str,
    topic_number: int,
    total_topics: int = 8,
    content_type: str = "general"
) -> str:
    """Generate prompt for a specific sequential topic from input text.
    
    This breaks down input text into sequential topics and generates
    a prompt for a specific topic number.
    
    Args:
        input_text: Full input text to analyze
        topic_number: Which topic to generate (1-8)
        total_topics: Total number of topics to extract (default 8)
        content_type: Type of content ("education", "news", "general")
    
    Returns:
        Formatted prompt for the specified topic
    """
    # Split text into logical segments
    paragraphs = [p.strip() for p in re.split(r'\n\n+', input_text) if p.strip()]
    sentences = [s.strip() for s in re.split(r'[.!?]\s+', input_text) if s.strip()]
    
    # Calculate which segment corresponds to this topic
    if paragraphs:
        segments = paragraphs
    else:
        # Group sentences into segments
        sentences_per_segment = max(1, len(sentences) // total_topics)
        segments = []
        for i in range(0, len(sentences), sentences_per_segment):
            segments.append(' '.join(sentences[i:i+sentences_per_segment]))
    
    # Get the segment for this topic (1-indexed to 0-indexed)
    topic_idx = min(topic_number - 1, len(segments) - 1)
    topic_text = segments[topic_idx] if segments else input_text[:200]
    
    # Extract topic title from segment
    topic_title = topic_text.split('.')[0].strip()[:50]
    topic_title = re.sub(r'[^\w\s-]', '', topic_title)
    if not topic_title:
        topic_title = f"Topic {topic_number}"
    
    # Generate the prompt
    return generate_editorial_style_prompt(
        input_text=topic_text,
        topic_title=topic_title,
        content_type=content_type
    )

