#!/usr/bin/env python3
"""Fail if a mow stem's board was not actually synced at Integrate.

**Board sync:** in the action report was a line you could write without running
`plan mark-shipped`. The skill already warns that mark-shipped "has silently
closed follow-ups, and has also moved nothing when it should have moved eight"
— then asked the operator to audit that by hand. A line in Verify cannot catch
either direction.

When the repo has no `.taskman.toml` this is a no-op: there is no board, and
the action-report gate already demands `**Board sync:** n/a` with a reason.

When the repo has a board, this looks at the board:

  - `**Board sync:** n/a` is a lie and refuses
  - every dispatch-brief task (except `kind:decision`) that Outcome called
    shipped, or that Outcome did not mention, must be `done`
  - a brief whose `source_ref` matches no board row means import never ran

It does not run mark-shipped. It reads. Mutating the board from a gate is how
you hide the miss this exists to catch.

Usage:
  python -m taskman.mow.check_board_sync docs/plans/<stem>

Exit 0 = board matches (or no board here). Exit 1 = refuse. Exit 2 = usage.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DECISION_TAG = "kind:decision"
_NA = re.compile(r"(?i)\*\*Board sync:\*\*\s*`?n/?a")
_SHIPPED = re.compile(r"(?i)\b(shipped|done|fixed in-run)\b")
_DEFERRED = re.compile(r"(?i)\b(skip|skipped|deferred|n/?a|not shipped)\b")


def _stem(stem_dir: Path) -> Path:
    return stem_dir.parent if stem_dir.name == "dispatch" else stem_dir


def _repo_root(stem_dir: Path) -> Path:
    """docs/plans/<stem> lives two levels under the repo root. Do not walk to /."""
    stem = _stem(stem_dir)
    if stem.parent.name == "plans" and stem.parent.parent.name == "docs":
        return stem.parent.parent.parent
    return stem.parent.parent.parent


def _toml_and_board(repo_root: Path) -> tuple[Path | None, Path | None]:
    toml = repo_root / ".taskman.toml"
    if not toml.is_file():
        return None, None
    return toml, repo_root / "board"


def _brief_names(dispatch: Path) -> list[str]:
    return sorted(p.name for p in dispatch.glob("[0-9][0-9]-*.md"))


def _source_refs(dispatch: Path, repo_root: Path) -> dict[str, str]:
    from taskman.plan import parse_brief

    refs: dict[str, str] = {}
    for name in _brief_names(dispatch):
        item = parse_brief(dispatch / name, repo_root=repo_root)
        if item is not None and item.source_ref:
            refs[name] = item.source_ref
    return refs


def _outcome_mentions(report_text: str) -> tuple[set[int], set[str], set[int], set[str]]:
    """Return (shipped_ids, shipped_todos, deferred_ids, deferred_todos).

    Outcome tables in the wild are `Item | Result` as often as `Task | Status`.
    Scan every cell for `#123` and `01-foo` names rather than requiring a
    header the existing reports do not use.
    """
    m = re.search(r"^## Outcome\s*$", report_text, re.M | re.I)
    if not m:
        return set(), set(), set(), set()
    section = report_text[m.end() :]
    stop = re.search(r"^## ", section, re.M)
    if stop:
        section = section[: stop.start()]

    shipped_ids: set[int] = set()
    shipped_todos: set[str] = set()
    deferred_ids: set[int] = set()
    deferred_todos: set[str] = set()
    for line in section.splitlines():
        ids = {int(x) for x in re.findall(r"#(\d+)", line)}
        todos = set(re.findall(r"(\d{2}-[\w.-]+)", line))
        if _DEFERRED.search(line) and not _SHIPPED.search(line):
            deferred_ids |= ids
            deferred_todos |= todos
        elif _SHIPPED.search(line) or ids or todos:
            shipped_ids |= ids
            shipped_todos |= todos
    return shipped_ids, shipped_todos, deferred_ids, deferred_todos


def _todo_id(source_ref: str) -> str:
    name = Path(str(source_ref).replace("\\", "/")).name
    return name.removesuffix(".md") if name.endswith(".md") else name


def check_stem(stem_dir: Path) -> list[str]:
    errors: list[str] = []
    stem = _stem(stem_dir)
    repo = _repo_root(stem)
    toml, board_dir = _toml_and_board(repo)
    if toml is None:
        return []

    dispatch = stem / "dispatch"
    refs = _source_refs(dispatch, repo)
    report = stem / "action-report.md"
    na = report.is_file() and _NA.search(report.read_text(encoding="utf-8"))

    # n/a is legitimate when this stem has no dispatch briefs to close — a
    # taskman repo can still host a docs-only stem. n/a is a lie the moment
    # this stem owns board work.
    if na and refs:
        errors.append(
            f"{report}: **Board sync:** is n/a but {toml} exists and this stem "
            "has dispatch briefs — run `taskman plan mark-shipped` (or say why "
            "the board is unusable, not n/a)"
        )

    if board_dir is None or not board_dir.is_dir():
        if refs:
            errors.append(
                f"{toml} exists but {repo / 'board'} is missing — `taskman init` "
                "first, or this stem should not claim a board"
            )
        return errors

    from taskman.eventlog import store

    if not refs:
        return errors

    tasks = list(store.state(board_dir).get("task", {}).values())
    by_ref = {
        t.get("source_ref"): t
        for t in tasks
        if t.get("source_ref")
    }

    shipped_ids, shipped_todos, deferred_ids, deferred_todos = (
        _outcome_mentions(report.read_text(encoding="utf-8")) if report.is_file() else (set(), set(), set(), set())
    )
    outcome_named = bool(shipped_ids or shipped_todos or deferred_ids or deferred_todos)

    unmatched = [name for name, ref in refs.items() if ref not in by_ref]
    if unmatched:
        errors.append(
            f"{len(unmatched)} dispatch brief(s) have source_refs that match no board "
            f"task ({', '.join(unmatched[:4])}{'…' if len(unmatched) > 4 else ''}) — "
            "`mow_plan_import` never ran, or the refs drifted"
        )

    still_open: list[str] = []
    for name, ref in refs.items():
        task = by_ref.get(ref)
        if not task:
            continue
        if DECISION_TAG in (task.get("tags") or []):
            continue
        tid = int(task["id"])
        todo = _todo_id(ref)
        if tid in deferred_ids or todo in deferred_todos:
            continue
        should_be_done = (not outcome_named) or tid in shipped_ids or todo in shipped_todos
        if should_be_done and task.get("status") != "done":
            still_open.append(f"#{tid} ({name}, status={task.get('status')})")

    if still_open:
        errors.append(
            f"{len(still_open)} dispatch task(s) still not `done`: {', '.join(still_open)} — "
            "`taskman plan mark-shipped` did not run, or Outcome and the board disagree"
        )
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
    errors = check_stem(stem)
    if errors:
        print("mow board-sync gate FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"mow board-sync gate OK: {stem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
