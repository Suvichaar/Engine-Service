# Streamlit Frontend - Input System Guide

Complete documentation for the Streamlit frontend input system, explaining how each field works for News and Curious modes.

## 📋 Table of Contents

1. [Overview](#overview)
2. [Mode Selection](#mode-selection)
3. [News Mode Input Fields](#news-mode-input-fields)
4. [Curious Mode Input Fields](#curious-mode-input-fields)
5. [Field Descriptions](#field-descriptions)
6. [Input Flow Diagrams](#input-flow-diagrams)
7. [Common Patterns](#common-patterns)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Streamlit frontend provides a user-friendly interface for creating web stories. The input system adapts based on the selected mode (News or Curious), showing relevant fields and options.

### Key Concepts

- **Content Input**: Text/URL for story content
- **Attachments**: Files for content extraction (OCR)
- **Background Images**: Images for slide backgrounds (separate from content)
- **Image Source**: How background images are generated/selected

---

## Mode Selection

### News Mode
- **Purpose**: Factual news articles and current events
- **Templates**: `test-news-1`, `test-news-2`
- **Slide Count**: 4-10 slides
- **Image Source**: `null` (default) or `"custom"`

### Curious Mode
- **Purpose**: Educational and explainable content
- **Templates**: `curious-template-1`
- **Slide Count**: 7-15 slides
- **Image Source**: `"ai"`, `"pexels"`, or `"custom"`

---

## News Mode Input Fields

### 1. **Template** (Dropdown)
- **Options**: `test-news-1`, `test-news-2`
- **Purpose**: Select HTML template for rendering
- **Required**: Yes

### 2. **Slide Count** (Number Input)
- **Range**: 4-10
- **Default**: 4
- **Purpose**: Number of slides in the story
- **Required**: Yes

### 3. **Category** (Text Input)
- **Default**: "News"
- **Examples**: "Technology", "Sports", "Politics", "Business"
- **Purpose**: Story category for classification
- **Required**: No (but recommended)

### 4. **Article URL or Content** (Text Area)
- **Purpose**: Main content input
- **Accepts**:
  - Article URLs (e.g., `https://indianexpress.com/article/...`)
  - Article content (pasted text)
- **Processing**:
  - URLs → Extracted via `URLContentExtractor` (newspaper3k)
  - Text → Used directly as `text_prompt`
- **Required**: Yes (or attachments)

### 5. **Attachments** (File Uploader - Optional)
- **Purpose**: Documents or images for content extraction
- **Accepts**: PDF, DOC, DOCX, JPG, JPEG, PNG, WEBP
- **Multiple Files**: Yes
- **Processing**:
  - Documents → OCR via Azure Document Intelligence
  - Images → OCR for text extraction
  - Content → Added to `semantic_chunks` for story generation
- **Note**: Files need to be uploaded to S3 first (production)
- **Required**: No

### 6. **Background Image Settings** (Radio)
- **Options**:
  - **Default Images**: Uses default news images (`image_source: null`)
  - **Custom Image**: Upload custom image (`image_source: "custom"`)
- **Purpose**: Images for slide backgrounds (NOT content)
- **Processing**:
  - Custom images → Uploaded to S3, resized to 720x1280 (portrait)
  - Used for all slides in News mode
- **Required**: No (defaults to default images)

### 7. **Voice Engine** (Dropdown)
- **Options**: `azure_basic`, `elevenlabs_pro`
- **Purpose**: Text-to-speech engine for narration
- **Required**: Yes

---

## Curious Mode Input Fields

### 1. **Template** (Dropdown)
- **Options**: `curious-template-1`
- **Purpose**: Select HTML template for rendering
- **Required**: Yes

### 2. **Slide Count** (Number Input)
- **Range**: 7-15
- **Default**: 7
- **Purpose**: Number of slides in the story
- **Required**: Yes

### 3. **Category** (Dropdown)
- **Options**: 
  - Education
  - Science
  - Technology
  - History
  - Nature
  - Space
  - Mathematics
  - Physics
  - Biology
  - Chemistry
  - General Knowledge
- **Default**: Education
- **Purpose**: Story category for classification
- **Required**: Yes

### 4. **Topic or Keywords** (Text Area)
- **Purpose**: Main content input
- **Accepts**:
  - Topics (e.g., "How does quantum computing work?")
  - Keywords (e.g., "quantum, computing, science")
  - Questions
- **Processing**: Used as `text_prompt` for educational content generation
- **Required**: Yes (or attachments)

### 5. **Attachments** (File Uploader - Optional)
- **Purpose**: Images or documents for content extraction
- **Accepts**: PDF, DOC, DOCX, JPG, JPEG, PNG, WEBP
- **Multiple Files**: Yes
- **Processing**:
  - Documents → OCR via Azure Document Intelligence
  - Images → OCR for text extraction
  - Content → Added to `semantic_chunks` for story generation
- **Note**: Files need to be uploaded to S3 first (production)
- **Required**: No

### 6. **Background Image Settings** (Radio)
- **Options**:
  - **AI Generated**: DALL-E 3 generates images from prompts (`image_source: "ai"`)
  - **Pexels**: Stock images from Pexels (`image_source: "pexels"`)
  - **Custom Images**: Upload custom images (`image_source: "custom"`)

#### 6a. **Prompt Keywords** (Text Input - If AI/Pexels)
- **Purpose**: Keywords for AI image generation or Pexels search
- **Format**: Comma-separated (e.g., "quantum, computing, science")
- **Required**: Recommended for AI/Pexels

#### 6b. **Custom Images Upload** (File Uploader - If Custom)
- **Purpose**: Upload images for slide backgrounds
- **Accepts**: JPG, JPEG, PNG, WEBP
- **Multiple Files**: Yes (must match slide_count)
- **Requirement**: Must upload exactly `slide_count` images
- **Processing**:
  - Each image → Uploaded to S3, resized to 720x1280 (portrait)
  - One image per slide background
- **Required**: Yes (if custom selected)

### 7. **Voice Engine** (Dropdown)
- **Options**: `azure_basic`, `elevenlabs_pro`
- **Purpose**: Text-to-speech engine for narration
- **Required**: Yes

---

## Field Descriptions

### Content Input vs Attachments

| Field | Purpose | Processing | Where It Reflects |
|-------|---------|------------|-------------------|
| **Content Input** | Main story content | URL extraction or direct text | `semantic_chunks` → Story narrative |
| **Attachments** | Additional content source | OCR/document processing | `semantic_chunks` → Story narrative |
| **Background Images** | Slide backgrounds | S3 upload, resize to 720x1280 | `image_assets` → Slide backgrounds |

### Image Source Options

#### News Mode
- **Default Images** (`image_source: null`):
  - Uses predefined default images
  - No upload required
  - Same image for all slides (or template-specific)

- **Custom Image** (`image_source: "custom"`):
  - Upload one image
  - Used for all slide backgrounds
  - Uploaded to S3 in portrait (720x1280)

#### Curious Mode
- **AI Generated** (`image_source: "ai"`):
  - DALL-E 3 generates images from alt texts
  - Requires `prompt_keywords` for better results
  - One image per slide

- **Pexels** (`image_source: "pexels"`):
  - Stock images from Pexels
  - Searched using `prompt_keywords`
  - One image per slide

- **Custom Images** (`image_source: "custom"`):
  - Upload multiple images (must match `slide_count`)
  - One image per slide background
  - Uploaded to S3 in portrait (720x1280)

---

## Input Flow Diagrams

### News Mode Flow

```
User Input
  ├─ Article URL → URLContentExtractor → semantic_chunks
  └─ Article Text → text_prompt → semantic_chunks
       ↓
Attachments (Optional)
  └─ Documents/Images → OCR → semantic_chunks
       ↓
semantic_chunks → NewsModelClient → Story Narrative
       ↓
Background Images
  ├─ Default (null) → Default images
  └─ Custom → S3 Upload (720x1280) → image_assets
       ↓
Final Story (HTML + Images + Voice)
```

### Curious Mode Flow

```
User Input
  ├─ Topic/Keywords → text_prompt → semantic_chunks
  └─ Question → text_prompt → semantic_chunks
       ↓
Attachments (Optional)
  └─ Documents/Images → OCR → semantic_chunks
       ↓
semantic_chunks → CuriousModelClient → Story Narrative (with alt texts)
       ↓
Background Images
  ├─ AI → DALL-E 3 (from alt texts) → image_assets
  ├─ Pexels → Search (from prompt_keywords) → image_assets
  └─ Custom → S3 Upload (720x1280, multiple) → image_assets
       ↓
Final Story (HTML + Images + Voice)
```

---

## Common Patterns

### Pattern 1: News Article from URL
```
Mode: news
Content: https://indianexpress.com/article/...
Attachments: None
Image Source: Default
Voice: azure_basic
```

### Pattern 2: News with Custom Image
```
Mode: news
Content: Article text...
Attachments: None
Image Source: Custom (upload 1 image)
Voice: azure_basic
```

### Pattern 3: News with Document
```
Mode: news
Content: (empty or summary)
Attachments: PDF document
Image Source: Default
Voice: azure_basic
```

### Pattern 4: Curious with AI Images
```
Mode: curious
Content: How does quantum computing work?
Attachments: None
Image Source: AI
Prompt Keywords: quantum, computing, science
Voice: azure_basic
```

### Pattern 5: Curious with Custom Images
```
Mode: curious
Content: Topic about photosynthesis
Attachments: None
Image Source: Custom
Upload: 7 images (for 7 slides)
Voice: azure_basic
```

### Pattern 6: Curious with Document
```
Mode: curious
Content: (empty or topic)
Attachments: Educational PDF
Image Source: Pexels
Prompt Keywords: education, science
Voice: azure_basic
```

---

## Troubleshooting

### Issue 1: "Please enter content (text/URL) or upload attachments"
**Solution**: Either provide content in text area OR upload attachments

### Issue 2: "Please upload exactly X images for X slides"
**Solution**: For Curious mode with custom images, upload exactly `slide_count` images

### Issue 3: Attachments not working
**Solution**: 
- In production, implement S3 upload first
- Get S3 URLs and add to `attachments` field in payload
- Currently, frontend shows warning (S3 upload not implemented)

### Issue 4: Background images not showing
**Solution**:
- Check if `image_source` is set correctly
- For custom images, ensure S3 upload is implemented
- Verify image URLs are accessible

### Issue 5: Prompt keywords not working
**Solution**:
- Only used for Curious mode with AI/Pexels
- Must be comma-separated
- Should be relevant to content

---

## API Payload Structure

### News Mode Example
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "https://example.com/article",
  "category": "Technology",
  "image_source": null,
  "voice_engine": "azure_basic",
  "attachments": []  // Optional: S3 URLs
}
```

### Curious Mode Example (AI Images)
```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 7,
  "user_input": "How does quantum computing work?",
  "category": "Science",
  "image_source": "ai",
  "prompt_keywords": ["quantum", "computing", "science"],
  "voice_engine": "azure_basic",
  "attachments": []  // Optional: S3 URLs
}
```

### Curious Mode Example (Custom Images)
```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 7,
  "user_input": "Topic about photosynthesis",
  "category": "Biology",
  "image_source": "custom",
  "voice_engine": "azure_basic",
  "attachments": [
    "s3://bucket/image1.jpg",
    "s3://bucket/image2.jpg",
    // ... 7 images total
  ]
}
```

---

## Best Practices

1. **Content Input**:
   - Prefer URLs for News mode (better content extraction)
   - Use clear topics/questions for Curious mode

2. **Attachments**:
   - Use for additional context or when content is in documents
   - Ensure files are readable (not corrupted)

3. **Background Images**:
   - Default images are fastest (News mode)
   - AI images work best with good `prompt_keywords`
   - Custom images give most control

4. **Categories**:
   - Use appropriate categories for better classification
   - Helps with template selection and SEO

5. **Voice Engine**:
   - `azure_basic`: Good quality, faster
   - `elevenlabs_pro`: Higher quality, slower

---

## Future Enhancements

1. **S3 Upload Integration**: Automatic file upload to S3
2. **Image Preview**: Preview images before upload
3. **Progress Tracking**: Show upload/generation progress
4. **Batch Processing**: Upload multiple stories
5. **Template Preview**: Preview templates before selection

---

## Related Documentation

- [FIELD_USAGE_MAPPING.md](./FIELD_USAGE_MAPPING.md) - Complete field usage mapping
- [INPUT_FIELD_GUIDE.md](./INPUT_FIELD_GUIDE.md) - Quick reference guide
- [API_USAGE_GUIDE.md](./API_USAGE_GUIDE.md) - API usage examples
- [FRONTEND_INTEGRATION_GUIDE.md](./FRONTEND_INTEGRATION_GUIDE.md) - Frontend integration guide

