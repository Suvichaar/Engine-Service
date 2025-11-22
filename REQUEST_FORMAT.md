# 📋 Request Format Guide

## ✅ Correct Request Format / सही Request Format

### Required Fields (जरूरी):
- `mode`: `"curious"` ya `"news"` (string)
- `template_key`: Template file name without `.html` (e.g., `"test-news-1"`)
- `slide_count`: **Minimum 4** (integer: 4, 8, ya 10)

### Optional Fields (वैकल्पिक):
- `category`: String (e.g., `"Art"`, `"News"`, `"Science"`)
- `text_prompt`: String (main content)
- `notes`: String (additional notes)
- `urls`: Array of valid URLs (e.g., `["https://example.com"]`)
- `attachments`: Array of strings (file identifiers)
- `prompt_keywords`: Array of strings (e.g., `["keyword1", "keyword2"]`)
- `image_source`: `"ai"` ya `"pexels"` ya `"custom"` (exactly one of these)
- `voice_engine`: `"elevenlabs_pro"` ya `"azure_basic"` (exactly one of these)

---

## ❌ Common Mistakes / Common गलतियाँ

### 1. Invalid slide_count
```json
❌ "slide_count": 0    // Minimum 4 required
❌ "slide_count": 2    // Minimum 4 required
✅ "slide_count": 4    // Correct
✅ "slide_count": 8    // Correct
✅ "slide_count": 10   // Correct
```

### 2. Invalid template_key
```json
❌ "template_key": "string"           // Not a real template
✅ "template_key": "test-news-1"      // Real template file
✅ "template_key": "test-news-2"      // Real template file
```

### 3. Invalid image_source
```json
❌ "image_source": "string"           // Invalid
❌ "image_source": "google"           // Invalid
✅ "image_source": "ai"               // Valid
✅ "image_source": "pexels"           // Valid
✅ "image_source": "custom"           // Valid
```

### 4. Invalid voice_engine
```json
❌ "voice_engine": "string"           // Invalid
❌ "voice_engine": "google_tts"        // Invalid
✅ "voice_engine": "elevenlabs_pro"   // Valid
✅ "voice_engine": "azure_basic"      // Valid
```

### 5. Invalid mode
```json
❌ "mode": "string"                   // Invalid
❌ "mode": "story"                    // Invalid
✅ "mode": "curious"                  // Valid
✅ "mode": "news"                     // Valid
```

---

## 📝 Example Requests / Example Requests

### Minimal Request (Minimum fields only):
```json
{
  "mode": "curious",
  "template_key": "test-news-1",
  "slide_count": 4
}
```

### Full Request (All fields):
```json
{
  "mode": "curious",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "Art",
  "text_prompt": "The history of Renaissance art",
  "notes": "Focus on famous artists",
  "urls": ["https://example.com/article"],
  "attachments": [],
  "prompt_keywords": ["art", "history", "renaissance"],
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

### News Mode Request:
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "text_prompt": "Breaking news about technology",
  "prompt_keywords": ["tech", "innovation"],
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

---

## 🔍 Validation Rules / Validation Rules

1. **slide_count**: Must be 4, 8, or 10
2. **template_key**: Must match existing template file (without `.html`)
3. **image_source**: Must be exactly `"ai"`, `"pexels"`, or `"custom"` (if provided)
4. **voice_engine**: Must be exactly `"elevenlabs_pro"` or `"azure_basic"` (if provided)
5. **mode**: Must be exactly `"curious"` or `"news"`
6. **urls**: Must be valid HTTP/HTTPS URLs

---

## 📂 Available Templates / Available Templates

Check `app/news_template/` folder:
- `test-news-1.html` → Use `"template_key": "test-news-1"`
- `test-news-2.html` → Use `"template_key": "test-news-2"`

---

## 🚀 Quick Test Request

Copy-paste ready request:

```json
{
  "mode": "curious",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "Art",
  "text_prompt": "Renaissance art history",
  "prompt_keywords": ["art", "history"],
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

