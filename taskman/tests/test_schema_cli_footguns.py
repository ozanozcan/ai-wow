"""Footgun fixes + decision CLI (d#856, d#865, d#866)."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from taskman.cli import main
from taskman.eventlog import store

MARKER = "schema-cli-footgun"


def _run(argv: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(argv)
    return buf.getvalue()


def test_task_set_add_tag_rm_tag_and_replace(board_dir: Path):
    out = _run(
        ["task", "add", f"Tagged {MARKER}", "--source", "tests", "-t", "a,b"]
    )
    task_id = int(out.split("#")[1].split()[0])

    _run(["task", "set", str(task_id), "--add-tag", "x"])
    assert store.state(board_dir)["task"][task_id]["tags"] == ["a", "b", "x"]

    _run(["task", "set", str(task_id), "--rm-tag", "a"])
    assert store.state(board_dir)["task"][task_id]["tags"] == ["b", "x"]

    _run(["task", "set", str(task_id), "-t", "c"])
    assert store.state(board_dir)["task"][task_id]["tags"] == ["c"]


def test_task_set_pbi_reparents_under_feature(board_dir: Path):
    out = _run(["feature", "add", f"Feat {MARKER}"])
    feat_id = int(out.split("#")[1].split()[0])
    out = _run(["pbi", "add", f"PBI {MARKER}", "--feature", str(feat_id)])
    pbi_id = int(out.split("#")[1].split()[0])
    out = _run(["task", "add", f"Orphan {MARKER}", "--source", "tests"])
    task_id = int(out.split("#")[1].split()[0])

    _run(["task", "set", str(task_id), "--pbi", str(pbi_id)])

    state = store.state(board_dir)
    assert state["task"][task_id]["pbi_id"] == pbi_id
    assert state["pbi"][pbi_id]["feature_id"] == feat_id

    board = _run(["board"])
    assert f"Orphan {MARKER}" in board
    assert f"Feat {MARKER}" in board or f"#{feat_id}" in board


def test_pbi_remove_refuses_with_tasks_unless_force(board_dir: Path):
    out = _run(["feature", "add", f"RmFeat {MARKER}"])
    feat_id = int(out.split("#")[1].split()[0])
    out = _run(["pbi", "add", f"RmPBI {MARKER}", "--feature", str(feat_id)])
    pbi_id = int(out.split("#")[1].split()[0])
    out = _run(
        ["task", "add", f"Child {MARKER}", "--source", "tests", "--pbi", str(pbi_id)]
    )
    task_id = int(out.split("#")[1].split()[0])

    with pytest.raises(SystemExit) as exc:
        _run(["pbi", "remove", str(pbi_id)])
    assert "force" in str(exc.value).lower() or "task" in str(exc.value).lower()

    _run(["pbi", "remove", str(pbi_id), "--force"])
    state = store.state(board_dir)
    assert state["task"][task_id]["pbi_id"] is None
    # Removed = invisible to every reader (the log keeps history; readers filter).
    assert f"RmPBI {MARKER}" not in _run(["pbi", "list"])
    with pytest.raises(SystemExit) as exc:
        _run(["task", "set", str(task_id), "--pbi", str(pbi_id)])
    assert "not found" in str(exc.value)


def test_decision_link_sets_owner_task():
    out = _run(["task", "add", f"LinkOwner {MARKER}", "--source", "tests"])
    task_id = int(out.split("#")[1].split()[0])
    out = _run(
        ["decision", "add", f"Unlinked {MARKER}", "--why", "link later"]
    )
    dec_id = int(out.split("#")[1].split()[0])

    _run(["decision", "link", str(dec_id), "--task", str(task_id)])
    listed = _run(["decision", "list", "--id", str(dec_id)])
    assert f"task=#{task_id}" in listed


def test_from_decisions_feature_override_mints_nothing(tmp_path, board_dir: Path):
    out = _run(["feature", "add", f"Existing {MARKER}"])
    feat_id = int(out.split("#")[1].split()[0])

    plan = {
        "plan": {
            "slug": f"footgun-{MARKER}",
            "title": f"Plan {MARKER}",
            "lane": "platform",
        },
        "items": [
            {
                "id": "only",
                "title": f"Imported {MARKER}",
                "source_ref": f"docs/plans/footgun-{MARKER}/dispatch/01-only.md",
                "priority": "med",
                "status": "backlog",
                "tags": [],
                "depends_on": [],
                "dispatch": {
                    "role": "code-edit",
                    "wave": 1,
                    "background": False,
                    "files": [],
                    "acceptance": "",
                    "do_not": [],
                    "context": [],
                },
            }
        ],
    }
    path = tmp_path / "taskman-plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")

    out = _run(
        ["plan", "from-decisions", str(path), "--feature", str(feat_id)]
    )
    assert f"feature #{feat_id}" in out
    assert "existing" in out

    feats = [
        f
        for f in store.state(board_dir)["feature"].values()
        if MARKER in (f.get("title") or "")
    ]
    assert len(feats) == 1
    assert feats[0]["id"] == feat_id

    assert f"Imported {MARKER}" in out


def test_decision_list_touching_finds_rows_beyond_default_limit():
    """--touching must not lose matches that sit below LIMIT (Wave 3 review)."""
    out = _run(
        [
            "decision",
            "add",
            f"Deep {MARKER}",
            "--why",
            "path match past limit",
            "-t",
            "path:app/domain/formation*.py",
        ]
    )
    deep_id = int(out.split("#")[1].split()[0])

    # Flood newer decisions so a LIMIT-first scan would miss deep_id.
    for i in range(8):
        _run(
            [
                "decision",
                "add",
                f"Flood {i} {MARKER}",
                "--why",
                "noise",
            ]
        )

    listed = _run(
        [
            "decision",
            "list",
            "--touching",
            "app/domain/formation_setup.py",
            "--limit",
            "3",
        ]
    )
    assert f"#{deep_id}" in listed
    assert "Flood" not in listed


def test_capture_list_honors_task_filter():
    task_out = _run(["task", "add", f"Cap task {MARKER}", "--source", "tests"])
    task_id = int(task_out.split("#")[1].split()[0])
    _run(
        [
            "capture",
            "add",
            "--kind",
            "qa",
            "--summary",
            f"linked {MARKER}",
            "--task",
            str(task_id),
        ]
    )
    _run(
        [
            "capture",
            "add",
            "--kind",
            "qa",
            "--summary",
            f"other {MARKER}",
        ]
    )

    listed = _run(
        ["capture", "list", "--task", str(task_id), "--limit", "20"]
    )
    assert f"linked {MARKER}" in listed
    assert f"other {MARKER}" not in listed
