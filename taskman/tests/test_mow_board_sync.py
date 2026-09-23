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


# --- the Outcome-escape regression (FTM #12290) -----------------------------
#
# The cases above all use a fixture Outcome of `| The thing | **Shipped** |`,
# which names nothing id-shaped. `outcome_named` is therefore False and the
# must-be-done check runs. That is the one input where this defect cannot
# appear (L46): the moment Outcome mentions ANY id- or todo-shaped token, the
# old `(not outcome_named) or ...` exempted every task Outcome did not name,
# and the gate written to catch mark-shipped's misses passed on exactly them.
#
# Observed on FTM's `reuse-db-seed-pollution`: both lane tasks sat in backlog,
# `plan mark-shipped` printed "no tasks moved", and this gate exited 0. The
# module docstring already promised the right rule -- "or that Outcome did not
# mention, must be `done`" -- so the code, not the spec, was wrong.


def _ran_report(stem: Path, extra_outcome_row: str = "") -> None:
    report = (stem / "action-report.md").read_text(encoding="utf-8")
    report = report.replace("**Board sync:** `n/a` — no taskman in this repo.", "**Board sync:** ran")
    if extra_outcome_row:
        report = report.replace("| The thing | **Shipped** |", f"{extra_outcome_row}\n| The thing | **Shipped** |")
    (stem / "action-report.md").write_text(report, encoding="utf-8")


def test_open_task_refused_when_outcome_names_an_unrelated_id(tmp_path, board_dir):
    """A decision id in Outcome must not exempt a dispatch task it never names."""
    stem, board = _with_board(tmp_path, board_dir)
    _ran_report(stem, "| Decision d#1279 | **Shipped** |")
    _add_task(board, status="todo", ref="docs/plans/demo/dispatch/01-a.md")
    errs = _mod.check_stem(stem)
    assert any("still not `done`" in e for e in errs), errs


def test_open_task_refused_when_outcome_carries_a_line_reference(tmp_path, board_dir):
    """`conftest.py:18, :34-35` must not read as the todo id `34-35`."""
    stem, board = _with_board(tmp_path, board_dir)
    _ran_report(stem, "| Guarded lines | **Shipped** — `conftest.py:18`, `:34-35` |")
    _add_task(board, status="todo", ref="docs/plans/demo/dispatch/01-a.md")
    errs = _mod.check_stem(stem)
    assert any("still not `done`" in e for e in errs), errs


def test_open_task_refused_when_outcome_carries_a_duration(tmp_path, board_dir):
    """`~190-260s suite` must not read as the todo id `90-260s`."""
    stem, board = _with_board(tmp_path, board_dir)
    _ran_report(stem, "| Cost | **Shipped** — ~190-260s suite |")
    _add_task(board, status="todo", ref="docs/plans/demo/dispatch/01-a.md")
    errs = _mod.check_stem(stem)
    assert any("still not `done`" in e for e in errs), errs


def test_deferral_is_still_the_one_exemption(tmp_path, board_dir):
    """Tightening the rule must not break the deferral escape hatch."""
    stem, board = _with_board(tmp_path, board_dir)
    _ran_report(stem, "| 01-a | **Deferred** — follow-up stem |\n| Decision d#1279 | **Shipped** |")
    _add_task(board, status="todo", ref="docs/plans/demo/dispatch/01-a.md")
    assert _mod.check_stem(stem) == []


def test_outcome_mentions_ignores_line_refs_and_durations(tmp_path):
    """The todo regex matched any NN-word text, including `34-35` and `90-260s`."""
    report = (
        "## Outcome\n\n"
        "| Item | Result |\n|---|---|\n"
        "| Guarded lines | **Shipped** — `conftest.py:18`, `:34-35` |\n"
        "| Cost | **Shipped** — ~190-260s suite |\n"
        "| Real brief | **Shipped** — 01-a |\n"
    )
    _s_ids, s_todos, _d_ids, _d_todos = _mod._outcome_mentions(report)
    assert "34-35" not in s_todos
    assert "90-260s" not in s_todos
    assert "01-a" in s_todos
