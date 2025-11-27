# 📋 Mode Field Reference Guide

Complete reference for all fields and parameters supported in each story generation mode.

## 📖 Table of Contents

1. [News Mode](#news-mode)
2. [Curious Mode](#curious-mode)
3. [Common Fields](#common-fields)
4. [Field Validation Rules](#field-validation-rules)
5. [Complete Examples](#complete-examples)
6. [Quick Reference Tables](#quick-reference-tables)

---

## 🗞️ News Mode

**Purpose**: Generate factual news stories and current events coverage

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `mode` | `string` | Must be `"news"` | `"news"` |
| `template_key` | `string` | Template identifier | `"test-news-1"`, `"test-news-2"` |

### Optional Fields

| Field | Type | Default | Description | Valid Values |
|-------|------|---------|-------------|--------------|
| `slide_count` | `integer` | `4` | Number of slides (4-10) | `4`, `5`, `6`, `7`, `8`, `9`, `10` |
| `user_input` | `string` | `null` | Content source | URL, text, or file path |
| `category` | `string` | `"News"` | Story category | Any string (e.g., "Technology", "Sports") |
| `image_source` | `string \| null` | `null` | Background image source | `null`, `"ai"`, `"custom"` |
| `attachments` | `array` | `[]` | File URLs for content/backgrounds | Array of URLs/S3 URIs |
| `prompt_keywords` | `array` | `[]` | Keywords for AI image generation | Array of strings |
| `voice_engine` | `string` | `"azure_basic"` | Text-to-speech engine | `"azure_basic"`, `"elevenlabs_pro"` |

### Image Source Options

#### 1. **Default Images** (`image_source: null`)
```json
{
  "image_source": null
}
```
- **Uses**: Default polaris images (polariscover.png, polarisslide.png)
- **Requirements**: None
- **Best for**: Quick story generation without custom visuals

#### 2. **AI Generated** (`image_source: "ai"`)
```json
{
  "image_source": "ai",
  "prompt_keywords": ["news", "technology", "breaking", "media"]
}
```
- **Uses**: DALL-E 3 to generate contextual images
- **Requirements**: `prompt_keywords` (recommended)
- **Best for**: Professional-looking, contextual news visuals

#### 3. **Custom Images** (`image_source: "custom"`)
```json
{
  "image_source": "custom",
  "attachments": [
    "https://example.com/slide1.jpg",
    "https://example.com/slide2.jpg",
    "https://example.com/slide3.jpg",
    "https://example.com/slide4.jpg"
  ]
}
```
- **Uses**: User-provided images
- **Requirements**: `attachments` array with image URLs
- **Best for**: Branded content or specific visuals

### Content Input Methods

#### 1. **Article URL**
```json
{
  "user_input": "https://indianexpress.com/article/technology/ai-breakthrough/"
}
```
- Automatically extracts article content
- Pulls headline, text, and metadata

#### 2. **Direct Text**
```json
{
  "user_input": "Breaking: Major technology breakthrough announced today..."
}
```
- Uses provided text as story content
- Good for custom or summarized content

#### 3. **Document Upload**
```json
{
  "user_input": null,
  "attachments": ["https://example.com/document.pdf"]
}
```
- OCR processes document for text extraction
- Supports PDF, DOC, DOCX, images

---

## 🔍 Curious Mode

**Purpose**: Generate educational and explainable content stories

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `mode` | `string` | Must be `"curious"` | `"curious"` |
| `template_key` | `string` | Template identifier | `"curious-template-1"`, `"template-v19"` |
| `image_source` | `string` | Background image source | `"ai"`, `"pexels"`, `"custom"` |

### Optional Fields

| Field | Type | Default | Description | Valid Values |
|-------|------|---------|-------------|--------------|
| `slide_count` | `integer` | `7` | Number of slides (7-15) | `7`, `8`, `9`, `10`, `11`, `12`, `13`, `14`, `15` |
| `user_input` | `string` | `null` | Topic or question | Topic, keywords, or question |
| `category` | `string` | `"Education"` | Story category | "Science", "Technology", "History", etc. |
| `attachments` | `array` | `[]` | File URLs for content/backgrounds | Array of URLs/S3 URIs |
| `prompt_keywords` | `array` | `[]` | Keywords for image generation | Array of strings |
| `voice_engine` | `string` | `"azure_basic"` | Text-to-speech engine | `"azure_basic"`, `"elevenlabs_pro"` |

### Image Source Options (Required)

#### 1. **AI Generated** (`image_source: "ai"`)
```json
{
  "image_source": "ai",
  "prompt_keywords": ["quantum", "computing", "science", "technology"]
}
```
- **Uses**: DALL-E 3 with content-based alt texts + keywords
- **Requirements**: `prompt_keywords` (fallback if alt texts unavailable)
- **Best for**: Contextual, educational visuals

#### 2. **Pexels Stock** (`image_source: "pexels"`)
```json
{
  "image_source": "pexels",
  "prompt_keywords": ["nature", "environment", "sustainability"]
}
```
- **Uses**: Pexels API for royalty-free stock images
- **Requirements**: `prompt_keywords` (required)
- **Best for**: High-quality stock photography

#### 3. **Custom Images** (`image_source: "custom"`)
```json
{
  "image_source": "custom",
  "slide_count": 7,
  "attachments": [
    "https://example.com/slide1.jpg",
    "https://example.com/slide2.jpg",
    "https://example.com/slide3.jpg",
    "https://example.com/slide4.jpg",
    "https://example.com/slide5.jpg",
    "https://example.com/slide6.jpg",
    "https://example.com/slide7.jpg"
  ]
}
```
- **Uses**: User-provided images (one per slide)
- **Requirements**: `attachments` array matching `slide_count`
- **Best for**: Branded educational content

### Content Input Methods

#### 1. **Topic/Question**
```json
{
  "user_input": "How does photosynthesis work in plants?"
}
```
- Generates educational explanation
- Creates step-by-step breakdown

#### 2. **Keywords**
```json
{
  "user_input": "quantum computing, qubits, superposition"
}
```
- Uses keywords to generate comprehensive content
- Good for broad topic exploration

#### 3. **Document-Based**
```json
{
  "user_input": "Explain this research paper",
  "attachments": ["https://example.com/research.pdf"]
}
```
- OCR processes document
- Creates educational summary

---

## 🔄 Common Fields

These fields work the same way across both modes:

### Voice Engine Options

| Value | Description | Quality | Use Case |
|-------|-------------|---------|----------|
| `"azure_basic"` | Azure Text-to-Speech | Good | Standard narration |
| `"elevenlabs_pro"` | ElevenLabs AI Voice | Premium | High-quality narration |

### Attachment Formats

| Type | Extensions | Purpose | Max Size |
|------|------------|---------|----------|
| **Images** | `.jpg`, `.jpeg`, `.png`, `.webp` | Backgrounds or content extraction | 200MB |
| **Documents** | `.pdf`, `.doc`, `.docx` | Content extraction via OCR | 200MB |

### Category Examples

#### News Mode Categories
- `"News"`, `"Technology"`, `"Sports"`, `"Politics"`, `"Business"`, `"Entertainment"`, `"Science"`, `"Health"`, `"World"`, `"Local"`

#### Curious Mode Categories
- `"Art"`, `"Travel"`, `"Entertainment"`, `"Literature"`, `"Books"`, `"Sports"`, `"History"`, `"Culture"`, `"Wildlife"`, `"Spiritual"`, `"Food"`, `"Education"`

---

## ✅ Field Validation Rules

### Slide Count Validation

| Mode | Min | Max | Default | Notes |
|------|-----|-----|---------|-------|
| **News** | 4 | 10 | 4 | Cover + Middle slides + CTA |
| **Curious** | 7 | 15 | 7 | Cover + Content slides |

### Image Source Validation

| Mode | Supported Values | Required Fields |
|------|------------------|-----------------|
| **News** | `null`, `"ai"`, `"custom"` | `prompt_keywords` (for AI), `attachments` (for custom) |
| **Curious** | `"ai"`, `"pexels"`, `"custom"` | `prompt_keywords` (for AI/Pexels), `attachments` (for custom) |

### Content Input Validation

| Field | Required | Validation |
|-------|----------|------------|
| `user_input` | No | Can be URL, text, or null |
| `attachments` | No | Must be valid URLs or S3 URIs |
| **Either** `user_input` **OR** `attachments` | Yes | At least one must be provided |

---

## 📝 Complete Examples

### News Mode Examples

#### Example 1: Default Images
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

#### Example 2: AI Generated Images
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "Breaking: Revolutionary AI breakthrough in healthcare diagnostics",
  "category": "Technology",
  "image_source": "ai",
  "prompt_keywords": ["news", "healthcare", "AI", "technology", "medical", "breakthrough"],
  "voice_engine": "azure_basic"
}
```

#### Example 3: Custom Images
```json
{
  "mode": "news",
  "template_key": "test-news-2",
  "slide_count": 5,
  "user_input": "Sports update: Championship finals results",
  "category": "Sports",
  "image_source": "custom",
  "attachments": [
    "https://example.com/sports1.jpg",
    "https://example.com/sports2.jpg",
    "https://example.com/sports3.jpg",
    "https://example.com/sports4.jpg",
    "https://example.com/sports5.jpg"
  ],
  "voice_engine": "elevenlabs_pro"
}
```

### Curious Mode Examples

#### Example 1: AI Generated Images
```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 7,
  "user_input": "How does quantum computing work?",
  "category": "Science",
  "image_source": "ai",
  "prompt_keywords": ["quantum", "computing", "qubits", "superposition", "science"],
  "voice_engine": "azure_basic"
}
```

#### Example 2: Pexels Stock Images
```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 8,
  "user_input": "Climate change effects and environmental solutions",
  "category": "Nature",
  "image_source": "pexels",
  "prompt_keywords": ["climate", "environment", "nature", "sustainability", "earth"],
  "voice_engine": "azure_basic"
}
```

#### Example 3: Custom Images
```json
{
  "mode": "curious",
  "template_key": "template-v19",
  "slide_count": 7,
  "user_input": "History of ancient civilizations",
  "category": "History",
  "image_source": "custom",
  "attachments": [
    "https://example.com/ancient1.jpg",
    "https://example.com/ancient2.jpg",
    "https://example.com/ancient3.jpg",
    "https://example.com/ancient4.jpg",
    "https://example.com/ancient5.jpg",
    "https://example.com/ancient6.jpg",
    "https://example.com/ancient7.jpg"
  ],
  "voice_engine": "elevenlabs_pro"
}
```

---

## 📊 Quick Reference Tables

### Field Support Matrix

| Field | News Mode | Curious Mode | Notes |
|-------|-----------|--------------|-------|
| `mode` | ✅ Required | ✅ Required | Must match mode |
| `template_key` | ✅ Required | ✅ Required | Mode-specific templates |
| `slide_count` | ✅ Optional (4-10) | ✅ Optional (7-15) | Different ranges |
| `user_input` | ✅ Optional | ✅ Optional | Content source |
| `category` | ✅ Optional | ✅ Optional | Different defaults |
| `image_source` | ✅ Optional | ✅ Required | Different options |
| `attachments` | ✅ Optional | ✅ Optional | Content + backgrounds |
| `prompt_keywords` | ✅ Optional | ✅ Optional | For AI/Pexels |
| `voice_engine` | ✅ Optional | ✅ Optional | Same options |

### Image Source Compatibility

| Image Source | News Mode | Curious Mode | Requirements |
|--------------|-----------|--------------|--------------|
| `null` (Default) | ✅ Yes | ❌ No | None |
| `"ai"` (AI Generated) | ✅ Yes | ✅ Yes | `prompt_keywords` |
| `"pexels"` (Stock) | ❌ No | ✅ Yes | `prompt_keywords` |
| `"custom"` (Upload) | ✅ Yes | ✅ Yes | `attachments` |

### Template Options

| Mode | Available Templates | Default Slide Count |
|------|-------------------|-------------------|
| **News** | `test-news-1`, `test-news-2` | 4 |
| **Curious** | `curious-template-1`, `template-v19` | 7 |

---

## 🚨 Common Validation Errors

### Missing Required Fields
```json
// ❌ ERROR: Missing mode
{
  "template_key": "test-news-1"
}

// ✅ CORRECT
{
  "mode": "news",
  "template_key": "test-news-1"
}
```

### Invalid Image Source for Mode
```json
// ❌ ERROR: Pexels not supported in News mode
{
  "mode": "news",
  "image_source": "pexels"
}

// ✅ CORRECT
{
  "mode": "news",
  "image_source": "ai",
  "prompt_keywords": ["news", "technology"]
}
```

### Missing Dependencies
```json
// ❌ ERROR: AI source without keywords
{
  "mode": "curious",
  "image_source": "ai"
}

// ✅ CORRECT
{
  "mode": "curious",
  "image_source": "ai",
  "prompt_keywords": ["science", "education"]
}
```

### Invalid Slide Count
```json
// ❌ ERROR: Slide count out of range
{
  "mode": "news",
  "slide_count": 15
}

// ✅ CORRECT
{
  "mode": "news",
  "slide_count": 6
}
```

---

**Last Updated**: 2025-01-21  
**Version**: 2.0  
**Modes Supported**: News, Curious  
**Total Fields**: 9  
**Image Sources**: 4 (Default, AI, Pexels, Custom)
