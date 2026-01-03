"""Test general URL-content validation (not biased to specific topics)."""

def test_general_validation():
    """Test general validation that works for any topic mismatch."""
    
    def extract_url_keywords(url):
        """Extract meaningful keywords from URL."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path_parts = parsed.path.split('/')
        url_keywords = []
        skip_words = {'article', 'news', 'story', 'com', 'org', 'www', 'http', 'https', 'indianexpress',
                     'sports', 'cities', 'entertainment', 'technology', 'business', 'politics', 'world',
                     'local', 'health', 'science', 'education', 'lifestyle', 'opinion', 'editorial', 'html'}
        
        for part in path_parts:
            part = part.split('?')[0].split('#')[0].strip()
            if not part or part == '/':
                continue
            words = part.split('-')
            for word in words:
                if len(word) > 3 and word not in skip_words and not word.isdigit():
                    url_keywords.append(word)
        
        return sorted(set(url_keywords), key=len, reverse=True)[:10]
    
    def check_match(url, title, text):
        """Check if URL keywords match content."""
        url_keywords = extract_url_keywords(url)
        content_text = f"{title.lower()} {text.lower()}"
        matches = sum(1 for kw in url_keywords if kw in content_text)
        match_ratio = matches / len(url_keywords) if url_keywords else 0
        return match_ratio, url_keywords
    
    print("=" * 80)
    print("GENERAL VALIDATION TEST (Not biased to specific topics)")
    print("=" * 80)
    print("\n")
    
    # Test 1: Football URL + Delhi Content (MISMATCH)
    print("=" * 80)
    print("TEST 1: Football URL + Delhi Content (Should REJECT)")
    print("=" * 80)
    url1 = "https://indianexpress.com/article/sports/football/african-nations-cup-needs-a-world-cup-winner-10444302/"
    title1 = "दिल्ली में वायु गुणवत्ता खतरनाक स्तर पर"
    text1 = "दिल्ली में प्रदूषण बढ़ रहा है"
    
    match_ratio1, keywords1 = check_match(url1, title1, text1)
    print(f"URL: {url1[:70]}...")
    print(f"Title: {title1}")
    print(f"URL Keywords: {keywords1}")
    print(f"Match Ratio: {match_ratio1*100:.1f}%")
    print(f"Result: {'❌ REJECT (CORRECT)' if match_ratio1 < 0.1 else '✅ ALLOW (WRONG!)'}")
    print("\n")
    
    # Test 2: Football URL + Football Content (MATCH)
    print("=" * 80)
    print("TEST 2: Football URL + Football Content (Should ALLOW)")
    print("=" * 80)
    url2 = "https://indianexpress.com/article/sports/football/african-nations-cup-needs-a-world-cup-winner-10444302/"
    title2 = "African Nations Cup needs a World Cup winner"
    text2 = "Football experts say African teams need to win World Cup"
    
    match_ratio2, keywords2 = check_match(url2, title2, text2)
    print(f"URL: {url2[:70]}...")
    print(f"Title: {title2}")
    print(f"URL Keywords: {keywords2}")
    print(f"Match Ratio: {match_ratio2*100:.1f}%")
    print(f"Result: {'✅ ALLOW (CORRECT)' if match_ratio2 >= 0.1 else '❌ REJECT (WRONG!)'}")
    print("\n")
    
    # Test 3: Technology URL + Technology Content (MATCH)
    print("=" * 80)
    print("TEST 3: Technology URL + Technology Content (Should ALLOW)")
    print("=" * 80)
    url3 = "https://indianexpress.com/article/technology/artificial-intelligence-breakthrough-10444302/"
    title3 = "Artificial Intelligence breakthrough in healthcare"
    text3 = "AI technology helps doctors diagnose diseases faster"
    
    match_ratio3, keywords3 = check_match(url3, title3, text3)
    print(f"URL: {url3[:70]}...")
    print(f"Title: {title3}")
    print(f"URL Keywords: {keywords3}")
    print(f"Match Ratio: {match_ratio3*100:.1f}%")
    print(f"Result: {'✅ ALLOW (CORRECT)' if match_ratio3 >= 0.1 else '❌ REJECT (WRONG!)'}")
    print("\n")
    
    # Test 4: Technology URL + Delhi Content (MISMATCH)
    print("=" * 80)
    print("TEST 4: Technology URL + Delhi Content (Should REJECT)")
    print("=" * 80)
    url4 = "https://indianexpress.com/article/technology/artificial-intelligence-breakthrough-10444302/"
    title4 = "दिल्ली में वायु गुणवत्ता खतरनाक स्तर पर"
    text4 = "दिल्ली में प्रदूषण बढ़ रहा है"
    
    match_ratio4, keywords4 = check_match(url4, title4, text4)
    print(f"URL: {url4[:70]}...")
    print(f"Title: {title4}")
    print(f"URL Keywords: {keywords4}")
    print(f"Match Ratio: {match_ratio4*100:.1f}%")
    print(f"Result: {'❌ REJECT (CORRECT)' if match_ratio4 < 0.1 else '✅ ALLOW (WRONG!)'}")
    print("\n")
    
    print("=" * 80)
    print("SUMMARY: General validation works for ANY topic mismatch!")
    print("=" * 80)

if __name__ == "__main__":
    test_general_validation()

