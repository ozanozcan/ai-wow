#!/usr/bin/env python3
"""Hydrate INDEX Decisions/Specs pointers into a file subagents can Read.

Cheaper than live taskman mid-lane: orchestrator (or /mow ready|/mow go) runs
this once; lanes open dispatch/hydrated-specs.md.

Usage:
  python -m taskman.mow.hydrate_specs docs/plans/<stem>
  python -m taskman.mow.hydrate_specs docs/plans/<stem>/dispatch

Exit 0 = wrote file (or wrote empty stub when all lanes are `-`).
Exit 1 = unresolvable id or missing INDEX.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterator
from pathlib import Path

from taskman.config import find_project  # noqa: E402
from taskman.eventlog import store  # noqa: E402

# Repeated ids under one prefix may be separated by whitespace, a comma, or the
# `·` the INDEX legend uses between pointers. Whitespace alone silently dropped
# every id after the first in the comma form (`req #277, #278`) — task #3329.
_POINTER_CHUNK = re.compile(
    r"\b(d|req|task|cap)\b\s*((?:`?#\d+`?[\s,·]*)+)",
    re.I,
)
_ID = re.compile(r"#(\d+)")
# Wave-offs in INDEX Decisions/Specs cells (d#852). Not hydrated, not citation-checked.
# Only the head is a regex: a reason may contain its own parens (`instantiate_day()`),
# so the closing paren is found by depth counting rather than by `[^)]*`.
_WAIVED_HEAD = re.compile(
    r"waived:\s*d\s*`?#(\d+)`?\s*\(",
    re.I,
)


def _iter_waived(cell: str) -> Iterator[tuple[int, int, int, str]]:
    """Yield ``(start, end, decision_id, reason)`` for each balanced waived marker.

    ``start``/``end`` bound the whole ``waived: d#N (…)`` span. A marker whose
    parens never close is not a marker: it is skipped and left in the cell, so the
    pointers-only check still reports it as residual text.
    """
    pos = 0
    while (m := _WAIVED_HEAD.search(cell, pos)) is not None:
        depth = 1
        i = m.end()
        while i < len(cell) and depth:
            if cell[i] == "(":
                depth += 1
            elif cell[i] == ")":
                depth -= 1
            i += 1
        if depth:
            pos = m.end()
            continue
        yield m.start(), i, int(m.group(1)), cell[m.end() : i - 1]
        pos = i


def parse_waived(cell: str) -> list[tuple[int, str]]:
    """Return ordered (decision_id, reason) from ``waived: d#N (reason)`` markers."""
    cell = cell.strip()
    if not cell or cell in {"-", "—", "`-`"}:
        return []
    return [(oid, reason.strip()) for _s, _e, oid, reason in _iter_waived(cell)]


def _cell_without_waived(cell: str) -> str:
    """Mask ``waived:…(…)`` spans so reason text cannot inject false pointers.

    Wave 4 review: reasons like ``(superseded by d#100; see task #3329)`` must not
    become hydrated/citation-gated ids. Parse waived markers from the raw cell;
    scan pointers / bare ``#id`` on the masked text only.
    """
    out: list[str] = []
    last = 0
    for start, end, _oid, _reason in _iter_waived(cell):
        out.append(cell[last:start])
        out.append(" ")
        last = end
    out.append(cell[last:])
    return "".join(out)


def unclaimed_ids(cell: str, pointers: list[tuple[str, int]]) -> list[int]:
    """Ids present in ``cell`` that no ``kind`` prefix claimed.

    The grammar fix above closes the comma form, but the defect that made #3329
    invisible for days was silence, not the grammar: a cell can always drift into
    a shape the parser reads short. Callers surface these as errors so a lane
    never builds against a lock set quieter than the INDEX claims.

    Waived decision ids count as claimed (they are intentionally not hydrated).
    Ids that appear only inside waived-reason text are ignored (masked out).
    """
    claimed = {oid for _kind, oid in pointers}
    claimed.update(oid for oid, _reason in parse_waived(cell))
    scan = _cell_without_waived(cell)
    return [int(m.group(1)) for m in _ID.finditer(scan) if int(m.group(1)) not in claimed]


def parse_pointer_cell(cell: str) -> list[tuple[str, int]]:
    """Return ordered (kind, id) from an INDEX Decisions / Specs cell.

    Waived decision ids (``waived: d#N (reason)``) are excluded — they are not
    hydrated and not citation-checked (d#852). Reason-body cross-refs are also
    excluded (masked before the pointer scan).
    """
    cell = cell.strip()
    if not cell or cell in {"-", "—", "`-`"}:
        return []
    scan = _cell_without_waived(cell)
    out: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for m in _POINTER_CHUNK.finditer(scan):
        kind = m.group(1).lower()
        for id_m in _ID.finditer(m.group(2)):
            oid = int(id_m.group(1))
            key = (kind, oid)
            if key not in seen:
                seen.add(key)
                out.append(key)
    return out


def _split_index_lanes(index_text: str) -> list[tuple[str, str, str]]:
    """Return (lane, decisions_cell, brief) from the Lanes table."""
    # Find header to locate Decisions / Specs column index
    header = None
    for line in index_text.splitlines():
        if line.startswith("|") and "Decisions / Specs" in line and "Lane" in line:
            header = [c.strip() for c in line.strip("|").split("|")]
            break
    if not header:
        return []
    try:
        dec_i = header.index("Decisions / Specs")
        brief_i = header.index("Brief")
        lane_i = header.index("Lane")
    except ValueError:
        return []

    rows: list[tuple[str, str, str]] = []
    in_table = False
    for line in index_text.splitlines():
        if line.startswith("|") and "Decisions / Specs" in line and "Lane" in line:
            in_table = True
            continue
        if in_table and line.startswith("|") and re.match(r"^\|\s*---", line):
            continue
        if in_table and line.startswith("|"):
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) <= max(dec_i, brief_i, lane_i):
                continue
            lane = cols[lane_i]
            if not re.fullmatch(r"[A-Z]", lane):
                # legend / prose row under table
                if not cols[0] or cols[0].startswith("`"):
                    break
                continue
            rows.append((lane, cols[dec_i], cols[brief_i]))
            continue
        if in_table and not line.startswith("|"):
            break
    return rows


def _board_dir() -> Path:
    """Board for the cwd project: next to the nearest .taskman.toml (d-p6)."""
    find_project()  # identity check — stops loudly on a missing marker or slug
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / ".taskman.toml").exists():
            board = d / "board"
            if not board.is_dir():
                raise SystemExit(f"taskman: {board} missing — run `taskman init` first.")
            return board
    raise SystemExit("taskman: no .taskman.toml found above cwd")


def resolve_entries(
    state: dict, pointers: list[tuple[str, int]]
) -> tuple[list[str], list[str]]:
    """Return (markdown bullets, errors) resolved over the replayed board.

    One board per repo (d-p6): every pointer resolves against the cwd
    project's own log — the old cross-project ``workflow`` visibility died
    with the Project table.
    """
    lines: list[str] = []
    errors: list[str] = []
    for kind, oid in pointers:
        if kind == "d":
            dec = state["decision"].get(oid)
            if dec is None:
                errors.append(f"decision #{oid} not found")
                continue
            bit = dec.get("implications") or dec.get("why") or ""
            one = bit.split("\n")[0].strip()
            if len(one) > 160:
                one = one[:157] + "…"
            suffix = f" — {one}" if one else ""
            lines.append(f"- d #{oid} — {dec.get('title', '')}{suffix}")
        elif kind == "req":
            req = state["requirement"].get(oid)
            if req is None:
                errors.append(f"requirement #{oid} not found")
                continue
            stmt = (req.get("statement") or "").split("\n")[0].strip()
            if len(stmt) > 200:
                stmt = stmt[:197] + "…"
            lines.append(f"- req #{oid} — {req.get('title', '')}: {stmt}")
        elif kind == "task":
            task = state["task"].get(oid)
            if task is None:
                errors.append(f"task #{oid} not found")
                continue
            note = (task.get("notes") or "").split("\n")[0].strip()
            if len(note) > 120:
                note = note[:117] + "…"
            suffix = f" — {note}" if note else ""
            lines.append(f"- task #{oid} — {task.get('title', '')}{suffix}")
        elif kind == "cap":
            cap = state["capture"].get(oid)
            if cap is None:
                errors.append(f"capture #{oid} not found")
                continue
            lines.append(f"- cap #{oid} — [{cap.get('kind', '')}] {cap.get('summary', '')}")
        else:
            errors.append(f"unknown pointer kind {kind!r}")
    return lines, errors


def hydrate_stem(stem_dir: Path) -> Path:
    dispatch = stem_dir / "dispatch" if (stem_dir / "dispatch").is_dir() else stem_dir
    if dispatch.name != "dispatch":
        raise SystemExit(f"expected …/<stem> or …/<stem>/dispatch, got {stem_dir}")
    index = dispatch / "INDEX.md"
    if not index.is_file():
        raise SystemExit(f"missing {index}")

    lanes = _split_index_lanes(index.read_text(encoding="utf-8"))
    if not lanes:
        raise SystemExit(
            f"{index}: no Lanes table with a Decisions / Specs column — "
            "add pointers (or `-`) before hydrating"
        )

    out_path = dispatch / "hydrated-specs.md"
    errors: list[str] = []
    sections: list[str] = [
        "# Hydrated Decisions / Specs",
        "",
        "Generated for blind lanes — **read this file**; do not require live taskman.",
        "",
        "Regenerate: `python -m taskman.mow.hydrate_specs docs/plans/<stem>`",
        "",
    ]
    try:
        rel_index = index.resolve().relative_to(Path.cwd())
    except ValueError:
        rel_index = index
    sections.insert(3, f"Source: `{rel_index}`")

    state = store.state(_board_dir())
    for lane, cell, brief in lanes:
        pointers = parse_pointer_cell(cell)
        for oid in unclaimed_ids(cell, pointers):
            errors.append(
                f"lane {lane}: #{oid} in the Decisions / Specs cell is not claimed by a "
                "d/req/task/cap prefix — write it as `<kind> `#id`` (ranges like "
                "`#198`–`#202` must be spelled out) so the lane gets the whole lock set"
            )
        sections.append(f"## Lane {lane} ({brief})")
        sections.append("")
        if not pointers:
            sections.append("_No Decisions / Specs pointers (`-`)._")
            sections.append("")
            continue
        bullets, errs = resolve_entries(state, pointers)
        errors.extend(f"lane {lane}: {e}" for e in errs)
        sections.extend(bullets or ["_No resolvable entries._"])
        sections.append("")

    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        raise SystemExit(1)

    out_path.write_text("\n".join(sections).rstrip() + "\n", encoding="utf-8")
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stem", type=Path, help="docs/plans/<stem> or …/dispatch")
    args = p.parse_args(argv)
    path = hydrate_stem(args.stem.resolve())
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
