# Study API — Quiz / Flashcards / Exam Plan Contract

Base prefix: `/api/study`.

## Request caps (Feature 2, slice 1)

`StudyRequest`: `topic` 1–300 chars (empty → 422, >300 → 422),
`level` in `easy|medium|hard|exam|olympiad` (else 422),
`count` 1–15 (matches UI `[3,5,10,15]`; 0 or 100 → 422 before any model call),
`days` 1–365. Rate: 30/min (slowapi; no-op where absent).

Why: previously `count` was uncapped — one `count=100` burned a full LLM
generation before the parser capped to 10. Now validation rejects it in <5 ms.

## Endpoints

- `POST /quiz` → `QuizResponse{questions[{question, options[4], correct A-D, explanation, verified}]}`.
  `verified`: `triple_verified|majority_verified|disputed|original|no_data|unverified`.
- `POST /quiz/stream` → SSE `total → question* → progress → done` (disconnect-aware).
- `POST /flashcards`, `/summary`, `/notes` — same caps.
- `POST /cheatsheet` — topic ≤300 (already), subject ≤80.
- `POST /exam-plan/parse-notification` — file ≤10 MB (→ 413), empty → 400,
  unreadable → 400, preview `text[:1500]`, stored `assessment_text[:4000]`.
- `POST /exam-plans/{id}/practice-set` — `count` clamped 3–10, `timed_mins=count*2`.

## Verification pipeline (unchanged this slice)

`generate_quiz` → tolerant `_parse_quiz` → parallel 2nd-model (12s) + Google (8s),
overall 25s (30s bg) → `_cross_compare` (triple/majority/math_corrected/disputed).
Timeout → `original/unverified`, never 500. Stream deadline 120s + `unverified` leftovers.

Next slice candidate: stored marking-accuracy bank (gradeable eval, CI gate >95% parse).
