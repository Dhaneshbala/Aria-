"""Opt-in anonymous telemetry for ARIA.

Records lightweight usage counters and crash events to a local JSONL file
(never leaves the machine). The user enables it in Admin → Privacy, and can
view or clear the data at any time.

Design decisions:
  • Off by default — strictly opt-in, clearly disclosed.
  • No user content — only event names, counts and error classes.
  • Bounded file (last 5000 lines) so it never grows unbounded.
  • Crash events are always captured locally so the "send logs" / support
    flow works even with telemetry disabled (nothing is shared).
"""
import json
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_EVENTS = 5000

_DATA_DIR = Path(os.environ.get("ARIA_DATA_DIR", Path.home() / ".aria_data"))
_DATA_DIR.mkdir(parents=True, exist_ok=True)
EVENTS_FILE = _DATA_DIR / "telemetry.jsonl"

_lock = threading.Lock()


def _enabled() -> bool:
    try:
        from models.database import get_config
        return bool(get_config().get("telemetry_enabled", False))
    except Exception:
        return False


def _append(event: dict) -> None:
    with _lock:
        try:
            lines = []
            if EVENTS_FILE.exists():
                lines = EVENTS_FILE.read_text().splitlines()[-MAX_EVENTS:]
            lines.append(json.dumps(event, ensure_ascii=False))
            EVENTS_FILE.write_text("\n".join(lines) + "\n")
        except Exception:
            pass


def record_event(name: str, **props) -> None:
    """Record an anonymous usage counter. No-op unless telemetry is on."""
    if not _enabled():
        return
    safe = {}
    for k, v in props.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            safe[k] = v
        else:
            safe[k] = type(v).__name__
    _append({
        "type": "event",
        "name": name[:80],
        "ts": time.time(),
        **safe,
    })


def record_crash(component: str, error: Exception | str) -> None:
    """Record a crash/error locally (always — supports the send-logs flow)."""
    msg = str(error) if isinstance(error, Exception) else str(error)
    _append({
        "type": "crash",
        "component": component[:60],
        "error": msg[:300],
        "error_class": type(error).__name__ if isinstance(error, Exception) else "str",
        "ts": time.time(),
    })


def get_events(limit: int = 500) -> list[dict]:
    if not EVENTS_FILE.exists():
        return []
    lines = EVENTS_FILE.read_text().splitlines()[-limit:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def summary() -> dict:
    events = get_events()
    crashes = [e for e in events if e.get("type") == "crash"]
    counts: dict = {}
    for e in events:
        if e.get("type") == "event":
            counts[e.get("name", "?")] = counts.get(e.get("name", "?"), 0) + 1
    return {
        "enabled": _enabled(),
        "total_events": len(events),
        "crash_count": len(crashes),
        "event_counts": counts,
    }


def clear() -> None:
    with _lock:
        try:
            if EVENTS_FILE.exists():
                EVENTS_FILE.unlink()
        except Exception:
            pass
