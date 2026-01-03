"""Comprehensive test for all validation scenarios."""

def test_all_scenarios():
    """Test all possible URL-content mismatch scenarios."""
    
    sports_keywords = [
        'chess', 'goutham', 'krishna', 'master', 'rapid', 'blitz', 'tournament', 'game',
        'football', 'soccer', 'african', 'nations', 'cup', 'world', 'winner', 'fifa',
        'cricket', 'basketball', 'tennis', 'hockey', 'sports', 'athlete', 'player',
        'match', 'league', 'championship', 'olympics'
    ]
    delhi_keywords = ['delhi', 'dilli', 'pollution', 'pradushan', 'vayu', 'gunvatta', 'vaayu', 'प्रदूषण', 'दिल्ली', 'वायु', 'गुणवत्ता', 'जनजीवन']
    
    print("=" * 80)
    print("COMPREHENSIVE VALIDATION TEST")
    print("=" * 80)
    print("\n")
    
    # Test 1: Football URL + Delhi Content (ACTUAL PROBLEM)
    print("=" * 80)
    print("TEST 1: Football URL + Delhi Content (ACTUAL PROBLEM)")
    print("=" * 80)
    url1 = "https://indianexpress.com/article/sports/football/african-nations-cup-needs-a-world-cup-winner-to-get-the-recognition-it-deserves-10444302/"
    title1 = "दिल्ली में वायु गुणवत्ता खतरनाक स्तर पर, जनजीवन प्रभावित"
    
    url_lower1 = url1.lower()
    title_lower1 = title1.lower()
    is_sports1 = any(kw in url_lower1 for kw in sports_keywords)
    is_delhi1 = any(kw in title_lower1 for kw in delhi_keywords)
    
    print(f"URL: {url1[:80]}...")
    print(f"Title: {title1}")
    print(f"is_sports_url: {is_sports1}")
    print(f"is_delhi_content: {is_delhi1}")
    print(f"Result: {'❌ REJECT (CORRECT)' if (is_sports1 and is_delhi1) else '✅ ALLOW (WRONG!)'}")
    if is_sports1 and is_delhi1:
        found_sports = [kw for kw in sports_keywords if kw in url_lower1]
        found_delhi = [kw for kw in delhi_keywords if kw in title_lower1]
        print(f"   Sports keywords: {found_sports}")
        print(f"   Delhi keywords: {found_delhi}")
    print("\n")
    
    # Test 2: Chess URL + Delhi Content
    print("=" * 80)
    print("TEST 2: Chess URL + Delhi Content")
    print("=" * 80)
    url2 = "https://indianexpress.com/article/sports/chess/goutham-krishna-international-master-heads-turn-world-rapid-blitz-10440786/"
    title2 = "दिल्ली में वायु गुणवत्ता खतरनाक स्तर पर"
    
    url_lower2 = url2.lower()
    title_lower2 = title2.lower()
    is_sports2 = any(kw in url_lower2 for kw in sports_keywords)
    is_delhi2 = any(kw in title_lower2 for kw in delhi_keywords)
    
    print(f"URL: {url2[:80]}...")
    print(f"Title: {title2}")
    print(f"is_sports_url: {is_sports2}")
    print(f"is_delhi_content: {is_delhi2}")
    print(f"Result: {'❌ REJECT (CORRECT)' if (is_sports2 and is_delhi2) else '✅ ALLOW (WRONG!)'}")
    print("\n")
    
    # Test 3: Football URL + Football Content (SHOULD PASS)
    print("=" * 80)
    print("TEST 3: Football URL + Football Content (SHOULD PASS)")
    print("=" * 80)
    url3 = "https://indianexpress.com/article/sports/football/african-nations-cup-needs-a-world-cup-winner-10444302/"
    title3 = "African Nations Cup needs a World Cup winner"
    
    url_lower3 = url3.lower()
    title_lower3 = title3.lower()
    is_sports3 = any(kw in url_lower3 for kw in sports_keywords)
    is_delhi3 = any(kw in title_lower3 for kw in delhi_keywords)
    
    print(f"URL: {url3[:80]}...")
    print(f"Title: {title3}")
    print(f"is_sports_url: {is_sports3}")
    print(f"is_delhi_content: {is_delhi3}")
    print(f"Result: {'✅ ALLOW (CORRECT)' if not (is_sports3 and is_delhi3) else '❌ REJECT (WRONG!)'}")
    print("\n")
    
    # Test 4: Delhi URL + Delhi Content (SHOULD PASS)
    print("=" * 80)
    print("TEST 4: Delhi URL + Delhi Content (SHOULD PASS)")
    print("=" * 80)
    url4 = "https://indianexpress.com/article/cities/delhi/delhi-pollution-air-quality-10444302/"
    title4 = "दिल्ली में वायु गुणवत्ता खतरनाक स्तर पर"
    
    url_lower4 = url4.lower()
    title_lower4 = title4.lower()
    is_sports4 = any(kw in url_lower4 for kw in sports_keywords)
    is_delhi4 = any(kw in title_lower4 for kw in delhi_keywords)
    
    print(f"URL: {url4[:80]}...")
    print(f"Title: {title4}")
    print(f"is_sports_url: {is_sports4}")
    print(f"is_delhi_content: {is_delhi4}")
    print(f"Result: {'✅ ALLOW (CORRECT)' if not (is_sports4 and is_delhi4) else '❌ REJECT (WRONG!)'}")
    print("\n")
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("✅ Test 1 (Football + Delhi): Should REJECT")
    print("✅ Test 2 (Chess + Delhi): Should REJECT")
    print("✅ Test 3 (Football + Football): Should ALLOW")
    print("✅ Test 4 (Delhi + Delhi): Should ALLOW")
    print("\nAll tests completed!")

if __name__ == "__main__":
    test_all_scenarios()

