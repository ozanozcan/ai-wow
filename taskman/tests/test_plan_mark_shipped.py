"""`taskman plan mark-shipped` — close board tasks when mow Integrates."""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest
from sqlalchemy import select, text

from taskman.cli import main
from taskman.db import Session, upgrade_head
from taskman.config import find_project
from taskman.models import Project, Task

MARKER = "mark-shipped-test"


@pytest.fixture(scope="module", autouse=True)
def _schema_ready():
    upgrade_head()


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    with Session() as session:
        slug, _ = find_project()
        proj = session.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            return
        session.execute(
            text("DELETE FROM taskman_task WHERE project_id = :pid AND title LIKE :m"),
            {"pid": proj.id, "m": f"%{MARKER}%"},
        )
        session.commit()


def _run(argv: list[str]) -> tuple[str, str]:
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        main(argv)
    return out_buf.getvalue(), err_buf.getvalue()


def _add_task(source_ref: str, *, status: str = "todo", priority: str = "med") -> int:
    title = f"Shippable {MARKER}"
    out, _ = _run(
        [
            "task",
            "add",
            title,
            "--source",
            source_ref,
            "--status",
            status,
            "-p",
            priority,
        ]
    )
    return int(out.split("#")[1].split()[0])


def _write_dispatch(
    tmp_path: Path,
    *,
    briefs: dict[str, str],
    index_briefs: list[str] | None = None,
    action_report: str | None = None,
) -> Path:
    dispatch = tmp_path / "dispatch"
    dispatch.mkdir(parents=True)
    listed = index_briefs if index_briefs is not None else list(briefs)
    brief_cell = ", ".join(listed)
    (dispatch / "INDEX.md").write_text(
        f"""# Dispatch index — {MARKER}

Source plan: `docs/plans/{MARKER}/plan.md`

## Lanes
| Lane | Todos (in order) | Brief |
|---|---|---|
| A | only | {brief_cell} |
""",
        encoding="utf-8",
    )
    for name, body in briefs.items():
        (dispatch / name).write_text(body, encoding="utf-8")
    if action_report is not None:
        (tmp_path / "action-report.md").write_text(action_report, encoding="utf-8")
    return dispatch


def _brief_body(source_ref: str) -> str:
    return f"""# todo: {MARKER}

**Role:** code-edit   **Wave:** 1

## Goal
Test fixture.

## Context & decisions (only what this todo needs)
- source_ref: `{source_ref}`
- Fixture.

## Do NOT
- n/a

## Acceptance check
- SHALL pass.

## QA contract
- `true`
"""


def test_moves_matching_tasks_without_action_report(tmp_path: Path):
    ref_a = f"docs/plans/{MARKER}/dispatch/01-a.md"
    ref_b = f"docs/plans/{MARKER}/dispatch/02-b.md"
    task_a = _add_task(ref_a, status="in_progress")
    task_b = _add_task(ref_b, status="todo")
    dispatch = _write_dispatch(
        tmp_path,
        briefs={
            "01-a.md": _brief_body(ref_a),
            "02-b.md": _brief_body(ref_b),
        },
    )

    out, err = _run(["plan", "mark-shipped", str(dispatch)])
    assert "no action-report" in err.lower()

    with Session() as session:
        assert session.get(Task, task_a).status == "done"
        assert session.get(Task, task_b).status == "done"
    assert f"#{task_a}" in out or "done" in out.lower()


def test_skips_deferred_in_action_report(tmp_path: Path):
    ref_done = f"docs/plans/{MARKER}/dispatch/01-done.md"
    ref_deferred = f"docs/plans/{MARKER}/dispatch/02-deferred.md"
    task_done = _add_task(ref_done, status="todo")
    task_deferred = _add_task(ref_deferred, status="todo")
    report = f"""# Action report

## Outcome

| Todo | Task | Status | Deliverable |
|---|---|---|---|
| done-todo | #{task_done} | Done | shipped |
| deferred-todo | #{task_deferred} | Deferred | later |
"""
    dispatch = _write_dispatch(
        tmp_path,
        briefs={
            "01-done.md": _brief_body(ref_done),
            "02-deferred.md": _brief_body(ref_deferred),
        },
        action_report=report,
    )

    _run(["plan", "mark-shipped", str(dispatch)])

    with Session() as session:
        assert session.get(Task, task_done).status == "done"
        assert session.get(Task, task_deferred).status == "todo"


def test_skips_already_done(tmp_path: Path):
    ref = f"docs/plans/{MARKER}/dispatch/01-a.md"
    task_id = _add_task(ref, status="done")
    dispatch = _write_dispatch(
        tmp_path,
        briefs={"01-a.md": _brief_body(ref)},
    )

    _run(["plan", "mark-shipped", str(dispatch)])

    with Session() as session:
        assert session.get(Task, task_id).status == "done"


def test_skips_blocked_without_force(tmp_path: Path):
    ref = f"docs/plans/{MARKER}/dispatch/01-a.md"
    blocker = _add_task(f"docs/plans/{MARKER}/dispatch/blocker.md", status="todo")
    blocked = _add_task(ref, status="blocked")
    _run(["task", "link", str(blocked), "--blocked-by", str(blocker)])
    dispatch = _write_dispatch(
        tmp_path,
        briefs={"01-a.md": _brief_body(ref)},
    )

    _, err = _run(["plan", "mark-shipped", str(dispatch)])

    with Session() as session:
        assert session.get(Task, blocked).status == "blocked"
    assert f"#{blocked}" in err


def test_moves_tasks_for_briefs_not_listed_in_index(tmp_path: Path):
    """Sequential lane todos may share one INDEX Brief cell; scan picks up the rest."""
    ref_index = f"docs/plans/{MARKER}/dispatch/01-index-only.md"
    ref_extra = f"docs/plans/{MARKER}/dispatch/02-not-in-index.md"
    task_index = _add_task(ref_index, status="todo")
    task_extra = _add_task(ref_extra, status="todo")
    dispatch = _write_dispatch(
        tmp_path,
        briefs={
            "01-index-only.md": _brief_body(ref_index),
            "02-not-in-index.md": _brief_body(ref_extra),
        },
        index_briefs=["01-index-only.md"],
    )

    _run(["plan", "mark-shipped", str(dispatch)])

    with Session() as session:
        assert session.get(Task, task_index).status == "done"
        assert session.get(Task, task_extra).status == "done"


def test_skips_extra_brief_when_deferred_in_action_report(tmp_path: Path):
    ref_index = f"docs/plans/{MARKER}/dispatch/01-done.md"
    ref_extra = f"docs/plans/{MARKER}/dispatch/02-deferred.md"
    task_index = _add_task(ref_index, status="todo")
    task_extra = _add_task(ref_extra, status="todo")
    report = f"""# Action report

## Outcome

| Todo | Task | Status | Deliverable |
|---|---|---|---|
| done-todo | #{task_index} | Done | shipped |
| extra-todo | #{task_extra} | Deferred | later |
"""
    dispatch = _write_dispatch(
        tmp_path,
        briefs={
            "01-done.md": _brief_body(ref_index),
            "02-deferred.md": _brief_body(ref_extra),
        },
        index_briefs=["01-done.md"],
    )
    (tmp_path / "action-report.md").write_text(report, encoding="utf-8")

    _run(["plan", "mark-shipped", str(dispatch)])

    with Session() as session:
        assert session.get(Task, task_index).status == "done"
        assert session.get(Task, task_extra).status == "todo"


def test_force_moves_blocked(tmp_path: Path):
    ref = f"docs/plans/{MARKER}/dispatch/01-a.md"
    blocked = _add_task(ref, status="blocked")
    dispatch = _write_dispatch(
        tmp_path,
        briefs={"01-a.md": _brief_body(ref)},
    )

    _run(["plan", "mark-shipped", str(dispatch), "--force"])

    with Session() as session:
        assert session.get(Task, blocked).status == "done"


def test_skips_kind_decision_tasks(tmp_path: Path):
    """req #433 / mis-sourced-decision-survives: kind:decision never swept to done."""
    ref = f"docs/plans/{MARKER}/dispatch/01-decision.md"
    out, _ = _run(
        [
            "task",
            "add",
            f"Open question {MARKER}",
            "--source",
            ref,
            "--status",
            "todo",
            "-t",
            "kind:decision",
        ]
    )
    decision_task = int(out.split("#")[1].split()[0])
    build_task = _add_task(ref, status="todo")
    dispatch = _write_dispatch(
        tmp_path,
        briefs={"01-decision.md": _brief_body(ref)},
    )

    _run(["plan", "mark-shipped", str(dispatch)])

    with Session() as session:
        assert session.get(Task, decision_task).status == "todo"
        assert session.get(Task, build_task).status == "done"
