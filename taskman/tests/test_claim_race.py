"""`task claim` CAS end-to-end: two racing *processes*, one winner.

The store's claim is a test-and-set under the board lock; this proves the CLI
wiring keeps it that way across process boundaries — exactly one claimer exits
0, and the loser's stderr names who holds the claim (fetched from state after
the lost claim, since the store's False return carries no claimant).
"""

from __future__ import annotations

import io
import subprocess
import sys
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
        '[project]\nslug = "claim-race-test"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    _run(["init"])
    return tmp_path


def test_loser_message_names_the_existing_claimant(project_dir: Path):
    out = _run(["task", "add", "contested", "--source", "tests"])
    task_id = int(out.split("#")[1].split()[0])
    _run(["task", "claim", str(task_id), "--agent", "alice"])

    with pytest.raises(SystemExit) as exc:
        _run(["task", "claim", str(task_id), "--agent", "bob"])
    msg = str(exc.value)
    assert "alice" in msg
    assert str(task_id) in msg


def test_two_racing_processes_exactly_one_wins(project_dir: Path):
    out = _run(["task", "add", "contested", "--source", "tests"])
    task_id = int(out.split("#")[1].split()[0])

    def spawn(agent: str) -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, "-m", "taskman", "task", "claim", str(task_id),
             "--agent", agent],
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    procs = {agent: spawn(agent) for agent in ("racer-a", "racer-b")}
    results = {agent: (p.wait(timeout=60), *p.communicate()) for agent, p in procs.items()}

    winners = [a for a, (code, _out, _err) in results.items() if code == 0]
    losers = [a for a in results if a not in winners]
    assert len(winners) == 1, f"expected exactly one winner: {results}"
    assert len(losers) == 1

    # The loser is told who holds the claim — the winner, by name.
    _code, _out, loser_err = results[losers[0]]
    assert winners[0] in loser_err
