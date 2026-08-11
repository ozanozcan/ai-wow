#!/usr/bin/env python3
"""Mandatory plan→board import gate after /mow plan.

Wraps ``taskman plan from-decisions`` so dispatch on disk and Postgres board
stay in sync. Refuses hand-off on non-zero exit.

Usage:
  python -m taskman.mow.plan_import docs/plans/<stem>
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

# Set at call time in main(), not at import time (fixes W5: cwd changes after import).
_ROOT: Path | None = None
_VENV_PYTHON: Path | None = None

_FEATURE_RE = re.compile(r"feature\s+#(\d+)", re.I)
_TASK_LINE_RE = re.compile(r"^\s*#(\d+)\b", re.M)


def resolve_dispatch(stem_dir: Path) -> tuple[Path, Path]:
    """Accept ``docs/plans/<stem>`` or ``…/<stem>/dispatch``; return dispatch + INDEX."""
    dispatch = stem_dir / "dispatch" if (stem_dir / "dispatch").is_dir() else stem_dir
    if dispatch.name != "dispatch":
        raise ValueError(f"expected …/<stem> or …/<stem>/dispatch, got {stem_dir}")
    return dispatch, dispatch / "INDEX.md"


def count_briefs(dispatch: Path) -> int:
    """Count ``NN-*.md`` lane briefs in a dispatch folder."""
    return len(list(dispatch.glob("[0-9][0-9]-*.md")))


def _default_run_cmd(argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        argv,
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


def _format_summary(stdout: str) -> str:
    """Extract feature + task ids from taskman stdout for operator summary."""
    feature_m = _FEATURE_RE.search(stdout)
    task_ids = _TASK_LINE_RE.findall(stdout)
    lines: list[str] = []
    if feature_m:
        lines.append(f"feature #{feature_m.group(1)}")
    for tid in task_ids:
        lines.append(f"  task #{tid}")
    if lines:
        return "\n".join(lines)
    return stdout.strip()


def run_plan_import(
    stem_dir: Path,
    *,
    repo_root: Path | None = None,
    python: Path | None = None,
    run_cmd: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> tuple[int, str]:
    """Run import gate. Return ``(exit_code, combined_output_message)``."""
    root = repo_root or _ROOT
    runner = run_cmd or _default_run_cmd

    try:
        dispatch, index_path = resolve_dispatch(stem_dir.resolve())
    except ValueError as exc:
        return 1, str(exc)

    if not index_path.is_file():
        return 1, f"missing dispatch: {index_path}"

    if count_briefs(dispatch) == 0:
        return 1, f"{dispatch}: no NN-*.md briefs in dispatch"

    py = python or (_VENV_PYTHON if _VENV_PYTHON and _VENV_PYTHON.is_file() else Path(sys.executable))
    argv = [str(py), "-m", "taskman", "plan", "from-decisions", str(dispatch)]
    proc = runner(argv, cwd=root)

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "from-decisions failed").strip()
        return 1, err

    summary = _format_summary(proc.stdout or "")
    stem_label = stem_dir.resolve()
    return 0, f"mow plan import OK: {stem_label}\n{summary}"


def main(argv: list[str] | None = None) -> int:
    global _ROOT, _VENV_PYTHON
    _ROOT = _ROOT or Path.cwd()
    _VENV_PYTHON = _VENV_PYTHON or (_ROOT / ".venv" / "bin" / "python")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stem", type=Path, help="docs/plans/<stem> or …/dispatch")
    p.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    args = p.parse_args(argv)

    stem = args.stem.resolve()
    if not stem.exists():
        print(f"not found: {stem}", file=sys.stderr)
        return 1

    code, message = run_plan_import(stem, repo_root=args.repo_root)
    if code != 0:
        print("mow plan import FAILED:", file=sys.stderr)
        print(f"  - {message}", file=sys.stderr)
    else:
        print(message)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
