"""AI provider abstraction — Ollama (local, default) + Anthropic (opt-in cloud).

Privacy-first routing rules
---------------------------
* Ollama is the only provider unless BOTH of these env vars are set:
    - ANTHROPIC_API_KEY        (the credential)
    - ARIA_CLOUD_CONSENT=1     (explicit consent that student messages go to
                                Anthropic — this cannot be implied)
* There is NO silent fallback to the cloud: if Ollama is down, requests fail
  with a clear message. Cloud consent must be deliberate.
* A model ID prefixed with `anthropic:` is an explicit per-request choice,
  e.g. `anthropic:claude-haiku-5-5` (verified ID, Claude docs 2026-10).
* Retries: non-streaming 5xx/429 get exactly one retry (1s backoff — bounded).
  Streaming starts get no retry (token already shown to the student).
* Usage: Anthropic reports exact input/output tokens in `usage`; those plus a
  configured-pricing estimate are written to the local usage ledger.

Verified endpoint/field contract (https://platform.claude.com/docs/en/api):
POST /v1/messages — headers x-api-key, anthropic-version: 2023-06-01;
body requires max_tokens; response content[].text, usage.input_tokens,
usage.output_tokens. Streaming = SSE lines, delta at
`type:"content_block_delta"` → delta.text; final `message_delta` carries
usage.output_tokens (set: include usage with `stream_usage` behaviour of the
messages API).
"""

import json
import logging
import time
from collections.abc import AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_BASE = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
_CLOUD_TIMEOUT = 120.0


class ProviderDisabledError(RuntimeError):
    """Raised when a cloud model is requested without consent/credential."""


def resolve_provider(model: str) -> tuple[str, str]:
    """("ollama"|"anthropic", model_id) from a possibly-prefixed model string.

    Unknown prefixes fall back to Ollama (the model list there is user-
    controlled), preserving today's behaviour for plain IDs.
    """
    if isinstance(model, str) and model.startswith("anthropic:"):
        return "anthropic", model.split(":", 1)[1].strip()
    return "ollama", model


def _cloud_enabled() -> bool:
    try:
        from config.settings import settings

        return bool(settings.anthropic_api_key) and bool(settings.aria_cloud_consent)
    except Exception:
        return False


class AnthropicProvider:
    """Server-side adapter for the Anthropic Messages API."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._base = (base_url or ANTHROPIC_BASE).rstrip("/")
        if api_key is not None:
            self._key = api_key
        else:
            from config.settings import settings

            self._key = settings.anthropic_api_key

    def _require_enabled(self):
        if not _cloud_enabled():
            raise ProviderDisabledError(
                "Cloud AI is disabled. ARIA runs fully offline by default. "
                "To use Anthropic models you must set ANTHROPIC_API_KEY and "
                "ARIA_CLOUD_CONSENT=1 — this sends student content to Anthropic."
            )

    def _headers(self) -> dict:
        return {
            "x-api-key": self._key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    def _body(
        self,
        model: str,
        system: str,
        message: str,
        max_tokens: int,
        stream: bool,
    ) -> dict:
        return {
            "model": model,
            # Require a positive cap — Anthropic rejects missing/zero
            "max_tokens": max(256, int(max_tokens or 2048)),
            "system": system or "You are a helpful assistant.",
            "messages": [{"role": "user", "content": message}],
            "stream": stream,
        }

    @staticmethod
    def _record(model: str, usage: dict, duration_ms: float, ok: bool = True) -> None:
        try:
            from services.usage_service import record_usage

            record_usage(
                provider="anthropic",
                model=model,
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                duration_ms=duration_ms,
                ok=ok,
            )
        except Exception as e:
            logger.debug("usage record (anthropic) failed: %s", e)

    async def complete(
        self,
        model: str,
        message: str,
        system: str = "You are a helpful assistant.",
        max_tokens: int = 2048,
        timeout: float | None = None,
    ) -> str:
        self._require_enabled()
        url = f"{self._base}/v1/messages"
        body = self._body(model, system, message, max_tokens, stream=False)
        started = time.monotonic()
        last_exc: Exception | None = None
        for attempt in range(2):  # one bounded retry on 429/5xx
            try:
                async with httpx.AsyncClient(
                    timeout=timeout or _CLOUD_TIMEOUT
                ) as client:
                    r = await client.post(url, json=body, headers=self._headers())
                if r.status_code in (429, 500, 502, 503) and attempt == 0:
                    logger.warning(
                        "Anthropic %s on %s — retrying once", r.status_code, model
                    )
                    import asyncio

                    await asyncio.sleep(1)
                    continue
                r.raise_for_status()
                data = r.json()
                usage = data.get("usage", {}) or {}
                self._record(model, usage, (time.monotonic() - started) * 1000)
                parts = [
                    b.get("text", "")
                    for b in data.get("content", [])
                    if b.get("type") == "text"
                ]
                return "".join(parts)
            except (httpx.HTTPError, ValueError) as e:
                last_exc = e
                self._record(model, {}, (time.monotonic() - started) * 1000, ok=False)
                break
        logger.error("Anthropic complete failed for %s: %s", model, last_exc)
        raise last_exc or RuntimeError("anthropic complete failed")

    async def stream(
        self,
        model: str,
        system: str,
        message: str,
        max_tokens: int = 2048,
        timeout: float | None = None,
    ) -> AsyncGenerator[str]:
        """Yield text deltas. No retry once streaming starts."""
        self._require_enabled()
        url = f"{self._base}/v1/messages"
        body = self._body(model, system, message, max_tokens, stream=True)
        started = time.monotonic()
        usage_in, usage_out = 0, 0
        try:
            async with (
                httpx.AsyncClient(timeout=timeout or _CLOUD_TIMEOUT) as client,
                client.stream("POST", url, json=body, headers=self._headers()) as resp,
            ):
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    try:
                        evt = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if evt.get("type") == "content_block_delta":
                        text = evt.get("delta", {}).get("text", "")
                        if text:
                            yield text
                    elif evt.get("type") == "message_start":
                        usage_in = (
                            evt.get("message", {})
                            .get("usage", {})
                            .get("input_tokens", 0)
                        )
                    elif evt.get("type") == "message_delta":
                        usage_out = evt.get("usage", {}).get("output_tokens", usage_out)
                    elif evt.get("type") == "error":
                        raise RuntimeError(
                            evt.get("error", {}).get(
                                "message", "anthropic stream error"
                            )
                        )
        except httpx.HTTPError as e:
            self._record(
                model,
                {"input_tokens": usage_in, "output_tokens": usage_out},
                (time.monotonic() - started) * 1000,
                ok=False,
            )
            logger.error("Anthropic stream failed for %s: %s", model, e)
            raise
        self._record(
            model,
            {"input_tokens": usage_in, "output_tokens": usage_out},
            (time.monotonic() - started) * 1000,
        )
