"""
API Error Handling Test Script
Tests various error scenarios for the story generation API.
"""

import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000/stories"

def print_test_header(test_name: str):
    """Print formatted test header."""
    print("\n" + "=" * 80)
    print(f"TEST: {test_name}")
    print("=" * 80)

def print_result(status_code: int, response_data: Any):
    """Print formatted test result."""
    print(f"Status Code: {status_code}")
    if isinstance(response_data, dict):
        print(f"Response: {json.dumps(response_data, indent=2)}")
    else:
        print(f"Response: {response_data}")

def test_1_invalid_json():
    """Test 1.1: Malformed JSON"""
    print_test_header("1.1 - Malformed JSON")
    try:
        response = requests.post(
            BASE_URL,
            data="invalid json {",
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print_result(response.status_code, response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text)
    except requests.exceptions.RequestException as e:
        print(f"Request Exception: {e}")

def test_2_missing_required_fields():
    """Test 1.2: Missing Required Fields"""
    print_test_header("1.2 - Missing Required Fields")
    payload = {"mode": "news"}  # Missing template_key, slide_count, etc.
    try:
        response = requests.post(BASE_URL, json=payload, timeout=10)
        print_result(response.status_code, response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text)
    except requests.exceptions.RequestException as e:
        print(f"Request Exception: {e}")

def test_3_invalid_field_values():
    """Test 1.3: Invalid Field Values"""
    print_test_header("1.3 - Invalid Field Values")
    payload = {
        "mode": "invalid_mode",  # Should be "news" or "curious"
        "template_key": "test-news-1",
        "slide_count": -5,  # Invalid negative number
        "user_input": "",
        "category": "News",
        "voice_engine": "azure_basic"
    }
    try:
        response = requests.post(BASE_URL, json=payload, timeout=10)
        print_result(response.status_code, response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text)
    except requests.exceptions.RequestException as e:
        print(f"Request Exception: {e}")

def test_4_wrong_data_types():
    """Test 1.4: Wrong Data Types"""
    print_test_header("1.4 - Wrong Data Types")
    payload = {
        "mode": "news",
        "template_key": 12345,  # Should be string
        "slide_count": "four",  # Should be integer
        "user_input": "test",
        "category": "News",
        "voice_engine": "azure_basic"
    }
    try:
        response = requests.post(BASE_URL, json=payload, timeout=10)
        print_result(response.status_code, response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text)
    except requests.exceptions.RequestException as e:
        print(f"Request Exception: {e}")

def test_5_dalle_api_failure():
    """Test 2.1: DALL-E API Failure (Note: Requires invalid API key in config)"""
    print_test_header("2.1 - DALL-E API Failure")
    print("NOTE: This test requires invalid DALL-E API key in config/settings.toml")
    print("The system should retry 3 times with exponential backoff")
    payload = {
        "mode": "news",
        "template_key": "test-news-1",
        "slide_count": 4,
        "user_input": "https://example.com/article",
        "category": "News",
        "image_source": "ai",
        "prompt_keywords": ["test"],
        "voice_engine": "azure_basic"
    }
    try:
        print("Sending request (this may take time due to retries)...")
        start_time = time.time()
        response = requests.post(BASE_URL, json=payload, timeout=120)
        elapsed = time.time() - start_time
        print(f"Request completed in {elapsed:.2f} seconds")
        print_result(response.status_code, response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text)
        print("\nCheck server logs for:")
        print("  - 'Rate limited (429), waiting X seconds before retry'")
        print("  - '400 Bad Request on attempt X/3, trying simpler prompt'")
        print("  - 'AI image generation failed'")
    except requests.exceptions.RequestException as e:
        print(f"Request Exception: {e}")

def test_6_dalle_content_policy():
    """Test 2.3: DALL-E Content Policy Violation"""
    print_test_header("2.3 - DALL-E Content Policy Violation")
    print("NOTE: This test uses prompts that might trigger content policy")
    payload = {
        "mode": "news",
        "template_key": "test-news-1",
        "slide_count": 4,
        "user_input": "test",
        "category": "News",
        "image_source": "ai",
        "prompt_keywords": ["violence", "explicit"],  # Might trigger policy
        "voice_engine": "azure_basic"
    }
    try:
        print("Sending request (system should try simpler prompt on retry)...")
        start_time = time.time()
        response = requests.post(BASE_URL, json=payload, timeout=120)
        elapsed = time.time() - start_time
        print(f"Request completed in {elapsed:.2f} seconds")
        print_result(response.status_code, response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text)
        print("\nCheck server logs for:")
        print("  - '400 Bad Request on attempt X/3, trying simpler prompt'")
        print("  - 'Using fallback image' (if available)")
    except requests.exceptions.RequestException as e:
        print(f"Request Exception: {e}")

def test_7_tts_failure():
    """Test 2.4: Azure TTS Failure (Note: Requires invalid TTS credentials)"""
    print_test_header("2.4 - Azure TTS Failure")
    print("NOTE: This test requires invalid TTS credentials in config")
    payload = {
        "mode": "news",
        "template_key": "test-news-1",
        "slide_count": 4,
        "user_input": "test",
        "category": "News",
        "voice_engine": "azure_basic"
    }
    try:
        response = requests.post(BASE_URL, json=payload, timeout=60)
        print_result(response.status_code, response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text)
        print("\nExpected: Story should still be generated (audio might be missing)")
        print("Check server logs for TTS error messages")
    except requests.exceptions.RequestException as e:
        print(f"Request Exception: {e}")

def test_8_s3_upload_failure():
    """Test 4.1: S3 Upload Failure (Note: Requires invalid S3 credentials)"""
    print_test_header("4.1 - S3 Upload Failure")
    print("NOTE: This test requires invalid S3 credentials in config")
    payload = {
        "mode": "news",
        "template_key": "test-news-1",
        "slide_count": 4,
        "user_input": "test",
        "category": "News",
        "image_source": "custom",
        "attachments": [
            "s3://suvichaarapp/media/images/backgrounds/20251129/test.jpg"
        ],
        "voice_engine": "azure_basic"
    }
    try:
        response = requests.post(BASE_URL, json=payload, timeout=60)
        print_result(response.status_code, response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text)
        print("\nExpected: Story should still be generated")
        print("Check server logs for:")
        print("  - 'Failed to upload image to S3: ...'")
        print("  - 'S3 client unavailable'")
    except requests.exceptions.RequestException as e:
        print(f"Request Exception: {e}")

def test_9_database_error():
    """Test 5.1: Database Connection Failure"""
    print_test_header("5.1 - Database Connection Failure")
    print("NOTE: This test requires invalid database URL in config")
    print("Expected: Story generation should continue, database save should fail gracefully")
    payload = {
        "mode": "news",
        "template_key": "test-news-1",
        "slide_count": 4,
        "user_input": "test",
        "category": "News",
        "voice_engine": "azure_basic"
    }
    try:
        response = requests.post(BASE_URL, json=payload, timeout=60)
        print_result(response.status_code, response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text)
        print("\nExpected: Story should be generated successfully")
        print("Check server logs for:")
        print("  - 'Failed to save story to database (non-critical): ...'")
        print("  - Story should still be returned in response")
    except requests.exceptions.RequestException as e:
        print(f"Request Exception: {e}")

def test_10_valid_request():
    """Test: Valid Request (Control Test)"""
    print_test_header("Control Test - Valid Request")
    payload = {
        "mode": "news",
        "template_key": "test-news-1",
        "slide_count": 4,
        "user_input": "https://example.com/article",
        "category": "News",
        "voice_engine": "azure_basic"
    }
    try:
        print("Sending valid request to verify API is working...")
        start_time = time.time()
        response = requests.post(BASE_URL, json=payload, timeout=120)
        elapsed = time.time() - start_time
        print(f"Request completed in {elapsed:.2f} seconds")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS: Story generated with ID: {data.get('story_id', 'N/A')}")
            print(f"   Story URL: {data.get('canurl1', 'N/A')}")
        else:
            print_result(response.status_code, response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text)
    except requests.exceptions.RequestException as e:
        print(f"Request Exception: {e}")

def main():
    """Run all error handling tests."""
    print("\n" + "=" * 80)
    print("API ERROR HANDLING TEST SUITE")
    print("=" * 80)
    print("\nThis script tests various error scenarios for the story generation API.")
    print("Make sure the API server is running on http://localhost:8000")
    print("\nPress Enter to start tests...")
    input()
    
    # Test 1: Invalid Inputs
    print("\n" + "=" * 80)
    print("SECTION 1: INVALID INPUTS (Bad JSON)")
    print("=" * 80)
    test_1_invalid_json()
    time.sleep(1)
    test_2_missing_required_fields()
    time.sleep(1)
    test_3_invalid_field_values()
    time.sleep(1)
    test_4_wrong_data_types()
    
    # Test 2: API Failures
    print("\n" + "=" * 80)
    print("SECTION 2: API FAILURES (DALL-E/TTS)")
    print("=" * 80)
    print("\n⚠️  NOTE: Tests 2.1, 2.3, 2.4 require invalid credentials in config")
    print("   Uncomment these tests when ready to test with invalid credentials\n")
    
    # Uncomment these when testing with invalid credentials:
    # test_5_dalle_api_failure()
    # test_6_dalle_content_policy()
    # test_7_tts_failure()
    
    # Test 4: S3 Upload Failures
    print("\n" + "=" * 80)
    print("SECTION 4: S3 UPLOAD FAILURES")
    print("=" * 80)
    print("\n⚠️  NOTE: Test 4.1 requires invalid S3 credentials in config")
    print("   Uncomment this test when ready to test with invalid credentials\n")
    
    # Uncomment when testing with invalid S3 credentials:
    # test_8_s3_upload_failure()
    
    # Test 5: Database Errors
    print("\n" + "=" * 80)
    print("SECTION 5: DATABASE ERRORS")
    print("=" * 80)
    print("\n⚠️  NOTE: Test 5.1 requires invalid database URL in config")
    print("   Uncomment this test when ready to test with invalid database\n")
    
    # Uncomment when testing with invalid database:
    # test_9_database_error()
    
    # Control Test
    print("\n" + "=" * 80)
    print("CONTROL TEST: VALID REQUEST")
    print("=" * 80)
    test_10_valid_request()
    
    print("\n" + "=" * 80)
    print("TEST SUITE COMPLETED")
    print("=" * 80)
    print("\nSummary:")
    print("✅ Tests 1.1-1.4: Invalid Inputs - Should return 422 errors")
    print("⚠️  Tests 2.1-2.4: API Failures - Uncomment when testing with invalid credentials")
    print("⚠️  Test 4.1: S3 Upload Failure - Uncomment when testing with invalid S3")
    print("⚠️  Test 5.1: Database Error - Uncomment when testing with invalid database")
    print("✅ Test 10: Valid Request - Should return 200 with story data")
    print("\nCheck server logs for detailed error messages and retry attempts.")

if __name__ == "__main__":
    main()

