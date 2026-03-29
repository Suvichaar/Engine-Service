# 🧪 Story Generation Testing Guide

## Step 1: Server Start Karein / Start the Server

### Terminal 1: Server Start
```bash
cd D:\Newslabservicev2
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

## Step 2: Health Check / Health Check

### Browser ya Terminal se:
```bash
# Terminal se
curl http://localhost:8000/health

# Ya browser mein
http://localhost:8000/health
```

**Expected Response:**
```json
{"status": "ok"}
```

---

## Step 3: Story Create Karein / Create a Story

### Option A: Test Script Use Karein (Easiest)

**Terminal 2 (naya terminal):**
```bash
cd D:\Newslabservicev2
python test_story_generation.py
```

### Option B: FastAPI Swagger UI (Visual)

1. Browser mein jao: **http://localhost:8000/docs**
2. `POST /stories` endpoint ko expand karein
3. "Try it out" button click karein
4. Request body mein yeh daalein:

```json
{
  "text_prompt": "Photosynthesis is the process by which plants convert light energy into chemical energy. This amazing process happens in the chloroplasts of plant cells.",
  "notes": "Educational content about photosynthesis for students",
  "urls": [],
  "attachments": [],
  "prompt_keywords": ["photosynthesis", "plants", "biology", "science"],
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "Science",
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

5. "Execute" button click karein
6. Response mein `id` copy karein

### Option C: cURL Command

```bash
curl -X POST "http://localhost:8000/stories" ^
  -H "Content-Type: application/json" ^
  -d "{\"text_prompt\": \"Test story about technology\", \"mode\": \"news\", \"template_key\": \"test-news-1\", \"slide_count\": 4, \"category\": \"News\", \"prompt_keywords\": [\"tech\", \"innovation\"]}"
```

---

## Step 4: Story Test Karein / Test Story Components

### Story ID use karke test endpoint call karein:

**Browser:**
```
http://localhost:8000/stories/{story_id}/test
```

**cURL:**
```bash
curl http://localhost:8000/stories/{story_id}/test
```

**Expected Response:**
```json
{
  "story_id": "...",
  "status": "ok",
  "components": {
    "slides": {
      "count": 4,
      "expected": 4,
      "status": "ok"
    },
    "images": {
      "count": 4,
      "status": "ok"
    },
    "voice": {
      "count": 1,
      "status": "ok"
    },
    "html_rendering": {
      "status": "success",
      "html_length": 50000
    }
  },
  "metadata": {
    "mode": "news",
    "category": "News",
    "language": "en",
    "template_key": "test-news-1",
    "created_at": "2024-..."
  }
}
```

---

## Step 5: HTML Get Karein / Get Rendered HTML

### Browser:
```
http://localhost:8000/stories/{story_id}/html
```

**Expected Response:**
```json
{
  "html": "<!DOCTYPE html>...",
  "story_id": "...",
  "template_key": "test-news-1"
}
```

### HTML File Save Karein:

**Python Script:**
```python
import requests
import json

story_id = "your-story-id-here"
response = requests.get(f"http://localhost:8000/stories/{story_id}/html")
data = response.json()

with open(f"story_{story_id}.html", "w", encoding="utf-8") as f:
    f.write(data["html"])

print(f"✅ HTML saved to story_{story_id}.html")
```

---

## Step 6: Story Details Dekhein / View Story Details

```
http://localhost:8000/stories/{story_id}
```

---

## Common Issues / Common Problems

### 1. Template Not Found
**Error:** `FileNotFoundError: Template not found`

**Solution:**
- Check karein: `app/news_template/test-news-1.html` exists hai
- Ya `template_key` sahi hai

### 2. Server Not Running
**Error:** `Connection refused`

**Solution:**
- Server start karein: `uvicorn app.main:app --reload`

### 3. Database Error
**Error:** `sqlite3.OperationalError`

**Solution:**
- Database file permissions check karein
- Ya fresh database create karein

### 4. HTML Rendering Failed
**Error:** `HTML rendering failed`

**Solution:**
- Check logs for detailed error
- Template file valid HTML hai ya nahi
- Placeholders correctly formatted hain

---

## Quick Test Checklist / Quick Test Checklist

- [ ] Server start ho gaya (`http://localhost:8000/health` works)
- [ ] Story create ho gaya (`POST /stories` returns 200)
- [ ] Story ID mil gaya
- [ ] Test endpoint works (`GET /stories/{id}/test`)
- [ ] HTML render ho gaya (`GET /stories/{id}/html`)
- [ ] HTML file save ho gaya aur browser mein open hota hai

---

## Example Test Request / Example Test Request

### Minimal Request (Required fields only):
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4
}
```

### Full Request (All fields):
```json
{
  "text_prompt": "Your story content here",
  "notes": "Additional notes",
  "urls": ["https://example.com/article"],
  "attachments": [],
  "prompt_keywords": ["keyword1", "keyword2"],
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

---

## Next Steps After Testing / Testing ke Baad

1. ✅ HTML output verify karein - browser mein open karke dekhein
2. ✅ Slides count verify karein - expected vs actual
3. ✅ Images verify karein - URLs valid hain ya nahi
4. ✅ Audio verify karein - URLs valid hain ya nahi
5. ✅ Template placeholders verify karein - sab replace ho gaye hain

---

## Tips / Tips

- **FastAPI Swagger UI** use karein for easy testing: `http://localhost:8000/docs`
- **Test script** use karein for automated testing: `python test_story_generation.py`
- **Logs** check karein agar koi error aaye
- **Template files** verify karein - valid HTML hain ya nahi

