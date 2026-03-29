# Engine Service Backend

This repository is now organized as a backend-first service. The old Streamlit frontend has been removed. The immediate focus is preparing the news backend cleanly so curious can be split by the other team without sharing a mixed service surface.

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

## Notes

- Root-level ad hoc tests, debug payloads, and stray local validation scripts were removed.
- JSON scenario payloads were preserved under `tests/fixtures/`.
- Legacy ecommerce artifacts were moved to `_archive/`.
- The current backend still contains both news and curious code paths internally, but the filesystem layout is now clean enough to continue the service split safely.
