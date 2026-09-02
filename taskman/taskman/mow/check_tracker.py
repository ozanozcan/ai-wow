#!/usr/bin/env python3
"""Reconcile a mow stem's tracker.json against what a finished run must look like.

/mow go §4 spends a whole subagent on this: spawn a `general-purpose` reader to
diff the board against reality and "report only discrepancies — lanes/agents left
`running` that actually finished, findings without taskman ids, any agent missing
`started`/`ended`, wave `started`/`ended` gaps". Most of that list is a query over
structured JSON, and a subagent's one-off probe leaves no artifact you can point
at later (L42). This is the mechanical half; the subagent keeps the semantic half
it is actually needed for — artifacts that were invented, lanes whose board status
disagrees with their own `## Verification` block.

Errors vs warnings follow the schema (skills/mow/TRACKER.md), not preference.
`started`/`ended` are documented **optional** with "omit rather than guess", so a
gap is reported and never blocks — gating on it would be stricter than the format
allows. A non-terminal status at close-out, a finding with no board row, or a
`run_status` still `running` are unambiguous, and those refuse.

A stem with no tracker.json never ran one; this no-ops.

Usage:
  python -m taskman.mow.check_tracker docs/plans/<stem>

Exit 0 = board matches (warnings may print). Exit 1 = refuse the `shipped` flip.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TERMINAL = frozenset({"done", "issues", "error"})
VOCABULARY = TERMINAL | {"pending", "running"}


def _tracker_path(stem_dir: Path) -> Path:
    stem = stem_dir.parent if stem_dir.name == "dispatch" else stem_dir
    return stem / "dispatch" / "tracker.json"


def _status_error(label: str, status: object) -> str | None:
    if not isinstance(status, str) or status not in VOCABULARY:
        return f"{label}: status {status!r} is outside the schema vocabulary"
    if status not in TERMINAL:
        return f"{label}: still `{status}` at close-out — a finished run has no pending work"
    return None


def _walk(data: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for wave in data.get("waves") or []:
        wn = f"wave {wave.get('wave', '?')}"
        if err := _status_error(wn, wave.get("status")):
            errors.append(err)

        gate = wave.get("gate")
        if not isinstance(gate, dict):
            errors.append(f"{wn}: no `gate` — every wave ends with a review gate (§2b)")
        elif err := _status_error(f"{wn} gate", gate.get("status")):
            errors.append(err)

        for field in ("started", "ended"):
            if not wave.get(field):
                warnings.append(f"{wn}: no `{field}` — the wave duration on the board comes from nothing else")

        for lane in wave.get("lanes") or []:
            ln = f"{wn} lane {lane.get('lane', '?')}"
            if err := _status_error(ln, lane.get("status")):
                errors.append(err)

            findings = lane.get("findings") or []
            if lane.get("status") == "issues" and not findings:
                errors.append(
                    f"{ln}: status `issues` with no `findings[]` — a lane goes issues "
                    "only once its findings are filed on the board"
                )
            for f in findings:
                if not str(f.get("task") or "").strip():
                    errors.append(
                        f"{ln}: finding {f.get('title', '?')!r} has no `task` id — "
                        "no board row, not a tracked finding"
                    )

            for todo in lane.get("todos") or []:
                if err := _status_error(f"{ln} todo {todo.get('id', '?')}", todo.get("status")):
                    errors.append(err)

            for agent in lane.get("agents") or []:
                an = f"{ln} agent {agent.get('name', '?')}"
                if err := _status_error(an, agent.get("status")):
                    errors.append(err)
                for field in ("started", "ended"):
                    if not agent.get(field):
                        warnings.append(
                            f"{an}: no `{field}` — the per-subagent duration beside its "
                            "name comes from nothing else"
                        )
                pending = [
                    s.get("name", "?") for s in (agent.get("skills") or [])
                    if s.get("status") == "pending"
                ]
                if pending:
                    warnings.append(
                        f"{an}: skills never reconciled against the lane's Verification "
                        f"block: {', '.join(pending)}"
                    )

    return errors, warnings


def _load(stem_dir: Path) -> tuple[dict | None, list[str]]:
    path = _tracker_path(stem_dir)
    if not path.is_file():
        return None, []
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, [f"{path}: unreadable ({exc})"]


def check_stem(stem_dir: Path) -> list[str]:
    data, errors = _load(stem_dir)
    if data is None:
        return errors

    path = _tracker_path(stem_dir)
    run_status = data.get("run_status")
    if run_status != "shipped":
        errors.append(
            f"{path}: run_status is {run_status!r}, not `shipped` — that flag is what "
            "moves this run from ?runs=live to ?runs=archive and what the "
            "still-running count reads; a run left `running` holds the board up for good"
        )

    walk_errors, _ = _walk(data)
    return errors + walk_errors


def collect_warnings(stem_dir: Path) -> list[str]:
    """Discrepancies worth reporting that the schema permits — never blocking."""
    data, _ = _load(stem_dir)
    if data is None:
        return []
    _, warnings = _walk(data)
    return warnings


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
    for w in collect_warnings(stem):
        print(f"  ! {w}", file=sys.stderr)
    if errors:
        print("mow tracker reconcile FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"mow tracker reconcile OK: {stem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
