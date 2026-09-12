"""Tests for the exam countdown planner (rule-based, no LLM needed)."""
from datetime import date, timedelta

import pytest

from services.exam_plan_service import build_schedule
import services.exam_plan_service as eps


def test_schedule_weak_topics_first_and_repeated():
    exam = date.today() + timedelta(days=6)
    sched = build_schedule(exam, ["Maths", "Science"], ["fractions"])
    assert len(sched) == 6
    focuses = [s["focus"] for s in sched]
    # weak topic leads and repeats (queue holds it twice, round-robin)
    assert focuses.count("fractions") >= 2
    assert focuses[0] == "fractions"


def test_schedule_last_day_is_light_review():
    exam = date.today() + timedelta(days=4)
    sched = build_schedule(exam, ["Maths"], [])
    assert sched[-1]["light"] is True
    assert "Light review" in sched[-1]["focus"]


def test_schedule_exam_today_single_light_day():
    sched = build_schedule(date.today(), ["Science"], [])
    assert len(sched) == 1
    assert sched[-1]["light"] is True


def test_schedule_defaults_subject():
    exam = date.today() + timedelta(days=2)
    sched = build_schedule(exam, [], [])
    assert all(s["focus"] for s in sched)


@pytest.mark.asyncio
async def test_create_plan_makes_todos_and_lists():
    from datetime import date as _d
    exam = (_d.today() + timedelta(days=3)).isoformat()
    plan = await eps.create_plan("NAPLAN", exam, ["Maths"], 30)
    assert plan["exam_name"] == "NAPLAN"
    assert len(plan["days"]) == 3
    assert all("todo_id" in d for d in plan["days"])
    plans = eps.list_plans()
    assert any(p["id"] == plan["id"] for p in plans)
    assert eps.delete_plan(plan["id"]) is True
    assert all(p["id"] != plan["id"] for p in eps.list_plans())


@pytest.mark.asyncio
async def test_create_plan_rejects_past_date():
    past = (date.today() - timedelta(days=1)).isoformat()
    with pytest.raises(ValueError):
        await eps.create_plan("Late", past, ["Maths"], 30)


@pytest.mark.asyncio
async def test_create_plan_rejects_bad_date():
    with pytest.raises(ValueError):
        await eps.create_plan("X", "not-a-date", ["Maths"], 30)
