"""Tmp-board isolation for the canonical taskman package suite.

Every test runs chdir'd into a throwaway project directory carrying a
`.taskman.toml` and an empty `board/`, so each test gets a fresh board and no
test can touch a real one. This replaces the throwaway-Postgres guard (d#867):
the event-log port made isolation structural — there is no database to guard,
no opt-in, and nothing to clean up afterwards.

Tests that need a *different* project layout (their own repo root, a missing
marker, ...) build one under their own tmp_path and chdir there; this fixture
only sets the default ground every other test stands on.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def board_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fresh tmp project per test; returns its board dir for state assertions."""
    (tmp_path / ".taskman.toml").write_text(
        '[project]\nslug = "taskman-tests"\nname = "taskman package test project"\n',
        encoding="utf-8",
    )
    board = tmp_path / "board"
    board.mkdir()
    monkeypatch.chdir(tmp_path)
    return board
