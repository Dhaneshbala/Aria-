# ARIA — AI Study Assistant v2.0
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
| Ollama | http://localhostx:11434 | AI model server |

If port 5173 is already in use, the frontend will start on 5174 (check Terminal output).

---

## AI Models

| Model | Size | RAM | Purpose |
|---|---|---|---|
| **qwen3:8b** | 5.2 GB | ~8 GB | Main reasoning — chat, quiz, notes, plans |
| **qwen2.5vl:3b** | 2.2 GB | ~4 GB | Vision — reads images & worksheets |
| **llama3.2:3b** | 2.0 GB | ~3 GB | Fast fallback |
| **Pollinations.ai** | 0 GB | 0 GB | Image generation (free, uses internet) |

Ollama loads ONE model at a time. M4 chip runs models on its built-in GPU via Metal.

---

## What You Can Do

Just type naturally — ARIA figures out what you need:

| What you type | What ARIA does |
|---|---|
| *"Explain photosynthesis"* | Full explanation + auto-generates flashcards |
| *"Quiz me on World War 2"* | Interactive multiple-choice quiz |
| *"Make a mind map of the water cycle"* | SVG mind map rendered in chat |
| *"Study plan for my maths exam next week"* | 7-day plan with tick boxes |
| *[attaches worksheet photo]* | Vision model reads it, answers each question |
| *[attaches PDF]* "What are quotes about diversity?" | Extracts relevant quotes with page numbers |
| *"Draw the solar system"* | Generates image (Pollinations.ai, free) |
| *[pastes YouTube URL]* | Gets transcript, summary, quiz, flashcards |
| *"Search for latest discoveries about black holes"* | Live web search + answer |
| *"Debug this code"* + paste code | Explains bugs, suggests fixes |
| *"Write an essay outline on climate change"* | Structured outline with key arguments |

---

## Features

### Chat
- Streaming responses
- Attach images — worksheets, handwritten notes, diagrams, photos
- Attach PDFs, Word, PowerPoint, Excel — ask questions about them
- Voice input
- Export chats as Markdown or JSON
- Pin and search past conversations
- Memory of past chats (ChromaDB)

### Study Tools
- Quiz — Easy / Medium / Hard / Olympiad / Exam mode
- Flashcards — Flip, shuffle, mark as known
- Mind Maps — Interactive SVG, downloadable
- Study Plan — Day-by-day with tick boxes
- Notes — Structured, Cornell, outline styles
- Essay Feedback — get detailed feedback on essays
- Formula Reference — quick formula lookup

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
│   │   ├── study_service.py  ← Quiz/flashcards/mindmap/notes
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
│   │   ├── pages/            ← Chat, Quiz, Flashcards, Coding, etc.
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
source venv/bin/activate
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
