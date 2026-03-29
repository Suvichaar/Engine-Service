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

## Notes

- Root-level ad hoc tests, debug payloads, and stray local validation scripts were removed.
- JSON scenario payloads were preserved under `tests/fixtures/`.
- Legacy ecommerce artifacts were moved to `_archive/`.
- The backend contract is being tightened around news-only behavior.
- Template metadata is centrally managed in `backend/app/templates/templates.yml` so future template add-ons stay configuration-driven.
