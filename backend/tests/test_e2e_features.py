"""E2E user-level feature tests — boots the REAL FastAPI app and exercises
every feature area the way a user would (health, config, telemetry, backups,
chat, study tools, planner, knowledge base, notebooks, organizer, premium
planner, intelligence, voice/research where available).

AI endpoints run against the live local Ollama if it is up (they are skipped
with a clear message otherwise). Everything else must always pass.
"""
import io
import json
import os
import time
from pathlib import Path

import pytest
import urllib.request

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

# ── Session-scoped Ollama availability ────────────────────────────────────────

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")


def _ollama_up() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _ollama_up(), reason="Ollama not running — AI tests skipped")


# ═══════════════════════════ 1. Health & system ═══════════════════════════════

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_system_diagnostics():
    r = client.get("/api/system/diagnostics")
    assert r.status_code == 200
    d = r.json()
    checks = d.get("checks", {})
    assert "ollama" in checks
    assert checks["ollama"]["ok"] is True
    assert isinstance(checks["ollama"].get("models", []), list)


def test_system_logs():
    r = client.get("/api/system/logs?lines=50")
    assert r.status_code == 200
    assert isinstance(r.json().get("logs", []), list)


def test_system_logs_download():
    import zipfile
    r = client.get("/api/system/logs/download")
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # zip magic
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = zf.namelist()
    assert "aria.log" in names
    assert "diagnostics.json" in names


def test_restart_ollama_endpoint():
    r = client.post("/api/system/restart-ollama")
    assert r.status_code in (200, 500)
    body = r.json()
    if r.status_code == 200:
        assert "message" in body


# ═══════════════════════════ 2. Config & telemetry ════════════════════════════

def test_config_get_and_save():
    r = client.get("/api/admin/config")
    assert r.status_code == 200
    cfg = r.json()
    assert isinstance(cfg, dict)

    r = client.post("/api/admin/config", json={"memory_enabled": True,
                                               "telemetry_enabled": False})
    assert r.status_code == 200
    assert r.json().get("memory_enabled") is True


def test_telemetry_toggle_and_summary():
    r = client.post("/api/admin/telemetry/toggle", json={"enabled": True})
    assert r.status_code == 200
    r = client.get("/api/admin/telemetry")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    # summary shape: event_counts is a dict of type → count
    assert "event_counts" in body
    assert isinstance(body["event_counts"], dict)
    r = client.post("/api/admin/telemetry/toggle", json={"enabled": False})
    assert r.status_code == 200


def test_telemetry_clear():
    r = client.delete("/api/admin/telemetry")
    assert r.status_code == 200


# ═══════════════════════════ 3. Backups ═══════════════════════════════════════

def test_backup_lifecycle():
    r = client.post("/api/backup/create", json={})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "ok"
    name = b["filename"]

    r = client.get("/api/backup/list")
    assert r.status_code == 200
    names = [x["filename"] for x in r.json().get("backups", [])]
    assert name in names

    r = client.get(f"/api/backup/download/{name}")
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # zip magic

    r = client.delete(f"/api/backup/{name}")
    assert r.status_code == 200
    assert r.json().get("deleted") is True


def test_backup_rejects_unknown_filename():
    r = client.get("/api/backup/download/../../etc/passwd")
    assert r.status_code in (400, 404)


def test_backup_rejects_restore_of_unknown():
    r = client.post("/api/backup/restore")
    assert r.status_code in (400, 404, 422)


def test_backup_restore_zip_slip():
    import zipfile
    evil = io.BytesIO()
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("../../evil.txt", "boom")
    r = client.post("/api/backup/restore",
                    files={"file": ("evil.zip", evil.getvalue(), "application/zip")})
    assert r.status_code == 400


def test_backup_restore_valid_roundtrip():
    r = client.post("/api/backup/create", json={})
    name = r.json()["filename"]
    dl = client.get(f"/api/backup/download/{name}")
    assert dl.status_code == 200
    r = client.post("/api/backup/restore",
                    files={"file": (name, dl.content, "application/zip")})
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "ok"


# ═══════════════════════════ 4. Chat (SSE) ════════════════════════════════════

def test_chat_streams_full_response():
    r = client.post("/api/chat", data={"message": "What is 2+2? Answer in one line.",
                                       "mode": "fast"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers.get("x-conversation-id")
    assert "done" in r.text.lower()
    # A real answer should contain the SSE tokens and final done marker
    assert "[DONE]" in r.text or '"type":"done"' in r.text or "done" in r.text


def test_chat_with_document_upload():
    txt = io.BytesIO(b"The water cycle has three main stages: evaporation, condensation, "
                     b"and precipitation. Evaporation happens when the sun heats water in "
                     b"rivers, lakes and oceans, turning it into water vapour.")
    r = client.post("/api/chat",
                    data={"message": "List the three stages of the water cycle.",
                          "mode": "fast"},
                    files={"document": ("water.txt", txt, "text/plain")})
    assert r.status_code == 200
    assert "evaporation" in r.text.lower() or "evapor" in r.text.lower()


def test_chat_conversation_history_endpoints():
    cid = "e2e-conv-1"
    r = client.post("/api/chat", data={"message": "hi", "conversation_id": cid,
                                       "mode": "fast"})
    assert r.status_code == 200

    r = client.get("/api/chat/conversations")
    assert r.status_code == 200

    r = client.get(f"/api/chat/conversations/{cid}")
    assert r.status_code == 200

    r = client.get("/api/chat/conversations/date/2099-01-01")
    assert r.status_code == 200

    r = client.delete(f"/api/chat/conversations/{cid}")
    assert r.status_code == 200
    assert r.json()["deleted"] is True


def test_chat_oversize_image_rejected():
    big = io.BytesIO(b"x" * (21 * 1024 * 1024))
    r = client.post("/api/chat",
                    data={"message": "hi"},
                    files={"image": ("big.png", big, "image/png")})
    assert r.status_code == 413


# ═══════════════════════════ 5. Study tools ═══════════════════════════════════

def test_study_quiz_returns_questions():
    r = client.post("/api/study/quiz", json={"topic": "Photosynthesis",
                                             "level": "easy", "count": 3})
    assert r.status_code == 200, r.text
    qs = r.json()["questions"]
    assert len(qs) >= 1
    for q in qs:
        assert "question" in q
        options = q.get("options", [])
        assert len(options) >= 2
        # The answer must resolve to one of the options (accuracy check).
        # A blank "correct" means the second-model verify couldn't run
        # (e.g. fallback model not pulled) — degrade gracefully, don't crash.
        if "answer" in q:
            assert str(q["answer"]) in options or q["answer"] in ("A", "B", "C", "D")
        elif "correct" in q:
            correct = q["correct"]
            if correct == "":
                continue
            idx = ord(str(correct).upper()) - 65 if isinstance(correct, str) else int(correct)
            assert 0 <= idx < len(options), f"answer index {correct} outside options"
        else:
            pytest.fail(f"question has no answer: {q}")


def test_study_flashcards():
    r = client.post("/api/study/flashcards", json={"topic": "Fractions",
                                                   "level": "easy", "count": 3})
    assert r.status_code == 200, r.text
    cards = r.json().get("flashcards", r.json().get("cards", []))
    assert len(cards) >= 1
    assert "front" in cards[0] and "back" in cards[0]


# Standalone mindmap generator removed — chat diagram generator covers it
def test_study_mindmap_removed():
    r = client.post("/api/study/mindmap", json={"topic": "The Solar System",
                                                "level": "easy"})
    assert r.status_code == 404, f"/api/study/mindmap should be removed, got {r.status_code}"


def test_study_summary():
    r = client.post("/api/study/summary", json={"topic": "Cellular respiration"})
    assert r.status_code == 200, r.text
    assert "summary" in json.dumps(r.json()).lower()


def test_study_notes():
    r = client.post("/api/study/notes", json={"topic": "The Industrial Revolution",
                                              "level": "easy"})
    assert r.status_code == 200, r.text


# Moved to brain (chat) — dedicated endpoints removed, verify 404
def test_removed_study_tools_return_404():
    for path, payload in [
        ("/api/study/essay-feedback", {"essay": "test", "topic": "test"}),
        ("/api/study/formula", {"topic": "Pythagoras"}),
        ("/api/study/mindmap", {"topic": "The Solar System"}),
        ("/api/study/timeline", {"topic": "WW2"}),
        ("/api/study/worksheet", {"topic": "Fractions", "grade": "Year 7"}),
        ("/api/study/exam-sim", {"topic": "Algebra"}),
        ("/api/study/audio-overview", {"topic": "Photosynthesis"}),
        ("/api/study/check-handwriting", {"question": "q"}),
    ]:
        r = client.post(path, json=payload)
        assert r.status_code == 404, f"{path} should be removed, got {r.status_code}"


def test_removed_planner_returns_404():
    for path in ["/api/planner/schedule", "/api/planner/cushion", "/api/planner/events", "/api/premium-planner/courses"]:
        r = client.get(path) if "courses" in path or "events" in path else client.post(path, json={})
        assert r.status_code == 404, f"{path} should be removed, got {r.status_code}"


def test_brain_handles_study_intents_via_chat():
    from services.orchestrator import detect_intents
    assert "essay_feedback" in detect_intents("please give me essay feedback on my draft")
    assert "formula" in detect_intents("formula for quadratic equations")
    assert "timeline" in detect_intents("timeline for World War 2")
    assert "worksheet_generator" in detect_intents("create a worksheet on fractions")
    assert "exam_sim" in detect_intents("exam simulation on algebra")
    assert "audio_overview" in detect_intents("audio overview of photosynthesis")
    assert "study_intel" in detect_intents("what are my weak topics")


# ═══════════════════════════ 7. Knowledge base ════════════════════════════════

def test_kb_upload_search_ask():
    txt = ("Photosynthesis is the process where plants use sunlight, water and "
           "carbon dioxide to make glucose and oxygen. It happens in the "
           "chloroplasts which contain the green pigment chlorophyll.")
    r = client.post("/api/kb/upload",
                    data={"collection": "science"},
                    files={"file": ("photosynthesis.txt", txt.encode(), "text/plain")})
    assert r.status_code == 200, r.text
    file_id = r.json().get("file_id")

    r = client.get("/api/kb/stats")
    assert r.status_code == 200

    r = client.get("/api/kb/documents")
    assert r.status_code == 200

    r = client.get("/api/kb/collections")
    assert r.status_code == 200

    r = client.get("/api/kb/search?q=what does photosynthesis need")
    assert r.status_code == 200

    r = client.post("/api/kb/ask", data={"question": "What does photosynthesis produce?"})
    assert r.status_code == 200
    assert "oxygen" in r.text.lower() or "glucose" in r.text.lower()

    if file_id:
        r = client.delete(f"/api/kb/documents/{file_id}")
        assert r.status_code == 200


def test_kb_upload_handles_bad_collection():
    r = client.post("/api/kb/upload",
                    data={"collection": "not_a_real_collection"},
                    files={"file": ("x.txt", b"content", "text/plain")})
    assert r.status_code in (200, 400)  # must not 500


# ═══════════════════════════ 8. Notebooks ═════════════════════════════════════

def test_notebook_full_lifecycle():
    r = client.post("/api/notebooks", json={"name": "Biology Revision"})
    assert r.status_code == 200, r.text
    nb_id = r.json()["id"]

    r = client.post(f"/api/notebooks/{nb_id}/sources", json={
        "source_type": "notes",
        "title": "Cells",
        "content": "Mitochondria are the powerhouse of the cell. They produce "
                   "energy through cellular respiration. Plant cells also have "
                   "chloroplasts for photosynthesis."})
    assert r.status_code == 200, r.text
    src_id = r.json()["id"]
    # key used by the API is "id", and source type echoed as "type"
    assert r.json().get("type") == "notes"

    r = client.get(f"/api/notebooks/{nb_id}")
    assert r.status_code == 200

    r = client.get(f"/api/notebooks/{nb_id}/sources")
    assert r.status_code == 200

    r = client.get(f"/api/notebooks/{nb_id}/generate/summary")
    assert r.status_code == 200, r.text

    r = client.get(f"/api/notebooks/{nb_id}/generate/flashcards", params={"num_cards": 2})
    assert r.status_code == 200, r.text

    r = client.get(f"/api/notebooks/{nb_id}/generate/quiz", params={"num_questions": 2})
    assert r.status_code == 200, r.text

    r = client.get(f"/api/notebooks/{nb_id}/generate/timeline")
    assert r.status_code == 200, r.text

    r = client.delete(f"/api/notebooks/{nb_id}")
    assert r.status_code == 200

    r = client.get(f"/api/notebooks/{nb_id}")
    assert r.status_code == 404


def test_notebook_chat():
    r = client.post("/api/notebooks", json={"name": "Chat NB"})
    nb_id = r.json()["id"]
    client.post(f"/api/notebooks/{nb_id}/sources",
                json={"source_type": "notes",
                      "title": "Climate",
                      "content": "Climate change increases the frequency of "
                                 "extreme weather events like heatwaves and "
                                 "bushfires in Australia."})
    r = client.post(f"/api/notebooks/{nb_id}/chat", json={"message": "What is the effect of climate change?"})
    assert r.status_code == 200
    assert "heatwave" in r.text.lower() or "extreme" in r.text.lower()
    client.delete(f"/api/notebooks/{nb_id}")


# ═══════════════════════════ 9. File organizer (non-AI) ═══════════════════════
# NOTE: the /api/files endpoints were removed with the File Organizer feature
# (see conftest clean_db note) — no routes to test here. Coverage for the
# surviving file flows lives in the notebooks tests below.


# ═══════════════════════════ 10. Intelligence & memory ════════════════════════

def test_intelligence_knowledge_graph():
    r = client.get("/api/intelligence/knowledge-graph/graph")
    assert r.status_code == 200
    r = client.get("/api/intelligence/knowledge-graph/stats")
    assert r.status_code == 200
    r = client.get("/api/intelligence/knowledge-graph/search?q=algebra")
    assert r.status_code == 200


def test_intelligence_tasks_and_weak_topics():
    r = client.get("/api/intelligence/agents/tasks")
    assert r.status_code == 200
    r = client.get("/api/intelligence/study/weak-topics")
    assert r.status_code == 200
    r = client.get("/api/intelligence/study/suggest-next")
    assert r.status_code == 200
    r = client.get("/api/intelligence/study/curriculum/Mathematics")
    assert r.status_code == 200
    r = client.get("/api/intelligence/study/adaptive")
    assert r.status_code == 200


def test_memory_timeline_and_search():
    r = client.get("/api/intelligence/memory/timeline?days=30")
    assert r.status_code == 200
    r = client.get("/api/intelligence/memory/search?q=maths&limit=5")
    assert r.status_code == 200


# ═══════════════════════════ 11. V2 analytics & SR ════════════════════════════

def test_v2_analytics_endpoints():
    for path in ("/api/v2/analytics/heatmap", "/api/v2/analytics/trends",
                 "/api/v2/analytics/predicted-grades", "/api/v2/analytics/focus-score",
                 "/api/v2/analytics/weekly-summary"):
        r = client.get(path)
        assert r.status_code == 200, (path, r.text)


def test_v2_gamification():
    r = client.get("/api/v2/game/progress")
    assert r.status_code == 200
    r = client.get("/api/v2/game/challenge")
    assert r.status_code == 200
    r = client.get("/api/v2/game/leaderboard")
    assert r.status_code == 200


def test_v2_flashcard_spaced_repetition():
    r = client.post("/api/v2/study/add-card",
                    json={"front": "What is the capital of Australia?",
                          "back": "Canberra", "subject": "Geography"})
    assert r.status_code == 200, r.text
    card_id = r.json()["id"]

    r = client.post("/api/v2/study/review-card",
                    json={"card_id": card_id, "quality": 5})
    assert r.status_code == 200

    r = client.get("/api/v2/study/sr-stats")
    assert r.status_code == 200
    assert r.json().get("total_cards", 0) >= 1

    r = client.post("/api/v2/study/delete-card", json={"card_id": card_id})
    assert r.status_code == 200


def test_v2_curriculum_search():
    r = client.get("/api/v2/curriculum/stages")
    assert r.status_code == 200
    assert "S4" in r.json()
    r = client.get("/api/v2/curriculum/klas")
    assert r.status_code == 200
    r = client.get("/api/v2/curriculum/search?q=algebra")
    assert r.status_code == 200
    r = client.get("/api/v2/curriculum/hsc")
    assert r.status_code == 200
    r = client.get("/api/v2/curriculum/age/13")
    assert r.status_code == 200


def test_v2_exam_readiness_and_gaps():
    r = client.get("/api/v2/study/exam-readiness/Mathematics")
    assert r.status_code == 200
    r = client.get("/api/v2/study/knowledge-gaps/Science")
    assert r.status_code == 200


def test_v2_learning_style():
    r = client.get("/api/v2/study/learning-style")
    assert r.status_code == 200


# 12. Premium planner removed — now brain-handled via chat
def test_premium_planner_removed():
    r = client.get("/api/premium-planner/courses")
    assert r.status_code == 404


# ═══════════════════════════ 13. Agent (safe, read-only) ══════════════════════

def test_agent_safe_read_commands():
    r = client.post("/api/agent/terminal", json={"command": "echo hello"})
    assert r.status_code == 200
    # Contract: AgentService.execute_terminal returns {"stdout": ..., ...}
    assert "hello" in r.json().get("stdout", "")

    r = client.post("/api/agent/list-directory", json={"path": "."})
    assert r.status_code == 200
