#!/usr/bin/env python3
"""Fail if the primary project's taskman/ tree drifts from the sibling project's copy.

Compares the entire taskman/ tree (not only alembic/versions/). Excludes
only generated artifacts (__pycache__/, *.pyc).

Usage:
  python -m taskman.mow.check_drift [sibling_project_root]
  python -m taskman.mow.check_drift --left DIR --right DIR

Default sibling root: ~/projects/web-app
Exit 0 = identical. Exit 1 = drift (differing paths printed). Exit 2 = usage.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path.cwd()
# Optional: TASKMAN_SIBLING_ROOT names a sibling project holding a second copy of
# taskman/. Unset means "no sibling configured" and the drift check no-ops.
_DEFAULT_SIBLING = (
    Path(os.environ["TASKMAN_SIBLING_ROOT"]).expanduser()
    if os.environ.get("TASKMAN_SIBLING_ROOT")
    else None
)


def _iter_source_files(tree: Path) -> dict[str, Path]:
    """Map relative posix path -> absolute path for source files under tree."""
    out: dict[str, Path] = {}
    if not tree.is_dir():
        return out
    for path in sorted(tree.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(tree)
        parts = rel.parts
        if "__pycache__" in parts:
            continue
        if path.suffix == ".pyc" or path.name.endswith(".pyc"):
            continue
        out[rel.as_posix()] = path
    return out


def compare_trees(left: Path, right: Path) -> list[str]:
    """Return sorted relative paths that differ in name or content."""
    left_files = _iter_source_files(left)
    right_files = _iter_source_files(right)
    diffs: list[str] = []

    only_left = set(left_files) - set(right_files)
    only_right = set(right_files) - set(left_files)
    for rel in sorted(only_left | only_right):
        diffs.append(rel)

    for rel in sorted(set(left_files) & set(right_files)):
        if left_files[rel].read_bytes() != right_files[rel].read_bytes():
            diffs.append(rel)

    return diffs


def check_drift(
    *,
    local_taskman: Path | None = None,
    sibling_root: Path | None = None,
    left: Path | None = None,
    right: Path | None = None,
) -> list[str]:
    """Compare two taskman trees; return list of differing relative paths."""
    if left is not None and right is not None:
        return compare_trees(left, right)
    local = local_taskman if local_taskman is not None else _ROOT / "taskman"
    sibling_src = sibling_root if sibling_root is not None else _DEFAULT_SIBLING
    if sibling_src is None:
        return []
    sibling = Path(sibling_src).expanduser()
    # Vendored copies are gone once repos consume the canonical package — drift is moot.
    if not local.is_dir() or not (sibling / "taskman").is_dir():
        return []
    return compare_trees(local, sibling / "taskman")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "sibling_root",
        nargs="?",
        type=Path,
        default=None,
        help="sibling project root (default: $TASKMAN_SIBLING_ROOT, else none)",
    )
    p.add_argument(
        "--left",
        type=Path,
        default=None,
        help="explicit left taskman/ tree (for tests)",
    )
    p.add_argument(
        "--right",
        type=Path,
        default=None,
        help="explicit right taskman/ tree (for tests)",
    )
    args = p.parse_args(argv)

    if (args.left is None) ^ (args.right is None):
        print("error: --left and --right must be used together", file=sys.stderr)
        return 2
    if args.left is not None and args.sibling_root is not None:
        print("error: do not pass sibling_root with --left/--right", file=sys.stderr)
        return 2

    if args.left is not None:
        left, right = args.left.resolve(), args.right.resolve()
        if not left.is_dir():
            print(f"not found: {left}", file=sys.stderr)
            return 2
        if not right.is_dir():
            print(f"not found: {right}", file=sys.stderr)
            return 2
        diffs = compare_trees(left, right)
        label = f"{left} vs {right}"
    else:
        sibling_src = args.sibling_root or _DEFAULT_SIBLING
        if sibling_src is None:
            print("no sibling root: pass one, or set TASKMAN_SIBLING_ROOT", file=sys.stderr)
            return 2
        sibling = Path(sibling_src).expanduser().resolve()
        left = (_ROOT / "taskman").resolve()
        right = (sibling / "taskman").resolve()
        if not left.is_dir():
            print(f"not found: {left}", file=sys.stderr)
            return 2
        if not right.is_dir():
            print(f"not found: {right}", file=sys.stderr)
            return 2
        diffs = compare_trees(left, right)
        label = f"{left} vs {right}"

    if diffs:
        print("taskman drift check FAILED:", file=sys.stderr)
        for rel in diffs:
            print(f"  - {rel}", file=sys.stderr)
        return 1
    print(f"taskman drift check OK: {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
