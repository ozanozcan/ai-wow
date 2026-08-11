#!/usr/bin/env python3
"""Deterministic /wrap-up gate — unattributed paths + stale in_progress.

Thin wrapper around ``taskman wrapup gate`` so skills can call a stable path:

  python -m taskman.mow.wrapup_reconcile
  python -m taskman.mow.wrapup_reconcile --since <sha>
  python -m taskman.mow.wrapup_reconcile --json

Exit 0 = clear. Exit 1 = worklists nonempty. Exit 2 = usage / no marker.

Sibling note (d#868): the wrapup gate attributes by *path*, not author — a second
session's edit to a file already claimed by an open lane task's Files in scope
rides that lane's attribution and never appears in the second session's
unattributed list (concurrent writes to a *claimed file* vs a shared plan).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Set at call time in main(), not at import time (fixes W5: cwd changes after import).
_ROOT: Path | None = None
_VENV_PYTHON: Path | None = None


def main(argv: list[str] | None = None) -> int:
    global _ROOT, _VENV_PYTHON
    _ROOT = _ROOT or Path.cwd()
    _VENV_PYTHON = _VENV_PYTHON or (_ROOT / ".venv" / "bin" / "python")
    args = list(argv if argv is not None else sys.argv[1:])
    py = str(_VENV_PYTHON if _VENV_PYTHON and _VENV_PYTHON.is_file() else sys.executable)
    cmd = [py, "-m", "taskman", "wrapup", "gate", *args]
    proc = subprocess.run(cmd, cwd=str(_ROOT))  # noqa: S603
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
