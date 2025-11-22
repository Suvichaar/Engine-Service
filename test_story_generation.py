"""Quick test script to verify story generation and HTML rendering."""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import httpx

BASE_URL = "http://localhost:8000"


def test_story_creation():
    """Test creating a story."""
    print("🧪 Testing Story Creation...")
    print("-" * 50)

    # Create a test story request
    payload = {
        "text_prompt": "Photosynthesis is the process by which plants convert light energy into chemical energy.",
        "notes": "This is a test story about photosynthesis for educational purposes.",
        "urls": [],
        "attachments": [],
        "prompt_keywords": ["photosynthesis", "plants", "biology"],
        "mode": "curious",
        "template_key": "test-news-1",
        "slide_count": 4,
        "category": "Science",
        "image_source": "pexels",
        "voice_engine": "azure_basic",
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            # Create story
            print("📝 Creating story...")
            response = client.post(f"{BASE_URL}/stories", json=payload)
            response.raise_for_status()
            story_data = response.json()

            story_id = story_data["id"]
            print(f"✅ Story created! ID: {story_id}")
            print(f"   Mode: {story_data['mode']}")
            print(f"   Category: {story_data['category']}")
            print(f"   Slides: {len(story_data['slide_deck']['slides'])}")
            print(f"   Images: {len(story_data['image_assets'])}")
            print(f"   Voice Assets: {len(story_data['voice_assets'])}")
            print()

            # Test story generation
            print("🔍 Testing story components...")
            test_response = client.get(f"{BASE_URL}/stories/{story_id}/test")
            test_response.raise_for_status()
            test_data = test_response.json()

            print(f"✅ Test Results:")
            print(f"   Status: {test_data['status']}")
            print(f"   Slides: {test_data['components']['slides']}")
            print(f"   Images: {test_data['components']['images']}")
            print(f"   Voice: {test_data['components']['voice']}")
            print(f"   HTML Rendering: {test_data['components']['html_rendering']}")
            print()

            # Get HTML
            print("📄 Getting rendered HTML...")
            html_response = client.get(f"{BASE_URL}/stories/{story_id}/html")
            html_response.raise_for_status()
            html_data = html_response.json()

            html_length = len(html_data["html"])
            print(f"✅ HTML rendered! Length: {html_length} characters")
            print(f"   Template: {html_data['template_key']}")

            # Save HTML to file for inspection
            output_file = Path(f"test_story_{story_id}.html")
            output_file.write_text(html_data["html"], encoding="utf-8")
            print(f"   Saved to: {output_file}")

            return True

    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"   Response: {e.response.text[:500]}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_health():
    """Test health endpoint."""
    print("🏥 Testing Health Endpoint...")
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{BASE_URL}/health")
            response.raise_for_status()
            print(f"✅ Health check passed: {response.json()}")
            return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Story Generation Test Script")
    print("=" * 50)
    print()

    # Test health first
    if not test_health():
        print("\n⚠️  Health check failed. Is the server running?")
        print("   Start server with: uvicorn app.main:app --reload")
        sys.exit(1)

    print()
    # Test story creation
    success = test_story_creation()

    print()
    print("=" * 50)
    if success:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    print("=" * 50)

