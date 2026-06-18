"""
Ollama service — wraps all model calls.
M4 MacBook Air optimised: Metal GPU via num_gpu_layers=-1.
"""
import httpx
import json
from typing import AsyncGenerator

OLLAMA_URL = "http://127.0.0.1:11434"

M4_OPTIONS = {
    "num_gpu_layers": -1,
    "temperature": 0.7,
    "num_ctx": 4096,
    "num_keep": 48,
    "repeat_penalty": 1.1,
}

TIMEOUT = 120.0


class OllamaService:

    async def stream(self, model: str, system: str, message: str, context_window: int = 4096) -> AsyncGenerator[str, None]:
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
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as resp:
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

    async def complete(self, model: str, prompt: str, max_tokens: int = 2048) -> str:
        result = []
        async for token in self.stream(model, "You are a helpful assistant.", prompt):
            result.append(token)
            if sum(len(t) for t in result) > max_tokens * 4:
                break
        return "".join(result)

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
        except Exception:
            pass
        return []

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{OLLAMA_URL}/api/tags")
                if r.status_code == 200:
                    models = [m["name"] for m in r.json().get("models", [])]
                    return {"ok": True, "models": models}
        except Exception:
            pass
        return {"ok": False, "models": []}

    async def model_info(self, model_name: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.post(f"{OLLAMA_URL}/api/show", json={"name": model_name})
                if r.status_code == 200:
                    return r.json()
        except Exception:
            pass
        return {}