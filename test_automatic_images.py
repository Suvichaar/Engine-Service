#!/usr/bin/env python3
"""
Test script for automatic content-based image generation
Tests both AI Generated and Pexels with/without user keywords
"""

import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def test_story_creation(payload: Dict[str, Any], test_name: str):
    """Create a story and check results."""
    print(f"\n{'='*60}")
    print(f"🧪 Test: {test_name}")
    print(f"{'='*60}")
    print(f"📝 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        # Create story
        response = requests.post(f"{BASE_URL}/stories", json=payload, timeout=300)
        
        if response.status_code != 200:
            # Show actual error message for debugging
            try:
                error_detail = response.json()
                print(f"❌ Error {response.status_code}: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"❌ Error {response.status_code}: {response.text[:500]}")
            return None, None
        
        story = response.json()
        
        story_id = story.get("id")
        print(f"✅ Story created: {story_id}")
        
        # Check image assets
        image_assets = story.get("image_assets", [])
        print(f"📸 Image assets generated: {len(image_assets)}")
        
        for idx, asset in enumerate(image_assets):
            print(f"   - Image {idx+1}: {asset.get('placeholder_id', 'N/A')} - {asset.get('source', 'N/A')}")
        
        # Get HTML to verify
        html_response = requests.get(f"{BASE_URL}/stories/{story_id}/html", timeout=30)
        if html_response.status_code == 200:
            print(f"✅ HTML generated successfully")
            html_content = html_response.text
            # Check if images are in HTML
            if "image" in html_content.lower():
                print(f"✅ Images found in HTML")
            else:
                print(f"⚠️  No images found in HTML")
        
        return story_id, story
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None

def main():
    """Run all test cases."""
    print("🚀 Starting Automatic Image Generation Tests")
    print(f"📍 Backend URL: {BASE_URL}")
    print("\n⚠️  Make sure backend is running: uvicorn app.main:app --reload")
    
    # Test 1: News mode - AI Generated - WITH user keywords
    test_1 = {
        "mode": "news",
        "template_key": "test-news-1",
        "slide_count": 4,  # Must be 4-10 per validation
        "category": "Technology",
        "user_input": "Quantum computing is revolutionizing technology",
        "image_source": "ai",
        "voice_engine": "azure_basic",
        "prompt_keywords": ["quantum", "computing", "technology"]  # User provided
    }
    test_story_creation(test_1, "News Mode - AI Generated - WITH User Keywords")
    time.sleep(2)
    
    # Test 2: News mode - AI Generated - WITHOUT user keywords (automatic)
    test_2 = {
        "mode": "news",
        "template_key": "test-news-1",
        "slide_count": 4,  # Must be 4-10 per validation
        "category": "Technology",
        "user_input": "Quantum computing is revolutionizing technology",
        "image_source": "ai",
        "voice_engine": "azure_basic",
        "prompt_keywords": []  # Empty - should auto-generate
    }
    test_story_creation(test_2, "News Mode - AI Generated - WITHOUT User Keywords (Auto)")
    time.sleep(2)
    
    # Test 3: News mode - Pexels - WITH user keywords
    test_3 = {
        "mode": "news",
        "template_key": "test-news-1",
        "slide_count": 4,  # Must be 4-10 per validation
        "category": "Technology",
        "user_input": "Artificial intelligence is transforming industries",
        "image_source": "pexels",
        "voice_engine": "azure_basic",
        "prompt_keywords": ["technology", "AI", "innovation"]  # User provided
    }
    test_story_creation(test_3, "News Mode - Pexels - WITH User Keywords")
    time.sleep(2)
    
    # Test 4: News mode - Pexels - WITHOUT user keywords (automatic)
    test_4 = {
        "mode": "news",
        "template_key": "test-news-1",
        "slide_count": 4,  # Must be 4-10 per validation
        "category": "Technology",
        "user_input": "Artificial intelligence is transforming industries",
        "image_source": "pexels",
        "voice_engine": "azure_basic",
        "prompt_keywords": []  # Empty - should auto-extract
    }
    test_story_creation(test_4, "News Mode - Pexels - WITHOUT User Keywords (Auto)")
    time.sleep(2)
    
    # Test 5: Curious mode - AI Generated - WITH user keywords
    test_5 = {
        "mode": "curious",
        "template_key": "curious-template-2",
        "slide_count": 4,
        "category": "Science",
        "user_input": "Tell me about photosynthesis",
        "image_source": "ai",
        "voice_engine": "azure_basic",
        "prompt_keywords": ["plants", "biology", "science"]  # User provided
    }
    test_story_creation(test_5, "Curious Mode - AI Generated - WITH User Keywords")
    time.sleep(2)
    
    # Test 6: Curious mode - AI Generated - WITHOUT user keywords (automatic)
    test_6 = {
        "mode": "curious",
        "template_key": "curious-template-2",
        "slide_count": 4,
        "category": "Science",
        "user_input": "Tell me about photosynthesis",
        "image_source": "ai",
        "voice_engine": "azure_basic",
        "prompt_keywords": []  # Empty - should auto-generate
    }
    test_story_creation(test_6, "Curious Mode - AI Generated - WITHOUT User Keywords (Auto)")
    time.sleep(2)
    
    # Test 7: Curious mode - Pexels - WITH user keywords
    test_7 = {
        "mode": "curious",
        "template_key": "curious-template-2",
        "slide_count": 4,
        "category": "Science",
        "user_input": "Tell me about quantum physics",
        "image_source": "pexels",
        "voice_engine": "azure_basic",
        "prompt_keywords": ["quantum", "physics", "science"]  # User provided
    }
    test_story_creation(test_7, "Curious Mode - Pexels - WITH User Keywords")
    time.sleep(2)
    
    # Test 8: Curious mode - Pexels - WITHOUT user keywords (automatic)
    test_8 = {
        "mode": "curious",
        "template_key": "curious-template-2",
        "slide_count": 4,
        "category": "Science",
        "user_input": "Tell me about quantum physics",
        "image_source": "pexels",
        "voice_engine": "azure_basic",
        "prompt_keywords": []  # Empty - should auto-extract
    }
    test_story_creation(test_8, "Curious Mode - Pexels - WITHOUT User Keywords (Auto)")
    
    print(f"\n{'='*60}")
    print("✅ All tests completed!")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()

