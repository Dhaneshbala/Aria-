"""Pytest configuration for organizer tests.

Sets ARIA_ORGANIZER_DB to a temp path BEFORE any service module is imported,
so tests never touch the real index. Imports of services.* happen lazily
inside fixtures/tests.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_TMP = Path(tempfile.mkdtemp(prefix="aria_orgtest_"))
os.environ["ARIA_ORGANIZER_DB"] = str(_TMP / "organizer_test.db")
os.environ["ARIA_ORGANIZER_TESTING"] = "1"
# Point all data (conversations, config, telemetry, logs, chroma) at the
# temp dir so tests never read or write the real ~/.aria_data.
os.environ["ARIA_DATA_DIR"] = str(_TMP / "aria_data")


def _select_embed_model():
    """Point ARIA_EMBED_MODEL at an installed embedding model.

    Canonical default is mxbai-embed-large (see start.sh). If this machine
    doesn't have it pulled (e.g. only nomic-embed-text), fall back so live-RAG
    tests exercise the real pipeline instead of failing on a missing model.
    Explicit user choice (env already set) always wins. No-op when Ollama is
    down — tests then fail/skip on their own terms.
    """
    if os.environ.get("ARIA_EMBED_MODEL"):
        return
    try:
        import json
        import urllib.request
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            names = [m.get("name", "") for m in json.load(r).get("models", [])]
        installed = {n.split(":")[0] for n in names}
        if "mxbai-embed-large" in installed:
            return  # canonical default already applies
        if "nomic-embed-text" in installed:
            os.environ["ARIA_EMBED_MODEL"] = "nomic-embed-text"
    except Exception:
        pass


_select_embed_model()

import pytest


@pytest.fixture(autouse=True)
def clean_db():
    """Wipe all tables before each test, return the Database instance.

    NOTE: File Organizer was removed — if services.organizer_db is gone,
    this fixture is a no-op so the remaining tests still run.
    """
    try:
        from services.organizer_db import get_db
    except ImportError:
        yield None
        return

    db = get_db()
    for table in ("files", "history", "rules", "profiles", "saved_searches",
                  "folders", "events", "settings", "feedback", "proposals"):
        db.query(f"DELETE FROM {table}")
    yield db


@pytest.fixture
def tmp_files(tmp_path):
    """Create a handful of sample files and return their paths."""
    files = {}
    for name, content in [
        ("algebra_hw.txt", "Solve for x: 2x + 5 = 13. Show working.\nHomework due Friday."),
        ("cells_notes.txt", "Plant cells have chloroplasts and a cell wall.\nAnimal cells do not."),
        ("python_code.py", "def fib(n):\n    return n if n < 2 else fib(n-1) + fib(n-2)\nprint(fib(10))"),
        ("invoice.pdf", ""),
        ("essay_english.docx", ""),
    ]:
        p = tmp_path / name
        p.write_text(content)
        files[name] = str(p)
    return files


# ── Mock LLM fixtures ──────────────────────────────────────────────────────

class MockOllamaStream:
    """Mock async generator that yields LLM tokens."""

    def __init__(self, tokens=None, system=None, prompt=None):
        self.tokens = tokens or ["Hello", " ", "world", "!"]
        self.system = system
        self.prompt = prompt

    async def __aiter__(self):
        for token in self.tokens:
            yield token


class MockOllamaService:
    """Mock OllamaService that returns canned responses."""

    def __init__(self):
        self._embed_dim = 1024

    async def health(self):
        return {"ok": True, "models": ["gemma4:e4b-mlx", "mxbai-embed-large"]}

    async def embed(self, model, text):
        return [0.1] * self._embed_dim

    async def stream(self, model, system, prompt, context_window=None):
        async for token in MockOllamaStream():
            yield token

    async def complete(self, model, prompt, context_window=None):
        return "Mock complete response"

    async def stream_chat(self, messages, model=None):
        async for token in MockOllamaStream():
            yield token

    async def list_models(self):
        return ["gemma4:e4b-mlx", "mxbai-embed-large"]

    async def pull_model(self, model_name):
        yield '{"status": " pulling manifest"}'
        yield '{"status": "complete"}'

    async def unload_model(self, model_name):
        pass


@pytest.fixture
def mock_ollama():
    """Provide a MockOllamaService instance."""
    return MockOllamaService()


@pytest.fixture
def mock_ollama_patch():
    """Patch OllamaService across all services for testing."""
    mock = MockOllamaService()
    with patch("services.ollama_service.OllamaService", return_value=mock):
        yield mock


@pytest.fixture
def mock_llm_stream():
    """Mock for LLM streaming responses."""
    return MockOllamaStream


@pytest.fixture
def mock_config():
    """Provide a test config dict."""
    return {
        "model": "gemma4:e4b-mlx",
        "reasoning_model": "gemma4:e4b-mlx",
        "vision_model": "gemma4:e4b-mlx",
        "embedding_model": "mxbai-embed-large",
        "doc_context_chars": 8000,
        "web_search_enabled": False,
        "knowledge_base_enabled": False,
        "memory_enabled": False,
        "voice_enabled": False,
        "image_gen_enabled": False,
        "telemetry_enabled": False,
    }
