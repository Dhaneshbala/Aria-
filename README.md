# ARIA — AI Study Assistant v2.6
### Built for MacBook Air M4 · 16 GB RAM

A fully local, private AI study workspace. All AI runs on your Mac.
No subscriptions. No data sent anywhere. Everything stays on your computer.
(Cloud AI is available through an explicit opt-in — see `docs/PROVIDERS.md`.)

---

## Quick Start

### 1. Install Ollama (one time only)
Go to **https://ollama.com** → download the Mac app → install it like any app.

### 2. Start ARIA
Open Terminal and run:
```bash
cd ~/Downloads/aria-2
chmod +x start.sh    # first time only
./start.sh
```

That's it. The script handles everything:
- Starts Ollama if it's not running
- Pulls AI models if missing (~8 GB, first run only)
- Creates Python virtual environment and installs dependencies
- Installs npm packages if missing
- Starts backend (port 8000) and frontend (port 5173)
- Opens your browser automatically

### 3. Stop ARIA
Press **Ctrl+C** in the Terminal window.

---

## First Run vs Normal Run

| | First time | Every time after |
|---|---|---|
| Ollama models | Downloads ~8 GB | Already installed |
| Python venv | Created + deps installed | Already exists |
| npm packages | Installed (~30 sec) | Already installed |
| Total time | ~2-3 minutes | ~5 seconds |

---

## URL Ports

| Service | URL | Notes |
|---|---|---|
| Frontend | http://localhost:5173 | Opens automatically |
| Backend API | http://localhost:8000 | FastAPI |
| Ollama | http://localhost:11434 | AI model server |

If port 5173 is already in use, the frontend will start on 5174 (check Terminal output).

---

## Use ARIA From Your Phone (Android / iPhone)

ARIA installs as an app via your browser — no Play Store / App Store needed.
Your Mac does the AI work; the phone is a remote control + camera.

### 1. Put backend + frontend on your Wi-Fi (on your Mac)

Find your Mac's Wi-Fi IP (System Settings → Wi-Fi → Details, e.g. `192.168.1.10`), then:

```bash
cd ~/Projects/ARIA/aria-2
ARIA_LAN=1 ARIA_HOST=0.0.0.0 \
  ARIA_CORS_ORIGINS=http://localhost:5173,http://192.168.1.10:5173 \
  ./start.sh
```

(`ARIA_LAN=1` also binds the frontend to the network. Replace `192.168.1.10` with your Mac's IP.)

### 2. Open it on your phone (same Wi-Fi)

- **Android (Chrome):** open `http://192.168.1.10:5173` → ⋮ menu → **Add to Home screen** (or **Install app**). ARIA then runs fullscreen with its own icon, plus Chat/Review/Voice shortcuts on long-press.
- **iPhone (Safari):** open the same URL → **Share → Add to Home Screen**. (iOS doesn't allow auto-install prompts, ARIA shows the steps in-app.)

### 3. Phone tips

- 📷 **Camera button** in chat takes a worksheet photo directly (gallery button still there for existing photos).
- 🎤 Voice input uses the phone mic; TTS answers play on the phone speaker.
- Use **trusted Wi-Fi only** — in LAN mode anyone on the network can reach the API. Terminal/file tools stay locked to the Mac itself, but chats have no login screen. Never enable `ARIA_HOST=0.0.0.0` on public Wi-Fi.

### Permanent install (no dev server)

```bash
cd ~/Projects/ARIA/aria-2/frontend
VITE_API_URL=http://192.168.1.10:8000/api npm run build
# serve dist/ on your LAN, e.g.:
npx serve -s dist -l 5173
```

Then install from `http://192.168.1.10:5173` as above. The installed app keeps working offline for the shell; AI features need the Mac + backend reachable.

### Away from home (mobile data / school Wi-Fi) — no Cloudflare

Why Wi-Fi only above? `192.168.1.x` addresses only exist inside your home network —
over mobile data your phone has no route to your Mac. Instead of opening ports
(or Cloudflare), use **Tailscale**: a free private WireGuard mesh between *your*
devices only. No open ports, no third-party proxy in front of ARIA.

1. Install Tailscale (free personal plan) on your **Mac** and your **phone**, log in with the same account.
2. On your Mac, start ARIA **normally** (localhost-only — no `ARIA_LAN` needed):
   ```bash
   ./start.sh
   ```
3. Still on the Mac, expose just the frontend to your private tailnet over HTTPS:
   ```bash
   tailscale serve --bg 5173
   ```
4. On your phone (mobile data is fine), open the HTTPS URL Tailscale shows:
   ```bash
   tailscale serve status   # e.g. https://macbook-air.tailabc123.ts.net
   ```
   Install it to the home screen exactly like the Wi-Fi flow above.

Why this is better than LAN mode:
- **HTTPS included** — mic/voice recording and auto-install only work in a secure context; plain `http://192.168...` blocks the mic on some browsers.
- **Backend stays localhost-only** — the Mac's Vite proxy forwards `/api` server-side, so nothing extra is exposed, and no CORS changes are needed.
- **Works anywhere** — school, bus, mobile data — only your logged-in devices can reach it.
- To stop sharing: `tailscale serve --bg off`.

---

## AI Models (16 GB unified memory — env overrides `ARIA_MAIN_MODEL` / `OLLAMA_URL`)

| Model | Size | RAM | Purpose |
|---|---|---|---|
| **qwen3.5:9b** | ~7.6 GB | ~10 GB | Main (multimodal, thinking) — chat, reasoning, vision, coding, math |
| **nomic-embed-text** | 274 MB | ~0.5 GB | Embeddings only — memory/RAG |
| **Pollinations.ai** | 0 GB | 0 GB | Image generation (free, uses internet) |

Single generation model avoids RAM pressure. The exact model lives in
`config.json` (Admin → model settings) — current default `qwen3.5:9b`.
Optional cloud models (Anthropic Claude) require an explicit
`anthropic:`-prefixed model ID plus consent envs — see `docs/PROVIDERS.md`.

## What You Can Do

Just type naturally — ARIA figures out what you need:

| What you type | What ARIA does (all via Chat brain) |
|---|---|
| *"Explain photosynthesis"* | Full explanation + auto-generates flashcards |
| *"Quiz me on World War 2"* | Interactive multiple-choice quiz |
| *"Make a mind map of the water cycle"* | Editable visual (flow/mind map/cycle/…) rendered in chat |
| *Any AI answer → ✨ Visualize* | Turn it into an editable visual (10 types, 5 styles, SVG/PNG/PDF export) |
| *[attaches worksheet photo]* | Vision reads it, answers each question |
| *[attaches handwriting photo] “check my answer”* | Transcribes + grades 0-10 with tips |
| *"Essay feedback on …"* | Detailed feedback (thesis/evidence/grammar) |
| *"Formula for quadratic"* | Formula sheet + worked example |
| *"Timeline for WW2"* | Chronological timeline with causes |
| *"Exam sim on algebra – 10q hard"* | Timed mock exam with explanations |
| *"Audio overview of photosynthesis"* | 3-5 min script → Listen button (TTS) |
| *"What are my weak topics?"* | Study intel from profile + NSW outcomes |
| *"Worksheet on fractions Year 7"* | NSW-aligned worksheet + answer key |
| *[attaches PDF]* "What are quotes about diversity?" | Extracts relevant quotes with page numbers |
| *"Draw the solar system"* | Generates image (Pollinations.ai, free) |
| *[pastes YouTube URL]* | Gets transcript, summary, quiz, flashcards |
| *"Search for latest discoveries about black holes"* | Live web search + answer |
| *"Debug this code"* + paste code | Explains bugs, suggests fixes |

---

## Features

### Chat
- Streaming responses — leave the page mid-answer, it keeps working (task pill follows you)
- **Retry failed messages** — connection errors surface a Retry button; your text is saved
- ✨ Visualize any answer as an editable diagram (flowchart, mind map, cycle, timeline, Venn, pie, bars…)
- Attach images — worksheets, handwritten notes, diagrams, photos
- Attach PDFs, Word, PowerPoint, Excel — ask questions about them
- Voice input
- Export chats as Markdown or JSON
- Pin (persists across reloads) and search past conversations
- Memory of past chats (ChromaDB)
- **AI usage ledger** — exact per-model token counts + optional cloud cost estimates,
  visible in Admin → AI Usage and via `GET /api/v2/usage/summary`

### Study Tools (now in Chat brain — no separate tabs)
- Quiz / Flashcards / Exam Plan — still in Create, also via chat
- Mind maps and diagrams — via chat visuals (pick a style, edit text, export)
- Background-safe — quiz/flashcard/mind-map/exam-plan generation continues if you navigate away; results land where they belong
- Notes — Structured, Cornell, outline styles (via chat)
- Essay Feedback / Formula / Timeline / Exam Sim / Audio Overview / Worksheet / Handwriting / Study Intel — just ask in Chat (see table above). Handwriting: upload photo → “check my answer”. Brain handles all via `backend/services/orchestrator.py` intents (`essay_feedback`, `formula`, `timeline`, `exam_sim`, `audio_overview`, `study_intel`, `worksheet_generator`, `image_analysis`).

### Coding
- Explain / Debug / Generate / Refactor code
- Multiple languages supported
- Terminal command generation

### Research
- Web Search — Live DuckDuckGo results
- YouTube Analyser — Paste URL → transcript, summary, quiz, flashcards

### Image Generation
- Powered by Pollinations.ai (free, no GPU needed)
- Just describe what you want

### Profile
- Tracks accuracy per subject
- Identifies weak and strong areas
- Study streak

---

## Folder Structure

```
aria-2/
├── start.sh                  ← Run this to start everything
├── backend/
│   ├── main.py               ← FastAPI entry point
│   ├── models/
│   │   └── database.py       ← Config + data storage
│   ├── services/
│   │   ├── orchestrator.py   ← The brain — coordinates all models
│   │   ├── ollama_service.py ← M4 Metal GPU optimised
│   │   ├── study_service.py  ← Quiz/flashcards/notes
│   │   ├── diagram_service.py ← Napkin-style visual specs (10 types)
│   │   ├── image_service.py  ← Vision + OCR
│   │   ├── document_service.py← PDF/Word/PPT reading
│   │   ├── memory_service.py ← ChromaDB RAG
│   │   ├── imagegen_service.py← Pollinations.ai image gen
│   │   ├── research_service.py← Web search
│   │   ├── youtube_service.py← Transcript + analysis
│   │   ├── voice_service.py  ← STT/TTS
│   │   └── agent_service.py  ← File/terminal operations
│   ├── routers/
│   │   ├── chat.py           ← Main SSE streaming endpoint
│   │   ├── study.py          ← Study tools API
│   │   ├── docs.py           ← PDF summarise/quotes/ask
│   │   ├── admin.py          ← Config, health, model management
│   │   ├── agent.py          ← Agent mode endpoints
│   │   └── ...
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx           ← Routes + Toast provider
│   │   ├── store.js          ← Global state (Zustand)
│   │   ├── services/api.js   ← All API calls
│   │   ├── hooks/useChat.js  ← Streaming + orchestrator logic
│   │   ├── services/tasks.js ← Background tasks survive navigation
│   │   ├── components/NapkinDiagram.jsx ← Editable visuals (SVG/PNG/PDF)
│   │   ├── pages/            ← Chat, Dashboard, Quiz, Flashcards, Coding, etc.
│   │   └── components/       ← Message, Sidebar, ChatInput, etc.
│   └── package.json
```

---

## Testing

| What | How |
|---|---|
| Backend unit tests (no live AI needed) | `cd backend && .venv/bin/python -m pytest -q --ignore=tests/test_e2e_features.py` (or `make fast` from repo root) |
| Full backend suite **with live model** | `make test` (needs Ollama running with `qwen3.5:9b`) |
| AI provider & usage ledger tests | `cd backend && .venv/bin/python -m pytest -q tests/test_ai_providers.py` |
| Frontend unit tests | `cd frontend && npm test` |
| Lint & dead code | `npm run lint` · `npm run dead` (backend: `make audit`, `make dead`) |
| Frontend build (PWA bundle) | `npm run build` |
| Browser E2E incl. mobile viewports | start backend + `npm run dev`, then `npx playwright test` |

Feature status and everything that is *not* done yet: `docs/KNOWN_LIMITATIONS.md`.
Cloud AI setup: `docs/PROVIDERS.md`. Growth/limits: `docs/SCALE.md`.

---

## Troubleshooting

### "Ollama offline" in the status bar
Ollama isn't running. Either:
- Run `ollama serve` in a separate Terminal window, OR
- Restart ARIA with `./start.sh` (it auto-starts Ollama)

### Port already in use
```bash
# Find and kill the process on the port
lsof -ti:5173 | xargs kill    # frontend
lsof -ti:8000 | xargs kill    # backend
```
Then run `./start.sh` again.

### Models are slow
Ollama + gemma3:12b needs room — see "Out of RAM" below first. If the model
itself is the bottleneck, a smaller model answers faster (less accurate).

### Out of RAM / app freezes
This Mac has 16 GB and ARIA's model needs ~8 GB resident. When macOS runs
out, it kills things. In order of impact:
1. **Close Chrome tabs** — each renderer is 200-600 MB; 10 tabs ≈ the model.
2. **Admin → Memory → Unload AI models** — frees ~8 GB instantly; reloads on next use.
3. Quit Slack and other Electron apps while studying (~400 MB each).
4. Tighten auto-unload: `OLLAMA_KEEP_ALIVE=2m ./start.sh` (default 5m) so RAM
   frees sooner when idle. Tradeoff: reload waits after idle.

### Image generation not working
Needs internet. Check your Wi-Fi connection.

### Voice not working
Allow microphone access in Safari/Chrome when prompted.

### Backend won't start
```bash
cd ~/Downloads/aria-2/backend
source ../.venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

### Frontend won't start
```bash
cd ~/Downloads/aria-2/frontend
npm install
npm run dev
```

---

Made with love for a 13-year-old who loves learning.
