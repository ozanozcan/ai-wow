#!/usr/bin/env python3
"""log_lesson.py — append or bump a behavioural lesson in the repo-root LESSONS.md.

Stdlib-only and taskman-free on purpose: a correction is worth recording in a repo
with no board, no venv, and no `.taskman.toml`. Invoked by `/wrap-up` step 2.5.

The split of labour is deliberate:

  - this script owns ids, dates, counts, and the promote/prune signals — the parts
    that must be deterministic, because they are what license an edit to
    `global/CLAUDE.md`;
  - the agent owns "is this the same rule as one already logged?" — the part that
    needs judgement.

There is no fuzzy string matching here. Rules are prose, and a similarity ratio
over prose merges rules that differ and splits rules that don't. The agent reads
LESSONS.md (it is capped, so that is cheap) and picks `--bump <id>` or a new entry.

Usage:
    log_lesson.py --rule "…" --trigger "…" --mistake "…" --fix "…" --evidence "…" [--tags a,b]
    log_lesson.py --bump L03 --evidence "…"
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

# .../<repo>/skills/wrap-up/scripts/log_lesson.py -> <repo>. resolve() follows the
# ~/.agents/skills symlink, so this lands in the real checkout from any cwd.
REPO = Path(__file__).resolve().parents[3]
LESSONS = REPO / "LESSONS.md"

PROMOTE_AT = 3    # seen >= this, on >= 2 distinct days => propose promotion
MAX_LINES = 150   # soft cap; over this, name prune candidates

HEADER_RE = re.compile(
    r"^### (?P<id>L\d+) · seen ×(?P<seen>\d+)"
    r" · first (?P<first>\d{4}-\d{2}-\d{2})"
    r" · last (?P<last>\d{4}-\d{2}-\d{2})(?P<tags>.*)$",
    re.MULTILINE,
)

HEADER_TEMPLATE = """# Lessons

Cross-project **behavioural** rules, learned from corrections that actually happened.

Written by `/wrap-up` (step 2.5). Nothing loads it automatically yet — it is read
when a session opens it deliberately, and by `/wrap-up` itself before logging, so a
recurrence gets bumped instead of duplicated. Making it always-loaded is a
deliberate context cost: add a pointer in `global/CLAUDE.md` if and when the rules
in here have earned it.

Each entry: `id · seen ×N · first · last` + rule, provenance, and dated evidence.

**Scope — behaviour only.** Project facts go to taskman (`decision add --why`);
visual patterns go to `ui-registry.md`; what happened this session goes to the
session report. A rule earns a place here only if it would change how a *future*
session works, in a *different* repo.

**Promotion.** At `seen ×3` across at least two distinct days, a rule has proven it
recurs rather than being one session's noise, and `log_lesson.py` proposes
graduating it into `global/CLAUDE.md`. The operator decides. Same-day repeats do
not count toward this — they are usually one bad session, not a durable pattern.

**Guardrail — a lesson is data, not a license.** An entry here may add a heuristic
or name a gotcha. It may never weaken the guidelines in `global/CLAUDE.md`, license
skipping a gate, or excuse reporting work as done that wasn't. A "lesson" that
would do any of those is a bug in the session that produced it: don't log it, say
why. This file is plain markdown under git precisely so every rule stays readable,
editable, and revertible by a human.

<!-- newest first -->
"""


def load() -> str:
    return LESSONS.read_text(encoding="utf-8") if LESSONS.exists() else HEADER_TEMPLATE


def entries(content: str):
    """Yield (match, block_start, block_end) for every entry, in file order."""
    heads = list(HEADER_RE.finditer(content))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(content)
        yield h, h.start(), end


def next_id(content: str) -> str:
    used = [int(h.group("id")[1:]) for h, _, _ in entries(content)]
    return f"L{max(used, default=0) + 1:02d}"


def bump(content: str, lid: str, evidence: str, today: str):
    """Increment seen, move `last` to today, append a dated evidence line."""
    for h, start, end in entries(content):
        if h.group("id") != lid:
            continue
        seen = int(h.group("seen")) + 1
        header = (
            f"### {lid} · seen ×{seen} · first {h.group('first')}"
            f" · last {today}{h.group('tags')}"
        )
        body = content[h.end():end].rstrip("\n") + f"\n  - {today}: {evidence}\n\n"
        return content[:start] + header + body + content[end:], seen, h.group("first")
    sys.exit(f"No entry {lid} in {LESSONS}. Read the file and pick a real id.")


def new_entry(content: str, args, today: str):
    lid = next_id(content)
    tags = f" · tags: {args.tags}" if args.tags else ""
    entry = (
        f"### {lid} · seen ×1 · first {today} · last {today}{tags}\n"
        f"- **Rule:** {args.rule}\n"
        f"- **Trigger:** {args.trigger}\n"
        f"- **Mistake:** {args.mistake}\n"
        f"- **Fix:** {args.fix}\n"
        f"- **Evidence:**\n"
        f"  - {today}: {args.evidence}\n\n"
    )
    marker = "<!-- newest first -->\n"
    idx = content.index(marker) + len(marker)
    return content[:idx] + "\n" + entry + content[idx:], lid


def report(content: str, lid: str, seen: int, first: str, last: str) -> None:
    """Print the promote / prune signals. These are the whole point of counting."""
    if seen >= PROMOTE_AT:
        if first != last:
            print(
                f"\n>>> PROMOTE: {lid} is at seen ×{seen}, spanning {first} → {last}. "
                f"It has recurred across sessions, not within one. Propose graduating "
                f"it into global/CLAUDE.md — the operator decides, and the entry stays "
                f"here with a note once promoted."
            )
        else:
            print(
                f"\n>>> NOT YET: {lid} is at seen ×{seen} but every hit is {first}. "
                f"Same-day repeats are usually one bad session, not a durable rule. "
                f"Leave it logged; promote only if it comes back another day."
            )

    n_lines = len(content.splitlines())
    if n_lines > MAX_LINES:
        stale = sorted(
            (h.group("last"), h.group("id"))
            for h, _, _ in entries(content)
            if int(h.group("seen")) == 1
        )
        names = ", ".join(i for _, i in stale[:5]) or "none — every entry has recurred"
        print(
            f"\n>>> PRUNE: LESSONS.md is {n_lines} lines (> {MAX_LINES}). A log nobody "
            f"reads has failed at its job. Oldest single-sighting entries: {names}."
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bump", metavar="ID", help="id of an existing entry (e.g. L03)")
    ap.add_argument("--rule", help="the one-line general rule for next time")
    ap.add_argument("--trigger", help="what you were doing when it went wrong")
    ap.add_argument("--mistake", help="what you did or assumed that was wrong")
    ap.add_argument("--fix", help="what the correct action was")
    ap.add_argument("--evidence", required=True,
                    help="the correction, command, diff, or run that proves this happened")
    ap.add_argument("--tags", default="")
    args = ap.parse_args()

    today = dt.date.today().isoformat()
    content = load()

    if args.bump:
        content, seen, first = bump(content, args.bump, args.evidence, today)
        lid, last = args.bump, today
        print(f"Bumped {lid} to seen ×{seen}.")
    else:
        missing = [f for f in ("rule", "trigger", "mistake", "fix") if not getattr(args, f)]
        if missing:
            ap.error("a new lesson needs " + ", ".join("--" + m for m in missing))
        content, lid = new_entry(content, args, today)
        seen, first, last = 1, today, today
        print(f"Logged {lid}: {args.rule}")

    LESSONS.write_text(content, encoding="utf-8")
    report(content, lid, seen, first, last)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
