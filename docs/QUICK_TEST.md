# ⚡ Quick Test Guide - Step by Step

## 🚀 Step 1: Server Start Karein

**Terminal 1 mein yeh command run karein:**
```bash
cd D:\Newslabservicev2
uvicorn app.main:app --reload
```

**Aapko yeh dikhna chahiye:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

---

## 🏥 Step 2: Health Check

**Browser mein jao:**
```
http://localhost:8000/health
```

**Ya Terminal 2 mein:**
```bash
curl http://localhost:8000/health
```

**Expected:** `{"status": "ok"}`

---

## 📝 Step 3: Story Create Karein

### Option A: Swagger UI (Easiest) 🌐

1. Browser mein jao: **http://localhost:8000/docs**
2. `POST /stories` ko click karein
3. "Try it out" button click karein
4. Request body mein yeh paste karein:

```json
{
  "text_prompt": "Photosynthesis is how plants make food using sunlight",
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "Science",
  "prompt_keywords": ["science", "plants"]
}
```

5. "Execute" click karein
6. Response mein `"id"` copy karein (yeh aapka story_id hai)

### Option B: Test Script 🐍

**Terminal 2 mein:**
```bash
cd D:\Newslabservicev2
python test_story_generation.py
```

Yeh automatically:
- Story create karega
- Test karega
- HTML generate karega
- File save karega

---

## 🔍 Step 4: Story Test Karein

**Browser mein jao (story_id use karke):**
```
http://localhost:8000/stories/{story_id}/test
```

**Expected Response:**
```json
{
  "status": "ok",
  "components": {
    "slides": {"count": 4, "status": "ok"},
    "images": {"count": 4, "status": "ok"},
    "voice": {"count": 1, "status": "ok"},
    "html_rendering": {"status": "success"}
  }
}
```

---

## 📄 Step 5: HTML Dekhein

**Browser mein:**
```
http://localhost:8000/stories/{story_id}/html
```

**Response mein HTML milega.** 
Agar HTML file save karni ho, toh:

**Python script:**
```python
import requests
story_id = "your-story-id"
response = requests.get(f"http://localhost:8000/stories/{story_id}/html")
with open(f"story_{story_id}.html", "w", encoding="utf-8") as f:
    f.write(response.json()["html"])
print("✅ HTML saved!")
```

---

## ✅ Success Indicators / Success के लक्षण

- ✅ Server start ho gaya
- ✅ Health check `{"status": "ok"}` return karta hai
- ✅ Story create ho gaya (200 status)
- ✅ Story ID mil gaya
- ✅ Test endpoint sab components "ok" dikhata hai
- ✅ HTML render ho gaya (html_length > 0)

---

## ❌ Common Errors / Common Errors

### 1. Template Not Found
**Error:** `FileNotFoundError: Template not found: test-news-1`

**Fix:**
- Check: `app/news_template/test-news-1.html` exists hai
- Ya `template_key` change karein

### 2. Connection Refused
**Error:** `Connection refused`

**Fix:**
- Server start karein: `uvicorn app.main:app --reload`

### 3. Import Error
**Error:** `ModuleNotFoundError`

**Fix:**
```bash
pip install -r requirements.txt
```

---

## 🎯 Quick Commands Summary

```bash
# 1. Server start
uvicorn app.main:app --reload

# 2. Health check
curl http://localhost:8000/health

# 3. Test script
python test_story_generation.py

# 4. Story test (replace {id})
curl http://localhost:8000/stories/{id}/test

# 5. Get HTML (replace {id})
curl http://localhost:8000/stories/{id}/html
```

---

## 📊 What to Check / क्या Check करें

1. **Slides Count:** Expected vs Actual match kare
2. **Images:** At least 1 image asset ho
3. **Voice:** At least 1 voice asset ho
4. **HTML:** HTML successfully render ho (no errors)
5. **Template:** Correct template use ho raha hai

---

**Ready? Server start karein aur test karein! 🚀**

