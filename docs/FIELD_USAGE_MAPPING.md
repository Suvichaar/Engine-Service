# Complete Field Usage Mapping - News vs Curious Mode

## Overview
This document provides a comprehensive mapping of every input field, showing how it's used in News and Curious modes, where changes reflect in the pipeline, and how to avoid conflicts.

---

## Table of Contents
1. [Field-by-Field Analysis](#field-by-field-analysis)
2. [Complete Flow Diagrams](#complete-flow-diagrams)
3. [Conflict Points & Resolutions](#conflict-points--resolutions)
4. [Usage Summary Table](#usage-summary-table)
5. [Best Practices](#best-practices)

---

## Field-by-Field Analysis

### 1. `user_input` (Unified Input Field)

**Type**: `string | null`  
**Purpose**: ChatGPT-style unified input that auto-detects content type

#### What It Accepts
- ✅ URLs (http://, https://, www.example.com)
- ✅ Plain text
- ✅ File references (s3://, file paths)

#### How It's Processed

**Step 1**: `SmartInputDetector.detect()` identifies type:
- `'url'` → URL detected
- `'text'` → Plain text
- `'file'` → File reference
- `'mixed'` → Both URL and text

**Step 2**: Extracted data mapped to internal fields:
- URL → `urls[]` list
- Text → `text_prompt`
- File → `attachments[]` list
- Mixed → Both `urls` and `text_prompt`/`notes`

#### Usage in News Mode

| Input Type | What Happens | Where It Reflects |
|------------|--------------|-------------------|
| **URL** | Extracted to `urls[]` → Article content extracted via `URLContentExtractor` (newspaper3k) | `document_intelligence.py` → `semantic_chunks` |
| **Text** | Used as `text_prompt` for story generation | `model_clients.py` → News narrative |
| **File Reference** | Added to `attachments[]` for OCR/document processing | `document_intelligence.py` → OCR → `semantic_chunks` |
| **Image URL** | Goes to `urls[]` → Content extraction (OCR if image) → **NOT for slide backgrounds** | `url_extractor.py` → Article images in metadata |

#### Usage in Curious Mode

| Input Type | What Happens | Where It Reflects |
|------------|--------------|-------------------|
| **URL** | Extracted to `urls[]` → Content extracted | `document_intelligence.py` → `semantic_chunks` |
| **Text** | Used as `text_prompt` for educational content generation | `model_clients.py` → Curious narrative |
| **File Reference** | Added to `attachments[]` for OCR/document processing | `document_intelligence.py` → OCR → `semantic_chunks` |
| **Image URL** | Goes to `urls[]` → Content extraction → **NOT for slide backgrounds** | `url_extractor.py` → Content extraction |

#### Where It Reflects in Pipeline

```
user_input
  ↓
SmartInputDetector.detect()
  ↓
Maps to: urls[] / text_prompt / attachments[]
  ↓
document_intelligence.py
  ↓
semantic_chunks
  ↓
model_clients.py
  ↓
narrative (slides)
```

#### ⚠️ Important Notes

1. **`user_input` images are for CONTENT EXTRACTION only**
   - Image URLs in `user_input` → `urls[]` → OCR → Text extraction
   - They do **NOT** become slide backgrounds

2. **For slide backgrounds**: Use `image_source: "custom"` + `attachments[]`

3. **Takes precedence**: If `user_input` is provided, it overrides separate `text_prompt`, `urls`, `notes` fields

---

### 2. `attachments` (Array of Files/Images)

**Type**: `array<string>`  
**Purpose**: Files, images, or documents to process

#### What It Accepts
- ✅ HTTP/HTTPS URLs (images, PDFs, documents)
- ✅ S3 URIs (`s3://bucket/key`)
- ✅ Local file paths (for testing)

#### How It's Processed

**Step 1**: Normalized by `DefaultUserInputService._normalize_attachments()`

**Step 2**: Processed by `DocumentIntelligencePipeline`:
- Images → OCR (text extraction)
- PDFs/Documents → OCR + parsing
- Content extracted to `semantic_chunks`

**Step 3**: If `image_source: "custom"`:
- Images used as slide backgrounds
- Uploaded to S3, resized to 720x1280 (portrait)

#### Usage in News Mode

| Scenario | What Happens | Where It Reflects |
|----------|--------------|-------------------|
| **Content Extraction** | Images/PDFs → OCR → Text extraction → `semantic_chunks` | `document_intelligence.py` → OCR adapters |
| **Slide Backgrounds** | IF `image_source: "custom"` → `attachments[0]` used as background for **all slides** | `image_pipeline.py` → `UserUploadProvider` → `html_renderer.py` → `s1image1`, `s2image1`, etc. |
| **Multiple Attachments** | All processed for content extraction, but only `attachments[0]` used for backgrounds | `document_intelligence.py` (all) + `image_pipeline.py` (first only) |

#### Usage in Curious Mode

| Scenario | What Happens | Where It Reflects |
|----------|--------------|-------------------|
| **Content Extraction** | Images/PDFs → OCR → Text extraction → `semantic_chunks` | `document_intelligence.py` → OCR adapters |
| **Slide Backgrounds** | IF `image_source: "custom"` → `attachments` used (one per slide or same for all) | `image_pipeline.py` → `UserUploadProvider` → `html_renderer.py` |
| **Multiple Attachments** | All processed for content extraction, can be used per slide for backgrounds | `document_intelligence.py` (all) + `image_pipeline.py` (per slide) |

#### Where It Reflects in Pipeline

```
attachments[]
  ↓
document_intelligence.py
  ├── OCR → semantic_chunks (content extraction)
  └── IF image_source: "custom"
      ↓
      image_pipeline.py → UserUploadProvider
      ↓
      S3 upload + resize (720x1280)
      ↓
      image_assets[]
      ↓
      html_renderer.py
      ↓
      s1image1, s2image1, etc. (background replacement)
```

#### ⚠️ Important Notes

1. **Dual Purpose**: `attachments` do **two things**:
   - **Always**: Content extraction (OCR)
   - **Conditionally**: Slide backgrounds (only if `image_source: "custom"`)

2. **News Mode**: Only `attachments[0]` used for backgrounds (same image for all slides)

3. **Curious Mode**: Can use multiple attachments (one per slide)

---

### 3. `image_source` (Image Source Selection)

**Type**: `string | null`  
**Purpose**: Controls which images are used for **slide backgrounds** (NOT content extraction)

#### Valid Values

| Value | News Mode | Curious Mode | Description |
|-------|-----------|--------------|-------------|
| `null` | ✅ Supported | ❌ NOT Supported | Default images |
| `"custom"` | ✅ Supported | ✅ Supported | User-provided images from `attachments` |
| `"ai"` | ✅ Supported | ✅ Supported | AI-generated images |
| `"pexels"` | ❌ NOT Supported | ✅ Supported | Pexels stock images |

#### Usage in News Mode

##### `image_source: null` (Default Images)

**What Happens**:
- Uses default polaris images:
  - Cover: `polariscover.png`
  - Slides: `polarisslide.png`

**Where It Reflects**:
- `app/services/html_renderer.py` → `PlaceholderMapper.map()`
- Sets `s1image1`, `s2image1`, etc. to default URLs directly
- `NewsDefaultImageProvider` returns empty list (no image generation needed)

**Example**:
```json
{
  "mode": "news",
  "image_source": null
  // No attachments needed
}
```

##### `image_source: "custom"` (Custom Images)

**What Happens**:
- Uses `attachments[0]` as background for **all slides**
- Downloads/uploads to S3
- Resizes to 720x1280 (portrait)
- Maps to `s1image1`, `s2image1`, etc.

**Where It Reflects**:
- `app/services/image_pipeline.py` → `UserUploadProvider.generate()`
- Downloads/loads image from URL/S3
- Uploads to S3 with unique key
- Generates resized URLs (720x1280)
- `app/services/html_renderer.py` → Maps `image_assets` to placeholders

**Example**:
```json
{
  "mode": "news",
  "image_source": "custom",
  "attachments": ["https://example.com/image.jpg"]
}
```

#### Usage in Curious Mode

##### `image_source: "ai"` (AI Generated Images)

**What Happens**:
- AI generates images using **alt texts** extracted from generated content
- Alt texts: `s0alt1` (cover), `s1alt1`, `s2alt1`, etc. (middle slides)
- Uses DALL-E 3 API
- Each slide gets unique image based on content

**Where It Reflects**:
- `app/services/model_clients.py` → `CuriousModelClient` → Generates `narrative_json` with alt texts
- `app/services/orchestrator.py` → Extracts `narrative_json` → Updates `payload.metadata`
- `app/services/image_pipeline.py` → `AIImageProvider.generate()` → Uses alt texts from `payload.metadata["narrative_json"]`
- `prompt_keywords` used as **fallback** if alt texts unavailable

**Example**:
```json
{
  "mode": "curious",
  "image_source": "ai",
  "prompt_keywords": ["quantum", "computing"]  // Fallback only
}
```

##### `image_source: "pexels"` (Pexels Stock Images)

**What Happens**:
- Fetches stock images from Pexels API
- Based on `prompt_keywords`
- Different images for each slide
- Portrait orientation

**Where It Reflects**:
- `app/services/image_pipeline.py` → `PexelsImageProvider.generate()`
- Searches Pexels using `prompt_keywords`
- Downloads and uploads to S3
- Maps to `image_assets`

**Example**:
```json
{
  "mode": "curious",
  "image_source": "pexels",
  "prompt_keywords": ["quantum", "computing", "science"]  // Required
}
```

##### `image_source: "custom"` (Custom Images)

**What Happens**:
- Uses `attachments` as backgrounds
- Can use one image for all slides or different images per slide
- Downloads/uploads to S3
- Resizes to 720x1280

**Where It Reflects**:
- `app/services/image_pipeline.py` → `UserUploadProvider.generate()`
- Same as News mode but can use multiple attachments

**Example**:
```json
{
  "mode": "curious",
  "image_source": "custom",
  "attachments": ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]
}
```

#### Where It Reflects in Pipeline

```
image_source
  ↓
image_pipeline.py → DefaultImageAssetPipeline.process()
  ↓
Provider Selection:
  - null (News) → NewsDefaultImageProvider (empty, uses defaults in HTML)
  - "custom" → UserUploadProvider
  - "ai" (Curious) → AIImageProvider
  - "pexels" (Curious) → PexelsImageProvider
  ↓
image_assets[]
  ↓
html_renderer.py → PlaceholderMapper.map()
  ↓
s1image1, s2image1, etc. (background replacement in HTML)
```

#### ⚠️ Important Notes

1. **`image_source` ONLY controls slide background images**
   - Does NOT affect content extraction
   - Does NOT affect article images from URLs

2. **News Mode Restrictions**:
   - Only `null` (default) or `"custom"` supported
   - `"ai"` and `"pexels"` NOT supported

3. **Curious Mode Requirements**:
   - `null` NOT supported (must provide image source)
   - `"ai"` uses alt texts (more contextual than keywords)

---

### 4. `urls` (Legacy Field - Auto-populated from `user_input`)

**Type**: `array<HttpUrl>`  
**Purpose**: Article URLs for content extraction

#### How It's Populated

1. **Directly provided** (legacy format)
2. **Auto-extracted from `user_input`** (if URL detected)

#### Usage in News Mode

**What Happens**:
- URLs se article content extract hota hai (newspaper3k)
- Article images extract hote hain → `doc_insights.metadata["article_images"]`
- Content → `semantic_chunks` → Narrative generation

**Where It Reflects**:
- `app/services/url_extractor.py` → `URLContentExtractor.extract()`
  - Extracts: title, text, summary, images
- `app/services/document_intelligence.py` → Processes URLs → `semantic_chunks`
- `app/services/orchestrator.py` → Article images stored in metadata

#### Usage in Curious Mode

**What Happens**:
- Same as News mode
- URLs se content extract → Educational content generation

**Where It Reflects**:
- Same pipeline as News mode

#### ⚠️ Important Notes

1. **Article images from URLs are NOT automatically used as slide backgrounds**
   - They're stored in `doc_insights.metadata["article_images"]`
   - Can be used later if needed

2. **Content extraction only**: URLs se extract hua content story generation ke liye use hota hai

---

### 5. `text_prompt` (Legacy Field - Auto-populated from `user_input`)

**Type**: `string | null`  
**Purpose**: Primary text input for story generation

#### How It's Populated

1. **Directly provided** (legacy format)
2. **Auto-extracted from `user_input`** (if text detected)

#### Usage in News Mode

**What Happens**:
- Text → `semantic_chunks` → News narrative generation
- Used by `NewsModelClient` to generate news story

**Where It Reflects**:
- `app/services/document_intelligence.py` → Added to `semantic_chunks`
- `app/services/model_clients.py` → `NewsModelClient.generate()` → News narrative

#### Usage in Curious Mode

**What Happens**:
- Text → `semantic_chunks` → Educational content generation
- Used by `CuriousModelClient` to generate educational story

**Where It Reflects**:
- `app/services/document_intelligence.py` → Added to `semantic_chunks`
- `app/services/model_clients.py` → `CuriousModelClient.generate()` → Curious narrative

#### ⚠️ Important Notes

1. **`user_input` takes precedence**: If `user_input` is provided, it overrides `text_prompt`

2. **Legacy field**: Prefer `user_input` for new implementations

---

### 6. `prompt_keywords` (Keywords for Image Generation)

**Type**: `array<string>`  
**Purpose**: Keywords for AI/Pexels image generation

#### Usage in News Mode

**Status**: ❌ **NOT USED**

- News mode doesn't support AI/Pexels images
- This field is ignored in News mode

#### Usage in Curious Mode

##### With `image_source: "ai"`

**What Happens**:
- Used as **fallback** if alt texts not available
- Primary: Curious mode uses **alt texts** from generated content (s0alt1, s1alt1, etc.)
- Fallback: If alt texts missing, uses `prompt_keywords` + slide text

**Where It Reflects**:
- `app/services/image_pipeline.py` → `AIImageProvider.generate()`
- Checks `payload.metadata["narrative_json"]` for alt texts first
- Falls back to `prompt_keywords` if alt texts unavailable

**Example**:
```json
{
  "mode": "curious",
  "image_source": "ai",
  "prompt_keywords": ["quantum", "computing"]  // Fallback only
}
```

##### With `image_source: "pexels"`

**What Happens**:
- **Required** for Pexels image search
- Used to search Pexels API for relevant images
- Different keywords can fetch different images per slide

**Where It Reflects**:
- `app/services/image_pipeline.py` → `PexelsImageProvider.generate()`
- Searches Pexels using keywords
- Downloads and uploads to S3

**Example**:
```json
{
  "mode": "curious",
  "image_source": "pexels",
  "prompt_keywords": ["quantum", "computing", "science"]  // Required
}
```

#### ⚠️ Important Notes

1. **News Mode**: `prompt_keywords` ka koi use nahi hai (ignored)

2. **Curious Mode with AI**: Alt texts primary hain, `prompt_keywords` fallback

3. **Curious Mode with Pexels**: `prompt_keywords` required

---

## Complete Flow Diagrams

### News Mode Complete Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    INPUT FIELDS                             │
├─────────────────────────────────────────────────────────────┤
│ user_input: "https://example.com/article"                   │
│ attachments: ["https://example.com/image.jpg"]              │
│ image_source: null OR "custom"                              │
│ prompt_keywords: [] (NOT USED)                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              SmartInputDetector.detect()                    │
├─────────────────────────────────────────────────────────────┤
│ Detects: URL → urls[]                                       │
│          File → attachments[]                               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│         Document Intelligence Pipeline                      │
├─────────────────────────────────────────────────────────────┤
│ urls[] → URLContentExtractor                                │
│   → Article content + images                                │
│   → semantic_chunks                                         │
│                                                             │
│ attachments[] → OCR                                         │
│   → Text extraction                                         │
│   → semantic_chunks                                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              Narrative Generation                           │
├─────────────────────────────────────────────────────────────┤
│ semantic_chunks → NewsModelClient                           │
│   → News narrative (slides)                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              Image Pipeline                                 │
├─────────────────────────────────────────────────────────────┤
│ IF image_source: null                                       │
│   → NewsDefaultImageProvider (empty)                        │
│   → HTML renderer uses default URLs directly                │
│                                                             │
│ IF image_source: "custom"                                   │
│   → UserUploadProvider                                      │
│   → attachments[0] → S3 upload + resize (720x1280)          │
│   → image_assets[]                                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              HTML Rendering                                 │
├─────────────────────────────────────────────────────────────┤
│ image_assets[] → PlaceholderMapper                          │
│   → s1image1, s2image1, etc. (background replacement)       │
│                                                             │
│ narrative.slides → s1paragraph1, s2paragraph1, etc.      │
└─────────────────────────────────────────────────────────────┘
```

### Curious Mode Complete Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    INPUT FIELDS                             │
├─────────────────────────────────────────────────────────────┤
│ user_input: "How does quantum computing work?"               │
│ attachments: ["https://example.com/image.jpg"]              │
│ image_source: "ai" OR "pexels" OR "custom"                 │
│ prompt_keywords: ["quantum", "computing"]                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│         Document Intelligence Pipeline                      │
├─────────────────────────────────────────────────────────────┤
│ Same as News mode                                           │
│   → semantic_chunks                                         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              Narrative Generation                           │
├─────────────────────────────────────────────────────────────┤
│ semantic_chunks → CuriousModelClient                        │
│   → Educational narrative (slides)                          │
│   → narrative_json (with alt texts: s0alt1, s1alt1, etc.)  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              Image Pipeline                                 │
├─────────────────────────────────────────────────────────────┤
│ IF image_source: "ai"                                       │
│   → AIImageProvider                                         │
│   → Uses alt texts from narrative_json (s0alt1, s1alt1)    │
│   → Fallback: prompt_keywords if alt texts missing         │
│   → DALL-E generation → image_assets[]                      │
│                                                             │
│ IF image_source: "pexels"                                   │
│   → PexelsImageProvider                                     │
│   → Uses prompt_keywords for search                         │
│   → Downloads from Pexels → image_assets[]                  │
│                                                             │
│ IF image_source: "custom"                                   │
│   → UserUploadProvider                                      │
│   → attachments → S3 upload + resize                        │
│   → image_assets[]                                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              HTML Rendering                                 │
├─────────────────────────────────────────────────────────────┤
│ Same as News mode                                           │
│   → s1image1, s2image1, etc. (background replacement)      │
└─────────────────────────────────────────────────────────────┘
```

---

## Conflict Points & Resolutions

### Conflict 1: `user_input` vs `attachments` for Images

**Scenario**: User provides image URL in both `user_input` and `attachments`

```json
{
  "user_input": "https://example.com/article-image.jpg",
  "attachments": ["https://example.com/custom-background.jpg"],
  "image_source": "custom"
}
```

**What Happens**:
1. `user_input` image → `urls[]` → Content extraction (OCR if image)
2. `attachments` image → `attachments[]` → Content extraction (OCR) + Slide background (because `image_source: "custom"`)

**Resolution**: 
- ✅ `user_input` images → Content extraction only
- ✅ `attachments` images → Content extraction + Slide backgrounds (if `image_source: "custom"`)

**Best Practice**: 
- Content extraction ke liye: `user_input` ya `attachments` dono use kar sakte hain
- Slide backgrounds ke liye: `image_source: "custom"` + `attachments` use karein

---

### Conflict 2: `image_source` Controls Backgrounds, NOT Content

**Scenario**: User wants to extract content from image AND use it as background

```json
{
  "user_input": "https://example.com/news-article-image.jpg",
  "image_source": "custom",
  "attachments": ["https://example.com/news-article-image.jpg"]
}
```

**What Happens**:
1. Image in `user_input` → `urls[]` → Content extraction (OCR)
2. Image in `attachments` → `attachments[]` → Content extraction (OCR) + Slide background (because `image_source: "custom"`)

**Resolution**: 
- ✅ Same image ko dono jagah provide karein if you want both content extraction AND background
- ✅ OR: Different images use karein (one for content, one for background)

**Best Practice**: 
- Agar same image se content extract karna hai aur background bhi use karna hai:
  ```json
  {
    "user_input": "https://example.com/image.jpg",  // Content extraction
    "attachments": ["https://example.com/image.jpg"],  // Background
    "image_source": "custom"
  }
  ```

---

### Conflict 3: News Mode - `image_source: null` vs `"custom"`

**Scenario**: News mode mein default vs custom images

```json
// Option 1: Default images
{
  "mode": "news",
  "image_source": null  // → polariscover.png, polarisslide.png
}

// Option 2: Custom images
{
  "mode": "news",
  "image_source": "custom",
  "attachments": ["https://example.com/image.jpg"]  // → This image for all slides
}
```

**Resolution**: 
- ✅ `null` → Default polaris images (no `attachments` needed)
- ✅ `"custom"` → Requires `attachments[0]` for slide backgrounds

**Best Practice**: 
- Default images ke liye: `image_source: null` (no `attachments` needed)
- Custom images ke liye: `image_source: "custom"` + `attachments[0]`

---

### Conflict 4: `prompt_keywords` in News Mode

**Scenario**: User provides `prompt_keywords` in News mode

```json
{
  "mode": "news",
  "prompt_keywords": ["technology", "AI"]  // ❌ NOT USED
}
```

**What Happens**:
- `prompt_keywords` is ignored in News mode
- No error, but field has no effect

**Resolution**: 
- ✅ News mode mein `prompt_keywords` provide mat karein (waste of bandwidth)
- ✅ Curious mode mein use karein (for AI fallback or Pexels)

---

## Usage Summary Table

| Field | News Mode | Curious Mode | Where It Reflects | Notes |
|-------|-----------|--------------|-------------------|-------|
| `user_input` | URLs → content extraction<br>Text → story generation<br>Files → OCR | Same | `user_input.py` → `document_intelligence.py` → `semantic_chunks` | Takes precedence over legacy fields |
| `attachments` | OCR + Backgrounds (if `image_source: "custom"`) | OCR + Backgrounds (if `image_source: "custom"`) | `document_intelligence.py` (OCR)<br>`image_pipeline.py` (backgrounds) | Dual purpose: content + backgrounds |
| `image_source` | `null` (default) or `"custom"`<br>❌ `"ai"` NOT SUPPORTED<br>❌ `"pexels"` NOT SUPPORTED | ❌ `null` NOT SUPPORTED<br>`"custom"`, `"ai"`, `"pexels"` | `image_pipeline.py` → Provider selection<br>`html_renderer.py` → Background mapping | ONLY controls slide backgrounds |
| `urls` | Article content extraction | Content extraction | `url_extractor.py` → Article content + images | Auto-populated from `user_input` |
| `text_prompt` | News story generation | Educational content generation | `model_clients.py` → Narrative generation | Auto-populated from `user_input` |
| `prompt_keywords` | ❌ NOT USED | AI fallback, Pexels required | `image_pipeline.py` → Image generation | Ignored in News mode |

---

## Best Practices

### For Content Extraction

1. **Use `user_input` for URLs/text**:
   ```json
   {
     "user_input": "https://example.com/article"  // Auto-detects URL
   }
   ```

2. **Use `attachments` for files/documents**:
   ```json
   {
     "attachments": ["https://example.com/document.pdf"]  // OCR processing
   }
   ```

3. **Combine both if needed**:
   ```json
   {
     "user_input": "https://example.com/article",
     "attachments": ["https://example.com/supporting-doc.pdf"]
   }
   ```

### For Slide Backgrounds

1. **News Mode - Default Images**:
   ```json
   {
     "mode": "news",
     "image_source": null  // No attachments needed
   }
   ```

2. **News Mode - Custom Images**:
   ```json
   {
     "mode": "news",
     "image_source": "custom",
     "attachments": ["https://example.com/image.jpg"]  // Same image for all slides
   }
   ```

3. **Curious Mode - AI Images**:
   ```json
   {
     "mode": "curious",
     "image_source": "ai",
     "prompt_keywords": ["quantum", "computing"]  // Fallback only
   }
   ```

4. **Curious Mode - Pexels Images**:
   ```json
   {
     "mode": "curious",
     "image_source": "pexels",
     "prompt_keywords": ["quantum", "computing", "science"]  // Required
   }
   ```

5. **Curious Mode - Custom Images**:
   ```json
   {
     "mode": "curious",
     "image_source": "custom",
     "attachments": ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]
   }
   ```

### For News Articles with Images

**Scenario**: Extract content from article URL AND use article image as background

```json
{
  "mode": "news",
  "user_input": "https://example.com/news-article",
  "image_source": "custom",
  "attachments": ["https://example.com/news-article-image.jpg"]
}
```

**What Happens**:
1. `user_input` URL → Article content extracted
2. `attachments` image → OCR (if text in image) + Slide background

---

## Common Mistakes to Avoid

### ✅ Using `image_source: "ai"` in News Mode (Now Supported)

```json
{
  "mode": "news",
  "image_source": "ai",
  "prompt_keywords": ["news", "technology", "breaking"]  // ✅ SUPPORTED
}
```

**Note**: AI image generation is now supported in News mode with prompt keywords

### ❌ Mistake 2: Expecting `user_input` images to become backgrounds

```json
{
  "user_input": "https://example.com/image.jpg",
  "image_source": "custom"  // ❌ Won't work - image not in attachments
}
```

**Fix**: Put image in `attachments`:
```json
{
  "user_input": "https://example.com/image.jpg",  // For content extraction
  "image_source": "custom",
  "attachments": ["https://example.com/image.jpg"]  // For background
}
```

### ❌ Mistake 3: Using `prompt_keywords` in News Mode

```json
{
  "mode": "news",
  "prompt_keywords": ["technology"]  // ❌ NOT USED - ignored
}
```

**Fix**: Remove `prompt_keywords` for News mode

### ❌ Mistake 4: Using `image_source: null` in Curious Mode

```json
{
  "mode": "curious",
  "image_source": null  // ❌ NOT SUPPORTED
}
```

**Fix**: Use `"ai"`, `"pexels"`, or `"custom"`

---

## Quick Reference

### News Mode Field Requirements

| Field | Required | Valid Values | Notes |
|-------|----------|--------------|-------|
| `mode` | ✅ Yes | `"news"` | |
| `template_key` | ✅ Yes | `"test-news-1"`, `"test-news-2"` | |
| `slide_count` | ✅ Yes | `4-10` | |
| `user_input` | ❌ No | URL, text, or file | Auto-detects type |
| `attachments` | ❌ No | Image/PDF URLs | Required if `image_source: "custom"` |
| `image_source` | ❌ No | `null` or `"custom"` | `null` = default, `"custom"` = requires `attachments` |
| `prompt_keywords` | ❌ No | `[]` | **NOT USED** - ignored |

### Curious Mode Field Requirements

| Field | Required | Valid Values | Notes |
|-------|----------|--------------|-------|
| `mode` | ✅ Yes | `"curious"` | |
| `template_key` | ✅ Yes | `"curious-template-1"` | |
| `slide_count` | ✅ Yes | `7+` | Typically 7 |
| `user_input` | ❌ No | URL, text, or file | Auto-detects type |
| `attachments` | ❌ No | Image/PDF URLs | Required if `image_source: "custom"` |
| `image_source` | ✅ Yes | `"ai"`, `"pexels"`, or `"custom"` | `null` NOT supported |
| `prompt_keywords` | ❌ No | `[]` | Required for `"pexels"`, fallback for `"ai"` |

---

**Last Updated**: 2025-01-21  
**Version**: 1.0.0

