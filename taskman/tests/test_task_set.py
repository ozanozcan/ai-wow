"""`task set` — edit a task's fields after creation."""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest
from sqlalchemy import select, text

from taskman.cli import main
from taskman.db import Session, upgrade_head
from taskman.config import find_project
from taskman.models import Project, Task

MARKER = "task-set-test"


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


def _run(argv: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(argv)
    return buf.getvalue()


def _add(priority: str = "med", **fields: str) -> int:
    argv = ["task", "add", f"Settable {MARKER}", "-p", priority, "--source", "tests"]
    for name, value in fields.items():
        argv += [f"--{name}", value]
    out = _run(argv)
    return int(out.split("#")[1].split()[0])


def test_set_priority_updates_task_and_reports_old_and_new():
    task_id = _add("med")

    out = _run(["task", "set", str(task_id), "--priority", "high"])
    assert "med" in out
    assert "high" in out

    with Session() as session:
        assert session.get(Task, task_id).priority == "high"


def test_set_priority_is_visible_on_show_and_board():
    task_id = _add("low")
    _run(["task", "set", str(task_id), "--priority", "keystone"])

    assert "priority: keystone" in _run(["task", "show", str(task_id)])
    assert "[keystone]" in _run(["board"])


def test_set_priority_rejects_invalid_value_and_leaves_task_untouched():
    task_id = _add("med")

    with pytest.raises(SystemExit) as exc:
        _run(["task", "set", str(task_id), "--priority", "urgent"])
    assert "urgent" in str(exc.value)

    with Session() as session:
        assert session.get(Task, task_id).priority == "med"


def test_set_priority_rejects_unknown_task_id():
    # Asserts on the _get_task message specifically: argparse's own bail-out is
    # SystemExit(2), so a missing/renamed subcommand can no longer pass this.
    with pytest.raises(SystemExit) as exc:
        _run(["task", "set", "99999999", "--priority", "high"])
    msg = str(exc.value)
    assert "99999999" in msg
    assert "not found" in msg


def test_set_lane_surface_afk_notes_and_tags_together():
    task_id = _add("med", lane="product")

    _run(
        [
            "task", "set", str(task_id),
            "--lane", "platform",
            "--surface", "prod-internal",
            "--afk", "yes",
            "--notes", "rewritten note",
            "--tags", "alpha,beta",
        ]
    )

    with Session() as session:
        task = session.get(Task, task_id)
        assert task.lane == "platform"
        assert task.surface == "prod-internal"
        assert task.afk == "yes"
        assert task.notes == "rewritten note"
        assert task.tags == ["alpha", "beta"]


def test_set_tags_replaces_rather_than_appends():
    task_id = _add("med", tags="alpha,beta")

    _run(["task", "set", str(task_id), "--tags", "gamma"])

    with Session() as session:
        assert session.get(Task, task_id).tags == ["gamma"]


def test_set_accepts_empty_string_to_clear_a_field():
    task_id = _add("med", lane="product", notes="original")

    _run(["task", "set", str(task_id), "--lane", "", "--notes", ""])

    with Session() as session:
        task = session.get(Task, task_id)
        assert task.lane == ""
        assert task.notes == ""


def test_set_leaves_unmentioned_fields_untouched():
    task_id = _add("high", lane="product", notes="keep me", tags="alpha")

    _run(["task", "set", str(task_id), "--lane", "platform"])

    with Session() as session:
        task = session.get(Task, task_id)
        assert task.lane == "platform"
        assert task.priority == "high"
        assert task.notes == "keep me"
        assert task.tags == ["alpha"]


def test_set_with_no_fields_is_an_error():
    task_id = _add("med")

    with pytest.raises(SystemExit) as exc:
        _run(["task", "set", str(task_id)])
    assert "no fields" in str(exc.value)


def test_set_rejects_invalid_lane_and_leaves_task_untouched():
    task_id = _add("med", lane="product", notes="original")

    with pytest.raises(SystemExit) as exc:
        _run(["task", "set", str(task_id), "--lane", "sideways", "--notes", "clobbered"])
    assert "sideways" in str(exc.value)

    with Session() as session:
        task = session.get(Task, task_id)
        assert task.lane == "product"
        assert task.notes == "original"


def test_set_reports_each_changed_field():
    task_id = _add("med", lane="product")

    out = _run(["task", "set", str(task_id), "--priority", "high", "--lane", "platform"])

    assert "priority" in out and "med" in out and "high" in out
    assert "lane" in out and "product" in out and "platform" in out
