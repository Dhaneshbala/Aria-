"""Shared retry policy for flaky HTTP/AI calls.

Pattern: wrap only idempotent, transient-prone calls (metadata fetches,
polls). Do NOT blanket-retry model generation — that multiplies latency
and cost on every slow (not failed) call.
"""

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


#: 3 attempts, 1s → 2s → 4s backoff, transient network/5xx/429 only.
TRANSIENT_HTTP_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception(_is_transient),
    reraise=True,
)
