"""P1 logic fixes: urgent todos + due-date normalization + achievement shape (hermetic)."""
import services.todo_service as todos
import services.gamification_service as game


def test_urgent_survives_add(tmp_path, monkeypatch):
    import pathlib
    monkeypatch.setattr(todos, "_load", lambda: [])
    saved = {}
    monkeypatch.setattr(todos, "_save", lambda t: saved.setdefault("todos", t))
    t = todos.add_todo("Maths", "HW", None, 30, "urgent")
    assert t["priority"] == "urgent"


def test_urgent_sorts_first(tmp_path, monkeypatch):
    monkeypatch.setattr(todos, "_load", lambda: [
        {"id": "1", "priority": "low", "due_date": None, "completed": False},
        {"id": "2", "priority": "urgent", "due_date": None, "completed": False},
        {"id": "3", "priority": "high", "due_date": None, "completed": False},
    ])
    ordered = [t["id"] for t in todos.list_todos()]
    assert ordered[0] == "2"


def test_garbage_due_date_normalizes_to_none(monkeypatch):
    monkeypatch.setattr(todos, "_load", lambda: [])
    monkeypatch.setattr(todos, "_save", lambda t: None)
    t = todos.add_todo("S", "task", "someday-ish", 30, "medium")
    assert t["due_date"] is None
    t2 = todos.add_todo("S", "task", "2026-10-01", 30, "medium")
    assert t2["due_date"] == "2026-10-01"


def test_update_normalizes_priority_and_due(monkeypatch):
    store = [{"id": "ab", "priority": "medium", "due_date": None, "estimated_mins": 30}]
    monkeypatch.setattr(todos, "_load", lambda: [dict(store[0])])
    monkeypatch.setattr(todos, "_save", lambda t: store.__setitem__(slice(None), t))
    out = todos.update_todo("ab", {"priority": "bogus", "due_date": "never"})
    assert out["priority"] == "medium"
    assert out["due_date"] is None


def test_progress_achievements_is_list():
    svc = game.GamificationService()
    svc._data = {"xp": 0, "level": 1, "achievements": [{"id": "first_quiz"}]}
    p = svc.get_progress()
    assert isinstance(p["achievements_earned"], list)
    assert len(p["achievements_earned"]) == 1
    assert p["earned_count"] == 1
    # Dashboard shape: .slice(0, 8).map works
    assert p["achievements_earned"][:8] == [{"id": "first_quiz"}]


def test_challenge_ids_ascii():
    import inspect
    src = inspect.getsource(game.GamificationService.get_challenge)
    assert "accuracy_challenge" in src
    assert all(ord(c) < 128 for c in src.split("challenges = [")[1].split("]")[0] if c.strip())
