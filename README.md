# Engine Service Backend

This repository is organized as a backend-first news service. The old Streamlit frontend has been removed, and this backend now targets the news workflow only.

## Structure

```text
backend/
  app/
    api/
    core/
    domain/
    persistence/
    prompts/
    services/
    templates/
      templates.yml
      news/
    utils/
    main.py
  data/
  scripts/
  requirements.txt
tests/
  backend/
  fixtures/
docs/
_archive/
docker-compose.yml
```

## Run Locally

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Or with Docker:

```bash
docker compose up --build
```

## Config

Configuration lives in:

- `backend/app/core/settings.example.toml`
- `backend/app/core/settings.toml`

Use the example file as the source of truth for non-secret structure. Replace local placeholder values before running integrations.

## API

Swagger UI is available at `http://localhost:8000/docs`. The `POST /stories` schema now includes ready-to-use example payloads directly inside the docs.

### `POST /stories`

Creates a news story from URL, free text, notes, or attachments.

#### Required Fields

- `mode`: must be `"news"`
- `template_key`: one of:
  - `test-news-1`
  - `test-news-2`
  - `test-news-3`
  - `test-news-3v1`
  - `test-news-org`
  - `template-v19`
- `slide_count`: integer from `4` to `10`

#### Optional Fields

- `category`: usually `"News"`
- `user_input`: unified input field. Can contain article text, one or more URLs, or a file reference. If provided, it takes precedence over the older split fields.
- `text_prompt`: extra instruction or direct text content
- `notes`: style or language guidance such as `"Make it in Hindi"`
- `urls`: explicit list of source article URLs
- `attachments`: uploaded file references
- `prompt_keywords`: extra focus keywords
- `image_source`: one of:
  - `null`
  - `"ai"`
  - `"pexels"`
  - `"custom"`
- `voice_engine`: one of:
  - `"elevenlabs_pro"`
  - `"azure_basic"`

#### Field Notes

- Prefer `user_input` for most clients. It is the primary modern input path.
- Use `urls` when you want to pass source URLs explicitly as a list.
- `image_source: null` means the backend can fall back to default news-image behavior.
- `voice_engine` is optional. If omitted, the backend uses its configured default provider.
- JSON `null` must be written as `null`, not `NULL`.

#### Minimal Payload

```json
{
  "mode": "news",
  "template_key": "test-news-3",
  "slide_count": 4,
  "user_input": "https://indianexpress.com/article/world/donald-trump-iran-oil-kharg-island-seizure-10608749/?ref=breaking_hp",
  "category": "News"
}
```

#### AI Image Example

```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "https://suvichaar.org/stories/trump-said-prefer-taking-oil-from-iran-possibility-of-seizing-kharg-island_300326094600956",
  "notes": "make it in english",
  "category": "News",
  "prompt_keywords": [
    "I want a good images"
  ],
  "image_source": "ai",
  "voice_engine": "elevenlabs_pro"
}
```

#### Pexels Image Example

```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "https://indianexpress.com/article/sports/cricket/ipl-cameron-green-bowling-cricket-australia-ajinkya-rahane-kkr-10608515/?ref=rhs_mar_30_latest_news_world",
  "notes": "I want it in english",
  "category": "News",
  "prompt_keywords": [
    "news",
    "breaking"
  ],
  "image_source": "pexels",
  "voice_engine": "elevenlabs_pro"
}
```

#### Custom Image Example

Use this when background images have already been uploaded to S3 and should be used directly by the story pipeline.

```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "https://indianexpress.com/article/sports/cricket/ipl-cameron-green-bowling-cricket-australia-ajinkya-rahane-kkr-10608515/?ref=rhs_mar_30_latest_news_world",
  "notes": "I want it english",
  "category": "News",
  "image_source": "custom",
  "voice_engine": "elevenlabs_pro",
  "attachments": [
    "s3://suvichaarapp/media/images/backgrounds/20260330/51d7eccb-2ce3-4de5-90af-ea7caba6f31f.JPG",
    "s3://suvichaarapp/media/images/backgrounds/20260330/aca7c320-4a47-43c2-bb20-cecbc556e4bd.png",
    "s3://suvichaarapp/media/images/backgrounds/20260330/dcc7adbd-1377-4776-85b4-18cfad7243ed.png"
  ]
}
```

#### Text-Only Example

```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "India's digital payments adoption continues to grow rapidly, with UPI transactions reaching new highs across urban and rural markets.",
  "notes": "Keep it factual and concise",
  "prompt_keywords": [
    "UPI",
    "digital payments",
    "India"
  ],
  "image_source": "ai",
  "voice_engine": "azure_basic"
}
```

#### Example Curl

```bash
curl -X POST \
  "http://localhost:8000/stories" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "news",
    "template_key": "test-news-1",
    "slide_count": 4,
    "user_input": "https://suvichaar.org/stories/trump-said-prefer-taking-oil-from-iran-possibility-of-seizing-kharg-island_300326094600956",
    "notes": "make it in english",
    "category": "News",
    "prompt_keywords": ["I want a good images"],
    "image_source": "ai",
    "voice_engine": "elevenlabs_pro"
  }'
```

#### Example Success Response

Response shape is large because it includes generated slides, insights, image assets, and voice assets. A shortened example:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "mode": "news",
  "category": "News",
  "input_language": "hi",
  "slide_count": 4,
  "template_key": "test-news-3",
  "slide_deck": {
    "template_key": "news_default",
    "language_code": "hi",
    "slides": [
      {
        "placeholder_id": "section_1",
        "text": "ट्रंप ने ईरान के तेल निर्यात पर कड़ा रुख दिखाया"
      },
      {
        "placeholder_id": "section_2",
        "text": "रिपोर्ट के अनुसार..."
      }
    ]
  },
  "image_assets": [
    {
      "source": "ai",
      "original_object_key": "media/images/example.png",
      "resized_variants": [
        "https://media.example.org/encoded-image"
      ]
    }
  ],
  "voice_assets": [
    {
      "provider": "elevenlabs_pro",
      "voice_id": "voice-id",
      "audio_url": "https://cdn.example.org/media/audio/example.mp3"
    }
  ],
  "prompt_version": "v1",
  "prompt_file": "news.v1.prompt",
  "canurl": "https://suvichaar.org/stories/example_300326101530123",
  "canurl1": "https://suvichaar.org/stories/example_300326101530123.html",
  "created_at": "2026-03-30T10:15:30.123456"
}
```

#### Common Error Responses

`422 Unprocessable Entity`

Usually means the JSON body itself is invalid or a field type is wrong.

Example:

```json
{
  "detail": [
    {
      "type": "json_invalid",
      "loc": ["body", 16],
      "msg": "JSON decode error",
      "ctx": {
        "error": "Expecting ',' delimiter"
      }
    }
  ]
}
```

Common causes:

- missing commas in JSON
- `NULL` instead of `null`
- `slide_count` outside `4..10`
- unsupported `template_key`

`400 Bad Request`

Usually means the request was valid JSON, but story creation failed due to business rules or external processing.

Examples:

```json
{
  "detail": "Unsupported template_key 'foo'. Allowed values: test-news-1, test-news-2, test-news-3, test-news-3v1, test-news-org, template-v19"
}
```

```json
{
  "detail": "Serper API key not provided. Set SERPER_API_KEY environment variable or pass api_key parameter to URLContentExtractor."
}
```

```json
{
  "detail": "Document processing failed: ..."
}
```

`404 Not Found`

Returned when fetching a story that does not exist.

```json
{
  "detail": "Story not found"
}
```

`500 Internal Server Error`

Returned for unexpected runtime failures.

```json
{
  "detail": "RuntimeError: ...",
  "error_type": "RuntimeError"
}
```

#### Other Useful Endpoints

- `GET /health`
- `GET /templates`
- `GET /stories/{story_id}`
- `GET /stories/{story_id}/html`
- `GET /stories/{story_id}/test`

### `GET /templates`

Returns the list of supported template keys.

Example response:

```json
[
  "template-v19",
  "test-news-1",
  "test-news-2",
  "test-news-3",
  "test-news-3v1",
  "test-news-org"
]
```

### `GET /stories/{story_id}`

Returns the full stored story record by UUID or slug.

### `GET /stories/{story_id}/html`

Returns rendered HTML for the generated story.

Example response:

```json
{
  "html": "<!doctype html>...",
  "story_id": "550e8400-e29b-41d4-a716-446655440000",
  "template_key": "test-news-3"
}
```

### `GET /health`

Simple health endpoint.

Example response:

```json
{
  "status": "ok"
}
```

## Notes

- Root-level ad hoc tests, debug payloads, and stray local validation scripts were removed.
- JSON scenario payloads were preserved under `tests/fixtures/`.
- Legacy ecommerce artifacts were moved to `_archive/`.
- The backend contract is being tightened around news-only behavior.
- Template metadata is centrally managed in `backend/app/templates/templates.yml` so future template add-ons stay configuration-driven.
