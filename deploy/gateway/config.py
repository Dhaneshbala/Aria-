"""Gateway configuration + verified price table.

Prices are USD per million tokens, verified against
https://platform.claude.com/docs/en/about-claude/pricing (2026-10) — the
same numbers as backend/config/pricing.py, duplicated here because the
gateway is a standalone deployable (keep them in sync; never scatter
prices through the code).

Cache multipliers verified against
https://platform.claude.com/docs/en/build-with-claude/prompt-caching
(2026-10-19): 5-minute cache writes bill at 1.25x base input (the 1-hour
TTL bills at 2x; this gateway never requests it), and reads bill at a
fraction of base input that varies by model — Claude Sonnet 5.5 and
Opus 5.5 read at 0.05x, Claude Fable 5.1 at 0.025x, other models at
0.1x.

Re-verify every figure before charging users: at least one source
describes Sonnet 5's $2/MTok input as introductory pricing. The caps in
here are safety rails, not bills.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Verified current Claude API IDs — base input / output / cache-read
# factor ($/MTok; factor is a fraction of base input).
MODEL_PRICES: dict[str, dict[str, float]] = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_read": 0.1},
    "claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_read": 0.05},
    "claude-opus-5-5": {"input": 4.0, "output": 20.0, "cache_read": 0.05},
    "claude-fable-5-1": {"input": 10.0, "output": 50.0, "cache_read": 0.025},
}
DEFAULT_CACHE_READ_FACTOR = 0.1  # models outside the table above
CACHE_WRITE_FACTOR = 1.25  # 5-minute TTL writes (1-hour not requested)


def estimate_cost(
    model: str,
    input_tokens: int,
    cache_creation_tokens: int,
    cache_read_tokens: int,
    output_tokens: int,
) -> float | None:
    """Cost in USD for one response, or None if the model is unknown.

    cache_creation tokens bill at the write premium, cache_read at the
    per-model read multiplier, everything else at base rates.
    """
    price = MODEL_PRICES.get(model)
    if price is None:
        return None
    input_price = price["input"]
    factor_read = price.get("cache_read", DEFAULT_CACHE_READ_FACTOR)
    billable = (
        input_tokens
        + cache_creation_tokens * CACHE_WRITE_FACTOR
        + cache_read_tokens * factor_read
    )
    return (
        billable / 1_000_000 * input_price + output_tokens / 1_000_000 * price["output"]
    )


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass
class GatewayConfig:
    admin_token: str | None = None  # gate for /admin/* (disabled if None)
    anthropic_api_key: str | None = None  # refused /v1/messages if None
    db_path: str = ""  # sqlite file; dirs are created by the store
    model_allowlist: list[str] = field(default_factory=lambda: ["claude-sonnet-5-5"])
    default_daily_cap_usd: float = 0.50
    default_monthly_cap_usd: float = 10.0
    max_tokens_limit: int = 8192  # clamp: bounds cap-overshoot in a burst
    anthropic_version: str = "2023-06-01"
    upstream_base_url: str = "https://api.anthropic.com"
    max_body_bytes: int = 2_000_000

    def __post_init__(self) -> None:
        self.max_tokens_limit = max(self.max_tokens_limit, 1)

    @classmethod
    def from_env(cls) -> GatewayConfig:
        raw_allow = os.environ.get("GATEWAY_MODEL_ALLOWLIST", "claude-sonnet-5-5")
        allowlist = [m.strip() for m in raw_allow.split(",") if m.strip()]
        db_path = os.environ.get("GATEWAY_DB_PATH") or str(
            Path.home() / ".aria_gateway" / "gateway.sqlite3"
        )
        return cls(
            admin_token=os.environ.get("GATEWAY_ADMIN_TOKEN"),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            db_path=db_path,
            model_allowlist=allowlist,
            default_daily_cap_usd=_env_float("GATEWAY_DEFAULT_DAILY_CAP_USD", 0.50),
            default_monthly_cap_usd=_env_float("GATEWAY_DEFAULT_MONTHLY_CAP_USD", 10.0),
            max_tokens_limit=int(os.environ.get("GATEWAY_MAX_TOKENS_LIMIT", "8192")),
            anthropic_version=os.environ.get("GATEWAY_ANTHROPIC_VERSION", "2023-06-01"),
            upstream_base_url=os.environ.get(
                "GATEWAY_UPSTREAM_BASE_URL", "https://api.anthropic.com"
            ),
        )
