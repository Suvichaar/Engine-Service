# API Usage Guide - News Mode

Complete guide for developers on how to use the Story Generation API with different image sources.

## Base URL
```
http://localhost:8000/stories
```

## Endpoint
```
POST /stories
```

---

## Scenario 1: Default Images (image_source = null)

**When to use**: When you want to use default background images for all slides.

**What happens**:
- Cover slide uses: `https://media.suvichaar.org/upload/polaris/polariscover.png`
- Middle slides use: `https://media.suvichaar.org/upload/polaris/polarisslide.png`
- No custom images are uploaded

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

## Scenario 2: Custom Image via URL (image_source = "custom")

**When to use**: When you have an image URL (HTTP/HTTPS) that you want to use for all slides.

**What happens**:
1. System downloads image from the provided URL
2. Image is uploaded to S3 with a unique key
3. Image is resized to portrait resolution (720x1280)
4. Same image is used across all slides (cover + middle slides)

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

## Scenario 3: Custom Image via S3 URI (image_source = "custom")

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

## Scenario 4: AI Generated Images (image_source = "ai")

**When to use**: When you want AI to generate images based on keywords.

**What happens**:
- AI generates unique images for each slide based on `prompt_keywords`
- Images are generated per slide (cover + middle slides)

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

---

## Scenario 5: Pexels Images (image_source = "pexels")

**When to use**: When you want royalty-free stock images from Pexels.

**What happens**:
- Fetches images from Pexels API based on `prompt_keywords`
- Different images for each slide

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

---

## Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | string | Yes | Story mode: `"news"` or `"curious"` |
| `template_key` | string | Yes | Template identifier: `"test-news-1"`, `"test-news-2"`, etc. |
| `slide_count` | integer | Yes | Total slides (4-10): 4 = cover + 2 middle + CTA |
| `category` | string | Optional | Story category (e.g., "News", "Technology") |
| `user_input` | string | Optional | Unified input: URL, text, or file reference (auto-detected) |
| `image_source` | string | Optional | Image source: `null`, `"custom"`, `"ai"`, `"pexels"` |
| `attachments` | array | Optional | Image URLs/URIs (required if `image_source="custom"`) |
| `prompt_keywords` | array | Optional | Keywords for AI/Pexels image generation |
| `voice_engine` | string | Optional | Voice provider: `"azure_basic"` or `"elevenlabs_pro"` |

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
    "slides": [
      {
        "placeholder_id": "section_1",
        "text": "Story title here...",
        "image_url": null
      },
      ...
    ]
  },
  "image_assets": [...],
  "voice_assets": [...],
  "created_at": "2025-01-XX...",
  ...
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

| image_source | attachments | Result |
|--------------|-------------|--------|
| `null` | Not needed | Default images (polariscover.png, polarisslide.png) |
| `"custom"` | HTTP/HTTPS URL | Downloads image, uploads to S3, resizes to 720x1280 |
| `"custom"` | S3 URI (`s3://...`) | Loads from S3, uploads with new key, resizes to 720x1280 |
| `"ai"` | Not needed | AI generates images based on `prompt_keywords` |
| `"pexels"` | Not needed | Fetches stock images from Pexels based on `prompt_keywords` |

---

## Notes

1. **Custom Images**: Only `attachments[0]` is used for all slides in News mode
2. **Resolution**: Custom images in News mode are automatically resized to 720x1280 (portrait)
3. **Image Formats**: Supports JPG, JPEG, PNG, WEBP
4. **Timeout**: Image downloads have a 30-second timeout
5. **S3 Credentials**: For S3 URIs, ensure AWS credentials are configured (IAM role, env vars, or explicit keys)

---

## Testing Examples

### Test with Default Images
```bash
# Use example_default_images.json
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d @example_default_images.json
```

### Test with Custom URL
```bash
# Use example_custom_image.json
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d @example_custom_image.json
```

### Test with Custom S3
```bash
# Use example_custom_image_s3.json
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d @example_custom_image_s3.json
```

