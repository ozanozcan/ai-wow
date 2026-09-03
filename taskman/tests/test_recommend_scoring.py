"""Pure scoring/parse helpers behind `recommend next` — invariants, not examples.

These pin the ported math itself (priority table, +20 in-progress bonus,
−2/day-after-7 staleness) and the hostile inputs a replayed board can carry
(missing fields, junk timestamps) — the CLI-level tests only sample it.
"""

from __future__ import annotations

import datetime as dt

from taskman.cli import (
    PRIORITY_ORDER,
    RECOMMEND_IN_PROGRESS_BONUS,
    RECOMMEND_PRIORITY_SCORE,
    RECOMMEND_STALE_GRACE_DAYS,
    RECOMMEND_STALE_PENALTY_PER_DAY,
    _parse_iso,
    _priority_rank,
    _score_recommend_task,
)
from taskman.eventlog.schema import PRIORITIES

NOW = dt.datetime(2026, 9, 3, 12, 0, tzinfo=dt.UTC)


def _score(task: dict) -> tuple[int, str]:
    return _score_recommend_task(
        task, now=NOW, sole_stem=None, sole_feature_id=None,
        feat_by_id={}, slug_by_feature={},
    )


def test_parse_iso_round_trips_aware_and_defaults_naive_to_utc():
    aware = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone(dt.timedelta(hours=5)))
    assert _parse_iso(aware.isoformat()) == aware
    naive = _parse_iso("2026-01-02T03:04:05")
    assert naive is not None and naive.tzinfo == dt.UTC


def test_parse_iso_junk_is_none_never_an_exception():
    for junk in (None, "", "   ", "not-a-date", 12345, True, "2026-13-99T99:99:99"):
        assert _parse_iso(junk) is None


def test_priority_rank_is_the_schema_order_with_unknown_last():
    ranks = [_priority_rank({"priority": p}) for p in PRIORITIES]
    assert ranks == sorted(ranks) == [PRIORITY_ORDER[p] for p in PRIORITIES]
    for unknown in ("", None, "urgent"):
        assert _priority_rank({"priority": unknown}) == len(PRIORITIES)
    assert _priority_rank({}) == len(PRIORITIES)


def test_score_equals_priority_table_when_not_in_progress():
    for p in PRIORITIES:
        score, reason = _score({"id": 1, "priority": p, "status": "todo"})
        assert score == RECOMMEND_PRIORITY_SCORE[p]
        assert reason.startswith(f"{p} priority")


def test_unknown_or_missing_priority_scores_as_med():
    for task in ({"id": 1, "status": "todo"}, {"id": 1, "priority": "urgent", "status": "todo"}):
        score, _reason = _score(task)
        assert score == RECOMMEND_PRIORITY_SCORE["med"]


def test_in_progress_bonus_and_exact_stale_penalty_over_a_year():
    base = RECOMMEND_PRIORITY_SCORE["high"]
    for days in range(0, 366):
        updated = (NOW - dt.timedelta(days=days)).isoformat(timespec="seconds")
        task = {"id": 1, "priority": "high", "status": "in_progress", "updated_at": updated}
        score, reason = _score(task)
        expected = base + RECOMMEND_IN_PROGRESS_BONUS
        if days > RECOMMEND_STALE_GRACE_DAYS:
            expected -= (days - RECOMMEND_STALE_GRACE_DAYS) * RECOMMEND_STALE_PENALTY_PER_DAY
            assert f"stale {days}d" in reason
        else:
            assert "stale" not in reason
        assert score == expected, f"day {days}: {score} != {expected}"


def test_in_progress_with_junk_or_missing_updated_at_gets_bonus_no_penalty():
    for updated in (None, "", "not-a-date", 42):
        task = {"id": 1, "priority": "low", "status": "in_progress", "updated_at": updated}
        score, reason = _score(task)
        assert score == RECOMMEND_PRIORITY_SCORE["low"] + RECOMMEND_IN_PROGRESS_BONUS
        assert "stale" not in reason
