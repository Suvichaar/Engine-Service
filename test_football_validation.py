"""Test script to verify Football URL vs Delhi content validation."""

def test_football_url_delhi_content():
    """Test if validation catches football URL with Delhi content."""
    
    # Test case: Football URL with Delhi title (the actual problem)
    url = "https://indianexpress.com/article/sports/football/african-nations-cup-needs-a-world-cup-winner-to-get-the-recognition-it-deserves-10444302/"
    title = "दिल्ली में वायु गुणवत्ता खतरनाक स्तर पर, जनजीवन प्रभावित"
    text = "दिल्ली में प्रदूषण बढ़ रहा है"
    
    url_lower = url.lower()
    title_lower = title.lower()
    text_lower = text.lower()
    
    sports_keywords = [
        'chess', 'goutham', 'krishna', 'master', 'rapid', 'blitz', 'tournament', 'game',
        'football', 'soccer', 'african', 'nations', 'cup', 'world', 'winner', 'fifa',
        'cricket', 'basketball', 'tennis', 'hockey', 'sports', 'athlete', 'player',
        'match', 'league', 'championship', 'olympics'
    ]
    delhi_keywords = ['delhi', 'dilli', 'pollution', 'pradushan', 'vayu', 'gunvatta', 'vaayu', 'प्रदूषण', 'दिल्ली', 'वायु', 'गुणवत्ता', 'जनजीवन']
    
    is_sports_url = any(kw in url_lower for kw in sports_keywords)
    is_delhi_content = any(kw in title_lower or kw in text_lower for kw in delhi_keywords)
    
    print("=" * 60)
    print("TEST: Football URL with Delhi Content")
    print("=" * 60)
    print(f"URL: {url}")
    print(f"Title: {title}")
    print(f"is_sports_url: {is_sports_url}")
    print(f"is_delhi_content: {is_delhi_content}")
    print(f"Should REJECT: {is_sports_url and is_delhi_content}")
    
    if is_sports_url and is_delhi_content:
        print("✅ VALIDATION WORKS: Would reject this!")
        found_sports = [kw for kw in sports_keywords if kw in url_lower]
        found_delhi = [kw for kw in delhi_keywords if kw in title_lower or kw in text_lower]
        print(f"   Sports keywords found: {found_sports}")
        print(f"   Delhi keywords found: {found_delhi}")
    else:
        print("❌ VALIDATION FAILED: Would NOT reject this!")
        if not is_sports_url:
            print("   Problem: Sports keywords not detected in URL")
        if not is_delhi_content:
            print("   Problem: Delhi keywords not detected in content")

if __name__ == "__main__":
    test_football_url_delhi_content()

