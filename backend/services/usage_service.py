"""Central AI usage accounting — one ledger for every model call.

Records provider-reported token counts (exact, never client-supplied) per
model per day: requests, prompt tokens, completion tokens, cache hits,
failures, wall time, and an estimated cost from config/*pricing* settings.

Design notes
------------
* Local-first: Ollama costs $0 — prices stay 0 unless a cloud provider is
  explicitly enabled (see services/ai_providers.py).
* Concurrency-safe: a threading.Lock guards read-modify-write; writes are
  atomic (tmp + os.replace), matching the pattern used by models/database.py.
* File shape: {"days": {"YYYY-MM-DD": {"providers": {"<provider>":
  {"<model>": {...fields...}}}}}, kept pruned to the last 90 days.
"""

import datetime as _dt
import json
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_LEDGER_NAME = "usage.json"
_MAX_DAYS = 90
_lock = threading.Lock()

try:
    from models.database import DATA_DIR

    LEDGER_PATH = DATA_DIR / _LEDGER_NAME
except Exception:  # pragma: no cover — tests set ARIA_DATA_DIR before import
    LEDGER_PATH = Path(os.environ.get("ARIA_DATA_DIR", "data")) / _LEDGER_NAME


def _empty_model_stats():
    return {
        "requests": 0,
        "failures": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cache_hits": 0,
        "duration_ms": 0.0,
        "estimated_cost_usd": 0.0,
        "cost_is_estimate": True,
    }


def _load():
    try:
        with open(LEDGER_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("days"), dict):
            return data
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.debug("usage ledger unreadable, starting fresh: %s", e)
    return {"days": {}}


def _atomic_write(data: dict):
    tmp = (
        LEDGER_PATH.with_suffix(".json.tmp")
        if LEDGER_PATH.suffix == ".json"
        else LEDGER_PATH / ".tmp"
    )
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, LEDGER_PATH)
    except Exception as e:
        logger.debug("usage ledger write failed: %s", e)


def _price_for(model_id: str, provider: str) -> tuple[float, float]:
    """(input, output) USD per MTok — one source of truth: config/pricing.py."""
    try:
        from config.pricing import price_for

        return price_for(provider, model_id)
    except Exception:
        return (0.0, 0.0)


def record_usage(
    provider: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    duration_ms: float = 0.0,
    ok: bool = True,
    cached: bool = False,
) -> None:
    """Record one model call. Tokens are provider-reported; estimates flagged."""
    if not model:
        return
    today = _dt.date.today().isoformat()
    with _lock:
        data = _load()
        days = data.setdefault("days", {})
        stats = (
            days.setdefault(today, {"providers": {}})
            .setdefault("providers", {})
            .setdefault(provider, {})
            .setdefault(model, _empty_model_stats())
        )
        stats["requests"] += 1
        if not ok:
            stats["failures"] += 1
        if cached:
            stats["cache_hits"] += 1
        # clamp negatives from misbehaving providers
        stats["prompt_tokens"] += max(0, int(prompt_tokens or 0))
        stats["completion_tokens"] += max(0, int(completion_tokens or 0))
        stats["duration_ms"] += max(0.0, float(duration_ms or 0.0))
        p_in, p_out = _price_for(model, provider)
        cost = (
            stats["prompt_tokens"] / 1_000_000 * p_in
            + stats["completion_tokens"] / 1_000_000 * p_out
        )
        stats["estimated_cost_usd"] = round(cost, 6)
        # prune beyond retention
        if len(days) > _MAX_DAYS:
            for old in sorted(days)[: len(days) - _MAX_DAYS]:
                days.pop(old, None)
        _atomic_write(data)


def get_summary(days: int = 30) -> dict:
    """Aggregated totals for the last N days, per provider/model and overall."""
    days = max(1, min(365, int(days or 30)))
    cutoff = (_dt.date.today() - _dt.timedelta(days=days - 1)).isoformat()
    with _lock:
        data = _load()
    out_days = {}
    totals = {
        "requests": 0,
        "failures": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cache_hits": 0,
        "duration_ms": 0.0,
        "estimated_cost_usd": 0.0,
        "cost_is_estimate": True,
    }
    for day, payload in sorted(data.get("days", {}).items()):
        if day < cutoff:
            continue
        providers = payload.get("providers") or {}
        out_days[day] = {
            "providers": {
                p: {m: dict(s) for m, s in ms.items()} for p, ms in providers.items()
            }
        }
        for models in providers.values():
            for s in models.values():
                for k in (
                    "requests",
                    "failures",
                    "prompt_tokens",
                    "completion_tokens",
                    "cache_hits",
                    "duration_ms",
                ):
                    totals[k] += s.get(k, 0)
                totals["estimated_cost_usd"] = round(
                    totals["estimated_cost_usd"] + s.get("estimated_cost_usd", 0), 6
                )
    return {
        "days": days,
        "range": {"from": cutoff, "to": _dt.date.today().isoformat()},
        "totals": totals,
        "by_day": out_days,
    }


def get_today() -> dict:
    today = _dt.date.today().isoformat()
    with _lock:
        data = _load()
    return data.get("days", {}).get(today, {"providers": {}})
