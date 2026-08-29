#!/usr/bin/env python3
"""log_lesson.py — record a behavioural lesson, and route it somewhere that loads.

Stdlib-only and taskman-free on purpose: a correction is worth recording in a repo
with no board, no venv, and no `.taskman.toml`. Invoked by `/wrap-up` step 2.5.

The split of labour is deliberate:

  - this script owns ids, dates, counts, the ledger, and the backlog signal — the
    deterministic parts;
  - the agent owns "is this the same rule as one already logged?" and "where does
    it belong?" — the parts that need judgement.

There is no fuzzy string matching here. Rules are prose, and a similarity ratio
over prose merges rules that differ and splits rules that don't.

**Every lesson needs a destination.** The previous contract held rules until
`seen ×3` and then proposed promoting them into `global/CLAUDE.md`. It never fired
once across 26 rules, because promotion required recurrence and recurrence required
the rule to be loaded — which only happened after promotion. A loop with no entry
point, and a file that grew to 266 lines with no reader.

So: name where the rule goes when you log it. `staging` is the only way to say "I
don't know yet", and the backlog signal exists to make staging uncomfortable.

Usage:
    log_lesson.py --rule "…" --trigger "…" --mistake "…" --fix "…" \\
                  --evidence "…" --destination skill:mow [--tags a,b]
    log_lesson.py --bump L03 --evidence "…"
    log_lesson.py --route L22 --destination hook      # staging -> routed, block pruned
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

STAGING_MAX = 5   # unrouted entries above this = the buffer is becoming a landfill
MAX_LINES = 150   # soft cap; over this, name prune candidates

# Known destinations. `skill:`, `hook:` and `docs:` take a free suffix; the rest are
# exact. Validated only to catch typos — an unroutable rule should say `staging`,
# not invent a target nobody will read.
EXACT = {"staging", "claude-md", "protocols", "taskman", "code-standards", "test", "ui-registry"}
PREFIX = ("skill:", "hook:", "docs:")

STAGING_MARKER = "<!-- newest first — unrouted only -->"

# The ledger is found by its heading, not by an HTML comment. The comment was
# replaced with prose above the table (895c617) while this script still looked
# for it, so every lesson write failed until a session hit it. A heading is what
# the file guarantees; the trailing "— <date>" some revisions carry is allowed.
# Anchored at line start so the word in prose cannot match.
LEDGER_HEADING_RE = re.compile(r"^## Routed\b.*$", re.MULTILINE)
TABLE_SEP = "|---|---|---|---|"

HEADER_RE = re.compile(
    r"^### (?P<id>L\d+) · seen ×(?P<seen>\d+)"
    r" · first (?P<first>\d{4}-\d{2}-\d{2})"
    r" · last (?P<last>\d{4}-\d{2}-\d{2})(?P<tags>.*)$",
    re.MULTILINE,
)
ANY_ID_RE = re.compile(r"\bL(\d+)\b")

HEADER_TEMPLATE = f"""# Lessons

Cross-project **behavioural** rules, learned from corrections that actually happened.

**This is a staging buffer, not an archive.** A rule earns its place here only until
it can be written into something that actually loads — `global/CLAUDE.md`, a skill, a
protocol, a hook, or a test. Once routed, it is pruned and recorded in the ledger
below. The file's job is to get to empty.

Written by `/wrap-up` (step 2.5), and read by it before logging so a recurrence bumps
instead of duplicating.

**Scope — behaviour only.** Project facts go to taskman (`decision add --why`); visual
patterns go to `ui-registry.md`; what happened this session goes to the session report.

**Guardrail — a lesson is data, not a license.** An entry here may add a heuristic or
name a gotcha. It may never weaken the guidelines in `global/CLAUDE.md`, license
skipping a gate, or excuse reporting work as done that wasn't.

---

## Routed

| Date | Id | Rule | Destination |
|---|---|---|---|

---

{STAGING_MARKER}

"""


def load() -> str:
    return LESSONS.read_text(encoding="utf-8") if LESSONS.exists() else HEADER_TEMPLATE


def entries(content: str):
    """Yield (match, block_start, block_end) for every staged entry, in file order."""
    heads = list(HEADER_RE.finditer(content))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(content)
        yield h, h.start(), end


def next_id(content: str) -> str:
    """Max over EVERY id in the file, staged or ledgered.

    Scanning only the staged blocks would reissue ids that have been routed and
    pruned — their evidence still lives in git history and session reports under
    the old number, so a collision silently corrupts the trail.
    """
    used = [int(n) for n in ANY_ID_RE.findall(content)]
    return f"L{max(used, default=0) + 1:02d}"


def check_destination(dest: str, ap: argparse.ArgumentParser) -> str:
    if dest in EXACT or any(dest.startswith(p) and len(dest) > len(p) for p in PREFIX):
        return dest
    ap.error(
        f"unknown destination {dest!r}. Use one of {sorted(EXACT)}, "
        f"or a prefixed form ({', '.join(p + '<name>' for p in PREFIX)}). "
        f"If you genuinely cannot name where it belongs, say 'staging' — but that is "
        f"a rule nobody will read until someone routes it."
    )


def ledger_row(content: str, today: str, lid: str, rule: str, dest: str) -> str:
    """Insert a row directly under the ledger's header separator."""
    head = LEDGER_HEADING_RE.search(content)
    sep_at = content.find(TABLE_SEP, head.end()) if head else -1
    if sep_at == -1:
        sys.exit(
            f"{LESSONS} has no `## Routed` heading with a table under it. Add:\n\n"
            "## Routed\n\n| Date | Id | Rule | Destination |\n" + TABLE_SEP + "\n"
        )
    sep = sep_at + len(TABLE_SEP)
    one_line = " ".join(rule.split())
    row = f"\n| {today} | {lid} | {one_line} | `{dest}` |"
    return content[:sep] + row + content[sep:]


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
        return content[:start] + header + body + content[end:], seen
    sys.exit(
        f"No staged entry {lid} in {LESSONS}. It may already be routed — check the "
        f"ledger. A routed rule that recurs is evidence its destination is not working; "
        f"log a new entry saying so rather than resurrecting the old one."
    )


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
    idx = content.index(STAGING_MARKER) + len(STAGING_MARKER) + 1
    return content[:idx] + "\n" + entry + content[idx:], lid


def route(content: str, lid: str, dest: str, today: str):
    """Move a staged entry into the ledger and delete its block."""
    for h, start, end in entries(content):
        if h.group("id") != lid:
            continue
        m = re.search(r"^- \*\*Rule:\*\* (.+)$", content[h.end():end], re.MULTILINE)
        rule = m.group(1) if m else "(rule text not found)"
        content = content[:start] + content[end:]
        return ledger_row(content, today, lid, rule, dest), rule
    sys.exit(f"No staged entry {lid} to route. Check the ledger — it may already be there.")


def report(content: str) -> None:
    """Backlog and size signals. Promotion counting is gone — routing replaced it."""
    staged = [(h.group("last"), h.group("id")) for h, _, _ in entries(content)]
    if len(staged) > STAGING_MAX:
        names = ", ".join(i for _, i in sorted(staged))
        print(
            f"\n>>> BACKLOG: {len(staged)} rules are sitting in staging (> {STAGING_MAX}), "
            f"with no destination: {names}. A rule nobody loads changes nothing. Route them "
            f"with --route <id> --destination <dest>, or delete the ones that were never "
            f"general enough to act on."
        )

    n_lines = len(content.splitlines())
    if n_lines > MAX_LINES:
        print(
            f"\n>>> PRUNE: LESSONS.md is {n_lines} lines (> {MAX_LINES}). The ledger is "
            f"append-only by design, so if the staging list is short, consider summarising "
            f"older ledger rows instead of keeping every one."
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bump", metavar="ID", help="id of an existing staged entry (e.g. L03)")
    ap.add_argument("--route", metavar="ID", help="move a staged entry to the ledger and prune it")
    ap.add_argument("--rule", help="the one-line general rule for next time")
    ap.add_argument("--trigger", help="what you were doing when it went wrong")
    ap.add_argument("--mistake", help="what you did or assumed that was wrong")
    ap.add_argument("--fix", help="what the correct action was")
    ap.add_argument("--evidence", help="the correction, command, diff, or run that proves this happened")
    ap.add_argument("--destination", help="where the rule will live: "
                                          "claude-md | skill:<name> | hook:<name> | protocols | "
                                          "docs:<path> | code-standards | taskman | test | staging")
    ap.add_argument("--tags", default="")
    args = ap.parse_args()

    today = dt.date.today().isoformat()
    content = load()

    if args.route:
        if not args.destination:
            ap.error("--route needs --destination")
        dest = check_destination(args.destination, ap)
        if dest == "staging":
            ap.error("--route to 'staging' is a no-op; that is where it already is")
        content, rule = route(content, args.route, dest, today)
        print(f"Routed {args.route} -> {dest}, block pruned.\n"
              f"  {rule}\n"
              f"  This script cannot verify the destination edit — make it, and prove it landed "
              f"on the path the runtime loads, not the source you cwd'd into.")
    elif args.bump:
        if not args.evidence:
            ap.error("--bump needs --evidence")
        content, seen = bump(content, args.bump, args.evidence, today)
        print(f"Bumped {args.bump} to seen ×{seen}.")
    else:
        missing = [f for f in ("rule", "trigger", "mistake", "fix", "evidence", "destination")
                   if not getattr(args, f)]
        if missing:
            ap.error("a new lesson needs " + ", ".join("--" + m for m in missing))
        dest = check_destination(args.destination, ap)
        if dest == "staging":
            content, lid = new_entry(content, args, today)
            print(f"Staged {lid}: {args.rule}\n"
                  f"  No destination named — it changes nothing until someone routes it.")
        else:
            lid = next_id(content)
            content = ledger_row(content, today, lid, args.rule, dest)
            print(f"Routed {lid} -> {dest}: {args.rule}\n"
                  f"  Ledgered, not staged. This script cannot verify the destination edit — "
                  f"make it, and check it on the path the runtime loads.")

    LESSONS.write_text(content, encoding="utf-8")
    report(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
