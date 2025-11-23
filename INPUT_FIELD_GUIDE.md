# Input Field Guide - Quick Reference

## Overview
Quick reference guide for all input fields, their purposes, and valid combinations for News and Curious modes.

---

## Field Quick Reference

### Required Fields

| Field | Type | News Mode | Curious Mode | Description |
|-------|------|-----------|--------------|-------------|
| `mode` | `string` | ✅ `"news"` | ✅ `"curious"` | Story mode |
| `template_key` | `string` | ✅ `"test-news-1"`, `"test-news-2"` | ✅ `"curious-template-1"` | Template identifier |
| `slide_count` | `integer` | ✅ `4-10` | ✅ `7+` | Number of slides |

### Optional Fields

| Field | Type | News Mode | Curious Mode | Description |
|-------|------|-----------|--------------|-------------|
| `user_input` | `string` | ✅ Supported | ✅ Supported | Unified input (URL/text/file) |
| `attachments` | `array<string>` | ✅ Supported | ✅ Supported | Files/images for content + backgrounds |
| `image_source` | `string \| null` | ✅ `null` or `"custom"` | ✅ `"ai"`, `"pexels"`, `"custom"` | Slide background source |
| `prompt_keywords` | `array<string>` | ❌ NOT USED | ✅ Optional/Required | Image generation keywords |
| `category` | `string` | ✅ Recommended | ❌ Optional | Story category |
| `voice_engine` | `string` | ✅ Optional | ✅ Optional | `"azure_basic"` or `"elevenlabs_pro"` |

---

## Field Purposes

### 1. `user_input` - Content Input
**Purpose**: Provide content for story generation

**Accepts**:
- URLs (articles, images)
- Plain text
- File references

**What It Does**:
- ✅ Content extraction (URLs → article content, images → OCR)
- ❌ Does NOT control slide backgrounds

**Examples**:
```json
// URL
"user_input": "https://indianexpress.com/article/..."

// Text
"user_input": "Breaking news: Technology breakthrough"

// Image URL (for content extraction)
"user_input": "https://example.com/article-image.jpg"
```

---

### 2. `attachments` - Files/Images
**Purpose**: Files for content extraction AND/OR slide backgrounds

**Accepts**:
- HTTP/HTTPS URLs
- S3 URIs
- Local file paths

**What It Does**:
- ✅ **Always**: Content extraction (OCR for images/PDFs)
- ✅ **Conditionally**: Slide backgrounds (if `image_source: "custom"`)

**Examples**:
```json
// For content extraction only
"attachments": ["https://example.com/document.pdf"]

// For content + slide backgrounds
"image_source": "custom",
"attachments": ["https://example.com/image.jpg"]
```

---

### 3. `image_source` - Background Image Control
**Purpose**: Controls which images are used for slide backgrounds

**News Mode**:
- `null` → Default polaris images
- `"custom"` → User-provided images from `attachments`

**Curious Mode**:
- `"ai"` → AI-generated images (uses alt texts from content)
- `"pexels"` → Pexels stock images (uses `prompt_keywords`)
- `"custom"` → User-provided images from `attachments`

**⚠️ Important**: `image_source` ONLY controls slide backgrounds, NOT content extraction.

---

### 4. `prompt_keywords` - Image Generation Keywords
**Purpose**: Keywords for AI/Pexels image generation

**News Mode**:
- ❌ NOT USED (ignored)

**Curious Mode**:
- `image_source: "ai"` → Fallback (primary: alt texts from content)
- `image_source: "pexels"` → Required for search

---

## Valid Combinations

### News Mode Combinations

#### Combination 1: Default Images + URL Content
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "https://indianexpress.com/article/...",
  "image_source": null
}
```
**Result**: Article content extracted, default polaris images used

#### Combination 2: Custom Images + Text Content
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "Breaking news: Technology breakthrough",
  "image_source": "custom",
  "attachments": ["https://example.com/image.jpg"]
}
```
**Result**: Text used for story, custom image as background for all slides

#### Combination 3: Custom Images + URL Content
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "https://indianexpress.com/article/...",
  "image_source": "custom",
  "attachments": ["https://example.com/custom-image.jpg"]
}
```
**Result**: Article content extracted, custom image as background

#### Combination 4: URL Content + Document Attachments
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "https://indianexpress.com/article/...",
  "attachments": ["https://example.com/supporting-doc.pdf"],
  "image_source": null
}
```
**Result**: Article content + document content extracted, default images used

---

### Curious Mode Combinations

#### Combination 1: AI Images + Text Content
```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 7,
  "user_input": "How does quantum computing work?",
  "image_source": "ai",
  "prompt_keywords": ["quantum", "computing"]  // Fallback only
}
```
**Result**: Educational content generated, AI images using alt texts from content

#### Combination 2: Pexels Images + URL Content
```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 7,
  "user_input": "https://example.com/educational-article",
  "image_source": "pexels",
  "prompt_keywords": ["quantum", "computing", "science"]  // Required
}
```
**Result**: Content extracted, Pexels stock images fetched

#### Combination 3: Custom Images + Text Content
```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 7,
  "user_input": "How does photosynthesis work?",
  "image_source": "custom",
  "attachments": ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]
}
```
**Result**: Educational content generated, custom images as backgrounds

---

## Field Interaction Matrix

### News Mode

| `user_input` | `attachments` | `image_source` | `prompt_keywords` | Result |
|--------------|---------------|----------------|-------------------|--------|
| URL | None | `null` | - | Article content extracted, default images |
| Text | None | `null` | - | Text used for story, default images |
| URL | Image | `null` | - | Article + image OCR, default images |
| URL | Image | `"custom"` | - | Article extracted, custom image as background |
| Text | Image | `"custom"` | - | Text used, custom image as background |
| URL | PDF | `null` | - | Article + PDF OCR, default images |

### Curious Mode

| `user_input` | `attachments` | `image_source` | `prompt_keywords` | Result |
|--------------|---------------|----------------|-------------------|--------|
| Text | None | `"ai"` | Optional | Educational content, AI images (alt texts) |
| Text | None | `"pexels"` | Required | Educational content, Pexels images |
| Text | Image | `"custom"` | - | Educational content, custom images |
| URL | None | `"ai"` | Optional | Content extracted, AI images (alt texts) |
| URL | Image | `"custom"` | - | Content extracted, custom images |

---

## Common Patterns

### Pattern 1: News Article with Default Images
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "https://indianexpress.com/article/...",
  "image_source": null,
  "voice_engine": "azure_basic",
  "category": "News"
}
```

### Pattern 2: News Article with Custom Background
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "https://indianexpress.com/article/...",
  "image_source": "custom",
  "attachments": ["https://example.com/custom-image.jpg"],
  "voice_engine": "azure_basic",
  "category": "News"
}
```

### Pattern 3: Educational Content with AI Images
```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 7,
  "user_input": "How does quantum computing work?",
  "image_source": "ai",
  "prompt_keywords": ["quantum", "computing"],
  "voice_engine": "azure_basic"
}
```

### Pattern 4: Educational Content with Pexels Images
```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 7,
  "user_input": "How does photosynthesis work?",
  "image_source": "pexels",
  "prompt_keywords": ["plants", "nature", "biology"],
  "voice_engine": "azure_basic"
}
```

---

## Field Dependencies

### News Mode Dependencies

```
image_source: "custom"
  → REQUIRES: attachments[] (at least 1 image)

image_source: null
  → NO dependencies (uses default images)
```

### Curious Mode Dependencies

```
image_source: "custom"
  → REQUIRES: attachments[] (at least 1 image)

image_source: "pexels"
  → REQUIRES: prompt_keywords[] (at least 1 keyword)

image_source: "ai"
  → OPTIONAL: prompt_keywords[] (fallback only, primary: alt texts)
```

---

## Error Prevention

### ❌ Don't Do This (News Mode)

```json
{
  "mode": "news",
  "image_source": "ai"  // ❌ NOT SUPPORTED
}

{
  "mode": "news",
  "image_source": "pexels"  // ❌ NOT SUPPORTED
}

{
  "mode": "news",
  "image_source": "custom"  // ❌ Missing attachments
  // attachments: []  // Empty
}
```

### ❌ Don't Do This (Curious Mode)

```json
{
  "mode": "curious",
  "image_source": null  // ❌ NOT SUPPORTED
}

{
  "mode": "curious",
  "image_source": "pexels"  // ❌ Missing prompt_keywords
  // prompt_keywords: []  // Empty
}

{
  "mode": "curious",
  "image_source": "custom"  // ❌ Missing attachments
  // attachments: []  // Empty
}
```

---

## Quick Decision Tree

### For Content Input
```
Need to extract content from URL?
  → Use user_input: "https://..."

Need to extract content from text?
  → Use user_input: "Your text here"

Need to extract content from file?
  → Use user_input: "s3://bucket/file.pdf" OR attachments: ["s3://bucket/file.pdf"]
```

### For Slide Backgrounds (News Mode)
```
Want default images?
  → image_source: null

Want custom image?
  → image_source: "custom" + attachments: ["https://example.com/image.jpg"]
```

### For Slide Backgrounds (Curious Mode)
```
Want AI-generated images?
  → image_source: "ai" + prompt_keywords: [...] (optional, fallback)

Want Pexels stock images?
  → image_source: "pexels" + prompt_keywords: [...] (required)

Want custom images?
  → image_source: "custom" + attachments: ["https://example.com/image.jpg"]
```

---

**Last Updated**: 2025-01-21  
**Version**: 1.0.0

