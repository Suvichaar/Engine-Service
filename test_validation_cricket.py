"""Test validation logic with cricket URL to ensure it rejects Delhi pollution content."""

import sys
import logging
from app.services.url_extractor import URLContentExtractor

# Set up logging to see validation messages
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)

def test_cricket_url():
    """Test cricket URL extraction and validation."""
    extractor = URLContentExtractor()
    
    # Cricket article URL
    cricket_url = "https://indianexpress.com/article/sports/cricket/what-if-alyssa-healy-had-caught-rodrigues-world-cup-semifinal-10445564/"
    
    print("=" * 80)
    print("TESTING: Cricket URL Extraction and Validation")
    print("=" * 80)
    print(f"URL: {cricket_url}")
    print()
    
    result = extractor.extract(cricket_url)
    
    if result is None:
        print("✅ VALIDATION WORKED: Article was REJECTED (expected if wrong content)")
        print("   This means the validation detected a mismatch!")
        return True
    else:
        print("⚠️ Article was EXTRACTED:")
        print(f"   Title: {result.title[:100]}")
        print(f"   Text preview: {result.text[:200]}")
        print()
        
        # Check if it's actually cricket content or Delhi pollution
        title_lower = result.title.lower()
        text_lower = result.text[:500].lower()
        
        cricket_keywords = ['cricket', 'alyssa', 'healy', 'rodrigues', 'world', 'cup', 'semifinal']
        delhi_keywords = ['delhi', 'pollution', 'air', 'quality', 'aqi', 'pradushan', 'vayu']
        
        cricket_matches = sum(1 for kw in cricket_keywords if kw in title_lower or kw in text_lower)
        delhi_matches = sum(1 for kw in delhi_keywords if kw in title_lower or kw in text_lower)
        
        print(f"   Cricket keyword matches: {cricket_matches}/{len(cricket_keywords)}")
        print(f"   Delhi keyword matches: {delhi_matches}/{len(delhi_keywords)}")
        print()
        
        if delhi_matches > cricket_matches:
            print("❌ PROBLEM: Extracted content is about DELHI POLLUTION, not cricket!")
            print("   Validation should have REJECTED this!")
            return False
        else:
            print("✅ Content appears to be about cricket (validation passed correctly)")
            return True

if __name__ == "__main__":
    success = test_cricket_url()
    sys.exit(0 if success else 1)

