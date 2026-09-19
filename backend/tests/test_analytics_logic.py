"""Feature 4 slice 1: analytics baselines pinned (hermetic)."""
from datetime import datetime, timezone, timedelta

import services.analytics_service as mod
from services.analytics_service import AnalyticsService


def _svc(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "CONVERSATIONS_FILE", tmp_path / "convs.json")
    monkeypatch.setattr(mod, "PROFILE_FILE", tmp_path / "profile.json")
    return AnalyticsService()


def test_streak_counts_consecutive(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    now = datetime(2026, 9, 18, tzinfo=timezone.utc)
    daily = {
        "2026-09-18": 2, "2026-09-17": 1, "2026-09-16": 3,
        "2026-09-14": 5,  # gap on 15th breaks streak
    }
    assert svc._calculate_streak(daily, now=now) == 3


def test_streak_zero_when_today_empty(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    now = datetime(2026, 9, 18, tzinfo=timezone.utc)
    assert svc._calculate_streak({"2026-09-17": 1}, now=now) == 0


def test_heatmap_levels_bounded(tmp_path, monkeypatch):
    import json
    svc = _svc(tmp_path, monkeypatch)
    convs = {"c1": [{"timestamp": datetime.now(timezone.utc).isoformat()} for _ in range(10)]}
    (tmp_path / "convs.json").write_text(json.dumps(convs))
    h = svc.get_heatmap(months=1)
    assert all(0 <= x["level"] <= 4 for x in h["heatmap"])
    assert h["total_interactions"] == 10


def test_weekly_summary_empty_safe(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    w = svc.get_weekly_summary()
    assert w["overall_accuracy"] == 0 and w["subjects"] == []
