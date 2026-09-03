"""Decision/Capture tags + decision owner-task link (d#852, d#865)."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

from taskman.cli import main
from taskman.eventlog import store

MARKER = "decision-tags-test"


def _run(argv: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(argv)
    return buf.getvalue()


def test_decision_add_with_tags_persists_array(board_dir: Path):
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

    dec = store.state(board_dir)["decision"][dec_id]
    assert dec["tags"] == ["path:app/domain/formation*.py", "backend"]


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


def test_decision_add_task_link_survives_list_and_show(board_dir: Path):
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

    assert store.state(board_dir)["decision"][dec_id]["task_id"] == task_id


def test_capture_add_with_tags(board_dir: Path):
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
    assert store.state(board_dir)["capture"][cap_id]["tags"] == ["path:docs/**/*.md"]


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
