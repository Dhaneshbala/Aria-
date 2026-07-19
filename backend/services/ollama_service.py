"""
Ollama service — wraps all model calls.
M4 MacBook Air optimised: Metal GPU via num_gpu_layers=-1.
"""
import httpx
import json
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://127.0.0.1:11434"

M4_OPTIONS = {
    "num_gpu_layers": -1,
    "temperature": 0.7,
    "num_ctx": 4096,
    "num_keep": 48,
    "repeat_penalty": 1.1,
}

TIMEOUT = 300.0


class OllamaService:

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=TIMEOUT, base_url=OLLAMA_URL)
        self._pptx_client = httpx.AsyncClient(timeout=300, base_url=OLLAMA_URL)

    async def stream(self, model: str, system: str, message: str, context_window: int = 4096, timeout: float = TIMEOUT) -> AsyncGenerator[str, None]:
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

    async def complete(self, model: str, prompt: str, system: str = "You are a helpful assistant.", max_tokens: int = 2048, timeout: float = TIMEOUT) -> str:
        result = []
        async for token in self.stream(model, system, prompt, timeout=timeout):
            result.append(token)
            if sum(len(t) for t in result) > max_tokens * 4:
                break
        return "".join(result)

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
