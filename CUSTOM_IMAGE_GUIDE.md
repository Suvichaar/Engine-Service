# Custom Image Upload Guide

## Overview
When using `image_source: "custom"` in News mode, you can provide your own images that will be:
1. Downloaded/fetched from the provided source
2. Saved to S3
3. Resized to portrait resolution (720x1280)
4. Used across all slides

## Input JSON Format

### Option 1: Image URL (HTTP/HTTPS)
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "Your article URL or text",
  "image_source": "custom",
  "attachments": [
    "https://example.com/path/to/image.jpg"
  ],
  "voice_engine": "azure_basic"
}
```

### Option 2: S3 URI
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "Your article URL or text",
  "image_source": "custom",
  "attachments": [
    "s3://bucket-name/path/to/image.jpg"
  ],
  "voice_engine": "azure_basic"
}
```

### Option 3: Local File Path (for testing)
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "Your article URL or text",
  "image_source": "custom",
  "attachments": [
    "D:/path/to/local/image.jpg"
  ],
  "voice_engine": "azure_basic"
}
```

## How It Works

1. **Image Download/Fetch**:
   - If `attachments[0]` is an HTTP/HTTPS URL → Downloads the image
   - If `attachments[0]` is an S3 URI (`s3://bucket/key`) → Loads from S3
   - If `attachments[0]` is a local file path → Reads from filesystem

2. **S3 Upload**:
   - Image is uploaded to S3 with a unique key
   - Original image is preserved

3. **Resize**:
   - For News mode with custom images, portrait resolution (720x1280) URLs are generated
   - Uses CloudFront resize functionality (base64-encoded template)

4. **Usage**:
   - Same image is used for all slides (cover + middle slides)
   - Image URLs are mapped to placeholders: `s1image1`, `s2image1`, `s3image1`, etc.

## Notes

- **First attachment is used**: Only `attachments[0]` is used for all slides
- **Multiple images**: If you provide multiple attachments, they will be cycled through (but typically you want the same image for all slides)
- **Image formats**: Supports JPG, JPEG, PNG, WEBP
- **Resolution**: Custom images in News mode are automatically resized to 720x1280 (portrait)

## Example Workflow

1. User uploads image to your frontend
2. Frontend saves image to S3 or provides a public URL
3. Frontend sends request with `image_source: "custom"` and `attachments: ["s3://bucket/image.jpg"]`
4. Backend:
   - Downloads/loads image from S3
   - Uploads to S3 with new unique key
   - Generates portrait resolution URLs (720x1280)
   - Uses across all slides

