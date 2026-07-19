"""
Chat router — main SSE streaming endpoint.
Handles text + optional image + optional document.
For large documents, uses smart chunking to pass only relevant pages.
"""
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
from services.orchestrator import orchestrate
from services.document_service import DocumentService
from services.memory_service import MemoryService
from models.database import get_config

router = APIRouter(prefix="/api/chat", tags=["chat"])
doc_svc = DocumentService()
mem_svc = MemoryService()

MAX_IMAGE_SIZE = 20 * 1024 * 1024   # 20 MB
MAX_DOC_SIZE = 50 * 1024 * 1024     # 50 MB


@router.post("")
async def chat(
    message:         str           = Form(...),
    conversation_id: str           = Form(default=""),
    image:           Optional[UploadFile] = File(default=None),
    document:        Optional[UploadFile] = File(default=None),
    mode:            str           = Form(default="normal"),
):
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

    # ── Read and smart-chunk document ─────────────────────────────────────────
    doc_text = None
    if document:
        doc_bytes = await document.read()
        if len(doc_bytes) > MAX_DOC_SIZE:
            raise HTTPException(413, f"Document too large. Maximum size: {MAX_DOC_SIZE // (1024*1024)} MB")
        filename  = document.filename or "document"

        # Get the most relevant sections of the document for THIS specific question
        # This means a 100-page PDF will still answer precisely about page 73 if needed
        doc_text = await doc_svc.get_context_for_query(
            doc_bytes, filename, message,
            max_chars=config.get("doc_context_chars", 8000)
        )

        # Prepend filename so the model knows what it's reading
        doc_text = f"[File: {filename}]\n\n{doc_text}"

    # ── Stream via orchestrator ───────────────────────────────────────────────
    async def event_stream():
        async for chunk in orchestrate(
            message=message,
            conversation_id=conversation_id,
            image_data=image_data,
            image_mime=image_mime,
            doc_text=doc_text,
            config=config,
            mode=mode,
        ):
            yield chunk

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
