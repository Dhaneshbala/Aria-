"""
Ollama service — wraps all model calls.
M4 MacBook Air optimised: Metal GPU via num_gpu_layers=-1.
Local-only: all calls go directly to Ollama.
"""

import asyncio
import json
import logging
import os
import threading as _threading
from collections.abc import AsyncGenerator

import httpx

logger = logging.getLogger(__name__)


def _record_usage(
    model, prompt_tokens=0, completion_tokens=0, duration_ms=0.0, ok=True, cached=False
):
    """Best-effort usage capture — a ledger failure must never break a chat."""
    try:
        from services.request_scope import current_username
        from services.usage_service import record_usage

        record_usage(
            provider="ollama",
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=duration_ms,
            ok=ok,
            cached=cached,
            user=current_username(),
        )
    except Exception as e:
        logger.debug("usage record failed: %s", e)


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
# Allow env like http://localhost:11434/api/generate — strip suffix to base
if OLLAMA_URL.endswith(("/api/generate", "/api/chat")):
    OLLAMA_URL = OLLAMA_URL.rsplit("/api", 1)[0]

# ── 16 GB optimisation: single main model (gemma3:12b) + nomic-embed-text  ──
# Avoid loading multiple large generation models at once. Keep context modest
# (8K default) to reduce KV-cache RAM; allow 16K only for large docs.
# gemma3 is multimodal — handles text, coding, vision, and tool calling.
#
# KEEP_ALIVE: how long a model stays in RAM after use. Shorter frees the
# ~8 GB sooner on pressured Macs (OLLAMA_KEEP_ALIVE=2m in tight setups);
# longer avoids reload waits. Per-request default, env-overridable.
KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "5m")

M4_OPTIONS = {
    "num_gpu_layers": -1,
    "temperature": 0.7,
    "num_ctx": 8192,  # sensible default for normal conversations (8K)
    "num_keep": 48,
    "repeat_penalty": 1.1,
    "num_thread": 8,  # M4 10-core (4P+6E) → 8 threads optimal
    "num_batch": 512,  # M4 batch sweet spot
    "low_vram": False,
}

# Single source of truth — import from database (task requirement).
try:
    from models.database import MODELS

    # ensure required keys exist
    assert "main" in MODELS and "embedding" in MODELS
except Exception:
    MODELS = {
        "main": "gemma3:12b",
        "embedding": "nomic-embed-text",
    }

# Cloud-vs-local routing (explicit `anthropic:` prefix only; see ai_providers.py)
try:
    from services.ai_providers import resolve_provider as _resolve_provider
except Exception:

    def _resolve_provider(model):
        return ("ollama", model)


TIMEOUT = 300.0

# ── Simple response cache (5-min TTL, persisted to disk) ─────────────────────
import json as _json
import time as _time
from pathlib import Path as _Path

try:
    from models.database import DATA_DIR as _DATA_DIR

    _CACHE_DIR = _Path(_DATA_DIR)
except Exception:
    import os as _os

    _CACHE_DIR = _Path(_os.environ.get("ARIA_DATA_DIR", _Path.home() / ".aria_data"))
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_CACHE_FILE = _CACHE_DIR / "cache.json"
_EMBED_CACHE_FILE = _CACHE_DIR / "embed_cache.json"
_CACHE: dict = {}
_EMBED_CACHE: dict = {}
CACHE_TTL_SEC = 300
_CACHE_LOCK = _threading.Lock()


def _atomic_write_json(path: _Path, data: dict):
    import os as _os
    import tempfile as _tf

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = _tf.mkstemp(dir=str(path.parent), prefix=f".{path.name}.tmp.")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            _json.dump(data, f)
            f.flush()
            _os.fsync(f.fileno())
        _Path(tmp_path).replace(path)
    finally:
        p = _Path(tmp_path)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass


def _ns() -> str:
    """Per-user cache namespace (stage 2): accounts never share cached
    completions or embeddings, local mode keeps the historic keys."""
    try:
        from services.scoping import scoped_user

        u = scoped_user()
        return f"u:{u}:" if u else ""
    except Exception:
        return ""


def _embed_key(model: str, text: str) -> str:
    """Stable, per-user-namespaced embed cache key."""
    import hashlib

    return (
        f"{_ns()}{model}:"
        f"{hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()}"
    )


def _load_cache():
    global _CACHE, _EMBED_CACHE
    with _CACHE_LOCK:
        try:
            if _CACHE_FILE.exists():
                data = _json.loads(_CACHE_FILE.read_text())
                # only load non-expired entries — and never blank ones (a cold
                # model can return "" which must not poison future calls)
                now = _time.time()
                _CACHE = {
                    k: tuple(v)
                    for k, v in data.items()
                    if now - v[1] < CACHE_TTL_SEC and str(v[0]).strip()
                }
        except Exception:
            pass
        try:
            if _EMBED_CACHE_FILE.exists():
                _EMBED_CACHE = _json.loads(_EMBED_CACHE_FILE.read_text())
        except Exception:
            pass


def _save_cache():
    with _CACHE_LOCK:
        try:
            _atomic_write_json(_CACHE_FILE, _CACHE)
        except Exception:
            pass
        try:
            _atomic_write_json(_EMBED_CACHE_FILE, _EMBED_CACHE)
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


_think_support: dict[str, bool] = {}


async def _model_supports_thinking(model: str) -> bool:
    """Cached /api/show capabilities probe for the `think` flag.

    gemma3-style models 400 on think=True ("does not support thinking").
    Fail-open (unknown => True) so a probe failure never breaks generation.
    """
    if model in _think_support:
        return _think_support[model]
    try:
        async with httpx.AsyncClient(timeout=10, base_url=OLLAMA_URL) as client:
            r = await client.post("/api/show", json={"name": model})
            caps = r.json().get("capabilities", []) if r.status_code == 200 else []
            ok = ("thinking" in caps) if caps else True
    except Exception:
        ok = True
    _think_support[model] = ok
    if not ok:
        logger.info("Model %s has no thinking capability — think flag dropped", model)
    return ok


class OllamaService:
    def __init__(self):
        # No persistent client: every method opens its own short-lived
        # httpx.AsyncClient so nothing is left unclosed on reload.
        pass

    async def stream(
        self,
        model: str,
        system: str,
        message: str,
        context_window: int = 8192,
        timeout: float = TIMEOUT,
        think: bool | None = False,
    ) -> AsyncGenerator[str]:
        options = {**M4_OPTIONS, "num_ctx": context_window}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": message},
            ],
            "stream": True,
            "options": options,
            "keep_alive": KEEP_ALIVE,
        }
        if think:
            # think=True 400s on non-thinking models — send only if supported
            if await _model_supports_thinking(model):
                payload["think"] = True
        elif think is not None:
            payload["think"] = think  # False is accepted by all models
        # Explicit cloud routing (`anthropic:` prefix) — opt-in via env only
        provider, cloud_model = _resolve_provider(model)
        if provider == "anthropic":
            from services.ai_providers import AnthropicProvider

            async for delta in AnthropicProvider().stream(
                cloud_model, system, message, max_tokens=2048
            ):
                yield delta
            return
        acquired = False
        try:
            await _acquire_slot()
            acquired = True
        except asyncio.CancelledError:
            return
        started = _time.monotonic() if _time else 0
        usage = {}
        try:
            async with (
                httpx.AsyncClient(timeout=timeout, base_url=OLLAMA_URL) as client,
                client.stream("POST", "/api/chat", json=payload) as resp,
            ):
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
                            usage = data
                            break
                    except json.JSONDecodeError:
                        continue
        except httpx.HTTPStatusError as e:
            logger.error("Ollama stream error for model %s: %s", model, e)
            _record_usage(
                model,
                duration_ms=(_time.monotonic() - started) * 1000
                if started and _time
                else 0,
                ok=False,
            )
            raise
        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama at %s", OLLAMA_URL)
            _record_usage(
                model,
                duration_ms=(_time.monotonic() - started) * 1000
                if started and _time
                else 0,
                ok=False,
            )
            raise
        finally:
            await _release_slot(acquired)
        # final `done` frame carries provider-reported exact token counts
        _record_usage(
            model,
            prompt_tokens=usage.get("prompt_eval_count", 0),
            completion_tokens=usage.get("eval_count", 0),
            duration_ms=(_time.monotonic() - started) * 1000
            if started and _time
            else 0,
        )

    async def stream_chat(
        self,
        messages: list[dict],
        model: str,
        context_window: int = 8192,
        timeout: float = TIMEOUT,
        think: bool | None = False,
    ) -> AsyncGenerator[str]:
        """Stream a chat completion for an explicit message list
        (system + user + optional earlier turns) — used by notebook chat."""
        options = {**M4_OPTIONS, "num_ctx": context_window}
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": options,
            "keep_alive": KEEP_ALIVE,
        }
        if think:
            # think=True 400s on non-thinking models — send only if supported
            if await _model_supports_thinking(model):
                payload["think"] = True
        elif think is not None:
            payload["think"] = think  # False is accepted by all models
        acquired = False
        try:
            await _acquire_slot()
            acquired = True
        except asyncio.CancelledError:
            return
        started = _time.monotonic() if _time else 0
        usage = {}
        try:
            async with (
                httpx.AsyncClient(timeout=timeout, base_url=OLLAMA_URL) as client,
                client.stream("POST", "/api/chat", json=payload) as resp,
            ):
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
                            usage = data
                            break
                    except json.JSONDecodeError:
                        continue
        except httpx.HTTPStatusError as e:
            logger.error("Ollama stream_chat error for model %s: %s", model, e)
            _record_usage(
                model,
                duration_ms=(_time.monotonic() - started) * 1000
                if started and _time
                else 0,
                ok=False,
            )
            raise
        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama at %s", OLLAMA_URL)
            _record_usage(
                model,
                duration_ms=(_time.monotonic() - started) * 1000
                if started and _time
                else 0,
                ok=False,
            )
            raise
        finally:
            await _release_slot(acquired)
        _record_usage(
            model,
            prompt_tokens=usage.get("prompt_eval_count", 0),
            completion_tokens=usage.get("eval_count", 0),
            duration_ms=(_time.monotonic() - started) * 1000
            if started and _time
            else 0,
        )

    async def complete(
        self,
        model: str,
        prompt: str,
        system: str = "You are a helpful assistant.",
        max_tokens: int = 2048,
        timeout: float = TIMEOUT,
        think: bool | None = None,
        json_mode: bool = False,
        context_window: int = 8192,
    ) -> str:
        """Non-streaming completion — returns the full, uncut response.
        Uses /api/chat with stream=False so structured output (JSON, lists)
        is never truncated mid-token like the streaming path can be.
        think=False disables gemma-style reasoning (fast, structured tasks);
        json_mode=True constrains the model to emit valid JSON only;
        context_window raises num_ctx for prompts with large system messages
        (8192 default, 16384 max for large docs). No larger than needed."""
        # Check cache (5-min TTL, same params = same output) — hashlib stable across restarts
        import hashlib as _hashlib

        _key_raw = (
            f"{system}\n{prompt}\n{max_tokens}\n{think}\n{json_mode}\n{context_window}"
        )
        cache_key = (
            f"complete:{_ns()}{model}:"
            f"{_hashlib.sha256(_key_raw.encode()).hexdigest()[:16]}"
        )
        cached = _CACHE.get(cache_key)
        if (
            cached
            and (_time.time() - cached[1] < CACHE_TTL_SEC)
            and str(cached[0]).strip()
        ):
            logger.info("Cache hit for %s", model)
            _record_usage(model, cached=True, duration_ms=0)
            return cached[0]

        # Provider routing: `anthropic:<id>` goes to Anthropic (opt-in cloud);
        # every plain Ollama ID is unchanged. No silent cloud fallback exists.
        provider, cloud_model = _resolve_provider(model)
        if provider == "anthropic":
            from services.ai_providers import AnthropicProvider

            return await AnthropicProvider().complete(
                cloud_model,
                prompt,
                system=system,
                max_tokens=max_tokens,
                timeout=min(timeout, 120.0),
            )

        options = {**M4_OPTIONS, "num_predict": max_tokens, "num_ctx": context_window}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": options,
            "keep_alive": KEEP_ALIVE,
        }
        if think:
            # think=True 400s on non-thinking models — send only if supported
            if await _model_supports_thinking(model):
                payload["think"] = True
        elif think is not None:
            payload["think"] = think  # False is accepted by all models
        if json_mode:
            payload["format"] = "json"
        acquired = False
        await _acquire_slot()
        acquired = True
        started = _time.monotonic() if _time else 0
        try:
            async with httpx.AsyncClient(
                timeout=timeout, base_url=OLLAMA_URL
            ) as client:
                r = await client.post("/api/chat", json=payload)
                r.raise_for_status()
                body = r.json()
                resp = body.get("message", {}).get("content", "")
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
                _record_usage(
                    model,
                    prompt_tokens=body.get("prompt_eval_count", 0),
                    completion_tokens=body.get("eval_count", 0),
                    duration_ms=(_time.monotonic() - started) * 1000 if _time else 0,
                    cached=False,
                )
                return resp
        except httpx.HTTPStatusError as e:
            logger.error("Ollama complete error for model %s: %s", model, e)
            _record_usage(
                model,
                duration_ms=(_time.monotonic() - started) * 1000 if _time else 0,
                ok=False,
            )
            raise
        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama at %s", OLLAMA_URL)
            _record_usage(
                model,
                duration_ms=(_time.monotonic() - started) * 1000 if _time else 0,
                ok=False,
            )
            raise
        finally:
            await _release_slot(acquired)

    async def chat_with_images(
        self,
        model: str,
        system: str,
        message: str,
        image_paths: list[str],
        max_tokens: int = 2048,
        timeout: float = TIMEOUT,
    ) -> str:
        """Send images (by file path) to a multimodal model and return the full response.
        Gemma4:12b-mlx handles images directly; same model as text — no extra VRAM."""
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
            "keep_alive": KEEP_ALIVE,
        }
        acquired = False
        await _acquire_slot()
        acquired = True
        started = _time.monotonic() if _time else 0
        try:
            async with httpx.AsyncClient(
                timeout=timeout, base_url=OLLAMA_URL
            ) as client:
                r = await client.post("/api/chat", json=payload)
                r.raise_for_status()
                body = r.json()
                _record_usage(
                    model,
                    prompt_tokens=body.get("prompt_eval_count", 0),
                    completion_tokens=body.get("eval_count", 0),
                    duration_ms=(_time.monotonic() - started) * 1000 if _time else 0,
                )
                return body.get("message", {}).get("content", "")
        except Exception as e:
            logger.error("Vision chat failed for model %s: %s", model, e)
            _record_usage(
                model,
                duration_ms=(_time.monotonic() - started) * 1000 if _time else 0,
                ok=False,
            )
            raise
        finally:
            await _release_slot(acquired)

    async def unload_model(self, model: str) -> bool:
        """Unload a model from RAM to free memory."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{OLLAMA_URL}/api/generate", json={"model": model, "keep_alive": 0}
                )
                if r.status_code == 200:
                    logger.info("Unloaded model: %s", model)
                    return True
        except Exception as e:
            logger.warning("Failed to unload model %s: %s", model, e)
        return False

    async def pull_model(self, model: str) -> AsyncGenerator[str]:
        """Stream model download progress."""
        try:
            async with (
                httpx.AsyncClient(timeout=600) as client,
                client.stream(
                    "POST", f"{OLLAMA_URL}/api/pull", json={"name": model}
                ) as resp,
            ):
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
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
                r = await client.post(
                    f"{OLLAMA_URL}/api/show", json={"name": model_name}
                )
                if r.status_code == 200:
                    return r.json()
        except Exception as e:
            logger.warning("Failed to get model info for %s: %s", model_name, e)
        return {}

    async def embed(self, model: str, text: str) -> list[float]:
        """Generate embedding vector for a single text.
        Tries modern /api/embed (with 'input') first, falls back to legacy /api/embeddings (with 'prompt').
        Handles :latest alias and 60s cold-start timeout. Uses hashlib for stable cache keys."""

        ek = _embed_key(model, text)
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
                    r = await client.post(
                        f"{OLLAMA_URL}/api/embed", json={"model": mdl, "input": text}
                    )
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("embeddings"):
                            emb = data["embeddings"][0]
                            if emb:
                                _EMBED_CACHE[ek] = emb
                                if len(_EMBED_CACHE) > 2000:
                                    _EMBED_CACHE.pop(next(iter(_EMBED_CACHE)))
                                _save_cache()
                                return emb
                        if data.get("embedding"):
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
                    r = await client.post(
                        f"{OLLAMA_URL}/api/embeddings",
                        json={"model": mdl, "prompt": text},
                    )
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

        # Check cache for all texts first
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []
        cached_embeddings: dict[int, list[float]] = {}
        for i, t in enumerate(texts):
            ek = _embed_key(model, t)
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
                        r = await client.post(
                            f"{OLLAMA_URL}/api/embed",
                            json={"model": mdl, "input": uncached_texts},
                        )
                        if r.status_code == 200:
                            data = r.json()
                            embs = data.get("embeddings") or []
                            if len(embs) == len(uncached_texts) and all(embs):
                                new_embeddings = embs
                                batch_ok = True
                                for txt, emb in zip(uncached_texts, embs):
                                    ek = _embed_key(model, txt)
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
