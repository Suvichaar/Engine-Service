"""Test script for unified input (ChatGPT-style) and legacy format."""

import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_legacy_format():
    """Test old format (separate fields)."""
    print("\n" + "=" * 60)
    print("Test 1: Legacy Format (Separate Fields)")
    print("=" * 60)
    
    payload = {
        "mode": "news",
        "template_key": "test-news-1",
        "slide_count": 4,
        "category": "News",
        "text_prompt": "Breaking news: New technology breakthrough",
        "notes": "Latest developments in AI research",
        "urls": ["https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/"],
        "attachments": [],
        "prompt_keywords": ["technology", "AI", "innovation"],
        "image_source": "pexels",
        "voice_engine": "azure_basic"
    }
    
    print(f"\n[REQUEST] Legacy Format")
    print(f"   Mode: {payload['mode']}")
    print(f"   Template: {payload['template_key']}")
    print(f"   URLs: {payload['urls']}")
    print(f"   Text Prompt: {payload['text_prompt']}")
    
    try:
        response = requests.post(f"{BASE_URL}/stories", json=payload, timeout=300)
        response.raise_for_status()
        story = response.json()
        print(f"\n[SUCCESS] Story created: {story['id']}")
        return story
    except Exception as e:
        print(f"\n[ERROR] {e}")
        if hasattr(e, 'response') and e.response:
            print(f"   Status: {e.response.status_code}")
            print(f"   Response: {e.response.text[:500]}")
        return None

def test_unified_input_urls():
    """Test new format with URLs only."""
    print("\n" + "=" * 60)
    print("Test 2: Unified Input - URLs Only")
    print("=" * 60)
    
    payload = {
        "mode": "news",
        "template_key": "test-news-1",
        "slide_count": 4,
        "category": "News",
        "user_input": "https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/",
        "image_source": "pexels",
        "voice_engine": "azure_basic"
    }
    
    print(f"\n[REQUEST] Unified Input (URLs)")
    print(f"   Mode: {payload['mode']}")
    print(f"   Template: {payload['template_key']}")
    print(f"   User Input: {payload['user_input']}")
    
    try:
        response = requests.post(f"{BASE_URL}/stories", json=payload, timeout=300)
        response.raise_for_status()
        story = response.json()
        print(f"\n[SUCCESS] Story created: {story['id']}")
        return story
    except Exception as e:
        print(f"\n[ERROR] {e}")
        if hasattr(e, 'response') and e.response:
            print(f"   Status: {e.response.status_code}")
            print(f"   Response: {e.response.text[:500]}")
        return None

def test_unified_input_multiple_urls():
    """Test new format with multiple URLs."""
    print("\n" + "=" * 60)
    print("Test 3: Unified Input - Multiple URLs")
    print("=" * 60)
    
    payload = {
        "mode": "news",
        "template_key": "test-news-1",
        "slide_count": 4,
        "category": "News",
        "user_input": "https://example.com/article1 https://example.com/article2",
        "image_source": "pexels",
        "voice_engine": "azure_basic"
    }
    
    print(f"\n[REQUEST] Unified Input (Multiple URLs)")
    print(f"   User Input: {payload['user_input']}")
    
    try:
        response = requests.post(f"{BASE_URL}/stories", json=payload, timeout=300)
        response.raise_for_status()
        story = response.json()
        print(f"\n[SUCCESS] Story created: {story['id']}")
        return story
    except Exception as e:
        print(f"\n[ERROR] {e}")
        if hasattr(e, 'response') and e.response:
            print(f"   Status: {e.response.status_code}")
            print(f"   Response: {e.response.text[:500]}")
        return None

def test_unified_input_text():
    """Test new format with plain text."""
    print("\n" + "=" * 60)
    print("Test 4: Unified Input - Plain Text")
    print("=" * 60)
    
    payload = {
        "mode": "news",
        "template_key": "test-news-1",
        "slide_count": 4,
        "category": "News",
        "user_input": "Breaking news: New AI breakthrough in technology. Scientists have developed a revolutionary algorithm.",
        "image_source": "pexels",
        "voice_engine": "azure_basic"
    }
    
    print(f"\n[REQUEST] Unified Input (Text)")
    print(f"   User Input: {payload['user_input'][:80]}...")
    
    try:
        response = requests.post(f"{BASE_URL}/stories", json=payload, timeout=300)
        response.raise_for_status()
        story = response.json()
        print(f"\n[SUCCESS] Story created: {story['id']}")
        return story
    except Exception as e:
        print(f"\n[ERROR] {e}")
        if hasattr(e, 'response') and e.response:
            print(f"   Status: {e.response.status_code}")
            print(f"   Response: {e.response.text[:500]}")
        return None

def test_unified_input_mixed():
    """Test new format with URL + text (mixed)."""
    print("\n" + "=" * 60)
    print("Test 5: Unified Input - URL + Text (Mixed)")
    print("=" * 60)
    
    payload = {
        "mode": "news",
        "template_key": "test-news-1",
        "slide_count": 4,
        "category": "News",
        "user_input": "https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/ Focus on technology impact",
        "image_source": "pexels",
        "voice_engine": "azure_basic"
    }
    
    print(f"\n[REQUEST] Unified Input (Mixed: URL + Text)")
    print(f"   User Input: {payload['user_input']}")
    
    try:
        response = requests.post(f"{BASE_URL}/stories", json=payload, timeout=300)
        response.raise_for_status()
        story = response.json()
        print(f"\n[SUCCESS] Story created: {story['id']}")
        return story
    except Exception as e:
        print(f"\n[ERROR] {e}")
        if hasattr(e, 'response') and e.response:
            print(f"   Status: {e.response.status_code}")
            print(f"   Response: {e.response.text[:500]}")
        return None

def test_template_url():
    """Test template loading from URL."""
    print("\n" + "=" * 60)
    print("Test 6: Template from URL")
    print("=" * 60)
    
    # Note: This would require a valid template URL
    # For now, just demonstrate the format
    payload = {
        "mode": "news",
        "template_key": "https://example.com/template.html",  # Would need real URL
        "slide_count": 4,
        "category": "News",
        "user_input": "https://example.com/article",
        "image_source": "pexels",
        "voice_engine": "azure_basic"  # Required: "azure_basic" or "elevenlabs_pro"
    }
    
    print(f"\n[REQUEST] Template from URL")
    print(f"   Template Key: {payload['template_key']}")
    print(f"   User Input: {payload['user_input']}")
    print(f"   Voice Engine: {payload['voice_engine']}")
    print(f"   [NOTE] This test requires a valid template URL")
    
    # Skip actual request for now
    print(f"\n[SKIPPED] Template URL test (requires valid URL)")

def main():
    print("=" * 60)
    print("Unified Input Testing Suite")
    print("=" * 60)
    print("\nThis script tests both legacy and new unified input formats.")
    print("Make sure the server is running on http://localhost:8000")
    
    results = []
    
    # Test 1: Legacy format
    results.append(("Legacy Format", test_legacy_format()))
    
    # Test 2: Unified input - URLs
    results.append(("Unified Input (URLs)", test_unified_input_urls()))
    
    # Test 3: Unified input - Multiple URLs
    results.append(("Unified Input (Multiple URLs)", test_unified_input_multiple_urls()))
    
    # Test 4: Unified input - Text
    results.append(("Unified Input (Text)", test_unified_input_text()))
    
    # Test 5: Unified input - Mixed
    results.append(("Unified Input (Mixed)", test_unified_input_mixed()))
    
    # Test 6: Template URL
    test_template_url()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for name, result in results:
        status = "[SUCCESS]" if result else "[FAILED]"
        print(f"{status} {name}")
    
    print("\n" + "=" * 60)
    print("Testing Complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()

