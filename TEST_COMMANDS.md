# Testing Commands - Template-Specific Slide Generators

## Quick Start

### Option 1: Automated Test Script (Recommended)

#### Step 1: Start Server
```bash
# Terminal 1 - Start FastAPI server
uvicorn app.main:app --reload
```

#### Step 2: Run Test Script
```bash
# Terminal 2 - Run automated tests
python test_template_generators.py
```

This will test all 4 scenarios:
- test-news-1 (File Name)
- test-news-2 (File Name)
- test-news-1 (URL Template Key)
- test-news-2 (URL Template Key)

---

### Option 2: Manual Testing with cURL

#### Step 1: Start Server
```bash
uvicorn app.main:app --reload
```

#### Step 2: Test test-news-1 Template
```bash
curl -X POST http://localhost:8000/stories \
  -H "Content-Type: application/json" \
  -d @example_template_test-news-1.json
```

#### Step 3: Test test-news-2 Template
```bash
curl -X POST http://localhost:8000/stories \
  -H "Content-Type: application/json" \
  -d @example_template_test-news-2.json
```

#### Step 4: Test URL Template Key
```bash
curl -X POST http://localhost:8000/stories \
  -H "Content-Type: application/json" \
  -d @example_template_url_test-news-1.json
```

---

### Option 3: Python Interactive Testing

#### Step 1: Start Server
```bash
uvicorn app.main:app --reload
```

#### Step 2: Run Python Script
```python
import requests
import json

# Load test file
with open("example_template_test-news-1.json", "r") as f:
    payload = json.load(f)

# Send request
response = requests.post("http://localhost:8000/stories", json=payload)
print("Status:", response.status_code)
print("Response:", json.dumps(response.json(), indent=2))

# Check HTML file
story_id = response.json()["id"]
html_file = f"output/{story_id}.html"
print(f"\nHTML file: {html_file}")
```

---

## Individual Test Commands

### Test 1: test-news-1 with File Name
```bash
curl -X POST http://localhost:8000/stories \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "news",
    "template_key": "test-news-1",
    "slide_count": 4,
    "category": "News",
    "user_input": "https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/",
    "image_source": "pexels",
    "voice_engine": "azure_basic"
  }'
```

### Test 2: test-news-2 with File Name
```bash
curl -X POST http://localhost:8000/stories \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "news",
    "template_key": "test-news-2",
    "slide_count": 4,
    "category": "News",
    "user_input": "https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/",
    "image_source": "pexels",
    "voice_engine": "azure_basic"
  }'
```

### Test 3: URL Template Key (Auto-extracts to test-news-1)
```bash
curl -X POST http://localhost:8000/stories \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "news",
    "template_key": "https://example.com/templates/test-news-1.html",
    "slide_count": 4,
    "category": "News",
    "user_input": "https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/",
    "image_source": "pexels",
    "voice_engine": "azure_basic"
  }'
```

---

## Verify Results

### Check HTML File
```bash
# List output files
ls -lh output/

# View HTML file (replace {story_id} with actual ID)
cat output/{story_id}.html | head -50

# Check for template structure
grep -n "centered-container" output/{story_id}.html
grep -n "text1" output/{story_id}.html
grep -n "INSERT_SLIDES_HERE" output/{story_id}.html  # Should NOT be found
```

### Check Story via API
```bash
# Get story details (replace {story_id} with actual ID)
curl http://localhost:8000/stories/{story_id}

# Get rendered HTML
curl http://localhost:8000/stories/{story_id}/html
```

---

## Expected Output

### Successful Response
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "slide_deck": {
    "slides": [...]
  },
  "image_assets": [...],
  "voice_assets": [...]
}
```

### HTML File Location
```
output/550e8400-e29b-41d4-a716-446655440000.html
```

### HTML File Should Contain
- ✅ `class="centered-container"` (for test-news-1)
- ✅ `class="text1"` (for test-news-1)
- ✅ `<amp-story-page>` elements
- ✅ `<!--INSERT_SLIDES_HERE-->` should be REMOVED (replaced with slides)

---

## Troubleshooting

### Server Not Running
```bash
# Check if server is running
curl http://localhost:8000/health

# Should return: {"status":"ok"}
```

### Port Already in Use
```bash
# Use different port
uvicorn app.main:app --reload --port 8001
```

### Template Not Found
```bash
# Check if template file exists
ls app/news_template/test-news-1.html
ls app/news_template/test-news-2.html
```

### HTML File Not Created
```bash
# Check output directory
ls -la output/

# Create if missing
mkdir -p output
```

---

## Quick Test (All-in-One)

```bash
# Terminal 1
uvicorn app.main:app --reload

# Terminal 2
python test_template_generators.py
```

That's it! 🚀

