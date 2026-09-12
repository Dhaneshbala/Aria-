# ARIA — AI Study Assistant v2.5
### Built for MacBook Air M4 · 16 GB RAM

A fully local, private AI study workspace. All AI runs on your Mac.
No subscriptions. No data sent anywhere. Everything stays on your computer.

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
- Pulls AI models if missing (~9 GB, first run only)
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
| Ollama models | Downloads ~9 GB | Already installed |
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

## AI Models (16 GB unified memory — env overrides `ARIA_MAIN_MODEL` / `OLLAMA_URL`)

| Model | Size | RAM | Purpose |
|---|---|---|---|
| **gemma4:e4b-mlx** | ~5-6 GB | ~9 GB | Main (multimodal) — chat, reasoning, vision, coding, math |
| **nomic-embed-text** | 274 MB | ~0.5 GB | Embeddings only — memory/RAG |
| **Pollinations.ai** | 0 GB | 0 GB | Image generation (free, uses internet) |

Single generation model avoids RAM pressure. Env: `OLLAMA_URL=http://localhost:11434/api/generate` (see `backend/models/database.py:OLLAMA_URL`).

---

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
- ✨ Visualize any answer as an editable diagram (flowchart, mind map, cycle, timeline, Venn, pie, bars…)
- Attach images — worksheets, handwritten notes, diagrams, photos
- Attach PDFs, Word, PowerPoint, Excel — ask questions about them
- Voice input
- Export chats as Markdown or JSON
- Pin and search past conversations
- Memory of past chats (ChromaDB)

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

### File Organizer
- **AI organization** — reads file *contents* (text, PDFs, Word, Excel, code, images via OCR/vision) not just filenames
- **Deep rename + organize (Riffo-style)** — "AI Rename + Organize" deep-reads every file and proposes a descriptive new name *and* the right folder; review in a table, apply with one click — **no file limit** (Riffo caps at 20). Progress streams live, everything is undoable
- **Y7 taxonomy** — subject + topic folders (Mathematics/Number & Algebra, Science/Cells & Living Things, …)
- **Rules engine** — user-editable priority rules applied before AI
- **Preview before changes** — dry-run plans every move with explanation + confidence
- **Undo everything** — history log + one-click rollback; every move is backed up and verified
- **Smart naming** — AI renames files with descriptive titles
- **Duplicates** — exact (SHA-256) and near-duplicate (content overlap) detection
- **Search** — scored full-text search across titles, content, tags, keywords + advanced filters
- **Folder watching** — auto-index new files dropped into watched folders
- **Tags & metadata** — auto-tagged with searchable subject/topic/people/companies/dates/keywords
- **Profiles** — save and reload reusable rule sets
- **Safety-first** — never deletes files automatically

API reference: `backend/docs/organizer_api.md` · Example rules: `backend/data/example_rules.json` · Sample data: `python backend/scripts/make_sample_data.py`

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
Go to **Admin** → change Reasoning Model to `qwen3:4b` (faster, still good).

### Out of RAM / app freezes
Close other apps (Chrome tabs, etc.) before using ARIA. ARIA + macOS needs ~13 GB for the main model.

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
