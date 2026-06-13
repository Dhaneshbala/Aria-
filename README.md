# ARIA — AI Study Assistant v2.0
### Built for MacBook Air M4 · 16 GB RAM · 100 GB free storage

A fully local, private AI study workspace. All AI runs on your Mac.
No subscriptions. No data sent anywhere. Everything stays on your computer.

---

## Quick Start (3 steps)

### Step 1 — Install Ollama
Go to **https://ollama.com** and download the Mac app. Install it like any app.

### Step 2 — Double-click to launch ARIA
```bash
# In Terminal, navigate to the ARIA folder:
cd aria
chmod +x start.sh
./start.sh
```
The script will:
- Pull the right AI models automatically (~9 GB, takes a few minutes first time)
- Start the backend and frontend
- Open your browser to **http://localhost:5173**

### Step 3 — Start studying!

---

## What your son can do in the chat

Just type naturally — ARIA figures out what he needs:

| What he types | What ARIA does |
|---|---|
| *"Explain photosynthesis"* | Full explanation + auto-generates flashcards |
| *"Quiz me on World War 2"* | Interactive multiple-choice quiz inline |
| *"Make a mind map of the water cycle"* | SVG mind map rendered in chat |
| *"Study plan for my maths exam next week"* | 7-day plan with tick boxes |
| *[attaches worksheet photo]* | Vision model reads it, answers each question |
| *[attaches PDF]* "What are quotes about diversity?" | Extracts relevant quotes with page numbers |
| *"Draw the solar system"* | Generates image (Pollinations.ai, free) |
| *[pastes YouTube URL]* | Gets transcript, summary, quiz, flashcards |
| *"Search for latest discoveries about black holes"* | Live web search + answer |
| *"Solve question 12"* + worksheet photo | Works through it step by step |

---

## AI Models (chosen for M4 MacBook Air 16 GB)

| Model | Size | RAM | Purpose |
|---|---|---|---|
| **qwen3:8b** | 5.2 GB | ~8 GB | Main reasoning — chat, quiz, notes, plans |
| **qwen2.5vl:3b** | 2.2 GB | ~4 GB | Vision — reads images & worksheets |
| **llama3.2:3b** | 2.0 GB | ~3 GB | Fast fallback |
| **Pollinations.ai** | 0 GB | 0 GB | Image generation (free, uses internet) |

**Total disk: ~9.4 GB** (well within your 100 GB free space)

**How RAM works:** Ollama loads ONE model at a time.
- Chatting = qwen3:8b (8 GB) + macOS (5 GB) = 13 GB ✅
- Image reading = qwen2.5vl:3b (4 GB) + macOS (5 GB) = 9 GB ✅
- M4 chip runs models on its built-in GPU automatically via Metal

---

## Features

### Chat (everything intertwined)
- Streaming responses like Claude
- Attach **images** — worksheets, handwritten notes, diagrams, photos
- Attach **PDFs, Word, PowerPoint, Excel** — ask questions about them
- **Voice input** — speak instead of typing
- **Export** chats as Markdown or JSON
- **Pin and search** past conversations
- Memory of past chats (ChromaDB)

### Study Tools (all work inline in chat too)
- **Quiz** — Easy / Medium / Hard / Olympiad / Exam mode
- **Flashcards** — Flip, shuffle, mark as known
- **Mind Maps** — Interactive SVG, downloadable
- **Study Plan** — Day-by-day with tick boxes
- **Notes** — Structured, Cornell, outline styles
- **PDF Summariser** — Works on large multi-page PDFs
- **Quote Extractor** — Find passages for essay themes

### Research
- **Web Search** — Live DuckDuckGo results
- **YouTube Analyser** — Paste URL → transcript, summary, quiz, flashcards

### Profile
- Tracks accuracy per subject
- Identifies weak and strong areas
- Study streak

---

## How the models work as a team

```
Your son types a message
        ↓
Orchestrator detects intent
(quiz? image? search? worksheet? YouTube?)
        ↓
Runs in parallel:
├── Vision model  → if image attached
├── Web search    → if current info needed
├── Memory recall → from past conversations
└── YouTube fetch → if URL present
        ↓
All results combined into one prompt
        ↓
qwen3:8b reasons and streams the answer
        ↓
Auto-generates extras inline:
├── Quiz?        → interactive cards in chat
├── Flashcards?  → flip cards in chat
├── Mind map?    → SVG diagram in chat
└── Study plan?  → tick-box checklist in chat
        ↓
Saves to memory for next session
```

---

## Folder structure

```
aria/
├── start.sh               ← Run this to start everything
├── backend/
│   ├── services/
│   │   ├── orchestrator.py    ← The brain — coordinates all models
│   │   ├── ollama_service.py  ← M4 Metal GPU optimised
│   │   ├── image_service.py   ← Vision + OCR
│   │   ├── document_service.py← PDF/Word/PPT reading + quote extraction
│   │   ├── memory_service.py  ← ChromaDB RAG
│   │   ├── imagegen_service.py← Pollinations.ai image gen
│   │   ├── research_service.py← Web search
│   │   ├── study_service.py   ← Quiz/flashcards/mindmap/notes
│   │   ├── youtube_service.py ← Transcript + analysis
│   │   └── voice_service.py   ← STT/TTS
│   └── routers/
│       ├── chat.py        ← Main SSE streaming endpoint
│       ├── docs.py        ← PDF summarise/quotes/ask
│       ├── study.py       ← Study tools API
│       └── ...
└── frontend/
    └── src/
        ├── pages/         ← 10 pages
        ├── components/    ← Chat, Message, Sidebar, etc.
        └── hooks/useChat.js ← All streaming logic
```

---

## If something isn't working

**Ollama not connecting:**
```bash
ollama serve
```

**Model too slow:**
Go to Admin → change Reasoning Model to `qwen3:4b` (faster, still good)

**Out of RAM:**
Close other apps (Chrome tabs, etc.) before using ARIA

**Image generation not working:**
Needs internet. Check your wifi connection.

**Voice not working:**
Allow microphone access in Safari/Chrome when prompted

---

Made with ❤️ for a 13-year-old who loves learning.
