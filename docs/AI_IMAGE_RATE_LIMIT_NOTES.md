# AI image generation — rate-limit behaviour & deferred fix

## Where this matters

`backend/app/services/image_pipeline.py` → class `AIImageProvider`.

The provider currently runs two image requests in parallel
(`_max_concurrent_requests = 2`) with a one-second cooldown between
request kickoffs (`_min_cooldown_seconds = 1.0`). Each individual
request is dispatched by `_generate_image`, which has its own retry
loop covering 429 (rate limited), 400 (content policy violation / bad
prompt), and other transient errors.

## Observed behaviour against FLUX-2-pro

The current Azure FLUX-2-pro endpoint
(`/providers/blackforestlabs/v1/flux-2-pro`) tolerates roughly one
sustained request per second; brief bursts above that produce 429s.

Most 8-slide jobs run cleanly under concurrency=2 + 1.0s cooldown.
However when one slide gets a 400 because of content moderation
("violence detection" or similar), `_generate_image` immediately retries
that slide with a simpler prompt — up to three times. Each retry is an
extra FLUX call that piles onto the budget already being consumed by
the other concurrent worker. The result is a short burst that can push
the *next* slot's first request into a 429, which then exponentially
backs off (10s → 20s → 30s) and slows the job down.

End-to-end the story still ships:
- the outer `generate()` falls back to a `deepcopy` of the most recent
  successful image (with the failed slot's `placeholder_id`), so every
  slide ends up with an image,
- the response is normal,
- the rendered AMP story page goes live (confirmed with
  `https://suvichaar.org/stories/youngest-and-fastest-vaibhav-sooryavanshi-shatters-ipl-records-again_200526172824562`).

The cosmetic downside is that a small number of slides in a job that
hits moderation will share a visual rather than each having a unique
generated image.

## Deferred fix (A + B)

When we are ready to revisit, two small changes eliminate the spiral:

**A. Stop retrying inside `_generate_image` on 400 responses.**
Replace the `elif e.response.status_code == 400 ...` branch with an
immediate `raise`. The outer `generate()` loop already falls back to
the nearest neighbour, so we lose nothing functionally; we just stop
making *additional* FLUX requests for prompts the moderator has
already rejected. Each slot becomes guaranteed to issue at most one
upstream request (plus 429 backoffs).

**B. Raise `_min_cooldown_seconds` from `1.0` to `2.0`.**
Half the sustained kickoff rate. With concurrency=2, the steady-state
becomes one request per second across both workers — comfortably below
the observed FLUX budget. Same change applies to the `__init__`
default `cooldown_seconds=1.0`.

Both changes ship together; tests were green when prototyped. Expected
result for a worst-case 8-slide + AI image news job:

- zero 429s,
- every slide gets a unique generated image (no deepcopy fallback),
- total time stays in the same band as today (~100–120s), because the
  removed retries were costing more time than the extra 1s of spacing
  adds.

## How to apply when the time comes

1. In `backend/app/services/image_pipeline.py` (both this repo and
   `Curious-service/`):
   - flip the class default and constructor default:
     `_min_cooldown_seconds = 2.0`, `cooldown_seconds: float = 2.0`,
   - in `_generate_image`, collapse the `elif e.response.status_code == 400 ...`
     branch into a single `else: ... raise` that bubbles non-429 status
     codes up to the caller.
2. Run `pytest tests/backend` in each repo; both should stay green.
3. Build + push a new tag and update the App Service container image
   (`engineservice2026.azurecr.io/newsengine-backend` and
   `…/curious-backend`).
4. Verify by submitting an 8-slide AI-image job and grepping the
   `/logs` endpoint for `429` and `Rate limited` — both should be zero.

## Why we are not shipping it right now

Stories complete successfully today and the cosmetic duplicate is rare
enough that we are not blocking on it. We will revisit once we have a
need for tighter image uniqueness or once we move off the current FLUX
endpoint.
