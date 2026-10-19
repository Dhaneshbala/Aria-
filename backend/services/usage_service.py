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
    user: str | None = None,
) -> None:
    """Record one model call. Tokens are provider-reported; estimates flagged.

    ``user`` adds attribution on a parallel ``users`` axis (additive —
    existing readers ignore it). Local mode attributes to 'local-owner'.
    """
    if not model:
        return
    today = _dt.date.today().isoformat()
    user = user or _scoped_user()
    with _lock:
        data = _load()
        days = data.setdefault("days", {})
        day = days.setdefault(today, {"providers": {}})
        stats = (
            day.setdefault("providers", {})
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
        if user:
            ustats = (
                day.setdefault("users", {})
                .setdefault(user, {})
                .setdefault(provider, {})
                .setdefault(model, _empty_model_stats())
            )
            ustats["requests"] += 1
            if not ok:
                ustats["failures"] += 1
            ustats["prompt_tokens"] += max(0, int(prompt_tokens or 0))
            ustats["completion_tokens"] += max(0, int(completion_tokens or 0))
            ucost = (
                ustats["prompt_tokens"] / 1_000_000 * p_in
                + ustats["completion_tokens"] / 1_000_000 * p_out
            )
            ustats["estimated_cost_usd"] = round(ucost, 6)
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
        # users axis passes through unmodified (additive attribution)
        users_axis = payload.get("users") or {}
        if users_axis:
            out_days[day]["users"] = users_axis
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


def user_summary(username: str, days: int = 30) -> dict:
    """Per-usage summary from the users axis — what a signed-in student
    sees as their OWN usage (accounts mode). Empty when nothing recorded."""
    summary = get_summary(days=days)
    totals = {
        "requests": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "estimated_cost_usd": 0.0,
        "cost_is_estimate": True,
    }
    by_day: dict[str, dict] = {}
    for day, payload in sorted(summary.get("by_day", {}).items()):
        mine = (payload.get("users") or {}).get(username) or {}
        if not mine:
            continue
        for models in mine.values():
            for s in models.values():
                totals["requests"] += s.get("requests", 0)
                totals["prompt_tokens"] += s.get("prompt_tokens", 0)
                totals["completion_tokens"] += s.get("completion_tokens", 0)
                totals["estimated_cost_usd"] = round(
                    totals["estimated_cost_usd"] + s.get("estimated_cost_usd", 0),
                    6,
                )
        by_day[day] = {"providers": mine}
    return {
        "days": days,
        "user": username,
        "totals": totals,
        "by_day": by_day,
    }


def _scoped_user() -> str | None:
    """Attribution helper: the request-scoped username, if any."""
    try:
        from services.request_scope import current_username

        return current_username()
    except Exception:
        return None


def admin_totals(days: int = 30) -> dict:
    """Admin overview totals: requests, tokens, estimated cost, and a
    per-provider split (estimated — config prices, not bills)."""
    summary = get_summary(days=days)
    totals = summary.get("totals", {})
    by_provider = {}
    for payload in summary.get("by_day", {}).values():
        for provider, models in (payload.get("providers") or {}).items():
            agg = by_provider.setdefault(
                provider,
                {
                    "requests": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "estimated_cost_usd": 0.0,
                },
            )
            for s in models.values():
                agg["requests"] += s.get("requests", 0)
                agg["prompt_tokens"] += s.get("prompt_tokens", 0)
                agg["completion_tokens"] += s.get("completion_tokens", 0)
                agg["estimated_cost_usd"] = round(
                    agg["estimated_cost_usd"] + s.get("estimated_cost_usd", 0), 6
                )
    return {
        "requests": totals.get("requests", 0),
        "prompt_tokens": totals.get("prompt_tokens", 0),
        "completion_tokens": totals.get("completion_tokens", 0),
        "estimated_cost_usd": totals.get("estimated_cost_usd", 0.0),
        "cost_is_estimate": True,
        "days": days,
        "by_provider": by_provider,
    }


def cost_by_user(days: int = 30) -> dict[str, dict]:
    """Per-username AI usage/cost over the window (users axis only)."""
    summary = get_summary(days=days)
    out: dict[str, dict] = {}
    for payload in summary.get("by_day", {}).values():
        for username, providers in (payload.get("users") or {}).items():
            agg = out.setdefault(
                username, {"requests": 0, "cost_usd": 0.0, "tokens": 0}
            )
            for models in providers.values():
                for s in models.values():
                    agg["requests"] += s.get("requests", 0)
                    agg["tokens"] += s.get("prompt_tokens", 0) + s.get(
                        "completion_tokens", 0
                    )
                    agg["cost_usd"] = round(
                        agg["cost_usd"] + s.get("estimated_cost_usd", 0), 6
                    )
    return out


def cloud_spend(day: str) -> float:
    """Estimated non-Ollama spend for one ISO day (drives the budget)."""
    with _lock:
        data = _load()
    total = 0.0
    payload = (data.get("days", {}) or {}).get(day) or {}
    for provider, models in (payload.get("providers") or {}).items():
        if provider in ("ollama", "local"):
            continue
        for s in models.values():
            total += s.get("estimated_cost_usd", 0.0)
    return round(total, 6)
