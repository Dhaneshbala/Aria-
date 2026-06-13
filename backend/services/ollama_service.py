"""
Ollama service — wraps all model calls.

M4 MacBook Air optimisations:
  - Uses Metal GPU acceleration automatically via Ollama on Apple Silicon
  - num_gpu_layers=-1 means "use all layers on GPU" (Metal)
  - num_ctx=4096 balanced for 16GB unified RAM
  - Keeps model loaded for 5 minutes between requests (num_keep)
  - Vision model is loaded separately only when an image is present
"""
import httpx
import json
from typing import AsyncGenerator

OLLAMA_URL = "http://127.0.0.1:11434"

# Options tuned for M4 MacBook Air 16GB
M4_OPTIONS = {
    "num_gpu_layers": -1,      # All layers on Metal GPU (Apple Silicon)
    "temperature": 0.7,
    "num_ctx": 4096,           # Context window — balanced for 16GB
    "num_keep": 48,            # Keep this many tokens in KV cache
    "repeat_penalty": 1.1,
}

TIMEOUT = 120.0


class OllamaService:

    async def stream(
        self, model: str, system: str, message: str,
        context_window: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from Ollama with M4 Metal acceleration."""
        options = {**M4_OPTIONS, "num_ctx": context_window}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": message},
            ],
            "stream": True,
            "options": options,
        }
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data  = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue

    async def complete(self, model: str, prompt: str, max_tokens: int = 2048) -> str:
        """Non-streaming completion."""
        result = []
        async for token in self.stream(model, "You are a helpful assistant.", prompt):
            result.append(token)
            if sum(len(t) for t in result) > max_tokens * 4:
                break
        return "".join(result)

    async def list_models(self) -> list[dict]:
        """Return installed models with size info."""
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(f"{OLLAMA_URL}/api/tags")
                if r.status_code == 200:
                    models = r.json().get("models", [])
                    return [
                        {
                            "name": m["name"],
                            "size_gb": round(m.get("size", 0) / 1e9, 1),
                            "modified": m.get("modified_at", ""),
                        }
                        for m in models
                    ]
        except Exception:
            pass
        return []

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=4) as client:
                r = await client.get(f"{OLLAMA_URL}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def model_info(self, model_name: str) -> dict:
        """Get details about a specific model."""
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.post(f"{OLLAMA_URL}/api/show", json={"name": model_name})
                if r.status_code == 200:
                    return r.json()
        except Exception:
            pass
        return {}
