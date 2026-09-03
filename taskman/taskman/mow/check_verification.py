#!/usr/bin/env python3
"""Fail if a mow wave's lanes have no durable ## Verification record.

The review gate (§2b.1) said "check each lane's ## Verification block against
its brief's QA contract and its Decisions / Specs pointers". Lane reports
landed in chat, so nothing could read them back — a wave could proceed, and a
run could ship, having never written the block anywhere a later agent could
see. L42: a subagent reporting it checked something leaves no artifact.

This is the disk half. Each lane (or the orchestrator, copying from the
lane's final message) writes `dispatch/verification/<brief>` containing the
four required bullets from the brief template. This script reads those files
against the INDEX and the briefs. It cannot tell whether the commands
actually passed — that is still a reader. It can refuse a missing block, a
block that dropped a pointed decision, or a contract that was never
accounted for.

Usage:
  python -m taskman.mow.check_verification docs/plans/<stem>
  python -m taskman.mow.check_verification docs/plans/<stem> --wave 1

Exit 0 = every named lane has a record. Exit 1 = refuse. Exit 2 = usage.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from taskman.mow.hydrate_specs import parse_pointer_cell
from taskman.mow.preflight import (
    _bullet_lines,
    _section_body,
    _split_lanes_table_extended,
)

_BRIEF_NAME = re.compile(r"(\d{2}-[\w.-]+\.md)")
_LABELS = ("Commands run", "Contract items", "Artifacts", "Decisions honored")
_HONORED_ID = re.compile(r"\b(d|req|task|cap)\s*`?#(\d+)`?", re.I)


def _stem(stem_dir: Path) -> Path:
    return stem_dir.parent if stem_dir.name == "dispatch" else stem_dir


def parse_wave_lane_letters(index_text: str) -> dict[str, list[str]]:
    """Wave number -> lane letters from ## Waves bullets.

    The INDEX writes ``- **Wave 1 (parallel, AFK):** A | B`` — letters sit
    after the colon, not inside parentheses, so the older parser that looked
    for ``A (`` misses every real map in the tree.
    """
    waves: dict[str, list[str]] = {}
    in_waves = False
    for line in index_text.splitlines():
        if line.startswith("## Waves"):
            in_waves = True
            continue
        if in_waves and line.startswith("## "):
            break
        if not in_waves:
            continue
        m = re.match(r"- \*\*Wave\s+(\d+)\b.*?:\*\*\s*(.*)", line)
        if not m:
            continue
        rest = m.group(2)
        letters = [L for L in re.findall(r"\b([A-Z])\b", rest) if L not in {"N"}]
        waves[m.group(1)] = letters
    return waves


def _brief_filename(cell: str) -> str | None:
    m = _BRIEF_NAME.search(cell)
    return m.group(1) if m else None


def _label_value(text: str, label: str) -> str | None:
    """Value of ``- Commands run: …`` (rest of the bullet, possibly multi-line)."""
    pattern = re.compile(
        rf"^[-*]\s*{re.escape(label)}\s*:\s*(.*)$",
        re.M | re.I,
    )
    m = pattern.search(text)
    if not m:
        return None
    parts = [m.group(1).strip()]
    for line in text[m.end() :].splitlines():
        if re.match(r"^[-*]\s+\S", line) or re.match(r"^## ", line):
            break
        stripped = line.strip()
        if stripped:
            parts.append(stripped)
    return " ".join(parts).strip()


def _qa_bullets(brief_text: str) -> list[str]:
    return _bullet_lines(_section_body(brief_text, "QA contract"))


def check_record(lane: str, brief_name: str, brief_text: str, pointers: list[tuple[str, int]], record: str) -> list[str]:
    errors: list[str] = []
    prefix = f"lane {lane} ({brief_name})"
    for label in _LABELS:
        value = _label_value(record, label)
        if value is None:
            errors.append(f"{prefix}: verification missing `{label}:` line")
            continue
        if not value or value.lower() in {"tbd", "todo", "see chat"}:
            errors.append(f"{prefix}: `{label}:` is empty — write what ran, or n/a with a reason")

    honored = _label_value(record, "Decisions honored") or ""
    if pointers:
        found = {(m.group(1).lower(), int(m.group(2))) for m in _HONORED_ID.finditer(honored)}
        for kind, oid in pointers:
            if (kind, oid) not in found:
                errors.append(
                    f"{prefix}: Decisions honored is missing {kind}#{oid} — every INDEX "
                    "pointer needs `d#N: how, file:line` (or the pointer does not belong on this lane)"
                )
    elif honored and "none pointed" not in honored.lower():
        # Cell is `-` but the record didn't say so. Not a miss of a pointer —
        # a missed acknowledgement. Refuse; "none pointed" is one token.
        errors.append(
            f"{prefix}: Decisions / Specs is `-` but Decisions honored does not "
            "say `none pointed`"
        )

    contract = _label_value(record, "Contract items") or ""
    qa = [b for b in _qa_bullets(brief_text) if b.lower() not in {"none", "n/a", "-"}]
    if qa:
        if re.fullmatch(r"(?i)n/a|none|-", contract or ""):
            errors.append(
                f"{prefix}: brief has {len(qa)} QA contract item(s) but Contract items "
                "is n/a — account for each (met / not-applicable + why)"
            )
        elif "all met" not in contract.lower():
            missing = [b for b in qa if b.casefold() not in contract.casefold()]
            # A short paraphrase still counts if they numbered them; only flag
            # when *nothing* from the contract text appears and they didn't
            # claim the lot.
            if len(missing) == len(qa):
                errors.append(
                    f"{prefix}: Contract items does not mention any QA contract bullet "
                    "and does not say `all met`"
                )
    return errors


def check_stem(stem_dir: Path, *, wave: str | None = None) -> list[str]:
    errors: list[str] = []
    stem = _stem(stem_dir)
    dispatch = stem / "dispatch"
    index_path = dispatch / "INDEX.md"
    if not index_path.is_file():
        return [f"missing {index_path}"]

    index_text = index_path.read_text(encoding="utf-8")
    rows = _split_lanes_table_extended(index_text)
    if wave is not None:
        waves = parse_wave_lane_letters(index_text)
        wanted = waves.get(str(wave))
        if not wanted:
            return [
                f"{index_path}: no lanes parsed for wave {wave} — the Waves bullets "
                "need `**Wave N …:** A | B` (letters after the colon)"
            ]
        rows = [r for r in rows if r["lane"] in wanted]

    for row in rows:
        brief_name = _brief_filename(row["brief"])
        if not brief_name:
            errors.append(f"lane {row['lane']}: INDEX Brief cell has no NN-*.md filename")
            continue
        brief_path = dispatch / brief_name
        record_path = dispatch / "verification" / brief_name
        if not record_path.is_file():
            errors.append(
                f"lane {row['lane']} ({brief_name}): missing {record_path} — write the "
                "lane's ## Verification block there before the wave gate (chat is not a record)"
            )
            continue
        brief_text = brief_path.read_text(encoding="utf-8") if brief_path.is_file() else ""
        pointers = parse_pointer_cell(row.get("decisions") or "")
        record = record_path.read_text(encoding="utf-8")
        errors.extend(check_record(row["lane"], brief_name, brief_text, pointers, record))
    return errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stem", type=Path, help="docs/plans/<stem> or …/<stem>/dispatch")
    p.add_argument("--wave", help="only this wave's lanes (review gate); omit for close-out")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)

    stem = args.stem.resolve()
    if not stem.exists():
        print(f"not found: {stem}", file=sys.stderr)
        return 2
    errors = check_stem(stem, wave=args.wave)
    if errors:
        print("mow verification gate FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"mow verification gate OK: {stem}" + (f" (wave {args.wave})" if args.wave else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
