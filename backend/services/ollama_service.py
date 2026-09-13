"""
Ollama service — wraps all model calls.
M4 MacBook Air optimised: Metal GPU via num_gpu_layers=-1.
Local-only: all calls go directly to Ollama.
"""
import httpx
import json
import logging
import asyncio
import threading as _threading
import os
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
# Allow env like http://localhost:11434/api/generate — strip suffix to base
if OLLAMA_URL.endswith("/api/generate") or OLLAMA_URL.endswith("/api/chat"):
    OLLAMA_URL = OLLAMA_URL.rsplit("/api", 1)[0]

# ── 16 GB optimisation: single main model (gemma4:e4b-mlx) + nomic-embed-text  ──
# Avoid loading multiple large generation models at once. Keep context modest
# (8K default) to reduce KV-cache RAM; allow 16K only for large docs.
# gemma4 is multimodal — handles text, coding, vision, and tool calling.

M4_OPTIONS = {
    "num_gpu_layers": -1,
    "temperature": 0.7,
    "num_ctx": 8192,       # sensible default for normal conversations (8K)
    "num_keep": 48,
    "repeat_penalty": 1.1,
    "num_thread": 8,       # M4 10-core (4P+6E) → 8 threads optimal
    "num_batch": 512,      # M4 batch sweet spot
    "low_vram": False,
}

# Single source of truth — import from database (task requirement).
try:
    from models.database import MODELS
    # ensure required keys exist
    assert "main" in MODELS and "embedding" in MODELS
except Exception:
    MODELS = {
        "main": "gemma4:e4b-mlx",
        "embedding": "nomic-embed-text",
    }

TIMEOUT = 300.0

# ── Simple response cache (5-min TTL, persisted to disk) ─────────────────────
import time as _time
import json as _json
from pathlib import Path as _Path
_CACHE_FILE = _Path(__file__).parent.parent / "storage" / "cache.json"
_EMBED_CACHE_FILE = _Path(__file__).parent.parent / "storage" / "embed_cache.json"
_CACHE: dict = {}
_EMBED_CACHE: dict = {}
CACHE_TTL_SEC = 300

def _load_cache():
    global _CACHE, _EMBED_CACHE
    try:
        if _CACHE_FILE.exists():
            data = _json.loads(_CACHE_FILE.read_text())
            # only load non-expired entries — and never blank ones (a cold
            # model can return "" which must not poison future calls)
            now = _time.time()
            _CACHE = {k: tuple(v) for k,v in data.items() if now - v[1] < CACHE_TTL_SEC and str(v[0]).strip()}
    except Exception:
        pass
    try:
        if _EMBED_CACHE_FILE.exists():
            _EMBED_CACHE = _json.loads(_EMBED_CACHE_FILE.read_text())
    except Exception:
        pass

def _save_cache():
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(_json.dumps(_CACHE))
    except Exception:
        pass
    try:
        _EMBED_CACHE_FILE.write_text(_json.dumps(_EMBED_CACHE))
    except Exception:
        pass

_load_cache()

# Concurrency guard: Ollama serves one (or few) models at a time; firing N
# parallel calls at the same model queues them up and causes timeouts.
# A process-wide per-loop semaphore (shared across all OllamaService
# instances) keeps in-flight model calls bounded. Per-loop so tests using
# fresh event loops don't trip "bound to a different event loop".
MAX_CONCURRENT_CALLS = 2
_loop_semaphores: dict = {}
_semaphore_key_lock = _threading.Lock()


async def _acquire_slot() -> None:
    """Acquire a concurrency slot for the current event loop. Returns True if acquired, False if cancelled."""
    loop = asyncio.get_running_loop()
    key = id(loop)
    with _semaphore_key_lock:
        sem = _loop_semaphores.get(key)
        if sem is None:
            sem = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
            _loop_semaphores[key] = sem
    await sem.acquire()
    return True


async def _release_slot(acquired: bool = True) -> None:
    if not acquired:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # no loop (shutdown) — nothing to release
    sem = _loop_semaphores.get(id(loop))
    if sem is not None:
        try:
            sem.release()
        except ValueError:
            pass  # over-release guard


class OllamaService:

    def __init__(self):
        # No persistent client: every method opens its own short-lived
        # httpx.AsyncClient so nothing is left unclosed on reload.
        pass

    async def stream(self, model: str, system: str, message: str, context_window: int = 8192, timeout: float = TIMEOUT, think: Optional[bool] = False) -> AsyncGenerator[str, None]:
        options = {**M4_OPTIONS, "num_ctx": context_window}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": message},
            ],
            "stream": True,
            "options": options,
        }
        if think is not None:
            payload["think"] = think
        acquired = False
        try:
            await _acquire_slot()
            acquired = True
        except asyncio.CancelledError:
            return
        try:
            async with httpx.AsyncClient(timeout=timeout, base_url=OLLAMA_URL) as client:
                async with client.stream("POST", "/api/chat", json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            token = data.get("message", {}).get("content", "")
                            if token:
                                yield token
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        except httpx.HTTPStatusError as e:
            logger.error("Ollama stream error for model %s: %s", model, e)
            raise
        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama at %s", OLLAMA_URL)
            raise
        finally:
            await _release_slot(acquired)

    async def stream_chat(self, messages: list[dict], model: str, context_window: int = 8192, timeout: float = TIMEOUT, think: Optional[bool] = False) -> AsyncGenerator[str, None]:
        """Stream a chat completion for an explicit message list
        (system + user + optional earlier turns) — used by notebook chat."""
        options = {**M4_OPTIONS, "num_ctx": context_window}
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": options,
        }
        if think is not None:
            payload["think"] = think
        acquired = False
        try:
            await _acquire_slot()
            acquired = True
        except asyncio.CancelledError:
            return
        try:
            async with httpx.AsyncClient(timeout=timeout, base_url=OLLAMA_URL) as client:
                async with client.stream("POST", "/api/chat", json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            token = data.get("message", {}).get("content", "")
                            if token:
                                yield token
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        except httpx.HTTPStatusError as e:
            logger.error("Ollama stream_chat error for model %s: %s", model, e)
            raise
        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama at %s", OLLAMA_URL)
            raise
        finally:
            await _release_slot(acquired)

    async def complete(self, model: str, prompt: str, system: str = "You are a helpful assistant.", max_tokens: int = 2048, timeout: float = TIMEOUT, think: Optional[bool] = None, json_mode: bool = False, context_window: int = 8192) -> str:
        """Non-streaming completion — returns the full, uncut response.
        Uses /api/chat with stream=False so structured output (JSON, lists)
        is never truncated mid-token like the streaming path can be.
        think=False disables gemma-style reasoning (fast, structured tasks);
        json_mode=True constrains the model to emit valid JSON only;
        context_window raises num_ctx for prompts with large system messages
        (8192 default, 16384 max for large docs). No larger than needed."""
        # Check cache (5-min TTL, same params = same output) — hashlib stable across restarts
        import hashlib as _hashlib
        _key_raw = f"{system}\n{prompt}\n{max_tokens}\n{think}\n{json_mode}\n{context_window}"
        cache_key = f"complete:{model}:{_hashlib.sha256(_key_raw.encode()).hexdigest()[:16]}"
        cached = _CACHE.get(cache_key)
        if cached and (_time.time() - cached[1] < CACHE_TTL_SEC) and str(cached[0]).strip():
            logger.info("Cache hit for %s", model)
            return cached[0]

        options = {**M4_OPTIONS, "num_predict": max_tokens, "num_ctx": context_window}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": options,
        }
        if think is not None:
            payload["think"] = think
        if json_mode:
            payload["format"] = "json"
        acquired = False
        try:
            await _acquire_slot()
            acquired = True
        except asyncio.CancelledError:
            raise
        try:
            async with httpx.AsyncClient(timeout=timeout, base_url=OLLAMA_URL) as client:
                r = await client.post("/api/chat", json=payload)
                r.raise_for_status()
                resp = r.json().get("message", {}).get("content", "")
                # Never cache blank replies (cold-model "" etc.) — caching
                # them poisons the key for the full TTL (GH: flashcards 0-card bug)
                if str(resp).strip():
                    _CACHE[cache_key] = (resp, _time.time())
                    # LRU prune if too large
                    if len(_CACHE) > 200:
                        oldest = min(_CACHE, key=lambda k: _CACHE[k][1])
                        del _CACHE[oldest]
                    _save_cache()
                else:
                    logger.warning("Blank reply from %s — not caching", model)
                return resp
        except httpx.HTTPStatusError as e:
            logger.error("Ollama complete error for model %s: %s", model, e)
            raise
        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama at %s", OLLAMA_URL)
            raise
        finally:
            await _release_slot(acquired)

    async def chat_with_images(self, model: str, system: str, message: str, image_paths: list[str], max_tokens: int = 2048, timeout: float = TIMEOUT) -> str:
        """Send images (by file path) to a multimodal model and return the full response.
        Gemma4:e4b-mlx handles images directly; same model as text — no extra VRAM."""
        import base64
        from pathlib import Path

        images = []
        for path in image_paths:
            p = Path(path)
            if not p.exists():
                continue
            data = p.read_bytes()
            if len(data) > 15 * 1024 * 1024:
                continue
            images.append(base64.b64encode(data).decode())

        if not images:
            return "[No readable image]"

        options = {**M4_OPTIONS, "num_ctx": 8192}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": message, "images": images},
            ],
            "stream": False,
            "options": options,
        }
        acquired = False
        try:
            await _acquire_slot()
            acquired = True
        except asyncio.CancelledError:
            raise
        try:
            async with httpx.AsyncClient(timeout=timeout, base_url=OLLAMA_URL) as client:
                r = await client.post("/api/chat", json=payload)
                r.raise_for_status()
                return r.json().get("message", {}).get("content", "")
        except Exception as e:
            logger.error("Vision chat failed for model %s: %s", model, e)
            raise
        finally:
            await _release_slot(acquired)

    async def unload_model(self, model: str) -> bool:
        """Unload a model from RAM to free memory."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(f"{OLLAMA_URL}/api/generate", json={"model": model, "keep_alive": 0})
                if r.status_code == 200:
                    logger.info("Unloaded model: %s", model)
                    return True
        except Exception as e:
            logger.warning("Failed to unload model %s: %s", model, e)
        return False

    async def pull_model(self, model: str) -> AsyncGenerator[str, None]:
        """Stream model download progress."""
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                async with client.stream("POST", f"{OLLAMA_URL}/api/pull", json={"name": model}) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if line.strip():
                            try:
                                data = json.loads(line)
                                status = data.get("status", "")
                                yield f"data: {json.dumps(data)}\n\n"
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error("Failed to pull model %s: %s", model, e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    async def list_models(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(f"{OLLAMA_URL}/api/tags")
                if r.status_code == 200:
                    return [
                        {
                            "name": m["name"],
                            "size_gb": round(m.get("size", 0) / 1e9, 1),
                            "modified": m.get("modified_at", ""),
                        }
                        for m in r.json().get("models", [])
                    ]
        except Exception as e:
            logger.warning("Failed to list models: %s", e)
        return []

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{OLLAMA_URL}/api/tags")
                if r.status_code == 200:
                    models = [m["name"] for m in r.json().get("models", [])]
                    return {"ok": True, "models": models}
        except Exception as e:
            logger.warning("Ollama health check failed: %s", e)
        return {"ok": False, "models": []}

    async def model_info(self, model_name: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.post(f"{OLLAMA_URL}/api/show", json={"name": model_name})
                if r.status_code == 200:
                    return r.json()
        except Exception as e:
            logger.warning("Failed to get model info for %s: %s", model_name, e)
        return {}

    async def embed(self, model: str, text: str) -> list[float]:
        """Generate embedding vector for a single text.
        Tries modern /api/embed (with 'input') first, falls back to legacy /api/embeddings (with 'prompt').
        Handles :latest alias and 60s cold-start timeout. Uses hashlib for stable cache keys."""
        import hashlib
        ek = f"{model}:{hashlib.md5(text.encode()).hexdigest()}"
        if ek in _EMBED_CACHE:
            return _EMBED_CACHE[ek]
        # Candidates: with and without :latest
        cands = [model]
        if model and not model.endswith(":latest"):
            cands.append(f"{model}:latest")
        elif model and model.endswith(":latest"):
            cands.append(model.replace(":latest", ""))
        for mdl in cands:
            # Modern endpoint /api/embed — supports single string via 'input'
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    r = await client.post(f"{OLLAMA_URL}/api/embed", json={"model": mdl, "input": text})
                    if r.status_code == 200:
                        data = r.json()
                        if "embeddings" in data and data["embeddings"]:
                            emb = data["embeddings"][0]
                            if emb:
                                _EMBED_CACHE[ek] = emb
                                if len(_EMBED_CACHE) > 2000:
                                    _EMBED_CACHE.pop(next(iter(_EMBED_CACHE)))
                                _save_cache()
                                return emb
                        if "embedding" in data and data["embedding"]:
                            emb = data["embedding"]
                            _EMBED_CACHE[ek] = emb
                            if len(_EMBED_CACHE) > 2000:
                                _EMBED_CACHE.pop(next(iter(_EMBED_CACHE)))
                            _save_cache()
                            return emb
            except Exception as e:
                logger.debug("Embed via /api/embed failed for %s: %s", mdl, e)
                continue
            # Legacy fallback /api/embeddings with 'prompt'
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    r = await client.post(f"{OLLAMA_URL}/api/embeddings", json={"model": mdl, "prompt": text})
                    if r.status_code == 200:
                        emb = r.json().get("embedding", [])
                        if emb:
                            _EMBED_CACHE[ek] = emb
                            if len(_EMBED_CACHE) > 2000:
                                _EMBED_CACHE.pop(next(iter(_EMBED_CACHE)))
                            _save_cache()
                        return emb
            except Exception as e:
                logger.debug("Embedding failed for model %s via embeddings: %s", mdl, e)
                continue
        logger.warning("Embedding failed for all candidates %s", cands)
        return []

    async def embed_batch(self, model: str, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts efficiently.
        Tries batch /api/embed with 'input': [texts] in ONE call (fast, M4 friendly).
        Falls back to sequential embed() if batch fails."""
        if not texts:
            return []
        import hashlib
        # Check cache for all texts first
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []
        cached_embeddings: dict[int, list[float]] = {}
        for i, t in enumerate(texts):
            ek = f"{model}:{hashlib.md5(t.encode()).hexdigest()}"
            if ek in _EMBED_CACHE:
                cached_embeddings[i] = _EMBED_CACHE[ek]
            else:
                uncached_indices.append(i)
                uncached_texts.append(t)

        new_embeddings: list[list[float]] = []
        if uncached_texts:
            # Try batch endpoint — 90s for cold start, try :latest alias
            cands = [model]
            if model and not model.endswith(":latest"):
                cands.append(f"{model}:latest")
            elif model and model.endswith(":latest"):
                cands.append(model.replace(":latest", ""))
            batch_ok = False
            for mdl in cands:
                try:
                    async with httpx.AsyncClient(timeout=90) as client:
                        r = await client.post(f"{OLLAMA_URL}/api/embed", json={"model": mdl, "input": uncached_texts})
                        if r.status_code == 200:
                            data = r.json()
                            embs = data.get("embeddings") or []
                            if len(embs) == len(uncached_texts) and all(embs):
                                new_embeddings = embs
                                batch_ok = True
                                for txt, emb in zip(uncached_texts, embs):
                                    ek = f"{model}:{hashlib.md5(txt.encode()).hexdigest()}"
                                    _EMBED_CACHE[ek] = emb
                                if len(_EMBED_CACHE) > 2000:
                                    while len(_EMBED_CACHE) > 2000:
                                        _EMBED_CACHE.pop(next(iter(_EMBED_CACHE)))
                                _save_cache()
                                break
                except Exception as e:
                    logger.debug("Batch embed failed for %s, falling back: %s", mdl, e)
                    continue

            if not batch_ok:
                # Sequential fallback (respects original M4 throttling)
                new_embeddings = []
                for text in uncached_texts:
                    emb = await self.embed(model, text)
                    new_embeddings.append(emb)

        # Reassemble in original order
        result: list[list[float]] = [[] for _ in texts]
        for i, emb in cached_embeddings.items():
            result[i] = emb
        for idx, emb in zip(uncached_indices, new_embeddings):
            result[idx] = emb
        return result
