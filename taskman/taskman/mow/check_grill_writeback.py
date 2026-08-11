#!/usr/bin/env python3
"""Fail if a mow stem claims grill done without durable write-back evidence.

Usage:
  python -m taskman.mow.check_grill_writeback docs/plans/<stem>
  python -m taskman.mow.check_grill_writeback docs/plans/<stem>/dispatch

Exit 0 = ok (or skipped grill). Exit 1 = refuse /mow go until write-back is fixed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def _load(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_stem(stem_dir: Path) -> list[str]:
    errors: list[str] = []
    dispatch = stem_dir / "dispatch" if (stem_dir / "dispatch").is_dir() else stem_dir
    if dispatch.name != "dispatch":
        errors.append(f"expected …/<stem> or …/<stem>/dispatch, got {stem_dir}")
        return errors

    plan = dispatch.parent / "plan.md"
    index = dispatch / "INDEX.md"
    if not index.is_file():
        errors.append(f"missing {index}")
        return errors

    index_text = _load(index)
    cp = re.search(
        r"\*\*Grill checkpoint:\*\*\s*(pending|done|skipped)\b(?:\s+(\d{4}-\d{2}-\d{2}))?",
        index_text,
        re.I,
    )
    if not cp:
        errors.append(
            f"{index}: missing **Grill checkpoint:** line "
            "(pending|done YYYY-MM-DD|skipped …)"
        )
        return errors

    status = cp.group(1).lower()
    wb = re.search(r"\*\*Grill write-back:\*\*\s*(.+)", index_text, re.I)

    if status == "pending":
        errors.append(
            f"{index}: grill still pending — run /mow ready before /mow go "
            "(or mark skipped with reason)"
        )
        return errors

    if status == "skipped":
        if not wb:
            errors.append(
                f"{index}: checkpoint skipped but missing **Grill write-back:** skipped"
            )
        return errors

    # done
    if not wb:
        errors.append(
            f"{index}: Grill checkpoint is done but **Grill write-back:** is missing. "
            "Chat-only grill answers are not visible to /mow go lanes — patch plan.md + "
            "briefs, then add the write-back line (see mow skill ready mode)."
        )
        return errors

    wb_body = wb.group(1).strip().lower()
    if wb_body.startswith("pending"):
        errors.append(f"{index}: **Grill write-back:** still pending")
        return errors

    if "no changes" in wb_body or "plan held" in wb_body:
        return errors

    if "plan.md" not in wb_body and "✓" not in wb_body and "ok" not in wb_body:
        # still allow explicit "briefs:" only listings if plan held is implied
        if "brief" not in wb_body:
            errors.append(
                f"{index}: **Grill write-back:** should cite plan.md ✓ and/or "
                "patched briefs (or 'no changes — plan held')"
            )

    if not plan.is_file():
        errors.append(f"missing {plan}")
        return errors

    plan_text = _load(plan)
    if not re.search(r"(?i)decisions locked|grill write-back|grill 20|grill q\d", plan_text):
        errors.append(
            f"{plan}: no Decisions locked / grill write-back evidence — "
            "locked answers must live in plan.md for blind lanes"
        )

    # If write-back lists brief filenames, require they exist
    for name in re.findall(r"(\d{2}-[\w.-]+\.md)", wb.group(1)):
        brief = dispatch / name
        if not brief.is_file():
            errors.append(f"write-back cites missing brief {brief}")

    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    stem = Path(args[0]).resolve()
    if not stem.exists():
        print(f"not found: {stem}", file=sys.stderr)
        return 2
    errs = check_stem(stem)
    if errs:
        print("mow grill write-back check FAILED:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"mow grill write-back check OK: {stem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
