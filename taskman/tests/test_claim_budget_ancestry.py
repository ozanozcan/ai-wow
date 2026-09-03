"""Claim locks, budget brief field, and ancestry warning (Paperclip steals)."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from taskman.cli import main
from taskman.eventlog import store

MARKER = "claim-budget-ancestry-test"


def _run(argv: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(argv)
    return buf.getvalue()


def test_task_claim_sets_claimed_by_on_board_and_show(board_dir: Path):
    out = _run(["task", "add", f"Claimable {MARKER}", "--source", "tests"])
    task_id = int(out.split("#")[1].split()[0])

    out = _run(["task", "claim", str(task_id), "--agent", "alice"])
    assert "claimed" in out
    assert "alice" in out

    out = _run(["board"])
    assert f"#{task_id}" in out
    assert "claimed=alice" in out

    out = _run(["task", "show", str(task_id)])
    assert "claimed=alice" in out

    task = store.state(board_dir)["task"][task_id]
    assert task["claimed_by"] == "alice"
    assert task["claimed_at"] is not None


def test_task_claim_rejects_second_agent_then_release_allows_reclaim():
    out = _run(["task", "add", f"Claim race {MARKER}", "--source", "tests"])
    task_id = int(out.split("#")[1].split()[0])
    _run(["task", "claim", str(task_id), "--agent", "alice"])

    with pytest.raises(SystemExit) as ei:
        _run(["task", "claim", str(task_id), "--agent", "bob"])
    assert "alice" in str(ei.value)

    out = _run(["task", "release", str(task_id)])
    assert "released" in out

    out = _run(["task", "claim", str(task_id), "--agent", "bob"])
    assert "bob" in out


def test_task_add_budget_tool_calls_stored_and_shown(board_dir: Path):
    out = _run(
        [
            "task",
            "add",
            f"Budgeted {MARKER}",
            "--source",
            "tests",
            "--budget-tool-calls",
            "20",
        ]
    )
    task_id = int(out.split("#")[1].split()[0])

    task = store.state(board_dir)["task"][task_id]
    assert task["brief"] == {"budget": {"max_tool_calls": 20}}

    out = _run(["board"])
    assert "budget=20" in out

    out = _run(["task", "show", str(task_id)])
    assert "budget=20" in out


def test_task_add_warns_without_pbi_or_source():
    out = _run(["task", "add", f"Orphan ancestry {MARKER}"])
    assert "no pbi and no source" in out
    assert "#" in out
