# Phase 1 Backend — Auth, Listing, Publishing

This Phase 1 work adds the API surface SuvichaarAdmin will consume:

- JWT auth (single admin, env-var seeded)
- Listing endpoint for the stories already produced by the pipeline
- Publish endpoint that records publish events to a new `publishes` table

The same changes ship to **both** services (News + Curious). They run as
two separate Azure App Services today, so each one keeps its own DB,
its own admin secret, and its own publish history.

---

## New environment variables

Set these per service (Azure App Service → Configuration → Application
settings, or local `.env` for dev):

| Variable | Required | Default | Notes |
|---|---|---|---|
| `ADMIN_EMAIL` | yes | — | Login email for the admin |
| `ADMIN_PASSWORD_HASH` | yes | — | bcrypt hash, generate via the script below |
| `JWT_SECRET` | yes | — | Long random string. Different per service or shared if SSO desired. |
| `JWT_ALGORITHM` | no | `HS256` | Rarely needs changing |
| `JWT_EXPIRES_MINUTES` | no | `720` (12 h) | Token lifetime |

### Generate the password hash

From the service backend root:

```bash
cd backend
pip install -r requirements.txt          # adds PyJWT + bcrypt
python scripts/hash_password.py 'my-secret-pass'
# → $2b$12$...   (paste into ADMIN_PASSWORD_HASH)
```

Run it with no argument for an interactive prompt.

---

## New endpoints (same on both services)

### `POST /auth/login`

Request:
```json
{ "email": "admin@suvichaar.org", "password": "my-secret-pass" }
```
Response (`200`):
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 43200,
  "user": { "email": "admin@suvichaar.org", "role": "admin" }
}
```
Errors: `401` invalid credentials, `503` auth not configured.

### `GET /auth/me`

Header: `Authorization: Bearer <token>`
Response (`200`):
```json
{ "email": "admin@suvichaar.org", "role": "admin" }
```

### `GET /stories`

Header: `Authorization: Bearer <token>`

Query params (all optional):
- `mode` — `news` | `curious`
- `category` — exact match
- `q` — search across `category`, `template_key`, and any JSON field of `doc_insights` (title, summary, …)
- `date_from`, `date_to` — ISO‑8601 timestamps
- `limit` — default `50`, max `200`
- `offset` — default `0`

Response (`200`):
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "ट्रम्प बोले: ईरान से तेल लेना पसंद…",
      "mode": "news",
      "category": "News",
      "input_language": "hi",
      "slide_count": 4,
      "template_key": "test-news-3",
      "canurl": "https://suvichaar.org/stories/...",
      "created_at": "2026-06-15T06:30:00Z"
    }
  ],
  "total": 128,
  "limit": 50,
  "offset": 0
}
```

### `POST /stories/{story_id}/publish`

Header: `Authorization: Bearer <token>`

Request body:
```json
{ "target": "suvichaar_live" }
```
or
```json
{ "target": "webhook", "webhook_url": "https://example.com/incoming" }
```

Response (`200`):
```json
{
  "id": "e3c7…",
  "story_id": "550e8400-…",
  "target": "suvichaar_live",
  "status": "success",
  "webhook_url": null,
  "error": null,
  "published_by": "admin@suvichaar.org",
  "published_at": "2026-06-15T11:22:00Z"
}
```
Errors: `400` missing `webhook_url`, `404` story not found, `503` DB not configured.

> **Note:** Phase 1 records the event only; it does **not** call any
> external API yet. Phase 2 wires actual webhook POSTs and a Suvichaar
> Live HTTP call.

### `GET /stories/{story_id}/publishes`

Header: `Authorization: Bearer <token>`

Response:
```json
{ "items": [ /* PublishHistoryItem[] */ ] }
```

---

## Database

A new `publishes` table is created at startup via SQLAlchemy
`Base.metadata.create_all`. Schema:

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36)` | UUID, PK |
| `story_id` | `VARCHAR(36)` | indexed |
| `target` | `VARCHAR(32)` | `suvichaar_live` \| `webhook` |
| `status` | `VARCHAR(16)` | `success` \| `failed` \| `pending` |
| `webhook_url` | `TEXT` | nullable |
| `error` | `TEXT` | nullable |
| `published_by` | `VARCHAR(255)` | admin email |
| `published_at` | `DateTime(tz)` | UTC |

No migration is required for fresh DBs. Existing DBs will get the table
created automatically on next startup.

---

## Local smoke test

```bash
cd backend
pip install -r requirements.txt

export ADMIN_EMAIL="admin@suvichaar.org"
export ADMIN_PASSWORD_HASH="$(python scripts/hash_password.py 'admin123')"
export JWT_SECRET="dev-only-not-for-prod"

uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@suvichaar.org","password":"admin123"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. Me
curl -s http://localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"

# 3. List
curl -s "http://localhost:8000/stories?limit=10" -H "Authorization: Bearer $TOKEN"

# 4. Publish (replace STORY_ID with a real id from step 3)
curl -s -X POST http://localhost:8000/stories/STORY_ID/publish \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"target":"suvichaar_live"}'
```

---

## What's intentionally not done in Phase 1

- Existing endpoints (`POST /stories`, template/prompt management, etc.)
  remain open so the existing Storygenerator frontend keeps working
  unchanged. Phase 2 will gate them behind `get_current_user`.
- Publish targets are recorded but not actually called externally.
- Refresh tokens — single short‑lived bearer is sufficient for an
  internal admin tool.
