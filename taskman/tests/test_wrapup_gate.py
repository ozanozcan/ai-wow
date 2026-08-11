"""Wrap-up reconcile gate — unattributed paths + stale in_progress."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import pytest
from sqlalchemy import select, text

from taskman.cli import main
from taskman.config import find_project
from taskman.db import Session, upgrade_head
from taskman.models import Project, Task
from taskman import wrapup as W

MARKER = "wrapup-gate-test"


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


def _run(argv: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    code = 0
    try:
        with redirect_stdout(out), redirect_stderr(err):
            main(argv)
    except SystemExit as exc:
        code = int(exc.code or 0)
    return code, out.getvalue(), err.getvalue()


def _add(
    title_suffix: str,
    *,
    status: str = "todo",
    files: list[str] | None = None,
    acceptance: str = "",
    tags: str = "",
    role: str = "code-edit",
) -> int:
    argv = [
        "task",
        "add",
        f"{title_suffix} {MARKER}",
        "--status",
        status,
        "--source",
        f"docs/plans/{MARKER}/brief.md",
    ]
    if tags:
        argv.extend(["-t", tags])
    code, out, err = _run(argv)
    assert code == 0, err or out
    tid = int(out.split("#")[1].split()[0])
    brief = {
        "role": role,
        "files": files or [],
        "acceptance": acceptance,
    }
    with Session() as session:
        task = session.get(Task, tid)
        assert task is not None
        task.brief = brief
        if tags:
            task.tags = [t.strip() for t in tags.split(",") if t.strip()]
        session.commit()
    return tid


def test_normalize_and_claim_paths():
    assert W.normalize_path("`workouts/foo.py`") == "workouts/foo.py"
    assert W.normalize_path("see plan later") is None
    claims = {"workouts/", "nutrition/services.py"}
    assert W.path_claimed("workouts/views/snacks.py", claims)
    assert W.path_claimed("nutrition/services.py", claims)
    assert not W.path_claimed("core/urls.py", claims)


def test_cli_gate_blocked_then_cleared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    slug, _ = find_project()
    repo = tmp_path / "repo"
    marker_dir = repo / ".session-markers"
    marker_dir.mkdir(parents=True)
    (repo / ".taskman.toml").write_text(f'[project]\nslug = "{slug}"\n', encoding="utf-8")
    monkeypatch.chdir(repo)

    start_sha = "deadbeef"
    from datetime import datetime, timezone, timedelta

    started = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    marker = marker_dir / "sess-1.json"
    marker.write_text(
        json.dumps(
            {
                "schema": 1,
                "session_id": "sess-1",
                "started_at": started,
                "start_sha": start_sha,
                "worktree": str(repo),
                "branch": "main",
            }
        ),
        encoding="utf-8",
    )

    tid = _add(
        "stale one",
        status="in_progress",
        files=["owned/file.py"],
        acceptance="- `pytest -q`",
    )

    monkeypatch.setattr(
        W,
        "changed_paths",
        lambda worktree, sha: ["owned/file.py", "orphan.py"],
    )

    code, out, _ = _run(["wrapup", "gate", "--marker", str(marker)])
    assert code == 1
    assert "orphan.py" in out
    assert f"#{tid}" in out

    _run(
        [
            "wrapup",
            "record",
            "--attach",
            "orphan.py",
            "--task",
            str(tid),
            "--marker",
            str(marker),
        ]
    )
    _run(
        [
            "wrapup",
            "record",
            "--stale",
            str(tid),
            "--verdict",
            "still-open",
            "--citation",
            "still wiring UI",
            "--marker",
            str(marker),
        ]
    )

    code, out, _ = _run(["wrapup", "gate", "--marker", str(marker)])
    assert code == 0, out
    assert "wrapup gate: OK" in out


def test_unattributed_minus_open_claims(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    slug, _ = find_project()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".taskman.toml").write_text(f'[project]\nslug = "{slug}"\n', encoding="utf-8")
    monkeypatch.chdir(repo)

    # Use real project DB but fake git via monkeypatch on changed_paths.
    tid = _add("owns snacks", status="in_progress", files=["workouts/snack_stats.py"])

    def fake_changed(worktree: Path, start_sha: str) -> list[str]:
        return [
            "workouts/snack_stats.py",
            "nutrition/views.py",
            "docs/session-reports/x.md",
        ]

    monkeypatch.setattr(W, "changed_paths", fake_changed)
    with Session() as session:
        proj = session.scalar(select(Project).where(Project.slug == slug))
        assert proj is not None
        left = W.unattributed_paths(repo, "abc", proj.id)

    assert "nutrition/views.py" in left
    assert "workouts/snack_stats.py" not in left
    assert "docs/session-reports/x.md" not in left
    assert tid > 0


def test_receipt_clears_lists():
    unattributed = ["a.py", "b.py"]
    stale = [
        {
            "id": 1,
            "title": "t",
            "verify": "pytest x",
            "needs_operator_ack": False,
        },
        {
            "id": 2,
            "title": "design",
            "verify": None,
            "needs_operator_ack": True,
        },
    ]
    receipt = {
        "unattributed": {"a.py": {"action": "attach", "task_id": 9}},
        "stale": {
            "1": {"verdict": "done", "citation": "commit abc", "verify_ok": True},
            "2": {
                "verdict": "still-open",
                "citation": "spike unfinished",
            },
        },
    }
    left_u, left_s = W.apply_receipt(unattributed, stale, receipt)
    assert left_u == ["b.py"]
    assert left_s == []


def test_done_design_requires_operator_ack():
    stale = [
        {
            "id": 3,
            "title": "pose",
            "verify": None,
            "needs_operator_ack": True,
        }
    ]
    receipt = {
        "unattributed": {},
        "stale": {"3": {"verdict": "done", "citation": "wrote report"}},
    }
    _, left_s = W.apply_receipt([], stale, receipt)
    assert len(left_s) == 1

    receipt["stale"]["3"]["operator_ack"] = True
    _, left_s = W.apply_receipt([], stale, receipt)
    assert left_s == []


def test_done_with_verify_requires_verify_ok():
    stale = [
        {
            "id": 4,
            "title": "code",
            "verify": "pytest tests/x.py",
            "needs_operator_ack": False,
        }
    ]
    receipt = {
        "unattributed": {},
        "stale": {"4": {"verdict": "done", "citation": "looks good"}},
    }
    _, left_s = W.apply_receipt([], stale, receipt)
    assert len(left_s) == 1

    receipt["stale"]["4"]["verify_ok"] = True
    _, left_s = W.apply_receipt([], stale, receipt)
    assert left_s == []


def test_extract_verify_and_design_flags():
    t = Task(title="x", status="in_progress", tags=["kind:design"], brief={})
    assert W.is_design_ticket(t)
    t2 = Task(
        title="y",
        status="in_progress",
        tags=[],
        brief={
            "role": "code-edit",
            "acceptance": "- SHALL x\n- `pytest tests/workouts/test_x.py -q`",
        },
    )
    assert W.extract_verify_command(t2) == "pytest tests/workouts/test_x.py -q"
    assert not W.is_design_ticket(t2)
