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
from pathlib import Path

from sqlalchemy import select

from taskman.config import find_project  # noqa: E402
from taskman.db import Session  # noqa: E402
from taskman.models import Capture, Decision, Project, Requirement, Task  # noqa: E402

# Reserved slug for machinery decisions/captures (d#856). Visible from any
# project cwd when hydrating d/cap pointers by global id.
WORKFLOW_SLUG = "workflow"

# Repeated ids under one prefix may be separated by whitespace, a comma, or the
# `·` the INDEX legend uses between pointers. Whitespace alone silently dropped
# every id after the first in the comma form (`req #277, #278`) — task #3329.
_POINTER_CHUNK = re.compile(
    r"\b(d|req|task|cap)\b\s*((?:`?#\d+`?[\s,·]*)+)",
    re.I,
)
_ID = re.compile(r"#(\d+)")
# Wave-offs in INDEX Decisions/Specs cells (d#852). Not hydrated, not citation-checked.
_WAIVED = re.compile(
    r"waived:\s*d\s*`?#(\d+)`?\s*\(([^)]*)\)",
    re.I,
)


def parse_waived(cell: str) -> list[tuple[int, str]]:
    """Return ordered (decision_id, reason) from ``waived: d#N (reason)`` markers."""
    cell = cell.strip()
    if not cell or cell in {"-", "—", "`-`"}:
        return []
    return [(int(m.group(1)), m.group(2).strip()) for m in _WAIVED.finditer(cell)]


def _cell_without_waived(cell: str) -> str:
    """Mask ``waived:…(…)`` spans so reason text cannot inject false pointers.

    Wave 4 review: reasons like ``(superseded by d#100; see task #3329)`` must not
    become hydrated/citation-gated ids. Parse waived markers from the raw cell;
    scan pointers / bare ``#id`` on the masked text only.
    """
    return _WAIVED.sub(" ", cell)


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


def _project(session) -> Project:
    slug, _name = find_project()
    proj = session.scalar(select(Project).where(Project.slug == slug))
    if proj is None:
        raise SystemExit(f"taskman: project slug {slug!r} not found")
    return proj


def _visible_project_ids_for_decisions(session, project: Project) -> set[int]:
    """Current project plus reserved ``workflow`` (d#856 cross-project visibility)."""
    ids = {project.id}
    workflow = session.scalar(select(Project).where(Project.slug == WORKFLOW_SLUG))
    if workflow is not None:
        ids.add(workflow.id)
    return ids


def resolve_entries(
    session, project: Project, pointers: list[tuple[str, int]]
) -> tuple[list[str], list[str]]:
    """Return (markdown bullets, errors).

    Decisions and captures resolve by global id when they live in the cwd
    project **or** the reserved ``workflow`` project. Requirements and tasks
    stay project-scoped.
    """
    lines: list[str] = []
    errors: list[str] = []
    visible = _visible_project_ids_for_decisions(session, project)
    for kind, oid in pointers:
        if kind == "d":
            dec = session.get(Decision, oid)
            if dec is None or dec.project_id not in visible:
                errors.append(f"decision #{oid} not found")
                continue
            bit = dec.implications or dec.why or ""
            one = bit.split("\n")[0].strip()
            if len(one) > 160:
                one = one[:157] + "…"
            suffix = f" — {one}" if one else ""
            lines.append(f"- d #{oid} — {dec.title}{suffix}")
        elif kind == "req":
            req = session.get(Requirement, oid)
            if req is None or req.project_id != project.id:
                errors.append(f"requirement #{oid} not found")
                continue
            stmt = (req.statement or "").split("\n")[0].strip()
            if len(stmt) > 200:
                stmt = stmt[:197] + "…"
            lines.append(f"- req #{oid} — {req.title}: {stmt}")
        elif kind == "task":
            task = session.get(Task, oid)
            if task is None or task.project_id != project.id:
                errors.append(f"task #{oid} not found")
                continue
            note = (task.notes or "").split("\n")[0].strip()
            if len(note) > 120:
                note = note[:117] + "…"
            suffix = f" — {note}" if note else ""
            lines.append(f"- task #{oid} — {task.title}{suffix}")
        elif kind == "cap":
            cap = session.get(Capture, oid)
            if cap is None or cap.project_id not in visible:
                errors.append(f"capture #{oid} not found")
                continue
            lines.append(f"- cap #{oid} — [{cap.kind}] {cap.summary}")
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

    with Session() as session:
        proj = _project(session)
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
            bullets, errs = resolve_entries(session, proj, pointers)
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
