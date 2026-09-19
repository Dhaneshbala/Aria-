# ARIA Feature Quality Bar

Every feature ships only when it clears all six gates — the same treatment
the voice tutor got over Days 1–54. No exceptions, no "demo depth".

## The six gates

1. **Baseline** — measured numbers on this Mac before changing anything
   (latency, sizes, accuracy where gradeable). Guesses don't count.
2. **Core improvement** — the actual user-facing win (faster, smarter,
   new capability). One slice at a time, each independently shippable.
3. **Robustness caps** — every unbounded thing gets a bound: sizes, counts,
   timeouts, concurrency, cache limits. Failures degrade (fallback), never
   hang or OOM. Matches house patterns (slowapi rates, 413s, LRU caches).
4. **Tests** — pytest for backend logic (fast, hermetic, no models/network),
   esbuild/node checks for frontend. New behavior pins a test; regressions
   run green before moving on.
5. **Docs** — protocol/behavior notes in `backend/docs/`, user-facing notes
   in README troubleshooting where relevant, Admin visibility where it fits.
6. **Live verification** — real HTTP against a running server with real
   models wherever possible (never the user's :8000 session; spare ports,
   killed afterwards).

## Feature order (highest leverage first)

1. **Chat core / orchestrator** — everything flows through it. (Voice days
   already measured TTFS 10–15 s live; that number must come down or be
   justified per mode.)
2. **Quiz + exam sim** — marking accuracy is gradeable → eval harness first.
3. **Spaced repetition + flashcards** — scheduling correctness (FSRS props).
4. **Study intel / analytics** — predictions must be backtestable, not vibes.
5. **File organizer** — destructive ops need dry-run + undo proof.
6. **Research / YouTube / docs** — citation accuracy, failure fallbacks.
7. **Diagrams / image gen** — output validity checks.
8. **Gamification / todos / notebooks / admin** — logic tests + caps.
9. **Voice** — DONE (Days 1–54, see `voice_api.md` + root `CHANGELOG.md`).

## Rules of the road

- Never touch the user's live :8000 session. Spare ports only.
- Never download gigabytes without an explicit go-ahead (fetch scripts are
  opt-in; `--check-only` must always work offline).
- Never trade correctness for speed without measuring both sides.
- Managed-network reality: pip + curl work; python-ssl + HF + ollama
  registry do not. Design provisioning accordingly.
