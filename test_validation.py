"""Test script to verify URL-content validation logic."""

def test_chess_url_delhi_content():
    """Test if validation catches chess URL with Delhi content."""
    
    # Test case 1: Chess URL with Delhi title
    url = "https://indianexpress.com/article/sports/chess/goutham-krishna-international-master-heads-turn-world-rapid-blitz-10440786/"
    title = "दिल्ली में वायु गुणवत्ता खतरनाक स्तर पर"
    text = "दिल्ली में प्रदूषण बढ़ रहा है"
    
    url_lower = url.lower()
    title_lower = title.lower()
    text_lower = text.lower()
    
    chess_keywords = ['chess', 'goutham', 'krishna', 'master', 'rapid', 'blitz', 'tournament', 'game']
    delhi_keywords = ['delhi', 'dilli', 'pollution', 'pradushan', 'vayu', 'gunvatta', 'vaayu', 'प्रदूषण', 'दिल्ली', 'वायु', 'गुणवत्ता']
    
    is_chess_url = any(kw in url_lower for kw in chess_keywords)
    is_delhi_content = any(kw in title_lower or kw in text_lower for kw in delhi_keywords)
    
    print("=" * 60)
    print("TEST 1: Chess URL with Delhi Content")
    print("=" * 60)
    print(f"URL: {url}")
    print(f"Title: {title}")
    print(f"is_chess_url: {is_chess_url}")
    print(f"is_delhi_content: {is_delhi_content}")
    print(f"Should REJECT: {is_chess_url and is_delhi_content}")
    
    if is_chess_url and is_delhi_content:
        print("✅ VALIDATION WORKS: Would reject this!")
        found_chess = [kw for kw in chess_keywords if kw in url_lower]
        found_delhi = [kw for kw in delhi_keywords if kw in title_lower or kw in text_lower]
        print(f"   Chess keywords found: {found_chess}")
        print(f"   Delhi keywords found: {found_delhi}")
    else:
        print("❌ VALIDATION FAILED: Would NOT reject this!")
    
    print("\n")
    
    # Test case 2: Chess URL with Chess content (should pass)
    url2 = "https://indianexpress.com/article/sports/chess/goutham-krishna-international-master-heads-turn-world-rapid-blitz-10440786/"
    title2 = "Goutham Krishna becomes International Master in chess"
    text2 = "Chess player Goutham Krishna won the tournament"
    
    url_lower2 = url2.lower()
    title_lower2 = title2.lower()
    text_lower2 = text2.lower()
    
    is_chess_url2 = any(kw in url_lower2 for kw in chess_keywords)
    is_delhi_content2 = any(kw in title_lower2 or kw in text_lower2 for kw in delhi_keywords)
    
    print("=" * 60)
    print("TEST 2: Chess URL with Chess Content (should pass)")
    print("=" * 60)
    print(f"URL: {url2}")
    print(f"Title: {title2}")
    print(f"is_chess_url: {is_chess_url2}")
    print(f"is_delhi_content: {is_delhi_content2}")
    print(f"Should REJECT: {is_chess_url2 and is_delhi_content2}")
    
    if is_chess_url2 and is_delhi_content2:
        print("❌ VALIDATION FAILED: Would reject this (but shouldn't!)")
    else:
        print("✅ VALIDATION WORKS: Would allow this (correct!)")
    
    print("\n")
    
    # Test case 3: Check with actual Hindi words
    print("=" * 60)
    print("TEST 3: Hindi keyword matching")
    print("=" * 60)
    hindi_text = "दिल्ली में वायु गुणवत्ता खतरनाक स्तर पर पहुँची"
    print(f"Text: {hindi_text}")
    for kw in delhi_keywords:
        if kw in hindi_text.lower():
            print(f"   ✅ Found keyword: {kw}")
        else:
            print(f"   ❌ Not found: {kw}")

if __name__ == "__main__":
    test_chess_url_delhi_content()

