# Frontend Integration Guide - Story Generation API

Complete guide for frontend developers on how to integrate the Story Generation API with proper UI/UX flow.

## Table of Contents
1. [Overview](#overview)
2. [Mode Selection](#mode-selection)
3. [Image Source Rules](#image-source-rules)
4. [Parameter Reference](#parameter-reference)
5. [UI/UX Flow](#uiux-flow)
6. [Conditional Logic](#conditional-logic)
7. [Examples](#examples)

---

## Overview

The Story Generation API allows users to create AMP Story web stories with different modes and image sources. The frontend must handle conditional parameter visibility based on user selections.

**Base Endpoint**: `POST /stories`

---

## Mode Selection

### Available Modes

| Mode | Value | Description |
|------|-------|-------------|
| **News** | `"news"` | For news articles and current events |
| **Curious** | `"curious"` | For educational/curiosity-driven content |

### Mode Selection Impact

When user selects a mode, it affects:
- ✅ Available image sources
- ✅ Required/optional parameters
- ✅ Default behaviors
- ✅ UI element visibility

---

## Image Source Rules

### Image Source Options by Mode

#### For **News Mode** (`mode: "news"`)

| Image Source | Value | When to Show | Description |
|--------------|-------|--------------|-------------|
| **Default** | `null` or `""` | Always available | Uses default polaris images (polariscover.png, polarisslide.png) |
| **Custom** | `"custom"` | Always available | User uploads/selects custom image |
| **AI Generated** | `"ai"` | Always available | AI generates images based on keywords |
| **Pexels** | `"pexels"` | Always available | Fetches stock images from Pexels |

#### For **Curious Mode** (`mode: "curious"`)

| Image Source | Value | When to Show | Description |
|--------------|-------|--------------|-------------|
| **AI Generated** | `"ai"` | Always available | AI generates images based on keywords |
| **Pexels** | `"pexels"` | Always available | Fetches stock images from Pexels |
| **Custom** | `"custom"` | Always available | User uploads/selects custom image |

**Note**: Curious mode does NOT support `null` (default images).

---

## Parameter Reference

### Required Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `mode` | `string` | ✅ Yes | Story mode: `"news"` or `"curious"` |
| `template_key` | `string` | ✅ Yes | Template identifier (e.g., `"test-news-1"`, `"test-news-2"`) |
| `slide_count` | `integer` | ✅ Yes | Total slides (4-10). For 4 slides: 1 cover + 2 middle + 1 CTA |

### Optional Parameters

| Parameter | Type | Required | Description | Conditional |
|-----------|------|----------|-------------|-------------|
| `user_input` | `string` | ❌ No | Unified input (URL, text, or file). Auto-detected. **Takes precedence** over separate fields. | Always available |
| `category` | `string` | ❌ No | Story category (e.g., "News", "Technology", "Sports") | Recommended for News mode |
| `image_source` | `string \| null` | ❌ No | Image source: `null`, `"custom"`, `"ai"`, `"pexels"` | See [Image Source Rules](#image-source-rules) |
| `attachments` | `array<string>` | ❌ No | Image URLs/URIs. Required if `image_source="custom"` | Show when `image_source="custom"` |
| `prompt_keywords` | `array<string>` | ❌ No | Keywords for AI/Pexels image generation | Show when `image_source="ai"` or `"pexels"` |
| `voice_engine` | `string` | ❌ No | Voice provider: `"azure_basic"` or `"elevenlabs_pro"` | Always available |
| `text_prompt` | `string` | ❌ No | **Legacy field** - Use `user_input` instead | For backward compatibility only |
| `notes` | `string` | ❌ No | **Legacy field** - Use `user_input` instead | For backward compatibility only |
| `urls` | `array<string>` | ❌ No | **Legacy field** - Use `user_input` instead | For backward compatibility only |

---

## UI/UX Flow

### Step-by-Step Flow

#### Step 1: Mode Selection
```
┌─────────────────────────┐
│  Select Story Mode      │
├─────────────────────────┤
│  ○ News                 │
│  ● Curious              │
└─────────────────────────┘
```

**Action**: User selects mode → Update available image sources

---

#### Step 2: Template Selection
```
┌─────────────────────────┐
│  Select Template        │
├─────────────────────────┤
│  ○ test-news-1          │
│  ○ test-news-2          │
│  ○ test-curious-1       │
└─────────────────────────┘
```

**Action**: User selects template → Validate template matches mode

---

#### Step 3: Slide Count
```
┌─────────────────────────┐
│  Number of Slides       │
├─────────────────────────┤
│  [4] [5] [6] [7] [8]    │
│  (4-10, default: 4)     │
└─────────────────────────┘
```

**Action**: User selects slide count (4-10)

---

#### Step 4: Image Source Selection

**For News Mode:**
```
┌─────────────────────────┐
│  Image Source           │
├─────────────────────────┤
│  ○ Default (Polaris)    │  ← image_source: null
│  ○ Custom Upload        │  ← image_source: "custom"
│  ○ AI Generated         │  ← image_source: "ai"
│  ○ Pexels Stock         │  ← image_source: "pexels"
└─────────────────────────┘
```

**For Curious Mode:**
```
┌─────────────────────────┐
│  Image Source           │
├─────────────────────────┤
│  ○ AI Generated         │  ← image_source: "ai"
│  ○ Pexels Stock         │  ← image_source: "pexels"
│  ○ Custom Upload        │  ← image_source: "custom"
└─────────────────────────┘
```

**Action**: User selects image source → Show/hide conditional fields

---

#### Step 5: Conditional Fields Based on Image Source

##### If `image_source = "custom"`:
```
┌─────────────────────────┐
│  Upload Custom Image    │
├─────────────────────────┤
│  [Choose File]          │
│  or                     │
│  [Enter Image URL]      │
│                         │
│  Accepted formats:      │
│  JPG, PNG, WEBP        │
│                         │
│  Supports:              │
│  • HTTP/HTTPS URLs      │
│  • S3 URIs (s3://...)   │
│  • Local files          │
└─────────────────────────┘
```

**Fields to Show**:
- File upload input OR
- URL input field
- Preview of selected image

**Payload**:
```json
{
  "image_source": "custom",
  "attachments": [
    "https://example.com/image.jpg"  // or file path or S3 URI
  ]
}
```

---

##### If `image_source = "ai"` or `"pexels"`:
```
┌─────────────────────────┐
│  Image Keywords         │
├─────────────────────────┤
│  [technology]           │
│  [AI]                   │
│  [innovation]           │
│                         │
│  [+ Add Keyword]        │
│                         │
│  (Keywords help AI      │
│   generate relevant     │
│   images)               │
└─────────────────────────┘
```

**Fields to Show**:
- Keyword input (multi-select or tags)
- Add/remove keyword buttons
- Preview of suggested keywords

**Payload**:
```json
{
  "image_source": "ai",  // or "pexels"
  "prompt_keywords": [
    "technology",
    "AI",
    "innovation"
  ]
}
```

---

##### If `image_source = null` (News Mode Only):
```
┌─────────────────────────┐
│  Default Images         │
├─────────────────────────┤
│  ✓ Using default        │
│    Polaris images       │
│                         │
│  Cover: polariscover.png│
│  Slides: polarisslide.png│
└─────────────────────────┘
```

**Fields to Show**:
- Info message (no input needed)
- Preview of default images (optional)

**Payload**:
```json
{
  "image_source": null
  // No attachments or prompt_keywords needed
}
```

---

#### Step 6: Content Input
```
┌─────────────────────────┐
│  Story Content          │
├─────────────────────────┤
│  [Enter URL or Text]    │
│                         │
│  Examples:              │
│  • https://example.com  │
│  • Your story text...   │
│                         │
│  Auto-detects:          │
│  • URLs → Extracts      │
│  • Text → Uses as-is    │
└─────────────────────────┘
```

**Fields to Show**:
- Single unified input field (`user_input`)
- Helper text explaining auto-detection
- Preview of detected type (optional)

**Payload**:
```json
{
  "user_input": "https://indianexpress.com/article/..."
  // OR
  "user_input": "Breaking news: Technology breakthrough..."
}
```

---

#### Step 7: Voice Selection
```
┌─────────────────────────┐
│  Voice Engine           │
├─────────────────────────┤
│  ○ Azure Basic          │  ← voice_engine: "azure_basic"
│  ○ ElevenLabs Pro       │  ← voice_engine: "elevenlabs_pro"
└─────────────────────────┘
```

**Fields to Show**:
- Radio buttons or dropdown
- Voice preview (optional)

---

#### Step 8: Category (Optional, Recommended for News)
```
┌─────────────────────────┐
│  Category               │
├─────────────────────────┤
│  [News ▼]               │
│                         │
│  Options:               │
│  • News                 │
│  • Technology           │
│  • Sports               │
│  • Entertainment        │
│  • Business             │
└─────────────────────────┘
```

**Fields to Show**:
- Dropdown or autocomplete
- Recommended for News mode

---

## Conditional Logic

### Frontend Validation Rules

#### Rule 1: Image Source Dependency
```javascript
if (image_source === "custom") {
  // REQUIRED: attachments array with at least 1 item
  if (!attachments || attachments.length === 0) {
    showError("Please upload or provide an image URL");
    return false;
  }
}

if (image_source === "ai" || image_source === "pexels") {
  // RECOMMENDED: prompt_keywords (but not strictly required)
  if (!prompt_keywords || prompt_keywords.length === 0) {
    showWarning("Keywords help generate better images");
  }
}
```

#### Rule 2: Mode-Specific Image Sources
```javascript
if (mode === "curious") {
  // Hide "Default" option
  hideImageSourceOption("default");
  
  // Show only: AI, Pexels, Custom
  showImageSourceOptions(["ai", "pexels", "custom"]);
}

if (mode === "news") {
  // Show all options including Default
  showImageSourceOptions(["default", "custom", "ai", "pexels"]);
}
```

#### Rule 3: Content Input Priority
```javascript
// user_input takes precedence over text_prompt, urls, notes
if (user_input) {
  // Use user_input, ignore text_prompt, urls, notes
  payload = {
    user_input: user_input,
    // ... other fields
  };
} else {
  // Fallback to legacy fields
  payload = {
    text_prompt: text_prompt,
    urls: urls,
    notes: notes,
    // ... other fields
  };
}
```

#### Rule 4: Slide Count Validation
```javascript
if (slide_count < 4 || slide_count > 10) {
  showError("Slide count must be between 4 and 10");
  return false;
}
```

---

## Complete Request Payload Examples

### Example 1: News Mode with Default Images
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "https://indianexpress.com/article/...",
  "image_source": null,
  "voice_engine": "azure_basic"
}
```

**UI State**:
- ✅ Mode: News selected
- ✅ Template: test-news-1
- ✅ Slide count: 4
- ✅ Image source: Default (null)
- ✅ Content: URL provided
- ✅ Voice: Azure Basic

---

### Example 2: News Mode with Custom Image
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "Breaking news: Technology breakthrough",
  "image_source": "custom",
  "attachments": [
    "https://example.com/my-image.jpg"
  ],
  "voice_engine": "azure_basic"
}
```

**UI State**:
- ✅ Mode: News selected
- ✅ Template: test-news-1
- ✅ Slide count: 4
- ✅ Image source: Custom
- ✅ **Image uploaded/URL provided** (attachments array)
- ✅ Content: Text provided
- ✅ Voice: Azure Basic

---

### Example 3: News Mode with AI Images
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 5,
  "category": "Technology",
  "user_input": "https://techcrunch.com/article/...",
  "image_source": "ai",
  "prompt_keywords": [
    "technology",
    "AI",
    "innovation",
    "future"
  ],
  "voice_engine": "elevenlabs_pro"
}
```

**UI State**:
- ✅ Mode: News selected
- ✅ Template: test-news-1
- ✅ Slide count: 5
- ✅ Image source: AI Generated
- ✅ **Keywords provided** (prompt_keywords array)
- ✅ Content: URL provided
- ✅ Voice: ElevenLabs Pro

---

### Example 4: Curious Mode with Pexels
```json
{
  "mode": "curious",
  "template_key": "test-curious-1",
  "slide_count": 6,
  "user_input": "How does quantum computing work?",
  "image_source": "pexels",
  "prompt_keywords": [
    "quantum",
    "computing",
    "science"
  ],
  "voice_engine": "azure_basic"
}
```

**UI State**:
- ✅ Mode: Curious selected
- ✅ Template: test-curious-1
- ✅ Slide count: 6
- ✅ Image source: Pexels
- ✅ **Keywords provided** (prompt_keywords array)
- ✅ Content: Text question provided
- ✅ Voice: Azure Basic
- ⚠️ Category: Not shown (not used in Curious mode)

---

## Frontend Implementation Checklist

### ✅ Required UI Components

- [ ] Mode selector (Radio buttons or Tabs)
- [ ] Template selector (Dropdown or Cards)
- [ ] Slide count selector (Slider or Number input, 4-10)
- [ ] Image source selector (Radio buttons, conditional based on mode)
- [ ] Content input (Textarea with URL/text detection)
- [ ] Voice engine selector (Radio buttons or Dropdown)
- [ ] Category selector (Dropdown, for News mode)
- [ ] Submit/Generate button

### ✅ Conditional Components

- [ ] **Image Upload Component** (Show when `image_source="custom"`)
  - File picker
  - URL input
  - Image preview
  - Format validation (JPG, PNG, WEBP)

- [ ] **Keyword Input Component** (Show when `image_source="ai"` or `"pexels"`)
  - Multi-tag input
  - Add/remove keywords
  - Keyword suggestions (optional)

- [ ] **Default Image Info** (Show when `image_source=null` in News mode)
  - Info message
  - Preview of default images (optional)

### ✅ Validation Rules

- [ ] Mode is selected
- [ ] Template is selected and matches mode
- [ ] Slide count is between 4-10
- [ ] If `image_source="custom"`, `attachments` array has at least 1 item
- [ ] If `image_source="ai"` or `"pexels"`, `prompt_keywords` is recommended
- [ ] `user_input` or legacy fields (`text_prompt`/`urls`) are provided
- [ ] Voice engine is selected

### ✅ Error Handling

- [ ] Show validation errors before submission
- [ ] Handle API errors (400, 500)
- [ ] Display error messages from API response
- [ ] Show loading state during request
- [ ] Handle timeout (300 seconds)

### ✅ Success Handling

- [ ] Display success message
- [ ] Show generated story ID
- [ ] Provide link to view HTML output
- [ ] Show image/voice asset URLs (optional)

---

## API Response Handling

### Success Response (200 OK)
```json
{
  "id": "uuid-here",
  "mode": "news",
  "category": "News",
  "slide_count": 4,
  "template_key": "test-news-1",
  "slide_deck": {
    "slides": [...]
  },
  "image_assets": [...],
  "voice_assets": [...],
  "created_at": "2025-01-XX...",
  ...
}
```

**Frontend Actions**:
1. Display success message
2. Show story ID
3. Provide download/view link for HTML file
4. Show preview (optional)

### Error Response (400/500)
```json
{
  "detail": "Error message here"
}
```

**Frontend Actions**:
1. Display error message
2. Highlight problematic fields
3. Allow user to retry

---

## Best Practices

### 1. Progressive Disclosure
- Show only relevant fields based on selections
- Hide advanced options by default
- Use accordions/tabs for optional sections

### 2. Real-time Validation
- Validate as user types/selects
- Show inline error messages
- Disable submit button until valid

### 3. User Feedback
- Show loading spinner during API call
- Display progress for long operations
- Provide clear success/error messages

### 4. Image Handling
- Validate image format before upload
- Show image preview
- Handle large file sizes
- Support drag-and-drop (optional)

### 5. URL Detection
- Auto-detect URLs in `user_input`
- Show detected type (URL vs Text)
- Validate URL format

---

## Quick Reference Table

| Selection | Parameter Value | Show Fields | Hide Fields |
|-----------|----------------|-------------|-------------|
| Mode: News | `mode: "news"` | All image sources | - |
| Mode: Curious | `mode: "curious"` | AI, Pexels, Custom | Default option |
| Image: Default | `image_source: null` | Info message | Upload, Keywords |
| Image: Custom | `image_source: "custom"` | Upload/URL input | Keywords |
| Image: AI | `image_source: "ai"` | Keywords input | Upload |
| Image: Pexels | `image_source: "pexels"` | Keywords input | Upload |

---

## Support & Resources

- **API Documentation**: See `API_USAGE_GUIDE.md`
- **Example Files**: 
  - `example_default_images.json`
  - `example_custom_image_url.json`
  - `example_custom_image_s3.json`
- **Custom Image Guide**: See `CUSTOM_IMAGE_GUIDE.md`

---

**Last Updated**: 2025-01-XX
**API Version**: 1.0.0

