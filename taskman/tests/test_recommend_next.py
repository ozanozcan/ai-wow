"""`taskman recommend next` — rule-based next-work suggestions."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path

from taskman.cli import main
from taskman.eventlog import store

MARKER = "recommend-next-test"
TAG = "recommend-next-test-tag"


def _run(argv: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(argv)
    return buf.getvalue()


def _add(title_suffix: str, *, priority: str = "med", status: str = "todo") -> int:
    out = _run(
        [
            "task",
            "add",
            f"{title_suffix} {MARKER}",
            "-p",
            priority,
            "--status",
            status,
            "--source",
            f"docs/plans/{MARKER}/brief.md",
            "-t",
            TAG,
        ]
    )
    return int(out.split("#")[1].split()[0])


def _recommend(*extra: str) -> str:
    return _run(["recommend", "next", "--tag", TAG, *extra])


def test_lists_high_priority_suggestion():
    _add("backlog slice", priority="high", status="backlog")

    out = _recommend()

    assert "recommend next" in out.lower()
    assert MARKER in out
    assert "high priority" in out


def test_keystone_beats_med_at_equal_status():
    med_id = _add("med task", priority="med", status="todo")
    key_id = _add("keystone task", priority="keystone", status="todo")

    out = _recommend()

    assert out.index(f"#{key_id}") < out.index(f"#{med_id}")


def test_stale_in_progress_penalty_in_reason(board_dir: Path):
    task_id = _add("stale wip", priority="high", status="in_progress")
    stale_at = (datetime.now(UTC) - timedelta(days=10)).isoformat(timespec="seconds")
    store.update(board_dir, "task", task_id, {"updated_at": stale_at})

    out = _recommend()

    assert f"#{task_id}" in out
    assert "stale 10d" in out


def test_feature_filter_empty_prints_none():
    feat_out = _run(["feature", "add", f"Empty {MARKER}", "-t", "plan:recommend-empty"])
    feat_id = int(feat_out.split("#")[1].split()[0])
    _add("unrelated", priority="high", status="todo")

    out = _recommend("--feature", str(feat_id))

    assert "none" in out.lower()


def test_json_output_valid_shape():
    _add("json task", priority="high", status="todo")

    raw = _recommend("--json")
    payload = json.loads(raw)

    assert isinstance(payload, list)
    assert len(payload) >= 1
    assert len(payload) <= 3
    row = payload[0]
    assert set(row.keys()) == {"id", "title", "reason", "score"}
    assert isinstance(row["score"], int)


def test_feature_filter_includes_pbi_member_without_plan_tag():
    """`--feature` matches PBI membership, same as `plan to-dispatch`."""
    feat_out = _run(["feature", "add", f"NoPlan {MARKER}"])
    feat_id = int(feat_out.split("#")[1].split()[0])
    pbi_out = _run(["pbi", "add", f"Slice {MARKER}", "--feature", str(feat_id)])
    pbi_id = int(pbi_out.split("#")[1].split()[0])
    task_out = _run(
        [
            "task", "add", f"under-pbi {MARKER}",
            "--pbi", str(pbi_id), "-p", "high", "--status", "todo",
        ]
    )
    task_id = int(task_out.split("#")[1].split()[0])

    out = _run(["recommend", "next", "--feature", str(feat_id)])
    assert f"#{task_id}" in out


def test_dangling_blocker_does_not_disqualify():
    task_id = _add("blocked-by-ghost", priority="high", status="todo")
    from pathlib import Path
    from taskman.eventlog import store
    board = Path.cwd() / "board"
    store.link(board, "task", task_id, "blocked_by", 99999)

    out = _recommend()
    assert f"#{task_id}" in out


def test_lane_filter_matches_feature_lane_via_pbi():
    feat_out = _run(["feature", "add", f"Plat {MARKER}", "--lane", "platform"])
    feat_id = int(feat_out.split("#")[1].split()[0])
    pbi_out = _run(["pbi", "add", f"Plat slice {MARKER}", "--feature", str(feat_id)])
    pbi_id = int(pbi_out.split("#")[1].split()[0])
    task_out = _run(
        ["task", "add", f"no-own-lane {MARKER}", "--pbi", str(pbi_id), "-p", "high"]
    )
    task_id = int(task_out.split("#")[1].split()[0])

    out = _run(["recommend", "next", "--lane", "platform"])
    assert f"#{task_id}" in out


def test_tag_filter_excludes_non_matching():
    tagged = _add("tagged", priority="keystone", status="todo")
    untagged = _add("untagged", priority="high", status="todo")
    _run(["task", "set", str(untagged), "--tags", ""])

    out = _recommend()

    assert f"#{tagged}" in out
    assert f"#{untagged}" not in out
