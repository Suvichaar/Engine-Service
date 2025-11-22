# API Usage Guide - News & Curious Modes

Complete guide for developers on how to use the Story Generation API with different modes and image sources.

## Base URL
```
http://localhost:8000/stories
```

## Endpoint
```
POST /stories
```

---

## Table of Contents

### News Mode
1. [Default Images (image_source = null)](#news-scenario-1-default-images)
2. [Custom Image via URL](#news-scenario-2-custom-image-via-url)
3. [Custom Image via S3 URI](#news-scenario-3-custom-image-via-s3-uri)
4. [AI Generated Images](#news-scenario-4-ai-generated-images)
5. [Pexels Images](#news-scenario-5-pexels-images)

### Curious Mode
6. [AI Generated Images](#curious-scenario-1-ai-generated-images)
7. [Pexels Images](#curious-scenario-2-pexels-images)
8. [Custom Images](#curious-scenario-3-custom-images)

### Reference
9. [Field Descriptions](#field-descriptions)
10. [Response Format](#response-format)
11. [Quick Reference Table](#quick-reference-table)

---

# News Mode Scenarios

## News Scenario 1: Default Images (image_source = null)

**When to use**: When you want to use default background images for all slides.

**What happens**:
- Cover slide uses: `https://media.suvichaar.org/upload/polaris/polariscover.png`
- Middle slides use: `https://media.suvichaar.org/upload/polaris/polarisslide.png`
- No custom images are uploaded
- **Note**: This is the default behavior when `image_source` is not provided or is `null`

### JSON Payload

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

### cURL Command

```bash
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "news",
    "template_key": "test-news-1",
    "slide_count": 4,
    "category": "News",
    "user_input": "https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/",
    "image_source": null,
    "voice_engine": "azure_basic"
  }'
```

### PowerShell Command

```powershell
$body = @{
    mode = "news"
    template_key = "test-news-1"
    slide_count = 4
    category = "News"
    user_input = "https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/"
    image_source = $null
    voice_engine = "azure_basic"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/stories" -Method Post -Body $body -ContentType "application/json"
```

---

## News Scenario 2: Custom Image via URL (image_source = "custom")

**When to use**: When you have an image URL (HTTP/HTTPS) that you want to use for all slides.

**What happens**:
1. System downloads image from the provided URL
2. Image is uploaded to S3 with a unique key
3. Image is resized to portrait resolution (720x1280)
4. Same image is used across all slides (cover + middle slides + CTA)

### JSON Payload

```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/",
  "image_source": "custom",
  "attachments": [
    "https://example.com/path/to/your-image.jpg"
  ],
  "voice_engine": "azure_basic"
}
```

### cURL Command

```bash
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "news",
    "template_key": "test-news-1",
    "slide_count": 4,
    "category": "News",
    "user_input": "https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/",
    "image_source": "custom",
    "attachments": [
      "https://example.com/path/to/your-image.jpg"
    ],
    "voice_engine": "azure_basic"
  }'
```

### PowerShell Command

```powershell
$body = @{
    mode = "news"
    template_key = "test-news-1"
    slide_count = 4
    category = "News"
    user_input = "https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/"
    image_source = "custom"
    attachments = @("https://example.com/path/to/your-image.jpg")
    voice_engine = "azure_basic"
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri "http://localhost:8000/stories" -Method Post -Body $body -ContentType "application/json"
```

---

## News Scenario 3: Custom Image via S3 URI (image_source = "custom")

**When to use**: When you have an image already stored in S3 that you want to use.

**What happens**:
1. System loads image from S3 using the provided URI
2. Image is uploaded to S3 with a new unique key
3. Image is resized to portrait resolution (720x1280)
4. Same image is used across all slides

### JSON Payload

```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "Breaking news: Technology breakthrough",
  "image_source": "custom",
  "attachments": [
    "s3://suvichaarapp/uploads/my-custom-image.jpg"
  ],
  "voice_engine": "azure_basic"
}
```

### cURL Command

```bash
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "news",
    "template_key": "test-news-1",
    "slide_count": 4,
    "category": "News",
    "user_input": "Breaking news: Technology breakthrough",
    "image_source": "custom",
    "attachments": [
      "s3://suvichaarapp/uploads/my-custom-image.jpg"
    ],
    "voice_engine": "azure_basic"
  }'
```

---

## News Scenario 4: AI Generated Images (image_source = "ai")

**When to use**: When you want AI to generate images based on keywords and article content.

**What happens**:
- AI generates unique images for each slide based on `prompt_keywords` and slide content
- Images are generated per slide (cover + middle slides)
- Uses DALL-E 3 API

### JSON Payload

```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "https://indianexpress.com/article/...",
  "image_source": "ai",
  "prompt_keywords": [
    "technology",
    "AI",
    "innovation"
  ],
  "voice_engine": "azure_basic"
}
```

### cURL Command

```bash
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "news",
    "template_key": "test-news-1",
    "slide_count": 4,
    "category": "News",
    "user_input": "https://indianexpress.com/article/...",
    "image_source": "ai",
    "prompt_keywords": ["technology", "AI", "innovation"],
    "voice_engine": "azure_basic"
  }'
```

---

## News Scenario 5: Pexels Images (image_source = "pexels")

**When to use**: When you want royalty-free stock images from Pexels.

**What happens**:
- Fetches images from Pexels API based on `prompt_keywords`
- Different images for each slide
- Portrait orientation, medium size

### JSON Payload

```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "https://indianexpress.com/article/...",
  "image_source": "pexels",
  "prompt_keywords": [
    "technology",
    "AI",
    "innovation"
  ],
  "voice_engine": "azure_basic"
}
```

### cURL Command

```bash
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "news",
    "template_key": "test-news-1",
    "slide_count": 4,
    "category": "News",
    "user_input": "https://indianexpress.com/article/...",
    "image_source": "pexels",
    "prompt_keywords": ["technology", "AI", "innovation"],
    "voice_engine": "azure_basic"
  }'
```

---

# Curious Mode Scenarios

## Curious Scenario 1: AI Generated Images (image_source = "ai")

**When to use**: When you want AI to generate educational images based on content.

**What happens**:
- AI generates images using **alt texts** extracted from the generated content
- Each slide gets a unique image based on its content
- Images are generated using DALL-E 3 with educational prompts
- Alt texts are automatically generated by the LLM for each slide

**Key Difference from News Mode**: 
- Curious mode uses **content-based alt texts** (s0alt1, s1alt1, etc.) instead of keywords
- Images are more contextually relevant to the slide content

### JSON Payload

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

### cURL Command

```bash
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "curious",
    "template_key": "curious-template-1",
    "slide_count": 7,
    "user_input": "How does quantum computing work?",
    "image_source": "ai",
    "prompt_keywords": ["quantum", "computing", "science"],
    "voice_engine": "azure_basic"
  }'
```

### PowerShell Command

```powershell
$body = @{
    mode = "curious"
    template_key = "curious-template-1"
    slide_count = 7
    user_input = "How does quantum computing work? Explain the basic principles, quantum bits (qubits), superposition, and entanglement."
    image_source = "ai"
    prompt_keywords = @("quantum", "computing", "science", "technology", "physics")
    voice_engine = "azure_basic"
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri "http://localhost:8000/stories" -Method Post -Body $body -ContentType "application/json"
```

---

## Curious Scenario 2: Pexels Images (image_source = "pexels")

**When to use**: When you want royalty-free stock images for educational content.

**What happens**:
- Fetches images from Pexels API based on `prompt_keywords`
- Different images for each slide
- Portrait orientation

### JSON Payload

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

### cURL Command

```bash
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "curious",
    "template_key": "curious-template-1",
    "slide_count": 7,
    "user_input": "How does photosynthesis work?",
    "image_source": "pexels",
    "prompt_keywords": ["plants", "nature", "biology", "science"],
    "voice_engine": "azure_basic"
  }'
```

---

## Curious Scenario 3: Custom Images (image_source = "custom")

**When to use**: When you have custom images you want to use for educational content.

**What happens**:
1. System loads images from provided URLs/URIs
2. Images are uploaded to S3 with unique keys
3. Images are resized to portrait resolution (720x1280)
4. Each slide can use a different image (if multiple attachments provided)

### JSON Payload

```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 7,
  "user_input": "Explain the water cycle",
  "image_source": "custom",
  "attachments": [
    "https://example.com/water-cycle-image.jpg"
  ],
  "voice_engine": "azure_basic"
}
```

### cURL Command

```bash
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "curious",
    "template_key": "curious-template-1",
    "slide_count": 7,
    "user_input": "Explain the water cycle",
    "image_source": "custom",
    "attachments": ["https://example.com/water-cycle-image.jpg"],
    "voice_engine": "azure_basic"
  }'
```

---

## Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | string | Yes | Story mode: `"news"` or `"curious"` |
| `template_key` | string | Yes | Template identifier: `"test-news-1"`, `"test-news-2"`, `"curious-template-1"`, etc. |
| `slide_count` | integer | Yes | Total slides: **News** (4-10), **Curious** (7+) |
| `category` | string | Optional | Story category (e.g., "News", "Technology") - Recommended for News mode |
| `user_input` | string | Optional | Unified input: URL, text, or file reference (auto-detected). **Takes precedence** over separate fields |
| `image_source` | string \| null | Optional | Image source: `null` (News only), `"custom"`, `"ai"`, `"pexels"` |
| `attachments` | array | Optional | Image URLs/URIs (required if `image_source="custom"`) |
| `prompt_keywords` | array | Optional | Keywords for AI/Pexels image generation |
| `voice_engine` | string | Optional | Voice provider: `"azure_basic"` or `"elevenlabs_pro"` |

### Mode-Specific Notes

#### News Mode
- `image_source: null` → Uses default images (polariscover.png, polarisslide.png)
- `slide_count: 4` = 1 cover + 2 middle + 1 CTA
- `category` is recommended for better content generation

#### Curious Mode
- `image_source: null` is **NOT supported** (must provide "ai", "pexels", or "custom")
- `slide_count: 7` = 1 cover + 5 middle + 1 CTA (for curious-template-1)
- AI images use **alt texts** extracted from generated content (more contextual)

---

## Response Format

### Success Response (200 OK)

```json
{
  "id": "uuid-here",
  "mode": "news",
  "category": "News",
  "slide_count": 4,
  "template_key": "test-news-1",
  "slide_deck": {
    "template_key": "test-news-1",
    "language_code": "en",
    "slides": [
      {
        "placeholder_id": "cover",
        "text": "Story title here...",
        "image_url": null
      },
      {
        "placeholder_id": "slide_1",
        "text": "First slide content...",
        "image_url": null
      }
    ]
  },
  "image_assets": [
    {
      "placeholder_id": "cover",
      "original_object_key": "media/images/uuid.png",
      "cdn_url": "https://cdn.suvichaar.org/media/images/uuid.png",
      "resized_variants": {
        "portrait": "https://cdn.suvichaar.org/..."
      }
    }
  ],
  "voice_assets": [
    {
      "provider": "azure_basic",
      "voice_id": "hi-IN-AaravNeural",
      "audio_url": "https://cdn.suvichaar.org/media/audio/uuid.wav",
      "duration_seconds": null
    }
  ],
  "canurl": "https://stories.suvichaar.org/{id}",
  "canurl1": "https://stories.suvichaar.org/{id}?variant=alt",
  "created_at": "2025-01-21T..."
}
```

### Error Response (400/500)

```json
{
  "detail": "Error message here"
}
```

---

## Quick Reference Table

### News Mode Image Sources

| image_source | attachments | prompt_keywords | Result |
|--------------|-------------|-----------------|--------|
| `null` | Not needed | Not needed | Default images (polariscover.png, polarisslide.png) |
| `"custom"` | HTTP/HTTPS URL | Not needed | Downloads image, uploads to S3, resizes to 720x1280 |
| `"custom"` | S3 URI (`s3://...`) | Not needed | Loads from S3, uploads with new key, resizes to 720x1280 |
| `"ai"` | Not needed | Required | AI generates images based on keywords + slide content |
| `"pexels"` | Not needed | Required | Fetches stock images from Pexels based on keywords |

### Curious Mode Image Sources

| image_source | attachments | prompt_keywords | Result |
|--------------|-------------|-----------------|--------|
| `"ai"` | Not needed | Optional | AI generates images using **alt texts** from content (more contextual) |
| `"pexels"` | Not needed | Required | Fetches stock images from Pexels based on keywords |
| `"custom"` | HTTP/HTTPS URL or S3 URI | Not needed | Downloads/loads image, uploads to S3, resizes to 720x1280 |

**Note**: Curious mode does NOT support `image_source: null` (default images).

---

## Key Differences: News vs Curious Mode

| Feature | News Mode | Curious Mode |
|---------|-----------|--------------|
| **Default Images** | ✅ Supported (`image_source: null`) | ❌ Not supported |
| **AI Image Generation** | Uses `prompt_keywords` + slide text | Uses **alt texts** from content (more contextual) |
| **Slide Count** | 4-10 slides | 7+ slides (typically 7 for curious-template-1) |
| **Content Style** | Factual, news-oriented | Educational, explainable |
| **Category Field** | Recommended | Optional |
| **Templates** | `test-news-1`, `test-news-2`, etc. | `curious-template-1`, etc. |

---

## Notes

1. **Custom Images**: 
   - News mode: Only `attachments[0]` is used for all slides
   - Curious mode: Can use multiple attachments (one per slide)

2. **Resolution**: Custom images are automatically resized to 720x1280 (portrait)

3. **Image Formats**: Supports JPG, JPEG, PNG, WEBP

4. **Timeout**: Image downloads have a 30-second timeout

5. **S3 Credentials**: For S3 URIs, ensure AWS credentials are configured

6. **AI Image Generation**:
   - News mode: Uses keywords + slide content
   - Curious mode: Uses alt texts (s0alt1, s1alt1, etc.) extracted from generated content

7. **Voice Synthesis**: Individual audio file per slide (not combined)

---

## Testing Examples

### Test News Mode - Default Images
```bash
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d @example_default_images.json
```

### Test News Mode - Custom URL
```bash
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d @example_custom_image_url.json
```

### Test Curious Mode - AI Images
```bash
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d @test_curious_mode.json
```

---

## Additional Resources

- [Frontend Integration Guide](FRONTEND_INTEGRATION_GUIDE.md) - Complete UI/UX flow guide
- [README.md](README.md) - Project overview and setup instructions
