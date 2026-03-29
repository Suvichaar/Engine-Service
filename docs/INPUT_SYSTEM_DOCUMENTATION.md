# Complete Input System Documentation

## Overview

This document provides a comprehensive guide to the input system for the Story Generation API, covering all input fields, their purposes, usage patterns, and how they interact with the backend.

---

## Table of Contents

1. [Input Fields Overview](#input-fields-overview)
2. [Mode-Specific Input Requirements](#mode-specific-input-requirements)
3. [Content Input Methods](#content-input-methods)
4. [Image Source Configuration](#image-source-configuration)
5. [Attachment Handling](#attachment-handling)
6. [Complete Input Flow](#complete-input-flow)
7. [Examples by Use Case](#examples-by-use-case)
8. [Best Practices](#best-practices)

---

## Input Fields Overview

### Core Required Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | `string` | ✅ Yes | Story mode: `"news"` or `"curious"` |
| `template_key` | `string` | ✅ Yes | Template identifier (e.g., `"test-news-1"`, `"curious-template-1"`) |
| `slide_count` | `integer` | ✅ Yes | Number of slides (News: 4-10, Curious: 7-15) |

### Content Input Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_input` | `string` | ⚠️ Conditional | Unified input: URL, text, or file reference. Auto-detected. |
| `attachments` | `array<string>` | ❌ No | Array of S3 URLs or HTTP URLs for files/images |

### Image Configuration Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `image_source` | `string \| null` | ❌ No | Image source for slide backgrounds |
| `prompt_keywords` | `array<string>` | ⚠️ Conditional | Keywords for AI/Pexels image generation (Curious mode only) |

### Other Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | `string` | ❌ No | Story category (e.g., "News", "Technology", "Education") |
| `voice_engine` | `string` | ❌ No | TTS engine: `"azure_basic"` or `"elevenlabs_pro"` |

---

## Mode-Specific Input Requirements

### News Mode

#### Content Input
- **`user_input`**: 
  - ✅ Article URL (e.g., `https://indianexpress.com/article/...`)
  - ✅ Article text content (pasted directly)
  - ✅ Both URL and text (mixed)

#### Attachments (Optional)
- **Purpose**: Content extraction via OCR
- **Accepted Types**: 
  - Documents: PDF, DOC, DOCX
  - Images: JPG, JPEG, PNG, WEBP
- **Usage**: Upload documents or article photos to extract text content
- **Processing**: Files are uploaded to S3, then processed via Azure Document Intelligence (OCR)

#### Image Source (Background Images)
- **Options**:
  - `null` (default): Use default news images
  - `"custom"`: Upload custom image for all slide backgrounds
- **Custom Image**:
  - Single image uploaded
  - Used for all slides
  - Resized to 720x1280 (portrait) on S3
  - CDN URL replaces placeholder in HTML

#### Categories
- Predefined dropdown options:
  - News, Technology, Sports, Politics, Business, Entertainment, Science, Health, World, Local

#### Example News Mode Input
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "https://indianexpress.com/article/technology/ai-breakthrough/",
  "category": "Technology",
  "image_source": null,
  "voice_engine": "azure_basic"
}
```

### Curious Mode

#### Content Input
- **`user_input`**: 
  - ✅ Topic/question (e.g., `"How does quantum computing work?"`)
  - ✅ Keywords (e.g., `"quantum, computing, physics"`)
  - ✅ Educational content description

#### Attachments (Optional)
- **Purpose**: Content extraction via OCR
- **Accepted Types**: 
  - Documents: PDF, DOC, DOCX
  - Images: JPG, JPEG, PNG, WEBP
- **Usage**: Upload images or documents to extract content for educational story
- **Processing**: Files are uploaded to S3, then processed via Azure Document Intelligence (OCR)

#### Image Source (Background Images)
- **Options**:
  - `"ai"`: AI-generated images (DALL-E 3)
  - `"pexels"`: Stock images from Pexels
  - `"custom"`: Upload custom images
- **AI/Pexels**:
  - Requires `prompt_keywords` array
  - Keywords used for image generation/search
- **Custom Images**:
  - Must upload **exactly `slide_count` images** (one per slide)
  - Each image resized to 720x1280 (portrait) on S3
  - CDN URLs replace placeholders in HTML

#### Categories
- Predefined dropdown options:
  - Education, Science, Technology, History, Nature, Space, Mathematics, Physics, Biology, Chemistry, General Knowledge

#### Example Curious Mode Input
```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 7,
  "user_input": "How does quantum computing work?",
  "category": "Science",
  "image_source": "ai",
  "prompt_keywords": ["quantum", "computing", "science", "physics"],
  "voice_engine": "azure_basic"
}
```

---

## Content Input Methods

### Method 1: URL Input

**Use Case**: Extract content from online articles

```json
{
  "user_input": "https://indianexpress.com/article/technology/ai-breakthrough/"
}
```

**How It Works**:
1. Backend detects URL in `user_input`
2. Extracts article content using `newspaper3k`
3. Processes content for story generation

### Method 2: Text Input

**Use Case**: Direct text content

```json
{
  "user_input": "Breaking news: Scientists have made a breakthrough in AI research..."
}
```

**How It Works**:
1. Backend detects text (not URL)
2. Uses text directly for story generation

### Method 3: Attachment Input

**Use Case**: Extract content from documents/images

```json
{
  "attachments": [
    "s3://bucket/media/attachments/20250121/uuid-123.pdf",
    "s3://bucket/media/attachments/20250121/uuid-456.jpg"
  ]
}
```

**How It Works**:
1. Files uploaded to S3 (via Streamlit frontend)
2. Backend loads files from S3 URLs
3. Processes via Azure Document Intelligence (OCR)
4. Extracted text used for story generation

### Method 4: Mixed Input

**Use Case**: URL + additional context

```json
{
  "user_input": "https://example.com/article",
  "attachments": ["s3://bucket/supplementary-doc.pdf"]
}
```

**How It Works**:
1. URL content extracted
2. Attachment content extracted via OCR
3. Both combined for comprehensive story

---

## Image Source Configuration

### News Mode Image Sources

#### Default Images (`image_source: null`)
- **Behavior**: Uses predefined default images
- **No upload required**
- **Images**: Pre-configured in template

#### Custom Image (`image_source: "custom"`)
- **Upload**: Single image file
- **Processing**:
  1. Upload to S3: `s3://bucket/media/images/backgrounds/YYYYMMDD/uuid.jpg`
  2. Resized to 720x1280 (portrait)
  3. CDN URL generated: `https://media.suvichaar.org/...`
  4. Used for all slide backgrounds
- **S3 Path**: `media/images/backgrounds/{date}/{uuid}.{ext}`
- **CDN URL**: Replaces `{{potraitcoverurl}}` and `{{s1image1}}`, `{{s2image1}}`, etc. in template

### Curious Mode Image Sources

#### AI Generated (`image_source: "ai"`)
- **Requires**: `prompt_keywords` array
- **Process**:
  1. Keywords combined with slide content
  2. DALL-E 3 generates images
  3. Images uploaded to S3
  4. CDN URLs replace placeholders
- **Example**:
```json
{
  "image_source": "ai",
  "prompt_keywords": ["quantum", "computing", "science"]
}
```

#### Pexels Stock (`image_source: "pexels"`)
- **Requires**: `prompt_keywords` array
- **Process**:
  1. Keywords used to search Pexels
  2. Relevant images selected
  3. Images uploaded to S3
  4. CDN URLs replace placeholders
- **Example**:
```json
{
  "image_source": "pexels",
  "prompt_keywords": ["nature", "forest", "trees"]
}
```

#### Custom Images (`image_source: "custom"`)
- **Requires**: Exactly `slide_count` images
- **Upload**: Multiple image files (one per slide)
- **Processing**:
  1. Each image uploaded to S3: `s3://bucket/media/images/backgrounds/YYYYMMDD/uuid-{n}.jpg`
  2. Each resized to 720x1280 (portrait)
  3. CDN URLs generated
  4. Each slide gets its own background image
- **S3 Path**: `media/images/backgrounds/{date}/uuid-{slide_number}.{ext}`
- **CDN URLs**: Replace `{{s1image1}}`, `{{s2image1}}`, etc. in template

---

## Attachment Handling

### Attachment Types

#### 1. Content Extraction Attachments
- **Purpose**: Extract text content via OCR
- **Types**: PDF, DOC, DOCX, Images (JPG, PNG, WEBP)
- **Processing**: Azure Document Intelligence OCR
- **Result**: Text extracted and used for story generation

#### 2. Background Image Attachments
- **Purpose**: Use as slide backgrounds
- **Types**: Images only (JPG, PNG, WEBP)
- **Processing**: 
  - Upload to S3
  - Resize to 720x1280 (portrait)
  - Generate CDN URL
  - Replace template placeholders

### S3 Upload Flow

```
User Uploads File
    ↓
Streamlit Frontend
    ↓
Upload to S3
    ↓
Generate S3 URL (s3://bucket/key)
    ↓
Add to payload.attachments[]
    ↓
Send to FastAPI Backend
    ↓
Backend loads from S3
    ↓
Process (OCR or Image Processing)
```

### S3 Path Structure

```
media/
├── attachments/
│   └── YYYYMMDD/
│       ├── uuid-1.pdf
│       └── uuid-2.jpg
└── images/
    └── backgrounds/
        └── YYYYMMDD/
            ├── uuid-1.jpg  (News: single image)
            ├── uuid-1.jpg  (Curious: slide 1)
            ├── uuid-2.jpg  (Curious: slide 2)
            └── ...
```

---

## Complete Input Flow

### News Mode Flow

```
1. User Input
   ├─ Option A: Article URL
   │  └─> Extract content via newspaper3k
   ├─ Option B: Text content
   │  └─> Use directly
   └─ Option C: Attachments (docs/images)
      └─> OCR via Azure Document Intelligence

2. Image Source
   ├─ Default (null)
   │  └─> Use template default images
   └─ Custom
      └─> Upload 1 image → S3 → Resize → CDN URL

3. Story Generation
   └─> Create slides with content + images
```

### Curious Mode Flow

```
1. User Input
   ├─ Option A: Topic/keywords
   │  └─> Generate educational content
   ├─ Option B: Attachments (docs/images)
   │  └─> OCR via Azure Document Intelligence
   └─ Option C: Both

2. Image Source
   ├─ AI
   │  └─> Generate images from prompt_keywords + content
   ├─ Pexels
   │  └─> Search images from prompt_keywords
   └─ Custom
      └─> Upload {slide_count} images → S3 → Resize → CDN URLs

3. Story Generation
   └─> Create slides with content + images
```

---

## Examples by Use Case

### Example 1: News Article with URL

```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "https://indianexpress.com/article/technology/ai-breakthrough/",
  "category": "Technology",
  "image_source": null,
  "voice_engine": "azure_basic"
}
```

**What Happens**:
1. Article content extracted from URL
2. Default images used
3. 4 slides generated
4. Story created

### Example 2: News with Custom Image

```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "Breaking news: Major technology announcement",
  "category": "Technology",
  "image_source": "custom",
  "attachments": ["s3://bucket/media/images/backgrounds/20250121/custom-bg.jpg"],
  "voice_engine": "azure_basic"
}
```

**What Happens**:
1. Text content used
2. Custom image uploaded to S3
3. Image resized to 720x1280
4. All 4 slides use same background image
5. CDN URL replaces placeholders

### Example 3: Curious with AI Images

```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 7,
  "user_input": "How does photosynthesis work?",
  "category": "Science",
  "image_source": "ai",
  "prompt_keywords": ["photosynthesis", "plants", "chlorophyll", "sunlight"],
  "voice_engine": "azure_basic"
}
```

**What Happens**:
1. Educational content generated
2. AI generates 7 images (one per slide) using keywords + content
3. Images uploaded to S3
4. Each slide gets unique AI-generated background

### Example 4: Curious with Custom Images

```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 7,
  "user_input": "Introduction to quantum mechanics",
  "category": "Physics",
  "image_source": "custom",
  "attachments": [
    "s3://bucket/media/images/backgrounds/20250121/slide-1.jpg",
    "s3://bucket/media/images/backgrounds/20250121/slide-2.jpg",
    "s3://bucket/media/images/backgrounds/20250121/slide-3.jpg",
    "s3://bucket/media/images/backgrounds/20250121/slide-4.jpg",
    "s3://bucket/media/images/backgrounds/20250121/slide-5.jpg",
    "s3://bucket/media/images/backgrounds/20250121/slide-6.jpg",
    "s3://bucket/media/images/backgrounds/20250121/slide-7.jpg"
  ],
  "voice_engine": "azure_basic"
}
```

**What Happens**:
1. Educational content generated
2. 7 custom images uploaded (one per slide)
3. Each image resized to 720x1280
4. Each slide gets its own background image
5. CDN URLs replace placeholders

### Example 5: News with Document Attachment

```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "Additional context about the article",
  "category": "News",
  "attachments": ["s3://bucket/media/attachments/20250121/article-photo.jpg"],
  "image_source": null,
  "voice_engine": "azure_basic"
}
```

**What Happens**:
1. Text content used
2. Image attachment processed via OCR (extracts text if any)
3. Extracted content combined with user_input
4. Default images used for backgrounds
5. Story generated

---

## Best Practices

### 1. Content Input

✅ **Do**:
- Use URLs for online articles
- Use text for direct content
- Use attachments for documents/images that need OCR

❌ **Don't**:
- Mix multiple URLs in `user_input` (use `attachments` for multiple files)
- Put image URLs in `user_input` for slide backgrounds (use `image_source: "custom"`)

### 2. Image Source

✅ **Do**:
- Use `null` (default) for News mode if no custom images needed
- Use `"custom"` with proper S3 URLs in `attachments`
- Upload exactly `slide_count` images for Curious custom mode
- Provide `prompt_keywords` for AI/Pexels in Curious mode

❌ **Don't**:
- Use `"pexels"` in News mode (not supported - use "ai" or "custom" instead)
- Upload wrong number of images for Curious custom mode
- Forget to upload images to S3 before adding to `attachments`

### 3. Attachments

✅ **Do**:
- Upload files to S3 first
- Use S3 URLs (`s3://bucket/key`) or HTTP URLs
- Separate content extraction attachments from background images
- Use proper file types (PDF, DOCX, JPG, PNG)

❌ **Don't**:
- Send file objects directly (must be S3/HTTP URLs)
- Mix content extraction files with background images in same array
- Use unsupported file types

### 4. Categories

✅ **Do**:
- Use predefined categories from dropdown
- Choose relevant category for better SEO

❌ **Don't**:
- Use random category names
- Leave category empty (use default)

---

## Field Interaction Matrix

| Field | Affects Content | Affects Background Images | Notes |
|-------|----------------|---------------------------|-------|
| `user_input` | ✅ Yes | ❌ No | Content extraction only |
| `attachments` (docs/images) | ✅ Yes (OCR) | ❌ No | Content extraction only |
| `attachments` (background images) | ❌ No | ✅ Yes | Slide backgrounds only |
| `image_source` | ❌ No | ✅ Yes | Controls background image source |
| `prompt_keywords` | ❌ No | ✅ Yes | For AI/Pexels image generation |

---

## Common Mistakes to Avoid

### ❌ Mistake 1: Using `user_input` for Background Images
```json
// WRONG
{
  "user_input": "https://example.com/image.jpg",  // This is for content, not backgrounds!
  "image_source": "custom"
}
```

**Correct**: Upload image to S3, add to `attachments`:
```json
{
  "image_source": "custom",
  "attachments": ["s3://bucket/media/images/backgrounds/20250121/bg.jpg"]
}
```

### ❌ Mistake 2: Wrong Number of Images for Curious Custom
```json
// WRONG - slide_count is 7 but only 5 images
{
  "mode": "curious",
  "slide_count": 7,
  "image_source": "custom",
  "attachments": ["s3://...", "s3://...", "s3://...", "s3://...", "s3://..."]
}
```

**Correct**: Upload exactly 7 images:
```json
{
  "mode": "curious",
  "slide_count": 7,
  "image_source": "custom",
  "attachments": ["s3://...", "s3://...", "s3://...", "s3://...", "s3://...", "s3://...", "s3://..."]
}
```

### ❌ Mistake 3: Using AI/Pexels in News Mode
```json
// WRONG
{
  "mode": "news",
  "image_source": "pexels",  // Pexels not supported in News mode!
  "prompt_keywords": ["tech"]
}
```

**Correct**: Use `null`, `"ai"`, or `"custom"`:
```json
{
  "mode": "news",
  "image_source": "ai",  // Now supported!
  "prompt_keywords": ["news", "technology"]
}
```

### ❌ Mistake 4: Missing prompt_keywords for AI/Pexels
```json
// WRONG
{
  "mode": "curious",
  "image_source": "ai",
  // Missing prompt_keywords!
}
```

**Correct**: Provide keywords:
```json
{
  "mode": "curious",
  "image_source": "ai",
  "prompt_keywords": ["quantum", "computing"]
}
```

---

## Quick Reference

### News Mode Valid Combinations

| user_input | attachments | image_source | Valid? |
|------------|-------------|--------------|--------|
| URL | - | null | ✅ |
| Text | - | null | ✅ |
| - | Docs (OCR) | null | ✅ |
| URL | Docs (OCR) | null | ✅ |
| Text | - | custom | ✅ |
| Text | Image (bg) | custom | ✅ |

### Curious Mode Valid Combinations

| user_input | attachments | image_source | prompt_keywords | Valid? |
|------------|-------------|--------------|-----------------|--------|
| Topic | - | ai | ✅ Yes | ✅ |
| Topic | - | pexels | ✅ Yes | ✅ |
| Topic | - | custom | - | ✅ (need {slide_count} images) |
| Topic | Docs (OCR) | ai | ✅ Yes | ✅ |
| - | Docs (OCR) | custom | - | ✅ (need {slide_count} images) |

---

## Summary

### Key Points

1. **`user_input`**: For content only (URL, text, or file reference)
2. **`attachments`**: Can be for content extraction (OCR) OR background images
3. **`image_source`**: Controls slide background images only
4. **News Mode**: Only supports `null` (default) or `"custom"` for image_source
5. **Curious Mode**: Supports `"ai"`, `"pexels"`, or `"custom"` for image_source
6. **Custom Images**: 
   - News: 1 image for all slides
   - Curious: Exactly `slide_count` images (one per slide)
7. **S3 Upload**: Required before adding to `attachments` array
8. **Portrait Size**: All background images resized to 720x1280

---

## Support

For questions or issues:
- Check `FIELD_USAGE_MAPPING.md` for detailed field analysis
- Check `INPUT_FIELD_GUIDE.md` for quick reference
- Review API documentation at `/docs` endpoint

