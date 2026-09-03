"""Tests for the board-sync gate (taskman.mow.check_board_sync).

The action-report line was never enough: you could write `**Board sync:** run`
and leave every dispatch task `todo`. These cases plant a real event-log board
and assert the gate reads it (L33).
"""

from __future__ import annotations

from pathlib import Path

from taskman.eventlog import store
from taskman.mow import check_board_sync as _mod
from taskman.mow import closeout

from tests.test_mow_closeout import _stem


def _with_board(tmp_path: Path, board_dir: Path) -> tuple[Path, Path]:
    """A complete close-out fixture on the suite's tmp board (conftest autouse)."""
    stem = _stem(tmp_path)
    (stem / "dispatch" / "01-a.md").write_text(
        "# 01-a: Do it\n\n**Role:** code-edit   **Wave:** 1\n\n"
        "## Goal\nDo it for the fixture.\n\n"
        "## Context & decisions (only what this todo needs)\n"
        "- source_ref: `docs/plans/demo/dispatch/01-a.md`\n"
        "- Fixture.\n",
        encoding="utf-8",
    )
    return stem, board_dir


def _add_task(board: Path, *, status: str, ref: str, tags: list[str] | None = None) -> int:
    return store.add(
        board,
        "task",
        {
            "title": "dispatch work",
            "status": status,
            "source_ref": ref,
            "tags": tags or [],
            "priority": "med",
        },
    )


def test_no_toml_is_a_noop(tmp_path):
    stem = _stem(tmp_path)
    (tmp_path / ".taskman.toml").unlink()
    assert _mod.check_stem(stem) == []


def test_na_line_refused_when_board_exists(tmp_path, board_dir):
    stem, board = _with_board(tmp_path, board_dir)
    _add_task(board, status="done", ref="docs/plans/demo/dispatch/01-a.md")
    errs = _mod.check_stem(stem)
    assert any("n/a but" in e and ".taskman.toml" in e for e in errs)


def test_open_task_refused(tmp_path, board_dir):
    stem, board = _with_board(tmp_path, board_dir)
    report = (stem / "action-report.md").read_text(encoding="utf-8")
    (stem / "action-report.md").write_text(
        report.replace("**Board sync:** `n/a` — no taskman in this repo.", "**Board sync:** ran"),
        encoding="utf-8",
    )
    _add_task(board, status="todo", ref="docs/plans/demo/dispatch/01-a.md")
    errs = _mod.check_stem(stem)
    assert any("still not `done`" in e for e in errs)


def test_done_task_passes(tmp_path, board_dir):
    stem, board = _with_board(tmp_path, board_dir)
    report = (stem / "action-report.md").read_text(encoding="utf-8")
    (stem / "action-report.md").write_text(
        report.replace("**Board sync:** `n/a` — no taskman in this repo.", "**Board sync:** ran"),
        encoding="utf-8",
    )
    _add_task(board, status="done", ref="docs/plans/demo/dispatch/01-a.md")
    assert _mod.check_stem(stem) == []


def test_deferred_task_may_stay_open(tmp_path, board_dir):
    stem, board = _with_board(tmp_path, board_dir)
    report = (stem / "action-report.md").read_text(encoding="utf-8")
    report = report.replace("**Board sync:** `n/a` — no taskman in this repo.", "**Board sync:** ran")
    report = report.replace(
        "| The thing | **Shipped** |",
        "| 01-a | **Deferred** — follow-up stem |\n| The thing | **Shipped** |",
    )
    (stem / "action-report.md").write_text(report, encoding="utf-8")
    _add_task(board, status="todo", ref="docs/plans/demo/dispatch/01-a.md")
    assert _mod.check_stem(stem) == []


def test_decision_tasks_are_not_swept(tmp_path, board_dir):
    stem, board = _with_board(tmp_path, board_dir)
    report = (stem / "action-report.md").read_text(encoding="utf-8")
    (stem / "action-report.md").write_text(
        report.replace("**Board sync:** `n/a` — no taskman in this repo.", "**Board sync:** ran"),
        encoding="utf-8",
    )
    _add_task(
        board,
        status="todo",
        ref="docs/plans/demo/dispatch/01-a.md",
        tags=["kind:decision"],
    )
    assert _mod.check_stem(stem) == []


def test_unmatched_source_ref_fails(tmp_path, board_dir):
    stem, _board = _with_board(tmp_path, board_dir)
    report = (stem / "action-report.md").read_text(encoding="utf-8")
    (stem / "action-report.md").write_text(
        report.replace("**Board sync:** `n/a` — no taskman in this repo.", "**Board sync:** ran"),
        encoding="utf-8",
    )
    # brief exists, no matching task
    errs = _mod.check_stem(stem)
    assert any("match no board task" in e for e in errs)


def test_missing_board_dir_fails(tmp_path, board_dir):
    stem = _stem(tmp_path)
    (stem / "dispatch" / "01-a.md").write_text(
        "# 01-a: Do it\n\n**Role:** code-edit   **Wave:** 1\n\n"
        "## Goal\nDo it for the fixture.\n\n"
        "## Context & decisions (only what this todo needs)\n"
        "- source_ref: `docs/plans/demo/dispatch/01-a.md`\n"
        "- Fixture.\n",
        encoding="utf-8",
    )
    import shutil

    shutil.rmtree(board_dir)
    errs = _mod.check_stem(stem)
    assert any("board" in e and "missing" in e for e in errs)


def test_closeout_refuses_open_board_task(tmp_path, board_dir):
    stem, board = _with_board(tmp_path, board_dir)
    report = (stem / "action-report.md").read_text(encoding="utf-8")
    (stem / "action-report.md").write_text(
        report.replace("**Board sync:** `n/a` — no taskman in this repo.", "**Board sync:** ran"),
        encoding="utf-8",
    )
    _add_task(board, status="in_progress", ref="docs/plans/demo/dispatch/01-a.md")
    errors, _ = closeout.run_closeout(stem)
    assert any("still not `done`" in e for e in errors)
