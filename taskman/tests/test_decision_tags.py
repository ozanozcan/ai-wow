"""Decision/Capture tags + decision owner-task link (d#852, d#865)."""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest
from sqlalchemy import select, text

from taskman.cli import main
from taskman.config import find_project
from taskman.db import Session, upgrade_head
from taskman.models import Capture, Decision, Project, Task

MARKER = "decision-tags-test"


@pytest.fixture(scope="module", autouse=True)
def _schema_ready():
    upgrade_head()


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    with Session() as session:
        slug, _ = find_project()
        projs = list(
            session.scalars(
                select(Project).where(Project.slug.in_([slug, "workflow"]))
            ).all()
        )
        for proj in projs:
            pid = proj.id
            session.execute(
                text(
                    "UPDATE taskman_decision SET task_id = NULL "
                    "WHERE project_id = :pid AND title LIKE :m"
                ),
                {"pid": pid, "m": f"%{MARKER}%"},
            )
            session.execute(
                text(
                    "DELETE FROM taskman_decision WHERE project_id = :pid AND title LIKE :m"
                ),
                {"pid": pid, "m": f"%{MARKER}%"},
            )
            session.execute(
                text(
                    "DELETE FROM taskman_capture WHERE project_id = :pid AND summary LIKE :m"
                ),
                {"pid": pid, "m": f"%{MARKER}%"},
            )
            session.execute(
                text(
                    "DELETE FROM taskman_task WHERE project_id = :pid AND title LIKE :m"
                ),
                {"pid": pid, "m": f"%{MARKER}%"},
            )
        session.commit()


def _run(argv: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(argv)
    return buf.getvalue()


def test_decision_add_with_tags_persists_array():
    out = _run(
        [
            "decision",
            "add",
            f"Scoped {MARKER}",
            "--why",
            "tags drive preflight",
            "-t",
            "path:app/domain/formation*.py,backend",
        ]
    )
    dec_id = int(out.split("#")[1].split()[0])

    with Session() as session:
        dec = session.get(Decision, dec_id)
        assert dec is not None
        assert dec.tags == ["path:app/domain/formation*.py", "backend"]


def test_decision_list_touching_path_include_and_exclude():
    _run(
        [
            "decision",
            "add",
            f"Formation {MARKER}",
            "--why",
            "path scope",
            "-t",
            "path:app/domain/formation*.py",
        ]
    )
    hit = _run(["decision", "list", "--touching", "app/domain/formation_setup.py"])
    miss = _run(["decision", "list", "--touching", "web/x.tsx"])
    assert f"Formation {MARKER}" in hit
    assert f"Formation {MARKER}" not in miss


def test_decision_add_task_link_survives_list_and_show():
    out = _run(["task", "add", f"Owner {MARKER}", "--source", "tests"])
    task_id = int(out.split("#")[1].split()[0])

    out = _run(
        [
            "decision",
            "add",
            f"Linked {MARKER}",
            "--why",
            "accountability",
            "--task",
            str(task_id),
        ]
    )
    dec_id = int(out.split("#")[1].split()[0])

    listed = _run(["decision", "list", "--id", str(dec_id)])
    shown = _run(["decision", "show", str(dec_id)])
    assert f"task=#{task_id}" in listed
    assert f"task: #{task_id}" in shown

    with Session() as session:
        assert session.get(Decision, dec_id).task_id == task_id


def test_capture_add_with_tags():
    out = _run(
        [
            "capture",
            "add",
            "--kind",
            "grill",
            "--summary",
            f"Tagged grill {MARKER}",
            "-t",
            "path:docs/**/*.md",
        ]
    )
    cap_id = int(out.split("#")[1].split()[0])
    with Session() as session:
        assert session.get(Capture, cap_id).tags == ["path:docs/**/*.md"]


def test_decision_list_tag_filter():
    _run(
        [
            "decision",
            "add",
            f"Area {MARKER}",
            "--why",
            "tag filter",
            "-t",
            "backend,path:app/**",
        ]
    )
    hit = _run(["decision", "list", "--tag", "backend", "--limit", "200"])
    miss = _run(["decision", "list", "--tag", "frontend", "--limit", "200"])
    assert f"Area {MARKER}" in hit
    assert f"Area {MARKER}" not in miss


def test_decision_add_project_workflow_override():
    out = _run(
        [
            "decision",
            "add",
            f"Workflow scoped {MARKER}",
            "--why",
            "no directory toml",
            "--project",
            "workflow",
            "-t",
            "path:docs/workflow/**",
        ]
    )
    assert "[workflow]" in out or "Workflow scoped" in out
    with Session() as session:
        from taskman.cli import WORKFLOW_SLUG

        workflow = session.scalar(select(Project).where(Project.slug == WORKFLOW_SLUG))
        assert workflow is not None
        dec = session.scalar(
            select(Decision)
            .where(Decision.title.like(f"%{MARKER}%"))
            .order_by(Decision.id.desc())
        )
        assert dec is not None
        assert dec.project_id == workflow.id
