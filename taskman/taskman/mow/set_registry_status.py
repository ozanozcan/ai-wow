#!/usr/bin/env python3
"""Flip a mow stem's status in docs/plans/INDEX.md (registry bookkeeping).

Fixes the recurring failure mode where /mow go writes the action report but
the operator forgets to hand-edit the registry row, leaving /mow list showing
a shipped run as still planned/running.

Flipping to `shipped` runs the close-out gate first (taskman.mow.closeout): the
ship-check verdict, the action report, and the tracker board. Those were all prose
in the mow skill — "required", "do not skip" — with nothing reading them back. This
is the chokepoint every flip already goes through, so it is where the requirements
become enforceable. There is no --force: the sanctioned escapes are a waiver entry
in the action report and a `*None — <reason>*` section, both of which stay auditable,
and the documented last resort is hand-editing the registry row.

Usage:
  python -m taskman.mow.set_registry_status <stem> <planned|running|shipped|paused>
  python -m taskman.mow.set_registry_status <stem> shipped --index docs/plans/INDEX.md

Exit 0 = row updated. Exit 1 = stem row not found. Exit 2 = bad usage.
Exit 3 = close-out gate refused the `shipped` flip.
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

VALID_STATUSES = {"planned", "running", "shipped", "paused"}


def set_status(index_path: Path, stem: str, status: str, today: str) -> bool:
    text = index_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    for i, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6 or cells[0] != stem:
            continue
        cells[4] = today  # Updated
        cells[5] = status  # Status
        lines[i] = "| " + " | ".join(cells) + " |\n"
        index_path.write_text("".join(lines), encoding="utf-8")
        return True

    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stem")
    parser.add_argument("status", choices=sorted(VALID_STATUSES))
    parser.add_argument("--index", default="docs/plans/INDEX.md")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    index_path = Path(args.index)
    if not index_path.is_file():
        print(f"not found: {index_path}", file=sys.stderr)
        return 2

    if args.status == "shipped":
        from taskman.mow.closeout import run_closeout

        stem_dir = index_path.parent / args.stem
        gate_errors, gate_warnings = run_closeout(stem_dir)
        for w in gate_warnings:
            print(f"  ! {w}", file=sys.stderr)
        if gate_errors:
            print(
                f"refusing to flip '{args.stem}' to shipped — close-out gate FAILED:",
                file=sys.stderr,
            )
            for e in gate_errors:
                print(f"  - {e}", file=sys.stderr)
            return 3

    today = datetime.date.today().isoformat()
    if set_status(index_path, args.stem, args.status, today):
        print(f"{index_path}: {args.stem} -> {args.status} (Updated {today})")
        return 0

    print(f"{index_path}: no row found for stem '{args.stem}'", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
