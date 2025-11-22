"""Smart input detection service for ChatGPT-style unified input."""

from __future__ import annotations

import re
from typing import Optional, Tuple
from urllib.parse import urlparse


class SmartInputDetector:
    """Detect input type from unified user input (ChatGPT-style)."""

    URL_PATTERNS = [
        r'https?://[^\s]+',  # http:// or https://
        r'www\.[^\s]+',      # www.example.com
        r'[a-zA-Z0-9-]+\.[a-zA-Z]{2,}[^\s]*',  # example.com/article
    ]

    def detect(self, user_input: str) -> Tuple[str, dict]:
        """
        Detect input type and extract data.

        Returns:
            Tuple of (input_type, extracted_data)
            Types: 'url', 'text', 'file', 'mixed'
            Data: dict with 'urls', 'text', 'file_path' keys
        """
        if not user_input or not user_input.strip():
            return 'text', {'text': ''}

        user_input = user_input.strip()

        # 1. Check for URLs
        urls = self._extract_urls(user_input)
        if urls:
            # Remove URLs from text
            remaining_text = self._remove_urls(user_input)
            if remaining_text.strip():
                return 'mixed', {
                    'urls': urls,
                    'text': remaining_text.strip()
                }
            return 'url', {'urls': urls}

        # 2. Check for file references
        if self._is_file_reference(user_input):
            return 'file', {'file_path': user_input}

        # 3. Plain text
        return 'text', {'text': user_input}

    def _extract_urls(self, text: str) -> list[str]:
        """Extract all URLs from text."""
        urls = []
        for pattern in self.URL_PATTERNS:
            matches = re.findall(pattern, text)
            urls.extend(matches)

        # Validate and normalize URLs
        validated = []
        for url in urls:
            # Normalize URLs without protocol
            if not url.startswith(('http://', 'https://')):
                if url.startswith('www.'):
                    url = 'https://' + url
                elif '.' in url and not url.startswith('file://'):
                    # Try to validate as domain
                    try:
                        parsed = urlparse('https://' + url)
                        if parsed.netloc:
                            url = 'https://' + url
                    except:
                        continue

            # Validate URL
            try:
                parsed = urlparse(url)
                if parsed.netloc and parsed.scheme in ('http', 'https'):
                    validated.append(url)
            except:
                continue

        return list(set(validated))  # Remove duplicates

    def _remove_urls(self, text: str) -> str:
        """Remove URLs from text, keep remaining content."""
        for pattern in self.URL_PATTERNS:
            text = re.sub(pattern, '', text)
        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _is_file_reference(self, text: str) -> bool:
        """Check if input is a file path/reference."""
        file_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.docx', '.txt', '.doc']
        text_lower = text.lower()
        
        return (
            (text.startswith(('file://', 's3://', 'http://', 'https://')) and
             any(text_lower.endswith(ext) for ext in file_extensions)) or
            (any(text_lower.endswith(ext) for ext in file_extensions) and
             ('/' in text or '\\' in text))
        )

