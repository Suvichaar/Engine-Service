# Curious Service Backend

This repository is the backend-first service for curious stories. The old Streamlit frontend has been removed, and this service is intended to be deployable independently in the same way as the news backend.

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
      curious/
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

Swagger UI is available at `http://localhost:8000/docs`.

### `POST /stories`

Creates a curious story from a prompt, URL, notes, or attachments.

Example payload:

```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 4,
  "category": "History",
  "user_input": "Explain the history of the Pyramids of Giza.",
  "prompt_keywords": ["pyramids", "egypt"],
  "image_source": "ai",
  "voice_engine": "elevenlabs_pro"
}
```

## Notes

- Root-level ad hoc tests, debug payloads, and stray local validation scripts were removed.
- JSON scenario payloads were preserved under `tests/fixtures/`.
- Legacy ecommerce artifacts were moved to `_archive/`.
- This service now has its own local config placeholders, configurable CORS support, and Azure App Service deployment scripts.
