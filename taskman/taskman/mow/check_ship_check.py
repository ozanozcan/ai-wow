#!/usr/bin/env python3
"""Fail if a mow stem is about to be flipped `shipped` without a ship-check record.

The ship-check gate was prose-only: /mow go §4 said "invoke the ship-check skill
before setting registry Status: shipped", and nothing read it back. A run could
write its action report, flip the registry and look finished having never compared
plan.md against the diff — which is the one comparison the gate exists to force.

What a script can and cannot do here: it cannot judge whether the code matches the
plan (that is the skill's Layer 1, and it needs a reader). It can refuse to let the
run call itself shipped until a verdict exists, is bound to the plan it reviewed,
and accounts for every Critical Layer-1 miss. That is what this checks.

The record is one line in the stem's action report:

  **Ship-check:** done 2026-09-02 · plan sha256:1a2b3c4d · L1 0 critical · L2 1 critical · L3 0 critical

and, when Layer 1 has Criticals, one waiver entry per Critical:

  **Ship-check waivers:** L1 missing CSV export — deferred to stem `exports`; L1 no audit log — fixed in-run

`--emit` prints the line with today's date and the live plan digest, but requires
the counts as arguments: the tool will not invent a verdict on the reviewer's behalf.

Usage:
  python -m taskman.mow.check_ship_check docs/plans/<stem>
  python -m taskman.mow.check_ship_check docs/plans/<stem> --emit --l1 0 --l2 1 --l3 0

Exit 0 = a ship-check verdict is on record. Exit 1 = refuse the `shipped` flip.
Exit 2 = bad usage / stem not found.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import re
import sys
from pathlib import Path

# One line, both markers optional-whitespace tolerant. Deliberately anchored to a
# single line: a verdict spread over a paragraph is what made the prose version
# unreadable, and half a regex over free text is worse than no check (L40).
_MARKER = re.compile(r"^\*\*Ship-check:\*\*\s*(?P<body>.+)$", re.M)
_WAIVERS = re.compile(r"^\*\*Ship-check waivers:\*\*\s*(?P<body>.+)$", re.M)
_DIGEST = re.compile(r"plan\s+sha256:(?P<hex>[0-9a-f]{8,64})\b", re.I)
_LAYER = re.compile(r"\bL(?P<n>[123])\s+(?P<count>\d+)\s+critical\b", re.I)
_DATE = re.compile(r"\bdone\s+(?P<date>\d{4}-\d{2}-\d{2})\b", re.I)

# A waiver whose reason is "n/a", "ok" or "see above" records nothing. Twelve
# characters is not a quality bar, it is a floor under the empty gesture.
_MIN_REASON = 12

DIGEST_LEN = 8


def plan_digest(plan_path: Path) -> str:
    """First DIGEST_LEN hex of sha256 over plan.md's bytes."""
    return hashlib.sha256(plan_path.read_bytes()).hexdigest()[:DIGEST_LEN]


def _split_waivers(body: str) -> list[str]:
    return [part.strip() for part in body.split(";") if part.strip()]


def check_stem(stem_dir: Path) -> list[str]:
    errors: list[str] = []

    stem = stem_dir.parent if stem_dir.name == "dispatch" else stem_dir
    plan = stem / "plan.md"
    report = stem / "action-report.md"

    if not plan.is_file():
        errors.append(f"missing {plan} — ship-check has no benchmark to compare against")
        return errors

    if not report.is_file():
        errors.append(
            f"missing {report} — /mow go Integrate writes the action report, and the "
            "ship-check verdict lives in it"
        )
        return errors

    text = report.read_text(encoding="utf-8")

    marker = _MARKER.search(text)
    if not marker:
        errors.append(
            f"{report}: no **Ship-check:** line. Run the ship-check skill against "
            "plan.md + the shipped diff, then record the verdict "
            "(`--emit --l1 N --l2 N --l3 N` prints the line)."
        )
        return errors

    body = marker.group("body").strip()

    if re.match(r"(?i)\bpending\b", body):
        errors.append(f"{report}: **Ship-check:** still pending")
        return errors

    if not _DATE.search(body):
        errors.append(
            f"{report}: **Ship-check:** must read `done YYYY-MM-DD` — got {body!r}"
        )

    digest = _DIGEST.search(body)
    if not digest:
        errors.append(
            f"{report}: **Ship-check:** missing `plan sha256:<hex>` — without it the "
            "verdict is not bound to the plan it reviewed"
        )
    else:
        live = plan_digest(plan)
        recorded = digest.group("hex")[:DIGEST_LEN]
        if recorded != live:
            errors.append(
                f"{report}: ship-check reviewed plan.md at sha256:{recorded}, but "
                f"{plan} is now sha256:{live} — the plan changed after the review. "
                "Re-run ship-check."
            )

    layers = {m.group("n"): int(m.group("count")) for m in _LAYER.finditer(body)}
    missing = [n for n in ("1", "2", "3") if n not in layers]
    if missing:
        errors.append(
            f"{report}: **Ship-check:** missing Layer "
            f"{', '.join(missing)} count(s) — the skill reports three layers "
            "side by side and a collapsed verdict hides a Layer-1 miss"
        )

    l1 = layers.get("1", 0)
    if l1:
        waivers = _WAIVERS.search(text)
        entries = _split_waivers(waivers.group("body")) if waivers else []
        if len(entries) < l1:
            errors.append(
                f"{report}: Layer 1 reports {l1} Critical(s) but "
                f"**Ship-check waivers:** accounts for {len(entries)} — a Critical spec "
                "miss blocks `shipped` until it is fixed or the operator defers it "
                "in writing (one `;`-separated entry each)"
            )
        for entry in entries:
            reason = entry.split("—", 1)[-1].strip() if "—" in entry else ""
            if len(reason) < _MIN_REASON:
                errors.append(
                    f"{report}: waiver {entry!r} has no reason — write "
                    "`L1 <what was missed> — <fixed in-run | deferred, why>`"
                )

    return errors


def emit_marker(stem_dir: Path, l1: int, l2: int, l3: int, today: str) -> str:
    stem = stem_dir.parent if stem_dir.name == "dispatch" else stem_dir
    digest = plan_digest(stem / "plan.md")
    return (
        f"**Ship-check:** done {today} · plan sha256:{digest} · "
        f"L1 {l1} critical · L2 {l2} critical · L3 {l3} critical"
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stem", type=Path, help="docs/plans/<stem> or …/<stem>/dispatch")
    p.add_argument("--emit", action="store_true", help="print the marker line and exit")
    p.add_argument("--l1", type=int, help="Layer 1 (spec) Critical count, with --emit")
    p.add_argument("--l2", type=int, help="Layer 2 (standards) Critical count")
    p.add_argument("--l3", type=int, help="Layer 3 (production) Critical count")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)

    stem = args.stem.resolve()
    if not stem.exists():
        print(f"not found: {stem}", file=sys.stderr)
        return 2

    if args.emit:
        if None in (args.l1, args.l2, args.l3):
            print(
                "--emit needs --l1/--l2/--l3: the verdict is the reviewer's, "
                "not this script's",
                file=sys.stderr,
            )
            return 2
        target = stem.parent if stem.name == "dispatch" else stem
        if not (target / "plan.md").is_file():
            print(f"missing {target / 'plan.md'}", file=sys.stderr)
            return 2
        print(emit_marker(stem, args.l1, args.l2, args.l3, datetime.date.today().isoformat()))
        return 0

    errors = check_stem(stem)
    if errors:
        print("mow ship-check gate FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"mow ship-check gate OK: {stem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
