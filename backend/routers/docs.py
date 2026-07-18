"""
Document router — PDF/DOCX/PPTX/XLSX reading, quote extraction, summarisation.
All endpoints accept file upload via multipart form.
"""
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from typing import Optional
from services.document_service import DocumentService
from services.ollama_service import OllamaService
from models.database import get_config

router = APIRouter(prefix="/api/docs", tags=["docs"])
doc_svc = DocumentService()
ollama  = OllamaService()


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document and return extracted text + metadata."""
    data = await file.read()
    pages = await doc_svc.extract_pages(data, file.filename or "file")
    full_text = "\n\n".join(f"[Page {p['page']}]\n{p['text']}" for p in pages)
    return {
        "filename": file.filename,
        "pages": len(pages),
        "characters": len(full_text),
        "words": len(full_text.split()),
        "preview": full_text[:600],
        "text": full_text,
    }


@router.post("/summarise")
async def summarise_document(
    file: UploadFile = File(...),
    style: str = Form(default="structured"),
    focus: Optional[str] = Form(default=None),
):
    """
    Summarise a document. Works on large PDFs by chunking.
    style: "structured" | "brief" | "detailed" | "key_points"
    focus: optional topic to focus the summary on
    """
    config = get_config()
    model  = config.get("reasoning_model", "qwen3:8b")
    data   = await file.read()
    pages  = await doc_svc.extract_pages(data, file.filename or "file")
    total_pages = len(pages)
    full_text   = "\n\n".join(f"[Page {p['page']}]\n{p['text']}" for p in pages)
    total_chars = len(full_text)

    style_instructions = {
        "structured": "Use clear headings, bullet points for key facts, and a one-paragraph overview at the top.",
        "brief":      "Write 3-5 sentences covering only the most important points. Be concise.",
        "detailed":   "Write a thorough summary covering all major sections, arguments, and examples.",
        "key_points": "List the 8-12 most important facts, arguments, or ideas as numbered bullet points.",
    }.get(style, "Use clear headings and bullet points.")

    focus_instruction = f"\nPay particular attention to content about: {focus}" if focus else ""

    async def stream_summary():
        # For short docs: summarise in one pass
        if total_chars <= 8000:
            prompt = (
                f"Summarise this document for a 13-year-old student.\n"
                f"Style: {style_instructions}{focus_instruction}\n\n"
                f"Document ({total_pages} pages):\n{full_text[:8000]}"
            )
            system = "You are a helpful study assistant. Summarise clearly and accurately."
            async for chunk in ollama.stream(model, system, prompt):
                yield f"data: {chunk}\n\n"

        else:
            # Large doc: summarise each chunk, then combine
            chunks = await doc_svc.smart_chunks(data, file.filename or "file", max_chars=4000)
            chunk_summaries = []

            yield f"data: 📄 Document has {total_pages} pages — summarising in {len(chunks)} sections...\n\n"

            for i, chunk in enumerate(chunks, 1):
                yield f"data: \n\n**Summarising pages {chunk['pages']}...**\n\n"
                chunk_sum = ""
                prompt = (
                    f"Summarise this section (pages {chunk['pages']}) of the document.\n"
                    f"Be thorough but concise. Focus on key facts and arguments.{focus_instruction}\n\n"
                    f"{chunk['text']}"
                )
                async for tok in ollama.stream(model, "Summarise accurately for a student.", prompt):
                    chunk_sum += tok
                    yield f"data: {tok}\n\n"
                chunk_summaries.append(f"[Pages {chunk['pages']}]\n{chunk_sum}")

            # Final synthesis
            yield f"data: \n\n---\n\n**Overall Summary**\n\n"
            combined = "\n\n".join(chunk_summaries)
            final_prompt = (
                f"You have just summarised a {total_pages}-page document section by section.\n"
                f"Now write a final cohesive summary for a 13-year-old student.\n"
                f"Style: {style_instructions}{focus_instruction}\n\n"
                f"Section summaries:\n{combined[:5000]}"
            )
            async for tok in ollama.stream(model, "Write a clear final summary.", final_prompt):
                yield f"data: {tok}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(stream_summary(), media_type="text/event-stream")


@router.post("/quotes")
async def extract_quotes(
    file: UploadFile = File(...),
    theme: str = Form(...),
    min_relevance: float = Form(default=0.2),
):
    """
    Extract quotes/passages from a document relevant to a theme.
    Example: theme = "diversity and acceptance"
    Returns ranked list of quotes with page numbers.
    """
    data   = await file.read()
    quotes = await doc_svc.extract_quotes(data, file.filename or "file", theme)
    filtered = [q for q in quotes if q["relevance"] >= min_relevance]

    return {
        "theme": theme,
        "filename": file.filename,
        "total_found": len(filtered),
        "quotes": filtered,
    }


@router.post("/ask")
async def ask_document(
    file: UploadFile = File(...),
    question: str = Form(...),
):
    """
    Ask any question about the document.
    Automatically retrieves the most relevant pages for the question.
    Streams the answer back.
    """
    config   = get_config()
    model    = config.get("reasoning_model", "qwen3:8b")
    data     = await file.read()
    filename = file.filename or "document"

    # Get relevant context for this specific question
    context = await doc_svc.get_context_for_query(data, filename, question)

    async def stream_answer():
        system = (
            f"You are a helpful study assistant for a 13-year-old student.\n"
            f"You have been given the content of '{filename}'.\n"
            f"Answer the student's question accurately and clearly based on the document.\n"
            f"Always cite page numbers when referencing specific content.\n"
            f"If the answer is not in the document, say so clearly."
        )
        prompt = f"Question: {question}\n\nDocument content:\n{context}"
        async for chunk in ollama.stream(model, system, prompt):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream_answer(), media_type="text/event-stream")


@router.post("/key-points")
async def extract_key_points(file: UploadFile = File(...)):
    """Extract the top 10 key points from a document."""
    config = get_config()
    model  = config.get("reasoning_model", "qwen3:8b")
    data   = await file.read()
    pages  = await doc_svc.extract_pages(data, file.filename or "file")
    full   = "\n\n".join(p["text"] for p in pages[:30])  # up to 30 pages

    prompt = (
        "Extract the 10 most important key points from this document.\n"
        "For each point, give: the key idea and the page number.\n"
        "Format: 1. [key point] (Page X)\n\n"
        f"{full[:6000]}"
    )
    text = await ollama.complete(model, prompt)
    return {"key_points": text, "pages": len(pages)}
