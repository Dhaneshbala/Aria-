"""
Cloud LLM provider layer — OpenAI-compatible APIs (Gemini, OpenRouter, Groq).
Used when a cloud_api_key is configured; falls back to Ollama otherwise.

Endpoints (all OpenAI /v1/chat/completions compatible):
  gemini     → https://generativelanguage.googleapis.com/v1beta/openai
  openrouter → https://openrouter.ai/api/v1
  groq       → https://api.groq.com/openai/v1
"""
import httpx
import json
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

PROVIDERS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.5-flash",
        "vision_model": "gemini-2.5-flash",
        "coding_model": "gemini-2.5-flash",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "deepseek/deepseek-chat",
        "vision_model": "google/gemini-2.5-flash",
        "coding_model": "deepseek/deepseek-chat",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "vision_model": "llama-3.3-70b-versatile",
        "coding_model": "llama-3.3-70b-versatile",
    },
}

_TIMEOUT = 300.0


class CloudLLM:

    def __init__(self, provider: str, api_key: str):
        self.provider = provider
        self.api_key = api_key
        info = PROVIDERS.get(provider, PROVIDERS["gemini"])
        self.base_url = info["base_url"]
        self.default_model = info["default_model"]
        self.vision_model = info["vision_model"]
        self.coding_model = info["coding_model"]

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _map_model(self, local_model: str, role: str = "reasoning") -> str:
        """Map an Ollama model name to the cloud model for this provider."""
        lower = (local_model or "").lower()
        if "vl" in lower or "vision" in lower or "llava" in lower:
            return self.vision_model
        if role == "coding" or "coder" in lower:
            return self.coding_model
        return self.default_model

    async def stream(
        self,
        local_model: str,
        system: str,
        message: str,
        role: str = "reasoning",
        max_tokens: int = 2048,
        timeout: float = _TIMEOUT,
    ) -> AsyncGenerator[str, None]:
        model = self._map_model(local_model, role)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": message},
            ],
            "stream": True,
            "max_tokens": max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self.headers,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        if line.startswith("data: "):
                            line = line[6:]
                        if line.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(line)
                            token = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if token:
                                yield token
                        except json.JSONDecodeError:
                            continue
        except httpx.HTTPStatusError as e:
            logger.error("Cloud %s stream error (%s): %s", self.provider, model, e)
            raise
        except httpx.ConnectError:
            logger.error("Cannot connect to cloud provider %s", self.provider)
            raise

    async def complete(
        self,
        local_model: str,
        prompt: str,
        system: str = "You are a helpful assistant.",
        role: str = "reasoning",
        max_tokens: int = 2048,
        timeout: float = _TIMEOUT,
    ) -> str:
        result = []
        async for token in self.stream(
            local_model, system, prompt, role=role, max_tokens=max_tokens, timeout=timeout
        ):
            result.append(token)
        return "".join(result)
