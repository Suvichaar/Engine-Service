"""Test script for template-specific slide generators."""

import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_template(test_name: str, json_file: str):
    """Test a specific template."""
    print("\n" + "=" * 60)
    print(f"Testing: {test_name}")
    print("=" * 60)
    
    # Load JSON file
    json_path = Path(json_file)
    if not json_path.exists():
        print(f"[ERROR] File not found: {json_file}")
        return None
    
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    
    print(f"\n[REQUEST]")
    print(f"   Template Key: {payload.get('template_key')}")
    print(f"   Mode: {payload.get('mode')}")
    print(f"   Slide Count: {payload.get('slide_count')}")
    print(f"   User Input: {payload.get('user_input', '')[:80]}...")
    
    try:
        print(f"\n[SENDING] POST {BASE_URL}/stories")
        response = requests.post(f"{BASE_URL}/stories", json=payload, timeout=300)
        response.raise_for_status()
        story = response.json()
        
        story_id = story.get("id")
        print(f"\n[SUCCESS] Story created!")
        print(f"   Story ID: {story_id}")
        print(f"   Template: {story.get('template_key')}")
        print(f"   Slides: {len(story.get('slide_deck', {}).get('slides', []))}")
        
        # Check HTML file
        html_file = Path(f"output/{story_id}.html")
        if html_file.exists():
            print(f"\n[HTML] File saved: {html_file}")
            print(f"   Size: {html_file.stat().st_size} bytes")
            
            # Check if template-specific structure is present
            html_content = html_file.read_text(encoding="utf-8")
            if 'class="centered-container"' in html_content:
                print(f"   [OK] Template structure found: centered-container")
            if 'class="text1"' in html_content:
                print(f"   [OK] Template structure found: text1")
            if '<!--INSERT_SLIDES_HERE-->' not in html_content:
                print(f"   [OK] Slides inserted (marker removed)")
            else:
                print(f"   [WARNING] Slide marker still present")
        else:
            print(f"\n[WARNING] HTML file not found: {html_file}")
        
        return story
        
    except requests.exceptions.HTTPError as e:
        print(f"\n[HTTP ERROR] Status: {e.response.status_code}")
        print(f"   Response: {e.response.text[:500]}")
        try:
            error_json = e.response.json()
            print(f"   Error Details:")
            print(json.dumps(error_json, indent=2))
        except:
            pass
        return None
    except requests.exceptions.RequestException as e:
        print(f"\n[REQUEST ERROR] {e}")
        return None
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("=" * 60)
    print("Template-Specific Slide Generator Testing")
    print("=" * 60)
    print("\nMake sure the server is running on http://localhost:8000")
    print("Press Ctrl+C to stop\n")
    
    # Test cases - Using file names only (no URLs)
    tests = [
        ("test-news-1", "example_template_test-news-1.json"),
        ("test-news-2", "example_template_test-news-2.json"),
    ]
    
    results = []
    
    for test_name, json_file in tests:
        result = test_template(test_name, json_file)
        results.append((test_name, result is not None))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, success in results:
        status = "[SUCCESS]" if success else "[FAILED]"
        print(f"{status} {test_name}")
    
    success_count = sum(1 for _, success in results if success)
    print(f"\nTotal: {success_count}/{len(results)} tests passed")
    
    print("\n" + "=" * 60)
    print("Testing Complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()

