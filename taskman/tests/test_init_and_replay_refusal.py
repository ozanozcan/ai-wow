"""`taskman init` (the dbless init-db successor) + fail-closed replay at the CLI.

`init` creates `board/` next to the nearest `.taskman.toml` and prints where.
The old `warn_if_behind` schema-drift warning has no replacement warning: replay
refusing an unrecognised event (naming the line) is the new guard (plan d-p1),
so it is asserted here through a real subcommand, not just the store suite.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from taskman.cli import main


def _run(argv: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(argv)
    return buf.getvalue()


@pytest.fixture()
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".taskman.toml").write_text(
        '[project]\nslug = "init-test"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_init_creates_board_next_to_marker_and_prints_where(project_dir: Path):
    out = _run(["init"])
    board = project_dir / "board"
    assert board.is_dir()
    assert str(board) in out


def test_init_is_idempotent(project_dir: Path):
    _run(["init"])
    out = _run(["init"])  # second run must not fail or clobber
    assert str(project_dir / "board") in out


def test_init_from_a_subdirectory_finds_the_marker(project_dir: Path, monkeypatch):
    sub = project_dir / "src" / "deep"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    _run(["init"])
    assert (project_dir / "board").is_dir()
    assert not (sub / "board").exists()


def test_init_without_marker_refuses(tmp_path_factory: pytest.TempPathFactory, monkeypatch):
    # A fresh tmp dir *outside* this test's tmp_path — the autouse tmp-board
    # fixture plants a .taskman.toml there, and init walks ancestors.
    bare = tmp_path_factory.mktemp("no-marker")
    monkeypatch.chdir(bare)
    with pytest.raises(SystemExit) as exc:
        _run(["init"])
    assert ".taskman.toml" in str(exc.value)


def test_command_refuses_future_event_version_naming_the_line(project_dir: Path):
    _run(["init"])
    log = project_dir / "board" / "events.jsonl"
    log.write_text(
        '{"v":1,"type":"task.add","id":1,"ts":"2026-01-01T00:00:00+00:00",'
        '"fields":{"title":"ok","status":"todo","priority":"med"}}\n'
        '{"v":2,"type":"task.add","id":2,"ts":"2026-01-01T00:00:00+00:00",'
        '"fields":{"title":"future"}}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as exc:
        _run(["board"])
    msg = str(exc.value)
    assert "line 2" in msg
    assert "version" in msg
