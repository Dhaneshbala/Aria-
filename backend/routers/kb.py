"""
Knowledge Base router — upload, search, manage documents for RAG.
"""
import os
import tempfile
from fastapi import APIRouter, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional
from services.knowledge_base_service import KnowledgeBaseService, COLLECTIONS
from services.ollama_service import OllamaService
from models.database import get_config, MODELS

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])
kb_svc = KnowledgeBaseService()
ollama = OllamaService()


@router.post("/upload")
async def upload_to_kb(
    file: UploadFile = File(...),
    collection: Optional[str] = Form(default=None),
):
    """Upload a document to the knowledge base. Auto-detects collection if not specified."""
    from fastapi import HTTPException
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 20 MB)")
    suffix = os.path.splitext(file.filename or "file")[1] or ".txt"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        result = await kb_svc.ingest_file(tmp_path, collection=collection)
        return result
    finally:
        os.unlink(tmp_path)


@router.post("/upload-multiple")
async def upload_multiple(
    files: list[UploadFile] = File(...),
    collection: Optional[str] = Form(default=None),
):
    """Upload multiple documents at once."""
    from fastapi import HTTPException
    if len(files) > 10:
        raise HTTPException(400, "Too many files (max 10)")
    results = []
    for file in files:
        data = await file.read()
        if not data:
            results.append({"status": "error", "error": "Empty file", "document": file.filename})
            continue
        if len(data) > 20 * 1024 * 1024:
            results.append({"status": "error", "error": "File too large (max 20 MB)", "document": file.filename})
            continue
        suffix = os.path.splitext(file.filename or "file")[1] or ".txt"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            result = await kb_svc.ingest_file(tmp_path, collection=collection)
            results.append(result)
        except Exception as e:
            results.append({"status": "error", "error": str(e), "document": file.filename})
        finally:
            os.unlink(tmp_path)
    return {"results": results, "total": len(results)}


@router.get("/search")
async def search_kb(
    q: str = Query(..., description="Search query"),
    collections: Optional[str] = Query(default=None, description="Comma-separated collection names"),
    n: int = Query(default=5, ge=1, le=20),
):
    """Semantic search across the knowledge base."""
    col_list = [c.strip() for c in collections.split(",")] if collections else None
    results = await kb_svc.search(q, collections=col_list, n_results=n)
    return {"query": q, "results": results, "count": len(results)}


@router.get("/documents")
async def list_documents(collection: Optional[str] = Query(default=None)):
    """List all ingested documents."""
    docs = kb_svc.list_documents(collection=collection)
    return {"documents": docs, "count": len(docs)}


@router.delete("/documents/{file_hash}")
async def delete_document(file_hash: str):
    """Delete a document and its chunks from the knowledge base."""
    ok = kb_svc.delete_document(file_hash)
    if ok:
        return {"status": "deleted", "file_hash": file_hash}
    return JSONResponse(status_code=404, content={"error": "Document not found"})


@router.get("/stats")
async def get_stats():
    """Get knowledge base statistics."""
    return kb_svc.get_stats()


@router.get("/collections")
async def list_collections():
    """List all available collections with their descriptions."""
    return {"collections": COLLECTIONS}


@router.post("/rebuild")
async def rebuild_index():
    """Rebuild all embeddings (e.g. after changing embedding model)."""
    result = await kb_svc.rebuild_index()
    return result


@router.post("/ask")
async def ask_kb(
    question: str = Form(..., min_length=1, max_length=8000),
    collections: Optional[str] = Form(default=None),
    n: int = Form(default=6, ge=1, le=20),
):
    """Multi-document RAG chat — search the whole library and stream an answer."""
    col_list = [c.strip() for c in collections.split(",")] if collections else None
    results = await kb_svc.search(question, collections=col_list, n_results=n)

    if not results:
        async def no_results():
            yield "data: I couldn't find anything in your document library about that.\n\n"
            yield "data: Try uploading documents first on this page.\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(no_results(), media_type="text/event-stream")

    context_parts = []
    for r in results:
        src = r.get("metadata", {}).get("source", r.get("collection", "unknown"))
        context_parts.append(f"[Source: {src}]\n{r['text'][:600]}")
    context = "\n\n".join(context_parts)

    config = get_config()
    model = config.get("model", config.get("reasoning_model", MODELS["main"]))
    system = (
        "You are ARIA, an AI study assistant. Answer the student's question using ONLY "
        "the document excerpts below. Quote the source document name for each fact "
        "(e.g. [Source: Science_Notes.pdf]). If the excerpts don't cover the question, say so.\n\n"
        f"DOCUMENTS:\n{context}"
    )

    async def generate():
        try:
            async for token in ollama.stream(model, system, question, context_window=8192):
                yield f"data: {token}\n\n"
        except Exception as e:
            yield f"data: ⚠️ AI unavailable: {e}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
