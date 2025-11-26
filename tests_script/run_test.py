#!/usr/bin/env python3
"""
Test runner for Story Generation System

Usage:
    python run_test.py <test_file.json>
    python run_test.py test_news_mode_single_image.json
"""

import json
import sys
import requests
from pathlib import Path
from typing import Dict, Any
import time

# Configuration
FASTAPI_BASE_URL = "http://localhost:8000"
TEST_TIMEOUT = 300  # 5 minutes

def load_test_case(test_file: str) -> Dict[str, Any]:
    """Load test case from JSON file."""
    test_path = Path(__file__).parent / test_file
    if not test_path.exists():
        raise FileNotFoundError(f"Test file not found: {test_file}")
    
    with open(test_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def run_test(test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Execute test case against FastAPI backend."""
    print(f"🧪 Running test: {test_case.get('description', 'Unknown test')}")
    print(f"📋 Mode: {test_case.get('mode')}, Template: {test_case.get('template_key')}")
    
    # Prepare payload (remove test-specific fields)
    payload = {k: v for k, v in test_case.items() 
               if k not in ['description', 'expected_behavior']}
    
    print(f"📤 Sending request to {FASTAPI_BASE_URL}/api/stories/")
    
    try:
        # Send request
        start_time = time.time()
        response = requests.post(
            f"{FASTAPI_BASE_URL}/api/stories/",
            json=payload,
            timeout=TEST_TIMEOUT
        )
        end_time = time.time()
        
        # Parse response
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Test completed successfully in {end_time - start_time:.2f}s")
            print(f"📊 Story ID: {result.get('id')}")
            print(f"🔗 URLs: {result.get('canurl')}")
            
            # Validate expected behavior
            expected = test_case.get('expected_behavior', {})
            if expected:
                print(f"\n📋 Expected Behavior Validation:")
                for key, value in expected.items():
                    print(f"   {key}: {value}")
            
            return {
                "status": "success",
                "duration": end_time - start_time,
                "story_id": result.get('id'),
                "response": result
            }
        else:
            print(f"❌ Test failed with status {response.status_code}")
            print(f"📄 Error: {response.text}")
            return {
                "status": "error",
                "status_code": response.status_code,
                "error": response.text
            }
            
    except requests.exceptions.Timeout:
        print(f"⏰ Test timed out after {TEST_TIMEOUT}s")
        return {"status": "timeout"}
    except requests.exceptions.ConnectionError:
        print(f"🔌 Connection error - is FastAPI server running on {FASTAPI_BASE_URL}?")
        return {"status": "connection_error"}
    except Exception as e:
        print(f"💥 Unexpected error: {str(e)}")
        return {"status": "unexpected_error", "error": str(e)}

def main():
    """Main test runner."""
    if len(sys.argv) != 2:
        print("Usage: python run_test.py <test_file.json>")
        print("\nAvailable tests:")
        test_dir = Path(__file__).parent
        for test_file in sorted(test_dir.glob("test_*.json")):
            print(f"  - {test_file.name}")
        sys.exit(1)
    
    test_file = sys.argv[1]
    
    try:
        # Load and run test
        test_case = load_test_case(test_file)
        result = run_test(test_case)
        
        # Print summary
        print(f"\n{'='*50}")
        print(f"📊 Test Summary for {test_file}")
        print(f"{'='*50}")
        print(f"Status: {result['status']}")
        
        if result['status'] == 'success':
            print(f"Duration: {result['duration']:.2f}s")
            print(f"Story ID: {result['story_id']}")
            print("✅ Test PASSED")
        else:
            print("❌ Test FAILED")
            
    except Exception as e:
        print(f"💥 Test execution failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
