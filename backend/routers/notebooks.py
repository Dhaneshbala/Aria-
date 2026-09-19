"""Notebook API router — Source-grounded AI notebooks (NotebookLM-style)."""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import json

from services.notebook_service import NotebookService
from services.document_service import DocumentService
from services.ollama_service import OllamaService
from models.database import get_config, MODELS

router = APIRouter(prefix="/api/notebooks", tags=["notebooks"])
svc = NotebookService()
doc_svc = DocumentService()
ollama = OllamaService()


class CreateNotebookRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    tags: List[str] = Field(default_factory=list, max_length=20)
    cover_color: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class UpdateNotebookRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    persona: Optional[str] = Field(default=None, max_length=500)
    tags: Optional[List[str]] = Field(default=None, max_length=20)


class AddSourceRequest(BaseModel):
    source_type: str = Field(..., min_length=1, max_length=50)
    content: str = Field(..., min_length=1, max_length=500000)
    title: str = Field(default="", max_length=500)
    metadata: dict = Field(default_factory=dict)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    notebook_context: str = Field(default="", max_length=50000)


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.get("")
async def list_notebooks():
    return svc.list_notebooks()


@router.post("")
async def create_notebook(req: CreateNotebookRequest):
    return svc.create_notebook(req.name, req.description, req.tags, req.cover_color)


@router.get("/{notebook_id}")
async def get_notebook(notebook_id: str):
    nb = svc.get_notebook(notebook_id)
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return nb


@router.put("/{notebook_id}")
async def update_notebook(notebook_id: str, req: UpdateNotebookRequest):
    updates = {k: v for k, v in req.dict().items() if v is not None}
    result = svc.update_notebook(notebook_id, **updates)
    if not result:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return result


@router.delete("/{notebook_id}")
async def delete_notebook(notebook_id: str):
    if not svc.delete_notebook(notebook_id):
        raise HTTPException(status_code=404, detail="Notebook not found")
    return {"status": "deleted"}


# ── Sources ───────────────────────────────────────────────────────────────────

@router.post("/{notebook_id}/sources")
async def add_source(notebook_id: str, req: AddSourceRequest):
    result = svc.add_source(notebook_id, req.source_type, req.content, req.title, req.metadata)
    if not result:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return result


@router.post("/{notebook_id}/sources/upload")
async def upload_source(notebook_id: str, file: UploadFile = File(...)):
    """Upload a file (PDF, DOCX, TXT, etc.) as a source."""
    nb = svc.get_notebook(notebook_id)
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")
    data = await file.read()
    filename = file.filename or "uploaded_file"
    pages = await doc_svc.extract_pages(data, filename)
    full_text = "\n\n".join(f"[Page {p['page']}]\n{p['text']}" for p in pages)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "text"
    result = svc.add_source(
        notebook_id, ext, full_text, filename,
        {"pages": len(pages), "original_size": len(data)}
    )
    if not result:
        raise HTTPException(status_code=500, detail="Failed to add source")
    return result


@router.delete("/{notebook_id}/sources/{source_id}")
async def remove_source(notebook_id: str, source_id: str):
    if not svc.remove_source(notebook_id, source_id):
        raise HTTPException(status_code=404, detail="Source or notebook not found")
    return {"status": "removed"}


@router.get("/{notebook_id}/sources")
async def list_sources(notebook_id: str):
    sources = svc.build_source_list(notebook_id)
    if sources is None:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return sources


# ── Context & Chat ────────────────────────────────────────────────────────────

@router.get("/{notebook_id}/context")
async def get_context(notebook_id: str, query: str = ""):
    context = svc.get_sources_context(notebook_id, query)
    return {"context": context, "prompt": svc.get_grounding_prompt(notebook_id, query)}


@router.post("/{notebook_id}/chat")
async def notebook_chat(notebook_id: str, req: ChatRequest):
    """Stream a chat response grounded in notebook sources."""
    grounding = svc.get_grounding_prompt(notebook_id, req.message)

    async def generate():
        config = get_config()
        model = config.get("model", config.get("reasoning_model", MODELS["main"]))
        system = grounding or "You are a helpful study assistant."
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": req.message},
        ]
        full = ""
        async for chunk in ollama.stream_chat(messages, model):
            full += chunk
            yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'content': full})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── AI Study Material Generation ─────────────────────────────────────────────

@router.get("/{notebook_id}/generate/summary")
async def generate_summary(notebook_id: str):
    """Generate a summary of all notebook sources."""
    content = svc.get_all_content(notebook_id)
    if not content:
        raise HTTPException(status_code=400, detail="No sources in notebook")

    async def generate():
        config = get_config()
        model = config.get("model", config.get("reasoning_model", MODELS["main"]))
        messages = [
            {"role": "system", "content": "You are a study assistant. Create a clear, structured summary of the following content. Use headings, bullet points, and key takeaways. Be comprehensive but concise."},
            {"role": "user", "content": f"Summarize the following study material:\n\n{content[:15000]}"},
        ]
        full = ""
        async for chunk in ollama.stream_chat(messages, model):
            full += chunk
            yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/{notebook_id}/generate/study-guide")
async def generate_study_guide(notebook_id: str):
    """Generate a study guide with key concepts, definitions, and review questions."""
    content = svc.get_all_content(notebook_id)
    if not content:
        raise HTTPException(status_code=400, detail="No sources in notebook")

    async def generate():
        config = get_config()
        model = config.get("model", config.get("reasoning_model", MODELS["main"]))
        messages = [
            {"role": "system", "content": """Create a comprehensive study guide with these sections:
1. **Key Concepts** — List and explain the main concepts
2. **Important Definitions** — Key terms and their meanings
3. **Key Formulas/Rules** — If applicable
4. **Common Misconceptions** — Things students often get wrong
5. **Review Questions** — 5-10 questions to test understanding
6. **Quick Reference** — A condensed cheat-sheet style summary"""},
            {"role": "user", "content": f"Create a study guide from:\n\n{content[:15000]}"},
        ]
        full = ""
        async for chunk in ollama.stream_chat(messages, model):
            full += chunk
            yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/{notebook_id}/generate/quiz")
async def generate_quiz(notebook_id: str, num_questions: int = 5):
    """Generate quiz questions from notebook sources."""
    num_questions = max(1, min(20, num_questions))
    content = svc.get_all_content(notebook_id)
    if not content:
        raise HTTPException(status_code=400, detail="No sources in notebook")

    async def generate():
        config = get_config()
        model = config.get("model", config.get("reasoning_model", MODELS["main"]))
        messages = [
            {"role": "system", "content": f"""Generate exactly {num_questions} quiz questions from the content.
Format as JSON array with objects: {{"question": "...", "options": ["A", "B", "C", "D"], "correct": 0, "explanation": "..."}}
Return ONLY the JSON array, no other text."""},
            {"role": "user", "content": f"Generate quiz from:\n\n{content[:15000]}"},
        ]
        full = ""
        async for chunk in ollama.stream_chat(messages, model):
            full += chunk
            yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/{notebook_id}/generate/flashcards")
async def generate_flashcards(notebook_id: str, num_cards: int = 10):
    """Generate flashcards from notebook sources."""
    num_cards = max(1, min(50, num_cards))
    content = svc.get_all_content(notebook_id)
    if not content:
        raise HTTPException(status_code=400, detail="No sources in notebook")

    async def generate():
        config = get_config()
        model = config.get("model", config.get("reasoning_model", MODELS["main"]))
        messages = [
            {"role": "system", "content": f"""Generate exactly {num_cards} flashcards from the content.
Format as JSON array with objects: {{"front": "question/term", "back": "answer/definition"}}
Return ONLY the JSON array, no other text."""},
            {"role": "user", "content": f"Generate flashcards from:\n\n{content[:15000]}"},
        ]
        full = ""
        async for chunk in ollama.stream_chat(messages, model):
            full += chunk
            yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/{notebook_id}/generate/timeline")
async def generate_timeline(notebook_id: str):
    """Generate a timeline of events from notebook sources."""
    content = svc.get_all_content(notebook_id)
    if not content:
        raise HTTPException(status_code=400, detail="No sources in notebook")

    async def generate():
        config = get_config()
        model = config.get("model", config.get("reasoning_model", MODELS["main"]))
        messages = [
            {"role": "system", "content": """Extract or create a timeline from the content.
Format as JSON array: [{{"date": "year or period", "event": "what happened", "significance": "why it matters"}}]
Include at least 5 events. Return ONLY the JSON array."""},
            {"role": "user", "content": f"Extract timeline from:\n\n{content[:15000]}"},
        ]
        full = ""
        async for chunk in ollama.stream_chat(messages, model):
            full += chunk
            yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── File Organizer ────────────────────────────────────────────────────────────

@router.get("/{notebook_id}/organizer")
async def get_organizer(notebook_id: str):
    """Get organized file data for the file organizer view."""
    data = svc.get_file_organizer_data(notebook_id)
    if not data:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return data


class RenameSourceRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)


class MoveSourceRequest(BaseModel):
    folder: str = Field(default="Uncategorized", max_length=200)


class BulkMoveRequest(BaseModel):
    source_ids: List[str] = Field(default_factory=list, max_length=100)
    folder: str = Field(default="Uncategorized", max_length=200)


class BulkDeleteRequest(BaseModel):
    source_ids: List[str] = Field(default_factory=list, max_length=100)


@router.put("/{notebook_id}/sources/{source_id}/rename")
async def rename_source(notebook_id: str, source_id: str, body: RenameSourceRequest):
    """Rename a source."""
    result = svc.rename_source(notebook_id, source_id, body.title)
    if not result:
        raise HTTPException(status_code=404, detail="Source not found")
    return result


@router.put("/{notebook_id}/sources/{source_id}/move")
async def move_source(notebook_id: str, source_id: str, body: MoveSourceRequest):
    """Move a source to a folder."""
    result = svc.move_source(notebook_id, source_id, body.folder)
    if not result:
        raise HTTPException(status_code=404, detail="Source not found")
    return result


@router.post("/{notebook_id}/sources/bulk-move")
async def bulk_move(notebook_id: str, body: BulkMoveRequest):
    """Move multiple sources to a folder."""
    count = svc.bulk_move_sources(notebook_id, body.source_ids, body.folder)
    return {"moved": count}


@router.post("/{notebook_id}/sources/bulk-delete")
async def bulk_delete(notebook_id: str, body: BulkDeleteRequest):
    """Delete multiple sources."""
    count = svc.bulk_delete_sources(notebook_id, body.source_ids)
    return {"deleted": count}


@router.post("/{notebook_id}/sources/{source_id}/ai-rename")
async def ai_rename_source(notebook_id: str, source_id: str):
    """AI suggests a better name based on file content."""
    notebook = svc.get_notebook(notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    source = None
    for s in notebook.get("sources", []):
        if s["id"] == source_id:
            source = s
            break
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    content = source.get("content", "")[:3000]
    old_title = source.get("title", "untitled")
    config = get_config()
    model = config.get("model", config.get("reasoning_model", MODELS["main"]))
    messages = [
        {"role": "system", "content": "You are a file naming assistant. Given a file's content and current name, suggest a clear, descriptive, concise name (max 60 chars). Return ONLY the new name, nothing else."},
        {"role": "user", "content": f"Current name: {old_title}\n\nContent:\n{content}"},
    ]
    suggested = ""
    async for chunk in ollama.stream_chat(messages, model):
        suggested += chunk
    suggested = suggested.strip().strip('"').strip("'")
    return {"old_title": old_title, "suggested_title": suggested}


@router.post("/{notebook_id}/sources/{source_id}/ai-folder")
async def ai_suggest_folder(notebook_id: str, source_id: str):
    """AI suggests which folder a file belongs to."""
    notebook = svc.get_notebook(notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    source = None
    for s in notebook.get("sources", []):
        if s["id"] == source_id:
            source = s
            break
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    content = source.get("content", "")[:2000]
    existing_folders = list(set(s.get("folder", "Uncategorized") for s in notebook.get("sources", [])))
    config = get_config()
    model = config.get("model", config.get("reasoning_model", MODELS["main"]))
    messages = [
        {"role": "system", "content": f"You are a file organizer. Given a file's content, suggest which folder it belongs to. Available folders: {existing_folders}. If none fit, suggest a new folder name. Return ONLY the folder name, nothing else."},
        {"role": "user", "content": f"File title: {source.get('title', 'untitled')}\n\nContent:\n{content}"},
    ]
    suggested = ""
    async for chunk in ollama.stream_chat(messages, model):
        suggested += chunk
    folder = suggested.strip().strip('"').strip("'").strip() or "Uncategorized"
    return {"folder": folder, "existing_folders": existing_folders}


@router.post("/{notebook_id}/sources/ai-autofolder")
async def ai_autofolder_all(notebook_id: str):
    """AI auto-organizes all sources into folders."""
    notebook = svc.get_notebook(notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    sources = notebook.get("sources", [])
    if not sources:
        raise HTTPException(status_code=400, detail="No sources")
    summaries = []
    for i, s in enumerate(sources):
        content = s.get("content", "")[:1500]
        summaries.append(f"[{i}] {s.get('title', 'untitled')}:\n{content}")
    all_text = "\n\n".join(summaries)
    config = get_config()
    model = config.get("model", config.get("reasoning_model", MODELS["main"]))
    messages = [
        {"role": "system", "content": """You are a file organizer. Given a list of files with their content, assign each to a logical folder.
Return ONLY a JSON array of objects like: [{"index": 0, "folder": "Science"}, {"index": 1, "folder": "History"}]
Use clear, descriptive folder names. Group related files together. No explanation."""},
        {"role": "user", "content": f"Files:\n\n{all_text[:12000]}"},
    ]
    result = ""
    async for chunk in ollama.stream_chat(messages, model):
        result += chunk
    import json as _json
    try:
        assignments = _json.loads(result.strip().strip("```json").strip("```"))
        count = 0
        for a in assignments:
            idx = a.get("index", -1)
            folder = a.get("folder", "Uncategorized")
            if 0 <= idx < len(sources):
                sources[idx]["folder"] = folder
                count += 1
        svc._save_notebook(notebook)
        return {"organized": count, "folders": list(set(s.get("folder", "Uncategorized") for s in sources))}
    except Exception:
        return {"organized": 0, "error": "Failed to parse AI response", "raw": result}
