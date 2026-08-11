"""Capture ↔ task linking (optional FK + CLI)."""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest
from sqlalchemy import select, text

from taskman.cli import main
from taskman.db import Session, upgrade_head
from taskman.config import find_project
from taskman.models import Capture, Project, Task

MARKER = "capture-task-link-test"


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
        pid = proj.id
        session.execute(
            text(
                "UPDATE taskman_capture SET task_id = NULL "
                "WHERE project_id = :pid AND summary LIKE :m"
            ),
            {"pid": pid, "m": f"%{MARKER}%"},
        )
        session.execute(
            text("DELETE FROM taskman_capture WHERE project_id = :pid AND summary LIKE :m"),
            {"pid": pid, "m": f"%{MARKER}%"},
        )
        session.execute(
            text("DELETE FROM taskman_task WHERE project_id = :pid AND title LIKE :m"),
            {"pid": pid, "m": f"%{MARKER}%"},
        )
        session.commit()


def _run(argv: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(argv)
    return buf.getvalue()


def test_capture_add_auto_links_task_from_summary_prefix():
    out = _run(["task", "add", f"Target task {MARKER}", "--source", "tests"])
    task_id = int(out.split("#")[1].split()[0])

    out = _run(
        [
            "capture",
            "add",
            "--kind",
            "qa",
            "--summary",
            f"#{task_id}: verify lane {MARKER}",
        ]
    )
    assert f"task=#{task_id}" in out

    with Session() as session:
        cap = session.scalar(
            select(Capture)
            .where(Capture.summary.like(f"%{MARKER}%"))
            .order_by(Capture.id.desc())
        )
        assert cap is not None
        assert cap.task_id == task_id


def test_capture_link_and_show():
    out = _run(["task", "add", f"Show task {MARKER}", "--source", "tests"])
    task_id = int(out.split("#")[1].split()[0])

    out = _run(
        [
            "capture",
            "add",
            "--kind",
            "plan",
            "--summary",
            f"Unlinked plan {MARKER}",
        ]
    )
    cap_id = int(out.split("#")[1].split()[0])

    _run(["capture", "link", str(cap_id), "--task", str(task_id)])

    out = _run(["task", "show", str(task_id)])
    assert f"#{cap_id}" in out
    assert f"Unlinked plan {MARKER}" in out


def test_task_add_from_capture_promotes_and_links():
    out = _run(
        [
            "capture",
            "add",
            "--kind",
            "plan",
            "--summary",
            f"Future idea {MARKER}",
            "--body",
            "Detailed scope for the idea.",
            "--source",
            "tests/from-capture",
        ]
    )
    cap_id = int(out.split("#")[1].split()[0])

    out = _run(
        [
            "task",
            "add",
            "--from-capture",
            str(cap_id),
            "--source",
            "tests",
            "-t",
            "data-db",
        ]
    )
    task_id = int(out.split("#")[1].split()[0])
    assert f"capture=#{cap_id}" in out

    with Session() as session:
        cap = session.get(Capture, cap_id)
        task = session.get(Task, task_id)
        assert cap is not None and task is not None
        assert cap.task_id == task_id
        assert "Future idea" in task.title
        assert "Detailed scope" in task.notes
        assert f"Promoted from capture #{cap_id}" in task.notes


def test_capture_list_unlinked_filter():
    out = _run(
        [
            "capture",
            "add",
            "--kind",
            "plan",
            "--summary",
            f"Orphan plan {MARKER}",
        ]
    )
    assert f"Orphan plan {MARKER}" in out

    out = _run(["capture", "list", "--unlinked", "--limit", "200"])
    assert f"Orphan plan {MARKER}" in out
