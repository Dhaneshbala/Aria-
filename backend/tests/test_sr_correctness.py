"""Feature 3 slice 1: SR scheduling correctness + ID/caps (hermetic)."""
import pytest

import services.advanced_study_service as adv


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.setattr(adv, "SR_FILE", tmp_path / "sr.json")
    from services.advanced_study_service import AdvancedStudyIntelligence
    return AdvancedStudyIntelligence()


async def test_sm2_intervals_1_6_ef(svc):
    c = await svc.add_flashcard("2+2", "4")
    c1 = await svc.review_flashcard(c["id"], 5)
    assert c1["interval"] == 1 and c1["repetitions"] == 1
    c2 = await svc.review_flashcard(c["id"], 5)
    assert c2["interval"] == 6 and c2["repetitions"] == 2
    c3 = await svc.review_flashcard(c["id"], 5)
    assert c3["interval"] == round(6 * c2["ease_factor"])
    assert c3["ease_factor"] >= 1.3


async def test_sm2_fail_resets(svc):
    c = await svc.add_flashcard("q", "a")
    await svc.review_flashcard(c["id"], 5)
    c2 = await svc.review_flashcard(c["id"], 2)
    assert c2["repetitions"] == 0 and c2["interval"] == 1


async def test_ids_unique_under_bulk(svc):
    added = await svc.add_flashcards_bulk([{"front": f"q{i}", "back": "a"} for i in range(50)], "s")
    ids = [c["id"] for c in added]
    assert len(set(ids)) == 50


async def test_bulk_skips_empties_and_caps_200(svc):
    cards = [{"front": "", "back": "x"}, {"front": "q", "back": ""}, {"front": "ok", "back": "yes"}]
    cards += [{"front": f"q{i}", "back": "a"} for i in range(300)]
    added = await svc.add_flashcards_bulk(cards, "s")
    # First 200 inputs contain 2 empties → 198 added; cap enforced.
    assert len(added) == 198
    assert all(c["front"].strip() and c["back"].strip() for c in added)


async def test_due_sort_overdue_first(svc):
    from datetime import datetime, timezone, timedelta
    c1 = await svc.add_flashcard("new", "x")
    c2 = await svc.add_flashcard("old", "y")
    # Force c2 far overdue by reviewing then backdating file directly
    import json
    p = adv.SR_FILE
    data = json.loads(p.read_text())
    for c in data:
        if c["id"] == c2["id"]:
            c["next_review"] = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        if c["id"] == c1["id"]:
            c["next_review"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    p.write_text(json.dumps(data))
    due = await svc.get_due_cards(limit=10)
    assert due[0]["id"] == c2["id"]


async def test_review_missing_returns_error_not_crash(svc):
    r = await svc.review_flashcard("card_nope", 4)
    assert r.get("error") == "Card not found"
