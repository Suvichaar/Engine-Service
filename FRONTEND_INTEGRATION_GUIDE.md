# Frontend Integration Guide - Story Generation API

Complete guide for frontend developers on how to integrate the Story Generation API with proper UI/UX flow, TypeScript examples, and best practices.

## Table of Contents
1. [Overview](#overview)
2. [API Endpoints](#api-endpoints)
3. [Mode Selection](#mode-selection)
4. [Image Source Rules](#image-source-rules)
5. [Parameter Reference](#parameter-reference)
6. [UI/UX Flow](#uiux-flow)
7. [Conditional Logic](#conditional-logic)
8. [TypeScript/JavaScript Examples](#typescriptjavascript-examples)
9. [Response Handling](#response-handling)
10. [Error Handling](#error-handling)
11. [Examples](#examples)
12. [Implementation Checklist](#implementation-checklist)

---

## Overview

The Story Generation API allows users to create AMP Story web stories with different modes and image sources. The frontend must handle conditional parameter visibility based on user selections.

**Base URL**: `http://localhost:8000` (development) or your production URL  
**API Endpoint**: `POST /stories`  
**Content-Type**: `application/json`

---

## API Endpoints

### Create Story
```
POST /stories
```

**Request**: `StoryCreateRequest` (see [Parameter Reference](#parameter-reference))  
**Response**: `StoryResponse` (200 OK) or Error (400/500)

### Get Story
```
GET /stories/{story_id}
```

**Response**: `StoryResponse` (200 OK) or 404 Not Found

### List Templates
```
GET /templates
```

**Response**: `List[string]` - Array of available template keys

---

## Mode Selection

### Available Modes

| Mode | Value | Description | Slide Count Range | Templates |
|------|-------|-------------|------------------|-----------|
| **News** | `"news"` | For news articles and current events | 4-10 | `test-news-1`, `test-news-2` |
| **Curious** | `"curious"` | For educational/curiosity-driven content | 7+ (typically 7) | `curious-template-1` |

### Mode Selection Impact

When user selects a mode, it affects:
- ✅ Available image sources
- ✅ Required/optional parameters
- ✅ Default behaviors
- ✅ UI element visibility
- ✅ Slide count range

---

## Image Source Rules

### Image Source Options by Mode

#### For **News Mode** (`mode: "news"`)

| Image Source | Value | When to Show | Description | Requires |
|--------------|-------|--------------|-------------|----------|
| **Default** | `null` or `""` | Always available | Uses default polaris images (polariscover.png, polarisslide.png) | Nothing |
| **AI Generated** | `"ai"` | Always available | AI generates images using DALL-E 3 based on content + keywords | `prompt_keywords` (recommended) |
| **Custom** | `"custom"` | Always available | User uploads/selects custom image | `attachments` array |

**Note**: News mode supports Default, AI, and Custom images. Pexels is **NOT** supported in News mode.

#### For **Curious Mode** (`mode: "curious"`)

| Image Source | Value | When to Show | Description | Requires |
|--------------|-------|--------------|-------------|----------|
| **AI Generated** | `"ai"` | Always available | AI generates images using **alt texts** from content (more contextual) | `prompt_keywords` (optional, used as fallback) |
| **Pexels** | `"pexels"` | Always available | Fetches stock images from Pexels | `prompt_keywords` (recommended) |
| **Custom** | `"custom"` | Always available | User uploads/selects custom image | `attachments` array |

**Important Notes**:
- Curious mode does **NOT** support `null` (default images)
- For Curious mode with `image_source: "ai"`, the system automatically generates alt texts (s0alt1, s1alt1, etc.) from content
- AI images in Curious mode are more contextually relevant than News mode

---

## Parameter Reference

### Required Parameters

| Parameter | Type | Required | Description | Validation |
|-----------|------|----------|-------------|------------|
| `mode` | `string` | ✅ Yes | Story mode: `"news"` or `"curious"` | Must be one of: `"news"`, `"curious"` |
| `template_key` | `string` | ✅ Yes | Template identifier | Min length: 1. Examples: `"test-news-1"`, `"test-news-2"`, `"curious-template-1"` |
| `slide_count` | `integer` | ✅ Yes | Total slides | **News**: 4-10, **Curious**: 7+ (typically 7) |

### Optional Parameters

| Parameter | Type | Required | Description | Conditional | Default |
|-----------|------|----------|-------------|-------------|---------|
| `user_input` | `string` | ❌ No | Unified input (URL, text, or file). Auto-detected. **Takes precedence** over separate fields. | Always available | `null` |
| `category` | `string` | ❌ No | Story category (e.g., "News", "Technology", "Sports") | Recommended for News mode | `null` |
| `image_source` | `string \| null` | ❌ No | Image source: `null` (News only - default), `"custom"` (News only), `"ai"` (Curious only), `"pexels"` (Curious only) | See [Image Source Rules](#image-source-rules) | `null` (News), must be set for Curious |
| `attachments` | `array<string>` | ❌ No | Image URLs/URIs. Required if `image_source="custom"` | Show when `image_source="custom"` | `[]` |
| `prompt_keywords` | `array<string>` | ❌ No | Keywords for AI/Pexels image generation (Curious mode only, not used in News mode) | Show when `image_source="ai"` or `"pexels"` (Curious mode only) | `[]` |
| `voice_engine` | `string` | ❌ No | Voice provider: `"azure_basic"` or `"elevenlabs_pro"` | Always available | `null` |
| `text_prompt` | `string` | ❌ No | **Legacy field** - Use `user_input` instead | For backward compatibility only | `null` |
| `notes` | `string` | ❌ No | **Legacy field** - Use `user_input` instead | For backward compatibility only | `null` |
| `urls` | `array<string>` | ❌ No | **Legacy field** - Use `user_input` instead | For backward compatibility only | `[]` |

---

## UI/UX Flow

### Step-by-Step Flow

#### Step 1: Mode Selection
```
┌─────────────────────────┐
│  Select Story Mode      │
├─────────────────────────┤
│  ○ News                 │  ← mode: "news"
│  ● Curious              │  ← mode: "curious"
└─────────────────────────┘
```

**Action**: User selects mode → Update available image sources, slide count range, and templates

---

#### Step 2: Template Selection
```
┌─────────────────────────┐
│  Select Template        │
├─────────────────────────┤
│  For News Mode:         │
│  ○ test-news-1          │
│  ○ test-news-2          │
│                         │
│  For Curious Mode:      │
│  ○ curious-template-1   │
└─────────────────────────┘
```

**Action**: User selects template → Validate template matches selected mode

---

#### Step 3: Slide Count
```
┌─────────────────────────┐
│  Number of Slides       │
├─────────────────────────┤
│  News Mode:             │
│  [4] [5] [6] [7] [8] [9] [10] │
│  (4-10, default: 4)     │
│                         │
│  Curious Mode:          │
│  [7] [8] [9] [10]       │
│  (7+, default: 7)       │
└─────────────────────────┘
```

**Action**: User selects slide count (validate based on mode)

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
│  ○ AI Generated         │  ← image_source: "ai" (uses alt texts)
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
│                         │
│  Preview:               │
│  [Image Preview]        │
└─────────────────────────┘
```

**Fields to Show**:
- File upload input OR
- URL input field
- Image preview
- Format validation (JPG, PNG, WEBP)

**Payload**:
```json
{
  "image_source": "custom",
  "attachments": [
    "https://example.com/image.jpg"  // or "s3://bucket/key.jpg" or local file path
  ]
}
```

---

##### If `image_source = "ai"` or `"pexels"`:
```
┌─────────────────────────┐
│  Image Keywords         │
├─────────────────────────┤
│  [technology] [x]       │
│  [AI] [x]               │
│  [innovation] [x]       │
│                         │
│  [+ Add Keyword]        │
│                         │
│  (Keywords help AI      │
│   generate relevant     │
│   images)               │
│                         │
│  Note for Curious:      │
│  AI uses content-based  │
│  alt texts (keywords    │
│  are fallback)          │
└─────────────────────────┘
```

**Fields to Show**:
- Keyword input (multi-select or tags)
- Add/remove keyword buttons
- Preview of suggested keywords
- Info message for Curious mode (alt texts are used)

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
│                         │
│  [Preview Images]       │
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
│                         │
│  Detected: [URL] [Text] │
└─────────────────────────┘
```

**Fields to Show**:
- Single unified input field (`user_input`)
- Helper text explaining auto-detection
- Preview of detected type (optional)
- Character counter (optional)

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
│                         │
│  [Preview Voice]        │
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
│                         │
│  (Recommended for       │
│   News mode)            │
└─────────────────────────┘
```

**Fields to Show**:
- Dropdown or autocomplete
- Recommended for News mode
- Hide for Curious mode (optional)

---

## Conditional Logic

### Frontend Validation Rules

#### Rule 1: Image Source Dependency
```typescript
function validateImageSource(imageSource: string | null, attachments: string[], promptKeywords: string[]): ValidationResult {
  if (imageSource === "custom") {
    // REQUIRED: attachments array with at least 1 item
    if (!attachments || attachments.length === 0) {
      return {
        valid: false,
        error: "Please upload or provide an image URL when using custom images"
      };
    }
  }

  if (imageSource === "ai" || imageSource === "pexels") {
    // RECOMMENDED: prompt_keywords (but not strictly required)
    if (!promptKeywords || promptKeywords.length === 0) {
      return {
        valid: true,
        warning: "Keywords help generate better images. Consider adding some."
      };
    }
  }

  return { valid: true };
}
```

#### Rule 2: Mode-Specific Image Sources
```typescript
function getAvailableImageSources(mode: "news" | "curious"): ImageSourceOption[] {
  if (mode === "curious") {
    // Hide "Default" option
    return [
      { value: "ai", label: "AI Generated", description: "Uses content-based alt texts" },
      { value: "pexels", label: "Pexels Stock", description: "Royalty-free stock images" },
      { value: "custom", label: "Custom Upload", description: "Upload your own image" }
    ];
  }

  if (mode === "news") {
    // Show all options including Default
    return [
      { value: null, label: "Default (Polaris)", description: "Uses default images" },
      { value: "custom", label: "Custom Upload", description: "Upload your own image" },
      { value: "ai", label: "AI Generated", description: "AI generates based on keywords" },
      { value: "pexels", label: "Pexels Stock", description: "Royalty-free stock images" }
    ];
  }

  return [];
}
```

#### Rule 3: Content Input Priority
```typescript
function buildPayload(formData: FormData): StoryCreateRequest {
  // user_input takes precedence over text_prompt, urls, notes
  if (formData.user_input) {
    return {
      mode: formData.mode,
      template_key: formData.template_key,
      slide_count: formData.slide_count,
      user_input: formData.user_input,  // Use unified input
      image_source: formData.image_source,
      // ... other fields
    };
  } else {
    // Fallback to legacy fields (for backward compatibility)
    return {
      mode: formData.mode,
      template_key: formData.template_key,
      slide_count: formData.slide_count,
      text_prompt: formData.text_prompt,
      urls: formData.urls,
      notes: formData.notes,
      // ... other fields
    };
  }
}
```

#### Rule 4: Slide Count Validation
```typescript
function validateSlideCount(mode: "news" | "curious", slideCount: number): ValidationResult {
  if (mode === "news") {
    if (slideCount < 4 || slideCount > 10) {
      return {
        valid: false,
        error: "Slide count must be between 4 and 10 for News mode"
      };
    }
  }

  if (mode === "curious") {
    if (slideCount < 7) {
      return {
        valid: false,
        error: "Slide count must be at least 7 for Curious mode"
      };
    }
  }

  return { valid: true };
}
```

#### Rule 5: Template-Mode Matching
```typescript
function validateTemplate(mode: "news" | "curious", templateKey: string): ValidationResult {
  const newsTemplates = ["test-news-1", "test-news-2"];
  const curiousTemplates = ["curious-template-1"];

  if (mode === "news" && !newsTemplates.includes(templateKey)) {
    return {
      valid: false,
      error: `Template "${templateKey}" is not valid for News mode. Use: ${newsTemplates.join(", ")}`
    };
  }

  if (mode === "curious" && !curiousTemplates.includes(templateKey)) {
    return {
      valid: false,
      error: `Template "${templateKey}" is not valid for Curious mode. Use: ${curiousTemplates.join(", ")}`
    };
  }

  return { valid: true };
}
```

---

## TypeScript/JavaScript Examples

### TypeScript Interfaces

```typescript
// Request Types
interface StoryCreateRequest {
  mode: "news" | "curious";
  template_key: string;
  slide_count: number;
  category?: string;
  user_input?: string;
  image_source?: "ai" | "pexels" | "custom" | null;
  attachments?: string[];
  prompt_keywords?: string[];
  voice_engine?: "azure_basic" | "elevenlabs_pro";
  // Legacy fields (for backward compatibility)
  text_prompt?: string;
  notes?: string;
  urls?: string[];
}

// Response Types
interface SlideBlock {
  placeholder_id: string;
  text: string | null;
  image_url: string | null;
  highlight_tags: string[];
}

interface SlideDeck {
  template_key: string;
  language_code: string | null;
  slides: SlideBlock[];
}

interface ImageAsset {
  source: string;
  original_object_key: string;
  resized_variants: string[];
  description: string | null;
}

interface VoiceAsset {
  provider: string;
  voice_id: string | null;
  audio_url: string;
  duration_seconds: number | null;
}

interface StoryResponse {
  id: string;
  mode: "news" | "curious";
  category: string;
  input_language: string | null;
  slide_count: number;
  template_key: string;
  slide_deck: SlideDeck;
  image_assets: ImageAsset[];
  voice_assets: VoiceAsset[];
  canurl: string;
  canurl1: string;
  created_at: string;
}
```

### API Client Example

```typescript
class StoryAPI {
  private baseURL: string;

  constructor(baseURL: string = "http://localhost:8000") {
    this.baseURL = baseURL;
  }

  async createStory(request: StoryCreateRequest): Promise<StoryResponse> {
    const response = await fetch(`${this.baseURL}/stories`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  async getStory(storyId: string): Promise<StoryResponse> {
    const response = await fetch(`${this.baseURL}/stories/${storyId}`);

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error("Story not found");
      }
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  async getTemplates(): Promise<string[]> {
    const response = await fetch(`${this.baseURL}/templates`);
    return response.json();
  }
}
```

### React Hook Example

```typescript
import { useState, useCallback } from "react";

function useStoryGeneration() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [story, setStory] = useState<StoryResponse | null>(null);

  const generateStory = useCallback(async (request: StoryCreateRequest) => {
    setLoading(true);
    setError(null);

    try {
      const api = new StoryAPI();
      const result = await api.createStory(request);
      setStory(result);
      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error";
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { generateStory, loading, error, story };
}
```

---

## Response Handling

### Success Response (200 OK)

```typescript
interface StoryResponse {
  id: "550e8400-e29b-41d4-a716-446655440000",
  mode: "news",
  category: "News",
  input_language: "en",
  slide_count: 4,
  template_key: "test-news-1",
  slide_deck: {
    template_key: "test-news-1",
    language_code: "en",
    slides: [
      {
        placeholder_id: "cover",
        text: "Breaking News: Technology Breakthrough",
        image_url: null,
        highlight_tags: []
      },
      {
        placeholder_id: "slide_1",
        text: "First slide content...",
        image_url: null,
        highlight_tags: []
      }
      // ... more slides
    ]
  },
  image_assets: [
    {
      source: "ai",
      original_object_key: "media/images/uuid.png",
      resized_variants: [
        "https://cdn.suvichaar.org/media/images/uuid.png?w=720&h=1280"
      ],
      description: "AI generated image"
    }
    // ... more image assets
  ],
  voice_assets: [
    {
      provider: "azure_basic",
      voice_id: "hi-IN-AaravNeural",
      audio_url: "https://cdn.suvichaar.org/media/audio/uuid.wav",
      duration_seconds: null
    }
    // ... more voice assets (one per slide)
  ],
  canurl: "https://stories.suvichaar.org/550e8400-e29b-41d4-a716-446655440000",
  canurl1: "https://stories.suvichaar.org/550e8400-e29b-41d4-a716-446655440000?variant=alt",
  created_at: "2025-01-21T10:30:00.000000"
}
```

**Frontend Actions**:
1. Display success message
2. Show story ID
3. Provide link to view HTML file (`canurl`)
4. Show preview of slides (optional)
5. Display image/voice asset URLs (optional)

---

## Error Handling

### Error Response (400/500)

```typescript
interface ErrorResponse {
  detail: string;
  error_type?: string;  // For 500 errors
}
```

### Error Handling Example

```typescript
async function handleStoryCreation(request: StoryCreateRequest) {
  try {
    const api = new StoryAPI();
    const story = await api.createStory(request);
    
    // Success handling
    showSuccessMessage(`Story created successfully! ID: ${story.id}`);
    navigateToStory(story.id);
    
  } catch (error) {
    // Error handling
    if (error instanceof Error) {
      if (error.message.includes("400")) {
        // Validation error
        showValidationError(error.message);
      } else if (error.message.includes("500")) {
        // Server error
        showServerError("Server error occurred. Please try again later.");
        logError(error);
      } else {
        // Network or other error
        showErrorMessage(error.message);
      }
    }
  }
}
```

### Common Error Scenarios

| Status Code | Error Type | Possible Causes | Frontend Action |
|-------------|------------|-----------------|-----------------|
| 400 | Validation Error | Invalid parameters, missing required fields | Show validation errors, highlight problematic fields |
| 404 | Not Found | Story ID doesn't exist | Show "Story not found" message |
| 500 | Server Error | Internal server error, API failure | Show generic error, allow retry, log for debugging |
| Network Error | Connection Failed | Network timeout, CORS issue | Show connection error, allow retry |

---

## Complete Request Payload Examples

### Example 1: News Mode with Default Images
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/",
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

---

**Note**: News mode does **NOT** support `image_source: "ai"` or `"pexels"`. For AI or Pexels images, use **Curious mode** instead.

---

### Example 4: Curious Mode with AI Images
```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 7,
  "user_input": "How does quantum computing work? Explain the basic principles, quantum bits (qubits), superposition, and entanglement.",
  "image_source": "ai",
  "prompt_keywords": [
    "quantum",
    "computing",
    "science",
    "technology",
    "physics"
  ],
  "voice_engine": "azure_basic"
}
```

**UI State**:
- ✅ Mode: Curious selected
- ✅ Template: curious-template-1
- ✅ Slide count: 7
- ✅ Image source: AI Generated (uses alt texts from content)
- ✅ **Keywords provided** (used as fallback if alt texts unavailable)
- ✅ Content: Text question provided
- ✅ Voice: Azure Basic
- ⚠️ Category: Not shown (not used in Curious mode)

---

### Example 5: Curious Mode with Pexels
```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 7,
  "user_input": "How does photosynthesis work?",
  "image_source": "pexels",
  "prompt_keywords": [
    "plants",
    "nature",
    "biology",
    "science"
  ],
  "voice_engine": "azure_basic"
}
```

**UI State**:
- ✅ Mode: Curious selected
- ✅ Template: curious-template-1
- ✅ Slide count: 7
- ✅ Image source: Pexels
- ✅ **Keywords provided** (prompt_keywords array)
- ✅ Content: Text question provided
- ✅ Voice: Azure Basic

---

## Implementation Checklist

### ✅ Required UI Components

- [ ] Mode selector (Radio buttons or Tabs)
- [ ] Template selector (Dropdown or Cards) - filter by mode
- [ ] Slide count selector (Slider or Number input, validate based on mode)
- [ ] Image source selector (Radio buttons, conditional based on mode)
- [ ] Content input (Textarea with URL/text detection)
- [ ] Voice engine selector (Radio buttons or Dropdown)
- [ ] Category selector (Dropdown, for News mode, hide for Curious)
- [ ] Submit/Generate button
- [ ] Loading indicator
- [ ] Error message display
- [ ] Success message display

### ✅ Conditional Components

- [ ] **Image Upload Component** (Show when `image_source="custom"`)
  - File picker
  - URL input
  - S3 URI input (optional)
  - Image preview
  - Format validation (JPG, PNG, WEBP)
  - File size validation

- [ ] **Keyword Input Component** (Show when `image_source="ai"` or `"pexels"`)
  - Multi-tag input
  - Add/remove keywords
  - Keyword suggestions (optional)
  - Info message for Curious mode (alt texts are used for AI)

- [ ] **Default Image Info** (Show when `image_source=null` in News mode)
  - Info message
  - Preview of default images (optional)

### ✅ Validation Rules

- [ ] Mode is selected
- [ ] Template is selected and matches mode
- [ ] Slide count is valid for selected mode (News: 4-10, Curious: 7+)
- [ ] If `image_source="custom"`, `attachments` array has at least 1 item
- [ ] If `image_source="ai"` or `"pexels"`, `prompt_keywords` is recommended (show warning if empty)
- [ ] `user_input` or legacy fields (`text_prompt`/`urls`) are provided
- [ ] Voice engine is selected (optional, but recommended)
- [ ] Image format is valid (if custom upload)
- [ ] URL format is valid (if URL provided)

### ✅ Error Handling

- [ ] Show validation errors before submission
- [ ] Handle API errors (400, 404, 500)
- [ ] Display error messages from API response
- [ ] Show loading state during request
- [ ] Handle timeout (suggest 300 seconds)
- [ ] Handle network errors
- [ ] Retry mechanism (optional)
- [ ] Error logging for debugging

### ✅ Success Handling

- [ ] Display success message
- [ ] Show generated story ID
- [ ] Provide link to view HTML output (`canurl`)
- [ ] Show preview of generated story (optional)
- [ ] Display image/voice asset URLs (optional)
- [ ] Download HTML file option (optional)
- [ ] Share story link (optional)

### ✅ User Experience

- [ ] Progressive disclosure (show only relevant fields)
- [ ] Real-time validation (as user types/selects)
- [ ] Inline error messages
- [ ] Disable submit button until valid
- [ ] Show loading spinner during API call
- [ ] Display progress for long operations
- [ ] Clear success/error messages
- [ ] Auto-save draft (optional)
- [ ] Form reset after successful submission

---

## Best Practices

### 1. Progressive Disclosure
- Show only relevant fields based on selections
- Hide advanced options by default
- Use accordions/tabs for optional sections
- Group related fields together

### 2. Real-time Validation
- Validate as user types/selects
- Show inline error messages
- Disable submit button until valid
- Highlight problematic fields

### 3. User Feedback
- Show loading spinner during API call
- Display progress for long operations (story generation can take 30-60 seconds)
- Provide clear success/error messages
- Show estimated time remaining (optional)

### 4. Image Handling
- Validate image format before upload
- Show image preview
- Handle large file sizes (warn if > 10MB)
- Support drag-and-drop (optional)
- Show upload progress (optional)

### 5. URL Detection
- Auto-detect URLs in `user_input`
- Show detected type (URL vs Text)
- Validate URL format
- Test URL accessibility (optional)

### 6. Error Recovery
- Allow user to retry after error
- Save form state for recovery
- Show helpful error messages
- Provide support contact information

---

## Quick Reference Table

| Selection | Parameter Value | Show Fields | Hide Fields | Notes |
|-----------|----------------|-------------|-------------|-------|
| Mode: News | `mode: "news"` | Default, Custom | AI, Pexels | Slide count: 4-10 |
| Mode: Curious | `mode: "curious"` | AI, Pexels, Custom | Default option | Slide count: 7+ |
| Image: Default | `image_source: null` | Info message | Upload, Keywords | News mode only |
| Image: Custom | `image_source: "custom"` | Upload/URL input | Keywords | Requires attachments (News & Curious) |
| Image: AI | `image_source: "ai"` | Keywords input | Upload | Curious mode only (uses alt texts) |
| Image: Pexels | `image_source: "pexels"` | Keywords input | Upload | Curious mode only (requires keywords) |

---

## Support & Resources

- **API Documentation**: See `API_USAGE_GUIDE.md` for complete API reference
- **Example Files**: 
  - `example_default_images.json` - News mode with default images
  - `example_custom_image_url.json` - Custom image via URL
  - `example_custom_image_s3.json` - Custom image via S3
  - `test_curious_mode.json` - Curious mode example
- **Custom Image Guide**: See `CUSTOM_IMAGE_GUIDE.md`
- **Backend Repository**: Check GitHub for latest updates

---

## Testing Checklist

Before deploying to production, test:

- [ ] All image source options work correctly
- [ ] Mode switching updates UI correctly
- [ ] Validation errors display properly
- [ ] API errors are handled gracefully
- [ ] Loading states work correctly
- [ ] Success responses are displayed
- [ ] Story links are accessible
- [ ] Image previews work
- [ ] File uploads work
- [ ] URL detection works
- [ ] Form resets after submission
- [ ] Mobile responsiveness

---

**Last Updated**: 2025-01-21  
**API Version**: 1.0.0  
**Backend Compatibility**: FastAPI with Pydantic v2
