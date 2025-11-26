#!/usr/bin/env python3
"""
Run all test cases for Story Generation System

Usage:
    python run_all_tests.py
    python run_all_tests.py --category news_mode
    python run_all_tests.py --category curious_mode
    python run_all_tests.py --category special_features
"""

import json
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any
import time
from run_test import load_test_case, run_test

# Test categories
TEST_CATEGORIES = {
    "news_mode": [
        "test_news_mode_single_image.json",
        "test_news_mode_multiple_images_perfect.json",
        "test_news_mode_extra_images.json",
        "test_news_mode_fewer_images.json",
        "test_news_mode_default_images.json",
        "test_news_mode_ai_images.json"
    ],
    "curious_mode": [
        "test_curious_mode_perfect_images.json",
        "test_curious_mode_ai_images.json",
        "test_curious_mode_pexels_images.json",
        "test_curious_mode_extra_images.json",
        "test_curious_mode_fewer_images.json"
    ],
    "special_features": [
        "test_url_generation_news.json",
        "test_attachments_content_extraction.json",
        "test_dual_purpose_attachments.json",
        "test_seo_metadata.json",
        "test_voice_synthesis.json"
    ]
}

def get_all_test_files() -> List[str]:
    """Get all test JSON files."""
    test_dir = Path(__file__).parent
    return [f.name for f in sorted(test_dir.glob("test_*.json"))]

def run_test_suite(test_files: List[str]) -> Dict[str, Any]:
    """Run a suite of tests and collect results."""
    results = {
        "total": len(test_files),
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "details": []
    }
    
    print(f"🚀 Running {len(test_files)} tests...")
    print("=" * 60)
    
    for i, test_file in enumerate(test_files, 1):
        print(f"\n[{i}/{len(test_files)}] {test_file}")
        print("-" * 40)
        
        try:
            test_case = load_test_case(test_file)
            result = run_test(test_case)
            
            # Categorize result
            if result['status'] == 'success':
                results['passed'] += 1
                status_icon = "✅"
            else:
                results['failed'] += 1
                status_icon = "❌"
            
            results['details'].append({
                "test_file": test_file,
                "status": result['status'],
                "duration": result.get('duration', 0),
                "story_id": result.get('story_id'),
                "error": result.get('error')
            })
            
            print(f"{status_icon} {test_file}: {result['status']}")
            
        except Exception as e:
            results['errors'] += 1
            results['details'].append({
                "test_file": test_file,
                "status": "error",
                "error": str(e)
            })
            print(f"💥 {test_file}: ERROR - {str(e)}")
    
    return results

def print_summary(results: Dict[str, Any]):
    """Print test results summary."""
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    print(f"Total Tests: {results['total']}")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"💥 Errors: {results['errors']}")
    
    success_rate = (results['passed'] / results['total']) * 100 if results['total'] > 0 else 0
    print(f"📈 Success Rate: {success_rate:.1f}%")
    
    # Detailed results
    if results['details']:
        print(f"\n📋 Detailed Results:")
        for detail in results['details']:
            status_icon = "✅" if detail['status'] == 'success' else "❌"
            duration = f" ({detail['duration']:.2f}s)" if detail.get('duration') else ""
            print(f"  {status_icon} {detail['test_file']}: {detail['status']}{duration}")
            if detail.get('error'):
                print(f"      Error: {detail['error']}")
    
    # Failed tests
    failed_tests = [d for d in results['details'] if d['status'] != 'success']
    if failed_tests:
        print(f"\n❌ Failed Tests ({len(failed_tests)}):")
        for test in failed_tests:
            print(f"  - {test['test_file']}: {test['status']}")
            if test.get('error'):
                print(f"    {test['error']}")

def main():
    """Main test suite runner."""
    parser = argparse.ArgumentParser(description="Run Story Generation System tests")
    parser.add_argument(
        "--category", 
        choices=list(TEST_CATEGORIES.keys()) + ["all"],
        default="all",
        help="Test category to run"
    )
    parser.add_argument(
        "--list-tests",
        action="store_true",
        help="List available tests and exit"
    )
    
    args = parser.parse_args()
    
    # List tests
    if args.list_tests:
        print("Available test categories:")
        for category, tests in TEST_CATEGORIES.items():
            print(f"\n{category}:")
            for test in tests:
                print(f"  - {test}")
        print(f"\nAll tests: {get_all_test_files()}")
        return
    
    # Determine which tests to run
    if args.category == "all":
        test_files = get_all_test_files()
    else:
        test_files = TEST_CATEGORIES.get(args.category, [])
    
    if not test_files:
        print(f"No tests found for category: {args.category}")
        sys.exit(1)
    
    # Run tests
    start_time = time.time()
    results = run_test_suite(test_files)
    end_time = time.time()
    
    # Print summary
    print_summary(results)
    print(f"\n⏱️ Total execution time: {end_time - start_time:.2f}s")
    
    # Exit with appropriate code
    if results['failed'] > 0 or results['errors'] > 0:
        sys.exit(1)
    else:
        print("\n🎉 All tests passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()
