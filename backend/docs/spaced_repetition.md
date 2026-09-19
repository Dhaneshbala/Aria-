# Spaced Repetition — SM-2 Contract + Caps

Base prefix: `/api/v2/study`.

## Algorithm (pinned, not vibes)

SM-2: `EF 2.5 / floor 1.3`, intervals `1 → 6 → round(interval*EF)`,
reset on `quality<3`, `next_review = now + interval days`,
`history[-200:]`. Overdue-first sort by `next_review`.
Streak: consecutive review days ending today/yesterday.

Pinned by `tests/test_sr_correctness.py` (intervals, reset, due-sort, streak-adjacent).

## IDs + caps (Feature 3, slice 1)

- IDs: `card_<12-hex-uuid>` (was `timestamp_ms[+len]` — collided under bulk-same-ms).
- `bulk-add-cards`: max 200 inputs, empties skipped (was: unbounded + stored blanks).
- `import-csv`: file ≤2 MB → 413, rows capped 200, header-skip, `No valid rows` error (was: unbounded → OOM).
- `add-card`: `front/back` 1–5000, `review-card`: `quality` 0–5 (422 on violation).
- `review-card` missing id → `{"error":"Card not found"}` (200, frontend-compatible; 404 deferred to avoid breaking `reviewSrCard().json()`).

Full FSRS + retention eval is the 1000-day target; SM-2 correctness + collision/cap fixes are this slice.
