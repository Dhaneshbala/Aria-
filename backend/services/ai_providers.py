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


class CreditsExhaustedError(RuntimeError):
    """Raised in accounts mode when a wallet has no credit for a cloud call."""


def _cloud_precheck() -> None:
    """Budget + wallet gates, both enforced before any cloud dispatch.

    - Global daily cloud budget (admin-dashboard-controlled). Local
      Ollama is never capped — offline study always stays free.
    - Wallet (accounts mode only): the caller needs at least some
      credit. Deduction happens after the exact provider-reported usage
      is captured, so a short overshoot is bounded by max_tokens.
    """
    try:
        from services.budget_service import cloud_spending_allowed

        allowed, message = cloud_spending_allowed()
        if not allowed:
            raise ProviderDisabledError(message)
    except ProviderDisabledError:
        raise
    except Exception as e:  # budget subsystem failure must not soft-block
        logger.debug("budget check skipped: %s", e)
    try:
        from services import accounts, credits

        if accounts.accounts_enabled():
            from services.request_scope import current_username

            user = accounts.get_user_by_username(current_username())
            if user is None:
                raise ProviderDisabledError("Session user is not resolvable.")
            if user["role"] != "superadmin" and not credits.reserve_enough(user["id"]):
                raise CreditsExhaustedError(
                    "Your Cloud Boost wallet is empty. Local models remain "
                    "always free; an admin can grant credits."
                )
    except (CreditsExhaustedError, ProviderDisabledError):
        raise
    except Exception as e:
        logger.debug("wallet check skipped: %s", e)


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

        consent = bool(settings.aria_cloud_consent)
        gateway = _gateway_url() is not None
        direct = bool(settings.anthropic_api_key)
        return consent and (direct or gateway)
    except Exception:
        return False


def _gateway_url() -> str | None:
    """The Cloud Boost gateway base URL, or None for direct Anthropic
    traffic. The gateway holds the real API key; the backend only carries
    its own gw_ token — never an Anthropic credential."""
    try:
        from config.settings import settings

        url = (settings.aria_gateway_url or "").strip()
        return url.rstrip("/") if url else None
    except Exception:
        return None


class AnthropicProvider:
    """Server-side adapter for the Anthropic Messages API.

    Routes direct to Anthropic, or through the Cloud Boost gateway when
    ``ARIA_GATEWAY_URL`` is set (gateway auth is ``Authorization: Bearer
    gw_…``; direct auth stays ``x-api-key`` on the real credential).
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        from config.settings import settings

        gw_url = _gateway_url() if base_url is None else None
        if gw_url:
            self._base = gw_url
            self._key = settings.aria_gateway_token
            self._via_gateway = True
        else:
            self._base = (base_url or ANTHROPIC_BASE).rstrip("/")
            if api_key is not None:
                self._key = api_key
            else:
                self._key = settings.anthropic_api_key
            self._via_gateway = False

    def _require_enabled(self):
        if not _cloud_enabled():
            raise ProviderDisabledError(
                "Cloud AI is disabled. ARIA runs fully offline by default. "
                "To use Anthropic models set ANTHROPIC_API_KEY (or route via "
                "ARIA_GATEWAY_URL) and consent with ARIA_CLOUD_CONSENT=1 — "
                "this sends student content to Anthropic."
            )
        _cloud_precheck()

    def _headers(self) -> dict:
        if self._via_gateway:
            return {
                "Authorization": f"Bearer {self._key}",
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            }
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
            from services.request_scope import current_username
            from services.usage_service import record_usage

            record_usage(
                provider="anthropic",
                model=model,
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                duration_ms=duration_ms,
                ok=ok,
                user=current_username(),
            )
        except Exception as e:
            logger.debug("usage record (anthropic) failed: %s", e)
            return
        # Credit deduction — only for successful cloud calls, accounts
        # mode, non-superadmin. Base-price estimate (cache discounts
        # ignored → never undercharges). One ledger row per call.
        if not ok:
            return
        try:
            from config.pricing import price_for
            from services import accounts, credits
            from services.request_scope import current_username

            if not accounts.accounts_enabled():
                return
            user = accounts.get_user_by_username(current_username())
            if user is None or user["role"] == "superadmin":
                return
            p_in, p_out = price_for("anthropic", model)
            if p_in <= 0 and p_out <= 0:
                return
            cost = (
                max(0, int(usage.get("input_tokens", 0))) / 1_000_000 * p_in
                + max(0, int(usage.get("output_tokens", 0))) / 1_000_000 * p_out
            )
            micro = round(cost * 1_000_000)
            if micro > 0:
                credits.apply(
                    user["id"],
                    -micro,
                    "usage",
                    f"Cloud {model} ({usage.get('input_tokens', 0)}in/"
                    f"{usage.get('output_tokens', 0)}out tok)",
                )
        except Exception as e:
            logger.debug("credit deduction skipped: %s", e)

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
