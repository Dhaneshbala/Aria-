"""
Model selection logic for ARIA.
───────────────────────────────
Extracted from orchestrator.py for maintainability.
Determines which model handles which role based on intents and config.
"""

import logging

logger = logging.getLogger(__name__)

# Single source of truth — import from database
try:
    from models.database import MODELS
except Exception:
    MODELS = {
        "main": "gemma4:e4b-mlx",
        "embedding": "mxbai-embed-large",
    }


def _main_model(config: dict) -> str:
    """Resolve the main generation model with legacy fallback."""
    return (
        config.get("model")
        or config.get("reasoning_model")
        or MODELS["main"]
    )


def choose_models(intents: list[str], config: dict) -> dict:
    """
    Return which model handles which role.

    16 GB optimisation: single generation model (gemma4:e4b-mlx) handles
    reasoning, coding, vision, and multimodal. No separate vision/coding
    models loaded — avoids RAM pressure. Easy to extend later if a
    specialist is proven necessary (e.g. add config['specialist_model']).
    """
    main = _main_model(config)
    models: dict = {}
    # Vision: gemma4 is multimodal, so same model handles images.
    # Keep a separate 'vision' key so the orchestrator can stream a
    # "Reading image..." status, but it points to the same model.
    if "image_analysis" in intents:
        # Use vision_model if user has set a specialist, else main
        vm = config.get("vision_model", main)
        # Migrate legacy qwen vl if present
        if vm in ("qwen2.5vl:3b", "qwen2.5vl:7b", "llava", "llava:13b"):
            vm = main
        models["vision"] = vm
    # Everything else → main model
    reasoning_intents = {
        "quiz", "exam_mode", "flashcard", "notes",
        "worksheet_solver", "worksheet_generator", "cheatsheet", "quote_extraction", "pdf_summarise",
        "math", "explain", "chat", "summary", "doc_chat",
        "web_search", "youtube", "video_summarise", "code", "coding",
        "essay_feedback", "formula", "timeline", "translate",
        "exam_sim", "audio_overview", "study_intel", "todo", "list_todos",
        "image_gen", "diagram",
    }
    if any(i in intents for i in reasoning_intents):
        models["reasoning"] = main
        models["fallback"] = main
    # If no reasoning intent matched but we have no models yet (e.g. unknown intent),
    # ensure we still have a reasoning model
    if not models:
        models["reasoning"] = main
        models["fallback"] = main
    return models
