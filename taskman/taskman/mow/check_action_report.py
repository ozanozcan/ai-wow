#!/usr/bin/env python3
"""Fail if a mow stem's action report is missing, skeletal, or unlinked.

The action report is the run's primary durable output — the thing anyone reads a
month later to find out what shipped and what was decided — and until this gate
existed nothing read it back. /mow go §4 calls it "required — do not skip" and
lists its sections; a run could flip to `shipped` with no report at all, or with
five headings and no bodies, and nothing would notice.

Section names and frontmatter fields here are taken from the shape already in the
tree (docs/plans/harness-boundary/action-report.md), not invented: this gate has
to pass the best existing report or it is measuring the wrong thing.

An empty section is a failure, but `*None — <reason>*` satisfies it, exactly as the
plan.md register sections work — "None, because …" is a claim someone made, an
omitted section is indistinguishable from one nobody considered.

Usage:
  python -m taskman.mow.check_action_report docs/plans/<stem>

Exit 0 = report is complete. Exit 1 = refuse the `shipped` flip. Exit 2 = usage.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# (canonical name, regex the heading must match). Alternates are real: the Open /
# deferred section is written three ways across existing reports.
_SECTIONS: list[tuple[str, str]] = [
    ("Outcome", r"outcome"),
    ("Wave results", r"wave results?"),
    ("Decisions locked", r"decisions locked"),
    ("Open / deferred", r"open\s*(/|and|,)?\s*deferred|deferred|open follow-?ups?"),
    ("Verify", r"verif(y|ication)"),
]

_FRONTMATTER = [
    ("Date", r"\*\*Date:\*\*\s*\d{4}-\d{2}-\d{2}"),
    ("Project slug", r"\*\*Project slug:\*\*\s*\S"),
    ("Plan", r"\*\*Plan:\*\*\s*\S"),
    ("Dispatch", r"\*\*Dispatch:\*\*\s*\S"),
]

_HEADING = re.compile(r"^(#{2,3})\s+(.*)$", re.M)
_NONE_MARKER = re.compile(r"^\s*\*?None\s*[—-]\s*\S", re.I | re.M)


def _sections(text: str) -> dict[str, str]:
    """Map every level-2 heading to its body (nested ### stay inside the body)."""
    out: dict[str, str] = {}
    matches = [m for m in _HEADING.finditer(text) if len(m.group(1)) == 2]
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[m.group(2).strip()] = text[m.end() : end]
    return out


def _has_body(body: str) -> bool:
    """A section with only blank lines, or only sub-headings, is not written."""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return True
    return False


def check_stem(stem_dir: Path) -> list[str]:
    errors: list[str] = []

    stem = stem_dir.parent if stem_dir.name == "dispatch" else stem_dir
    report = stem / "action-report.md"
    dispatch_index = stem / "dispatch" / "INDEX.md"

    if not report.is_file():
        errors.append(
            f"missing {report} — /mow go §4 writes the action report before the "
            "registry flip; a run with no report cannot be marked shipped"
        )
        return errors

    text = report.read_text(encoding="utf-8")
    sections = _sections(text)

    for name, pattern in _FRONTMATTER:
        if not re.search(pattern, text):
            errors.append(f"{report}: frontmatter missing **{name}:**")

    found: dict[str, str] = {}
    for canonical, pattern in _SECTIONS:
        match = next(
            (body for head, body in sections.items() if re.fullmatch(pattern, head.strip(), re.I)),
            None,
        )
        if match is None:
            errors.append(f"{report}: missing `## {canonical}` section")
        else:
            found[canonical] = match
            if not _has_body(match) and not _NONE_MARKER.search(match):
                errors.append(
                    f"{report}: `## {canonical}` is an empty heading — write it, or "
                    "`*None — <reason>*` if there is genuinely nothing"
                )

    verify = found.get("Verify", "")
    if verify:
        if not re.search(r"\*\*Board sync:\*\*", verify):
            errors.append(
                f"{report}: `## Verify` has no **Board sync:** line — record the "
                "`plan mark-shipped` run, or `n/a` with the reason (no taskman here)"
            )
        if not re.search(r"(?i)\*\*P3\b|post-build protocol", verify):
            errors.append(
                f"{report}: `## Verify` has no P3 post-build record — record each step, "
                "or `n/a` with the reason"
            )

    if not dispatch_index.is_file():
        errors.append(f"missing {dispatch_index}")
    elif not re.search(r"\*\*Action report:\*\*", dispatch_index.read_text(encoding="utf-8")):
        errors.append(
            f"{dispatch_index}: missing the "
            "`**Action report:** [`../action-report.md`](../action-report.md)` line"
        )

    return errors


def has_triage_record(stem_dir: Path) -> bool:
    """True when finding-triage is recorded — its own section, or (a)/(b)/(c) in Verify.

    Both shapes exist in the tree; §4.1 describes the second, the one report that
    has actually done it used the first. Callers use this for the cross-check
    against tracker findings — absent findings, triage has nothing to record.
    """
    stem = stem_dir.parent if stem_dir.name == "dispatch" else stem_dir
    report = stem / "action-report.md"
    if not report.is_file():
        return False
    text = report.read_text(encoding="utf-8")
    if any(re.fullmatch(r"(?i)finding[- ]triage", h.strip()) for h in _sections(text)):
        return True
    verify = next(
        (b for h, b in _sections(text).items() if re.fullmatch(r"(?i)verif(y|ication)", h.strip())),
        "",
    )
    return bool(re.search(r"\*\*\(?[abc]\)?\*\*|\(a\) mechanizable|\(b\) convention|\(c\) one-off", verify))


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    stem = Path(args[0]).resolve()
    if not stem.exists():
        print(f"not found: {stem}", file=sys.stderr)
        return 2
    errors = check_stem(stem)
    if errors:
        print("mow action-report gate FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"mow action-report gate OK: {stem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
