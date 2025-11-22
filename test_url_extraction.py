"""Test script for URL extraction and article content processing."""

import requests
import json
import os
from pathlib import Path

BASE_URL = "http://localhost:8000"

def create_story(payload):
    """Create a story via POST /stories."""
    print(f"\n[CREATING] Creating story with URL extraction...")
    print(f"   URL: {payload.get('urls', [])}")
    print(f"   Mode: {payload.get('mode')}")
    print(f"   Image Source: {payload.get('image_source')}")
    
    try:
        response = requests.post(f"{BASE_URL}/stories", json=payload, timeout=300)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"\n[HTTP ERROR] Status: {e.response.status_code}")
        print(f"\nFull Response Headers:")
        for key, value in e.response.headers.items():
            print(f"  {key}: {value}")
        print(f"\nFull Response Text ({len(e.response.text)} chars):")
        print("-" * 60)
        print(e.response.text)
        print("-" * 60)
        # Try to parse as JSON
        try:
            error_json = e.response.json()
            print(f"\nParsed Error JSON:")
            print(json.dumps(error_json, indent=2))
        except:
            print("\n(Response is not JSON)")
        raise
    except requests.exceptions.RequestException as e:
        print(f"\n[REQUEST ERROR] {e}")
        raise

def get_story_details(story_id):
    """Get story details via GET /stories/{id}."""
    response = requests.get(f"{BASE_URL}/stories/{story_id}")
    response.raise_for_status()
    return response.json()

def get_story_html(story_id):
    """Get rendered HTML via GET /stories/{id}/html."""
    response = requests.get(f"{BASE_URL}/stories/{story_id}/html")
    response.raise_for_status()
    return response.json()

def get_story_test_results(story_id):
    """Get test results via GET /stories/{id}/test."""
    response = requests.get(f"{BASE_URL}/stories/{story_id}/test")
    response.raise_for_status()
    return response.json()

def main():
    print("=" * 60)
    print("URL Extraction & Article Content Test")
    print("=" * 60)
    
    # Load test payload
    test_file = Path("test_url_extraction.json")
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return
    
    with open(test_file, "r", encoding="utf-8") as f:
        payload = json.load(f)
    
    try:
        # 1. Create story
        print("\n" + "=" * 60)
        print("Step 1: Creating Story")
        print("=" * 60)
        created_story = create_story(payload)
        story_id = created_story["id"]
        print(f"\n[SUCCESS] Story created successfully!")
        print(f"   Story ID: {story_id}")
        print(f"   Mode: {created_story.get('mode')}")
        print(f"   Category: {created_story.get('category')}")
        print(f"   Slide Count: {created_story.get('slide_count')}")
        
        # Check if HTML file was saved
        html_file = Path(f"output/{story_id}.html")
        if html_file.exists():
            print(f"\n[HTML] HTML file saved: {html_file}")
            print(f"   Size: {html_file.stat().st_size} bytes")
        else:
            print(f"\n[WARNING] HTML file not found at: {html_file}")
        
        # 2. Get story details
        print("\n" + "=" * 60)
        print("Step 2: Fetching Story Details")
        print("=" * 60)
        story_details = get_story_details(story_id)
        
        # Check for article content
        doc_insights = story_details.get("doc_insights", {})
        semantic_chunks = doc_insights.get("semantic_chunks", [])
        print(f"\n[INFO] Document Insights:")
        print(f"   Semantic Chunks: {len(semantic_chunks)}")
        
        # Check for URL-extracted content
        url_chunks = [chunk for chunk in semantic_chunks if chunk.get("source_id", "").startswith("http")]
        if url_chunks:
            print(f"   [OK] URL-extracted chunks: {len(url_chunks)}")
            first_chunk = url_chunks[0]
            text_preview = first_chunk.get("text", "")[:200]
            print(f"   Preview: {text_preview}...")
        else:
            print(f"   [WARNING] No URL-extracted chunks found")
        
        # Check for article images
        metadata = doc_insights.get("metadata", {})
        article_images = metadata.get("article_images", [])
        if article_images:
            print(f"\n[IMAGES] Article Images Found: {len(article_images)}")
            for idx, img_url in enumerate(article_images[:3], 1):
                print(f"   {idx}. {img_url[:80]}...")
        else:
            print(f"\n[WARNING] No article images found in metadata")
        
        # Check image assets
        image_assets = story_details.get("image_assets", [])
        print(f"\n[IMAGES] Image Assets: {len(image_assets)}")
        for idx, asset in enumerate(image_assets[:3], 1):
            source = asset.get("source", "unknown")
            print(f"   {idx}. Source: {source}")
            if asset.get("original_url"):
                print(f"      URL: {asset['original_url'][:80]}...")
        
        # 3. Get test results
        print("\n" + "=" * 60)
        print("Step 3: Test Results")
        print("=" * 60)
        test_results = get_story_test_results(story_id)
        print(json.dumps(test_results, indent=2))
        
        # 4. Get rendered HTML
        print("\n" + "=" * 60)
        print("Step 4: Rendered HTML")
        print("=" * 60)
        html_response = get_story_html(story_id)
        html_content = html_response.get("html", "")
        
        if html_content:
            output_file = f"test_story_{story_id}.html"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"[SUCCESS] HTML saved to: {output_file}")
            print(f"   Size: {len(html_content)} characters")
            
            # Check for article images in HTML
            if article_images:
                found_in_html = sum(1 for img_url in article_images if img_url in html_content)
                print(f"   Article images in HTML: {found_in_html}/{len(article_images)}")
        else:
            print("[WARNING] No HTML content returned")
        
        print("\n" + "=" * 60)
        print("[SUCCESS] Test Complete!")
        print("=" * 60)
        
    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] API Error: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"   Status: {e.response.status_code}")
            print(f"\n   Full Error Response:")
            print(f"   {e.response.text}")
            try:
                error_detail = e.response.json()
                print(f"\n   Error Details (JSON):")
                print(f"   {json.dumps(error_detail, indent=4)}")
            except:
                pass
    except Exception as e:
        print(f"\n[ERROR] Unexpected Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

