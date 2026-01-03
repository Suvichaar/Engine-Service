"""Detect explicit language requests from user input."""

import re
from typing import Optional, Tuple

# Language request patterns (case-insensitive)
# Maps language codes to patterns that detect explicit language requests
LANGUAGE_PATTERNS = {
    "hi": [
        r"\bin\s+hindi\b",
        r"\bin\s+हिंदी\b",
        r"हिंदी\s+में\b",
        r"hindi\s+mein\b",
        r"hindi\s+me\b",
        r"हिंदी\s+मैं\b",
        r"hindi\s+me\s+batao\b",
        r"hindi\s+me\s+likho\b",
    ],
    "en": [
        r"\bin\s+english\b",
        r"\bin\s+अंग्रेजी\b",
        r"english\s+mein\b",
        r"english\s+me\b",
        r"english\s+me\s+batao\b",
    ],
    "mr": [
        r"\bin\s+marathi\b",
        r"\bin\s+मराठी\b",
        r"marathi\s+mein\b",
        r"marathi\s+me\b",
        r"मराठी\s+मध्ये\b",
    ],
    "gu": [
        r"\bin\s+gujarati\b",
        r"\bin\s+ગુજરાતી\b",
        r"gujarati\s+mein\b",
        r"gujarati\s+me\b",
    ],
    "ta": [
        r"\bin\s+tamil\b",
        r"\bin\s+தமிழ்\b",
        r"tamil\s+mein\b",
        r"tamil\s+me\b",
    ],
    "te": [
        r"\bin\s+telugu\b",
        r"\bin\s+తెలుగు\b",
        r"telugu\s+mein\b",
        r"telugu\s+me\b",
    ],
    "kn": [
        r"\bin\s+kannada\b",
        r"\bin\s+ಕನ್ನಡ\b",
        r"kannada\s+mein\b",
        r"kannada\s+me\b",
    ],
    "bn": [
        r"\bin\s+bengali\b",
        r"\bin\s+বাংলা\b",
        r"bengali\s+mein\b",
        r"bengali\s+me\b",
    ],
    "pa": [
        r"\bin\s+punjabi\b",
        r"\bin\s+ਪੰਜਾਬੀ\b",
        r"punjabi\s+mein\b",
        r"punjabi\s+me\b",
    ],
    "ur": [
        r"\bin\s+urdu\b",
        r"\bin\s+اردو\b",
        r"urdu\s+mein\b",
        r"urdu\s+me\b",
    ],
    "or": [
        r"\bin\s+odia\b",
        r"\bin\s+ଓଡ଼ିଆ\b",
        r"odia\s+mein\b",
        r"odia\s+me\b",
    ],
    "ml": [
        r"\bin\s+malayalam\b",
        r"\bin\s+മലയാളം\b",
        r"malayalam\s+mein\b",
        r"malayalam\s+me\b",
    ],
}


def detect_language_request(text: str) -> Optional[str]:
    """
    Detect explicit language request from user input.
    
    Examples:
        "tell me about lord shiva in hindi" -> "hi"
        "हिंदी में बताओ" -> "hi"
        "explain in english" -> "en"
        "tell me about marathi in marathi" -> "mr"
    
    Args:
        text: User input text to analyze
        
    Returns:
        Language code (ISO 639-1) if explicit request found, None otherwise.
    """
    if not text or not text.strip():
        return None
    
    text_lower = text.lower().strip()
    
    # Check each language pattern
    for lang_code, patterns in LANGUAGE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return lang_code
    
    return None


def extract_language_and_content(text: str) -> Tuple[Optional[str], str]:
    """
    Extract language request and clean content.
    
    Args:
        text: User input text
        
    Returns:
        Tuple of (detected_language_code, cleaned_text)
        If no language request found, returns (None, original_text)
    """
    detected_lang = detect_language_request(text)
    
    # Remove language request phrases from text for cleaner content
    cleaned_text = text
    if detected_lang:
        for pattern in LANGUAGE_PATTERNS.get(detected_lang, []):
            cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE)
        cleaned_text = cleaned_text.strip()
    
    return detected_lang, cleaned_text

