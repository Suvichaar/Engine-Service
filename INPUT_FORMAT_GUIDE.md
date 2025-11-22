# Input Format Guide

## Overview

The API supports **two input formats**:
1. **Legacy Format**: Separate fields for URLs, text, notes, etc.
2. **Unified Input Format** (ChatGPT-style): Single `user_input` field that auto-detects content type

Both formats are fully supported and backward compatible.

---

## Field Reference

### Required Fields
- `mode`: `"news"` or `"curious"`
- `template_key`: Template identifier (file name, URL, or S3 path)
- `slide_count`: Number of slides (4, 8, or 10)

### Optional Fields
- `category`: Story category (e.g., "News", "Technology")
- `image_source`: `"pexels"`, `"ai"`, `"custom"`, or `null` (default for news mode)
- `voice_engine`: `"azure_basic"` or `"elevenlabs_pro"` ⚠️ **Important: Must be one of these exact values**

### Legacy Format Fields
- `text_prompt`: Primary text input
- `notes`: Additional notes/context
- `urls`: Array of article URLs
- `attachments`: Array of file references (S3/Blob storage keys)
- `prompt_keywords`: Array of focus keywords

### New Unified Format Field
- `user_input`: Single field that auto-detects URLs, text, or files

---

## Format 1: Legacy Format (Separate Fields)

### Example 1: With URL
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "urls": ["https://indianexpress.com/article/..."],
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

### Example 2: With Text Prompt
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "text_prompt": "Breaking news: New technology breakthrough",
  "notes": "Latest developments in AI research",
  "prompt_keywords": ["technology", "AI", "innovation"],
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

### Example 3: With URL + Additional Context
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "urls": ["https://example.com/article"],
  "notes": "Focus on technology impact",  // Used as guidance
  "prompt_keywords": ["technology", "impact"],
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

---

## Format 2: Unified Input Format (ChatGPT-style)

### Example 1: URL Only
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "https://example.com/article",
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

### Example 2: Multiple URLs
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "https://example.com/article1 https://example.com/article2",
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

### Example 3: Plain Text
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "Breaking news: New AI breakthrough in technology. Scientists have developed a revolutionary algorithm.",
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

### Example 4: URL + Text (Mixed)
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "https://example.com/article Focus on technology impact",
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

### Example 5: Template from URL
```json
{
  "mode": "news",
  "template_key": "https://example.com/template.html",
  "slide_count": 4,
  "category": "News",
  "user_input": "https://example.com/article",
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

---

## URL Priority Logic

When URLs are provided (either via `urls` field or detected in `user_input`):
- ✅ **URL content is used as primary source** (article text is extracted)
- ✅ **`notes` is used as additional context/guidance** (if provided)
- ❌ **`text_prompt` is skipped** (URL content takes precedence)
- ✅ **`prompt_keywords` are always included** (for story angle/focus)

When NO URLs are provided:
- ✅ **`text_prompt` is used as primary source**
- ✅ **`notes` is used as additional context**
- ✅ **`prompt_keywords` are included**

---

## Voice Engine Options

⚠️ **Important**: `voice_engine` must be exactly one of:
- `"azure_basic"` - Azure Text-to-Speech (basic)
- `"elevenlabs_pro"` - ElevenLabs Pro voice synthesis

Invalid values will be rejected.

---

## Template Key Formats

The `template_key` field supports multiple formats:

1. **File Name**: `"test-news-1"` → Loads from `app/news_template/test-news-1.html`
2. **HTTP/HTTPS URL**: `"https://example.com/template.html"` → Loads from URL
3. **S3 URI**: `"s3://bucket/template.html"` → Loads from S3

The system **auto-detects** the format based on the prefix.

---

## Image Source Options

- `"pexels"` - Use Pexels stock images
- `"ai"` - Generate AI images
- `"custom"` - Use custom uploaded images
- `null` or not provided (News mode only) - Use default `polariscover.png`

---

## Best Practices

### For News Mode with URLs:
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "https://example.com/article",
  "image_source": null,  // Will use default polariscover.png
  "voice_engine": "azure_basic"
}
```

### For News Mode with Text:
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "Breaking news: Important story content...",
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

### For Mixed Input (URL + Guidance):
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "https://example.com/article Emphasize human interest angle",
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

---

## Testing

Use the test script to verify both formats:
```bash
python test_unified_input.py
```

Make sure the server is running on `http://localhost:8000`.

