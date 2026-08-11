"""`taskman recommend next` — rule-based next-work suggestions."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text, update

from taskman.cli import main
from taskman.db import Session, upgrade_head
from taskman.config import find_project
from taskman.models import Project, Task

MARKER = "recommend-next-test"
TAG = "recommend-next-test-tag"


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
        session.execute(
            text("DELETE FROM taskman_feature WHERE project_id = :pid AND title LIKE :m"),
            {"pid": proj.id, "m": f"%{MARKER}%"},
        )
        session.commit()


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


def test_stale_in_progress_penalty_in_reason():
    task_id = _add("stale wip", priority="high", status="in_progress")
    stale_at = datetime.now(UTC) - timedelta(days=10)
    with Session() as session:
        session.execute(
            update(Task).where(Task.id == task_id).values(updated_at=stale_at)
        )
        session.commit()

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


def test_tag_filter_excludes_non_matching():
    tagged = _add("tagged", priority="keystone", status="todo")
    untagged = _add("untagged", priority="high", status="todo")
    _run(["task", "set", str(untagged), "--tags", ""])

    out = _recommend()

    assert f"#{tagged}" in out
    assert f"#{untagged}" not in out
