"""Mistake book — every wrong answer, one drill queue.

Wrong quiz/maths answers auto-land here (no user action). Drilling an item
3 times in a row retires it. Cross-subject, persistent, tiny.
"""

import json
import logging
import re
import threading
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

MASTER_STREAK = 3

# Module-level lock: async chat/quiz paths can call record()/review()
# concurrently; without it the last-writer-wins race could drop mistakes.
_LOCK = threading.RLock()


def _data_file() -> Path:
    from services.scoping import store_path

    return store_path("mistakes.json")


def _norm(question: str) -> str:
    return re.sub(r"\s+", " ", (question or "").strip().lower())[:200]


def _load() -> dict:
    try:
        p = _data_file()
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.debug("Mistake load failed: %s", e)
    return {"items": []}


def _save(data: dict) -> None:
    try:
        p = _data_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        logger.debug("Mistake save failed: %s", e)


def record(
    question: str,
    correct_answer: str = "",
    given_answer: str = "",
    subject: str = "general",
    topic: str = "",
    source: str = "quiz",
) -> dict | None:
    """Record a wrong answer. Re-missing an open item bumps times_missed."""
    if not (question or "").strip():
        return None
    key = _norm(question)
    with _LOCK:
        data = _load()
        for item in data["items"]:
            if not item.get("mastered") and _norm(item.get("question", "")) == key:
                item["times_missed"] = int(item.get("times_missed", 1)) + 1
                item["last_missed"] = time.time()
                if given_answer:
                    item["given_answer"] = str(given_answer)[:300]
                _save(data)
                return item
        item = {
            "id": uuid.uuid4().hex[:12],
            "source": source,
            "subject": (subject or "general")[:40],
            "topic": (topic or "")[:80],
            "question": question.strip()[:1000],
            "correct_answer": str(correct_answer or "")[:500],
            "given_answer": str(given_answer or "")[:300],
            "times_missed": 1,
            "streak": 0,
            "reviews": 0,
            "mastered": False,
            "created_at": time.time(),
            "last_missed": time.time(),
        }
        data["items"].append(item)
        # Bound growth: keep last 500
        data["items"] = data["items"][-500:]
        _save(data)
        return item


def review(item_id: str, correct: bool) -> dict | None:
    """Grade one drill rep. 3-in-a-row retires the item."""
    with _LOCK:
        data = _load()
        for item in data["items"]:
            if item.get("id") == item_id and not item.get("mastered"):
                item["reviews"] = int(item.get("reviews", 0)) + 1
                if correct:
                    item["streak"] = int(item.get("streak", 0)) + 1
                    if item["streak"] >= MASTER_STREAK:
                        item["mastered"] = True
                else:
                    item["streak"] = 0
                    item["times_missed"] = int(item.get("times_missed", 1)) + 1
                    item["last_missed"] = time.time()
                _save(data)
                return item
    return None


def due(limit: int = 20) -> list[dict]:
    """Open items, least-streaked and oldest first (hardest, stalest)."""
    items = [i for i in _load()["items"] if not i.get("mastered")]
    items.sort(key=lambda i: (int(i.get("streak", 0)), float(i.get("last_missed", 0))))
    return items[: max(1, min(limit, 50))]


def stats() -> dict:
    items = _load()["items"]
    active = [i for i in items if not i.get("mastered")]
    by_subject: dict[str, int] = {}
    for i in active:
        by_subject[i.get("subject", "general")] = (
            by_subject.get(i.get("subject", "general"), 0) + 1
        )
    return {
        "total": len(items),
        "active": len(active),
        "mastered": len(items) - len(active),
        "by_subject": by_subject,
    }
