"""
Chat router — main SSE streaming endpoint.
Handles text + optional image + optional document.
For large documents, uses smart chunking to pass only relevant pages.
"""
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Optional, List
from services.orchestrator import orchestrate
from services.document_service import DocumentService
from services.memory_service import MemoryService
from models.database import get_config

router = APIRouter(prefix="/api/chat", tags=["chat"])
doc_svc = DocumentService()
mem_svc = MemoryService()

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    _chat_limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])
    _chat_limit = _chat_limiter.limit("30/minute")
except Exception:
    _chat_limiter = None
    _chat_limit = lambda f: f  # no-op

MAX_IMAGE_SIZE = 20 * 1024 * 1024   # 20 MB
MAX_DOC_SIZE = 50 * 1024 * 1024     # 50 MB


@router.post("")
@_chat_limit
async def chat(
    request:        Request,
    message:         str           = Form(...),
    conversation_id: str           = Form(default=""),
    image:           Optional[UploadFile] = File(default=None),
    document:        Optional[UploadFile] = File(default=None),
    documents:       Optional[List[UploadFile]] = File(default=None),
    mode:            str           = Form(default="normal"),
):
    # Input validation — prevent abuse / prompt injection via huge payloads
    if len(message) > 8000:
        raise HTTPException(400, "Message too long (max 8000 chars)")
    # Strip control chars except newline/tab
    message = "".join(c for c in message if c == "\n" or c == "\t" or ord(c) >= 32)
    if not message.strip():
        raise HTTPException(400, "Message cannot be empty")
    if mode not in ("normal", "think", "fast", "socratic", "hype"):
        mode = "normal"
    # Simple conversation_id sanitization (uuid or hex)
    if conversation_id and len(conversation_id) > 64:
        raise HTTPException(400, "Invalid conversation_id")
    if not conversation_id:
        conversation_id = str(uuid.uuid4())

    config = get_config()

    # ── Read image ────────────────────────────────────────────────────────────
    image_data = None
    image_mime = None
    if image:
        image_data = await image.read()
        if len(image_data) > MAX_IMAGE_SIZE:
            raise HTTPException(413, f"Image too large. Maximum size: {MAX_IMAGE_SIZE // (1024*1024)} MB")
        image_mime = image.content_type or "image/jpeg"

    # Normalize to list — supports 1 or up to 10 PDFs
    all_docs: List[UploadFile] = []
    if document:
        all_docs.append(document)
    if documents:
        # FastAPI may give single or list; ensure list
        if isinstance(documents, list):
            all_docs.extend(documents)
        else:
            all_docs.append(documents)
    # Deduplicate only when we are sure it is the same file sent twice.
    # UploadFile.size is None on Starlette, so (name, None) would wrongly
    # drop two different files with the same filename.
    seen = set()
    uniq_docs = []
    for d in all_docs:
        size = getattr(d, 'size', None)
        if size is None:
            uniq_docs.append(d)
            continue
        key = (d.filename, size)
        if key not in seen:
            seen.add(key)
            uniq_docs.append(d)
    all_docs = uniq_docs[:10]  # cap at 10

    from services.telemetry_service import record_event
    record_event("chat_message", mode=mode, has_image=image_data is not None,
                 has_doc=len(all_docs) > 0, doc_count=len(all_docs))

    # ── Read and smart-chunk documents (multiple PDFs) ────────────────────────
    doc_text = None
    if all_docs:
        # Split budget across docs so total stays within max_chars
        total_budget = config.get("doc_context_chars", 8000)
        # If many docs, give more budget but cap at 15000 to avoid context blowout
        if len(all_docs) > 1:
            total_budget = min(15000, total_budget + (len(all_docs)-1)*2000)
        per_doc_budget = max(1500, total_budget // len(all_docs))
        parts = []
        for doc_file in all_docs:
            doc_bytes = await doc_file.read()
            if len(doc_bytes) > MAX_DOC_SIZE:
                raise HTTPException(413, f"Document {doc_file.filename} too large. Maximum size: {MAX_DOC_SIZE // (1024*1024)} MB")
            filename = doc_file.filename or "document"
            ctx = await doc_svc.get_context_for_query(
                doc_bytes, filename, message,
                max_chars=per_doc_budget
            )
            parts.append(f"[File: {filename}]\n\n{ctx}")
        doc_text = "\n\n---\n\n".join(parts)

    # ── Stream via orchestrator — respects client Stop (AbortError) ─────────
    import asyncio
    import logging
    _log = logging.getLogger(__name__)

    async def event_stream():
        try:
            async for chunk in orchestrate(
                message=message,
                conversation_id=conversation_id,
                image_data=image_data,
                image_mime=image_mime,
                doc_text=doc_text,
                config=config,
                mode=mode,
            ):
                # If user pressed Stop (AbortError), client disconnects
                if await request.is_disconnected():
                    _log.info("Client disconnected (%s), aborting stream", conversation_id[:8])
                    break
                yield chunk
        except asyncio.CancelledError:
            _log.info("Stream cancelled for %s", conversation_id[:8])
            raise
        except Exception as e:
            # Don't leak internal errors as 500 — orchestrator already yields error chunks
            _log.debug("event_stream ended: %s", e)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Conversation-Id": conversation_id,
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations")
async def get_conversations():
    return await mem_svc.get_conversations()


@router.get("/search")
async def search_conversations(q: str = ""):
    if not q.strip():
        return []
    return await mem_svc.search_conversations(q)


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    return await mem_svc.get_conversation(conversation_id)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    await mem_svc.delete_conversation(conversation_id)
    return {"deleted": True}


@router.get("/conversations/date/{date}")
async def get_conversations_for_date(date: str):
    return await mem_svc.get_conversations_for_date(date)


@router.get("/conversations/{conversation_id}/title")
async def get_title(conversation_id: str):
    title = await mem_svc.get_title(conversation_id)
    if title is None:
        raise HTTPException(404, "Conversation not found")
    return {"id": conversation_id, "title": title}


@router.put("/conversations/{conversation_id}/title")
async def set_title(conversation_id: str, request: Request):
    try:
        body = await request.json()
        title = (body.get("title") or "").strip()
    except Exception:
        raise HTTPException(400, "Invalid body, expected {title}")
    if not title:
        raise HTTPException(400, "Title cannot be empty")
    if len(title) > 60:
        title = title[:60]
    # verify conversation exists
    conv = await mem_svc.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    new_title = await mem_svc.set_title(conversation_id, title)
    return {"id": conversation_id, "title": new_title}


@router.post("/conversations/{conversation_id}/regenerate-title")
async def regenerate_title(conversation_id: str):
    conv = await mem_svc.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    new_title = await mem_svc.regenerate_title(conversation_id, use_llm=True)
    if not new_title:
        raise HTTPException(500, "Failed to generate title")
    return {"id": conversation_id, "title": new_title}
