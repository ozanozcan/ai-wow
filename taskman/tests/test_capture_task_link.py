"""Capture ↔ task linking (optional link + CLI)."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

from taskman.cli import main
from taskman.eventlog import store

MARKER = "capture-task-link-test"


def _run(argv: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(argv)
    return buf.getvalue()


def test_capture_add_auto_links_task_from_summary_prefix(board_dir: Path):
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

    caps = [
        c
        for c in store.state(board_dir)["capture"].values()
        if MARKER in (c.get("summary") or "")
    ]
    assert caps
    assert max(caps, key=lambda c: c["id"])["task_id"] == task_id


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


def test_task_add_from_capture_promotes_and_links(board_dir: Path):
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

    state = store.state(board_dir)
    cap = state["capture"][cap_id]
    task = state["task"][task_id]
    assert cap["task_id"] == task_id
    assert "Future idea" in task["title"]
    assert "Detailed scope" in task["notes"]
    assert f"Promoted from capture #{cap_id}" in task["notes"]


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
