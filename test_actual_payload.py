"""Test actual payload with URL extraction and validation."""

import sys
import logging
from app.services.url_extractor import URLContentExtractor

# Setup logging to see all warnings/errors
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)

def test_football_url_extraction():
    """Test the actual football URL from the payload."""
    
    print("=" * 80)
    print("TESTING ACTUAL PAYLOAD: Football URL with Hindi request")
    print("=" * 80)
    print("\n")
    
    # The actual URL from payload
    url = "https://indianexpress.com/article/sports/football/african-nations-cup-needs-a-world-cup-winner-to-get-the-recognition-it-deserves-10444302/?ref=rhs_more_sports_chess"
    
    print(f"URL: {url}")
    print(f"Expected: Should extract FOOTBALL content, NOT Delhi pollution")
    print("\n" + "=" * 80)
    print("Starting extraction...")
    print("=" * 80 + "\n")
    
    # Create extractor
    extractor = URLContentExtractor()
    
    # Extract
    result = extractor.extract(url)
    
    print("\n" + "=" * 80)
    print("EXTRACTION RESULT")
    print("=" * 80)
    
    if result is None:
        print("❌ EXTRACTION REJECTED (returned None)")
        print("✅ This is CORRECT if validation detected a mismatch!")
        print("   (URL keywords don't match extracted content)")
        return False
    else:
        print("✅ EXTRACTION SUCCESSFUL")
        print(f"\nTitle: {result.title}")
        print(f"Text length: {len(result.text)} characters")
        print(f"Text preview: {result.text[:300]}...")
        print(f"Summary: {result.summary[:200]}...")
        
        # Check if it's about football or Delhi
        title_lower = result.title.lower()
        text_lower = result.text[:500].lower()
        
        football_keywords = ['football', 'african', 'nations', 'cup', 'world', 'winner', 'fifa', 'soccer']
        delhi_keywords = ['delhi', 'dilli', 'pollution', 'pradushan', 'vayu', 'gunvatta', 'vaayu', 'प्रदूषण', 'दिल्ली', 'वायु', 'गुणवत्ता']
        
        has_football = any(kw in title_lower or kw in text_lower for kw in football_keywords)
        has_delhi = any(kw in title_lower or kw in text_lower for kw in delhi_keywords)
        
        print("\n" + "=" * 80)
        print("CONTENT ANALYSIS")
        print("=" * 80)
        print(f"Has football keywords: {has_football}")
        print(f"Has Delhi keywords: {has_delhi}")
        
        if has_football and not has_delhi:
            print("\n✅ CORRECT: Extracted FOOTBALL content (as expected)")
            return True
        elif has_delhi and not has_football:
            print("\n❌ WRONG: Extracted DELHI content (should be football!)")
            print("   This indicates the validation failed or extraction is wrong")
            return False
        else:
            print("\n⚠️  UNCLEAR: Content doesn't clearly match either")
            return None

if __name__ == "__main__":
    success = test_football_url_extraction()
    
    print("\n" + "=" * 80)
    print("FINAL RESULT")
    print("=" * 80)
    if success is True:
        print("✅ TEST PASSED: Correct content extracted")
    elif success is False:
        print("❌ TEST FAILED: Wrong content or validation issue")
    else:
        print("⚠️  TEST UNCLEAR: Need manual inspection")
    print("=" * 80)

