"""Time-frozen tests — streaks and dates must be deterministic.

freezegun pins `datetime.now` so midnight-boundary behaviour is pinned,
not flaky.
"""

from datetime import UTC, datetime

from freezegun import freeze_time

from services.gamification_service import GamificationService

svc = GamificationService()


def _daily(n_days, end=None):
    """n consecutive active days ending at `end` (default: frozen now)."""
    from datetime import timedelta

    end = end or datetime.now(UTC).date()
    return {(end - timedelta(days=i)).strftime("%Y-%m-%d"): 1 for i in range(n_days)}


@freeze_time("2026-10-14 12:00:00", tz_offset=0)
def test_streak_counts_backwards_from_today():
    assert svc._calc_streak(_daily(5)) == 5


@freeze_time("2026-10-14 12:00:00", tz_offset=0)
def test_streak_breaks_on_gap():
    d = _daily(3)
    d["2026-10-12"] = 0  # gap two days back breaks the run
    assert svc._calc_streak(d) == 2  # today + yesterday only


@freeze_time("2026-10-14 00:00:01", tz_offset=0)
def test_streak_stable_just_after_midnight():
    # One minute past midnight: yesterday's work still chains via today=0?
    # No — today has no activity, streak is 0. This pins the boundary rule.
    assert svc._calc_streak(_daily(5, end=datetime(2026, 10, 13).date())) == 0


@freeze_time("2026-10-14 12:00:00", tz_offset=0)
def test_streak_empty_is_zero():
    assert svc._calc_streak({}) == 0
