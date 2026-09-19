# Voice API — Realtime Tutor Protocol

Base prefix: `/api/voice`. REST stays the source of truth for accuracy;
the WebSocket exists for latency (live partials, VAD feedback).

## Feature detection

`GET /api/voice/stream-info` →

```json
{
  "ws_transcribe": "/api/voice/ws-transcribe",
  "chunk_endpoint": "/api/voice/chunk",
  "tts_voices": ["ta", "hi", "..."],
  "tts_voices_installed": ["ta", "hi", "..."],
  "stats": {"ws_sessions": 0, "ws_partials": 0, "ws_finals": 0, "tts_hits": 0, "tts_misses": 0},
  "ws_idle_timeout_s": 300,
  "ws_max_session_s": 900
}
```

## REST

| Method | Endpoint | Notes |
|---|---|---|
| POST | `/voice/transcribe` | `audio` file (≤25 MB, empty → blank result) + optional `language` hint → `{transcript, language, …}` |
| POST | `/voice/synthesize` | `{text, language?}` → audio bytes. `X-Cache: HIT/MISS`, `X-Voice: <name>`, `X-Engine: piper\|say` |
| POST | `/voice/chunk` | `{text, max_chars}` → `{chunks, count}` sentence chunks for streaming TTS |
| GET | `/voice/languages` | 99 Whisper languages, each with `tts` / `tts_voice` availability flags |

TTS engines (in order): **Piper neural** for mapped languages
(`en→lessac`, `hi→pratham`, `te→maya`, `bn→google`, `ml→meera`,
`mr→google`, `ur→aegis_female`; ~65 MB ONNX voices each in
`$ARIA_DATA_DIR/piper`, WAV output) → **macOS `say`** (M4A, incl. all 19
language voices — the only engine for `ta`, `kn`, `fr`, …) →
pyttsx3 → error. Provision voices reproducibly with
`python3 backend/scripts/fetch_piper_voices.py` (curl-based, skips present
files, `--check-only` to audit), or opt into fetch-at-boot with
`ARIA_FETCH_VOICES=1 ./start.sh` (never fails the boot; default off).
Loaded Piper voices are LRU-capped at 3 resident (~200 MB) so 7 installed
voices can't squeeze the 16 GB Mac next to whisper + gemma. Measured here: Piper en 0.54 s, hi/te/bn/
ml/mr/ur 0.11–0.17 s per medium sentence vs `say` ~1.0–1.3 s.
Live-verified over HTTP: en → `x-engine: piper` + valid WAV, ta → `x-engine:
say, x-voice: Vani` + valid M4A, repeat → `x-cache: HIT`.
`tts_engine(lang)` picks without synthesizing; the TTS cache key includes
the engine tag so WAVs and M4As never collide.

TTS cache: 50 entries / 20 MB LRU, keyed by (text, language). At most 2
parallel syntheses (semaphore) to protect the M4 CPU.
Voices: macOS `say -v` map (`ta→Vani`, `hi→Lekha`, …); installed voices are
probed once at startup and missing ones fall back to the default voice.
English always uses the default voice.

## WebSocket `/voice/ws-transcribe`

Binary audio chunks in (e.g. `MediaRecorder` 250 ms timeslices), JSON out.

Client → server:
- `{"type":"config","language":"ta","mime":"audio/webm"}` (optional;
  language ≤10 chars, mime ≤40 chars, longer values ignored)
- binary audio chunks (≤1 MB each; larger ones get an error, connection stays open)
- `{"type":"flush"}` → final transcript, buffer cleared, stays open
- `{"type":"reset"}` → clear buffer
- non-object JSON → `bad_json` error, connection stays open

Server → client: `ready`, `vad` (`{speech, energy, bytes}` per chunk),
`partial` (throttled: ≥30 KB buffer, ≥8 s gap, never overlapping),
`final` (`{transcript, language, …}`), `error`.

Limits: 1 MB per chunk, 8 MB buffer, 5 min idle timeout, 15 min absolute
session cap, max 4 concurrent streams (5th gets `busy` + close 1013).
REST guards: 25 MB transcribe cap, slowapi rates (30/min transcribe,
120/min synthesize, 240/min chunk — no-op where slowapi is absent).
Empty `flush` returns an empty final (counted in stats).

## Frontend flow (`VoiceTutorPage`)

1. `listen()` opens the WS in the background (never blocks mic start),
   seeded with last turn's language; records with 250 ms timeslices.
2. Timeslices go to the WS (live partial bubble) and the REST blob.
3. Silence (2.5 s, with level meter) or 45 s cap stops recording → REST
   `transcribe` (truth; ≤25 MB, empty input short-circuits), falling back to
   the WS live partial if REST fails. Pressing stop discards the buffered
   audio so no ghost turn fires.
4. Chat streams with `mode: 'voice'` (short, speakable, no markdown,
   student's language).
5. Sentence 1 goes to language-matched TTS immediately; next sentences
   prefetch while playing; empties/repeats are skipped.
6. `Interrupt` / `Esc` aborts LLM + audio and re-listens (barge-in);
   hidden tabs pause audio. Dev proxy passes WS upgrades (`ws: true`).

Speech cleanup: `clean_for_speech()` verbalizes maths (`x^2` → "x squared")
and strips markdown. Frontend `voiceQueue.js` mirrors the backend helpers —
keep the two in sync.

## Baseline budget (this Mac, `python3 backend/scripts/bench_voice.py`)

| Stage | Median (two runs) |
|---|---|
| TTS `say`, short ("Well done!") | 0.7–0.9 s |
| TTS `say`, medium sentence | 1.2–1.3 s |
| TTS `say`, Tamil short | 0.45–0.65 s |
| STT whisper-small, cold (model load) | 3.0–4.8 s |
| STT whisper-small, warm, ~5 s audio | 1.9–2.3 s (+875 MB RSS) |

Takeaways: sentence-1 prefetch hides the ~1 s TTS cost (TTFA ≈ TTFS + ~1 s);
WS partials cost a full warm transcribe (~2.3 s), hence the ≥30 KB / ≥8 s
throttle. Whisper stays lazily loaded — pre-warming would pin ~875 MB for
non-voice users next to the ~9 GB main model on 16 GB RAM. Instead the model
warms in the background when a voice stream connects (first-turn cold
4.8 s → ~2.3 s); the large-v3-turbo fallback stays lazy so opening the
tutor never triggers its ~1.6 GB download.

## Day 40: end-to-end voice latency (live server + real models)

Full spoken turn measured live: LLM first text token **10.0 s**, Piper
sentence-1 synth **0.8 s** → TTFA ≈ **10.8 s**. TTS is 7% of the budget —
the bottleneck is gemma TTFT on-device. Voice mode therefore never streams
reasoning preambles (`stream_think=False` even for math/explain intents;
post-hoc math verification still runs). A smaller voice model
(`qwen3:4b`) was evaluated as the next lever but its registry is
unreachable from managed networks (`ollama pull` → EOF), so gemma stays
the voice model until the network allows otherwise.
