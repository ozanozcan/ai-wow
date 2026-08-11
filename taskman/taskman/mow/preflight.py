#!/usr/bin/env python3
"""Deterministic mow preflight gate before /mow go fan-out.

Composes grill write-back, hydrate (when pointers exist), thin-brief validation,
pointer citation (d#853), INDEX pointer-prose lint (d#946), decision candidate
surfacing (d#852), same-wave overlap, brief/INDEX drift, and cross-plan file overlap.

Sibling note (d#868): wrapup attributes by *path*, not author — a second session's
edit to a file already claimed by an open lane task's Files in scope rides that
lane's attribution (concurrent writes to a *claimed file* vs a shared plan).

Usage:
  python -m taskman.mow.preflight docs/plans/<stem>
  python -m taskman.mow.preflight docs/plans/<stem> --json
  python -m taskman.mow.preflight docs/plans/<stem> --skip-hydrate
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_ROOT_DEFAULT = None  # repo root defaults to Path.cwd() at call time

_VAGUE_SCOPE = frozenset(
    {"tbd", "see plan", "see chat", "the backend", "backend", "frontend"}
)
_THIN_ACCEPTANCE_WEAK = frozenset(
    {
        "works correctly",
        "tests pass",
        "done when merged",
        "it works",
    }
)

# Citations inside Acceptance / Do NOT — flexible spacing/backticks (d#853).
_CITATION = re.compile(r"\b(d|req|task|cap)\s*`?#(\d+)`?", re.I)
_PATH_PREFIX = "path:"

def paths_overlap(a: str, b: str) -> bool:
    """True when paths are equal or one is a directory prefix of the other."""
    a_norm = a.strip().rstrip("/")
    b_norm = b.strip().rstrip("/")
    if not a_norm or not b_norm:
        return False
    if a_norm == b_norm:
        return True
    return a_norm.startswith(b_norm + "/") or b_norm.startswith(a_norm + "/")


def parse_files_owned(cell: str) -> list[str]:
    """Extract repo-relative paths from an INDEX Files owned cell."""
    cell = cell.strip()
    if not cell or cell in {"-", "—"}:
        return []
    paths: list[str] = []
    for m in re.finditer(r"`([^`]+)`", cell):
        p = _normalize_scope_path(m.group(1))
        if p:
            paths.append(p)
    if paths:
        return paths
    for part in cell.split(","):
        p = _normalize_scope_path(part)
        if p:
            paths.append(p)
    return paths


def _normalize_scope_path(raw: str) -> str:
    p = raw.strip().strip("`")
    p = re.sub(r"\s*\([^)]*\)\s*$", "", p).strip()
    return p.rstrip("/")


def _split_lanes_table(index_text: str) -> list[dict[str, str]]:
    """Return lane rows with lane, files_owned, brief keys."""
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    in_table = False
    for line in index_text.splitlines():
        if line.startswith("|") and "Lane" in line and "Brief" in line:
            header = [c.strip() for c in line.strip("|").split("|")]
            in_table = True
            continue
        if in_table and line.startswith("|") and re.match(r"^\|\s*---", line):
            continue
        if in_table and line.startswith("|"):
            if header is None:
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            try:
                lane_i = header.index("Lane")
                brief_i = header.index("Brief")
            except ValueError:
                continue
            files_i = None
            for name in ("Files owned", "Files Owned"):
                if name in header:
                    files_i = header.index(name)
                    break
            if len(cols) <= max(lane_i, brief_i):
                continue
            lane = cols[lane_i]
            if not re.fullmatch(r"[A-Z]", lane):
                if not cols[0] or cols[0].startswith("`"):
                    break
                continue
            rows.append(
                {
                    "lane": lane,
                    "files_owned": cols[files_i] if files_i is not None and len(cols) > files_i else "",
                    "brief": cols[brief_i],
                }
            )
            continue
        if in_table and not line.startswith("|"):
            break
    return rows


def parse_wave_lanes(index_text: str) -> dict[str, list[str]]:
    """Map wave number -> ordered lane letters from ## Waves bullets."""
    waves: dict[str, list[str]] = {}
    in_waves = False
    for line in index_text.splitlines():
        if line.startswith("## Waves"):
            in_waves = True
            continue
        if in_waves and line.startswith("## "):
            break
        if not in_waves or not line.strip().startswith("- **Wave"):
            continue
        m = re.match(r"- \*\*Wave\s+(\d+)", line)
        if not m:
            continue
        wave_num = m.group(1)
        lanes = re.findall(r"\b([A-Z])\b\s*\(", line)
        if lanes:
            waves[wave_num] = lanes
    return waves


def check_same_wave_overlap(index_text: str) -> list[str]:
    """Detect overlapping Files owned within the same wave."""
    errors: list[str] = []
    wave_lanes = parse_wave_lanes(index_text)
    rows = _split_lanes_table(index_text)
    lane_files = {r["lane"]: parse_files_owned(r["files_owned"]) for r in rows}

    if not wave_lanes:
        # Single implicit wave — compare all lanes together
        wave_lanes = {"1": [r["lane"] for r in rows]}

    for wave_num, lanes in wave_lanes.items():
        for i, lane_a in enumerate(lanes):
            files_a = lane_files.get(lane_a, [])
            for lane_b in lanes[i + 1 :]:
                files_b = lane_files.get(lane_b, [])
                for fa in files_a:
                    for fb in files_b:
                        if paths_overlap(fa, fb):
                            errors.append(
                                f"same-wave overlap wave {wave_num}: lane {lane_a} "
                                f"({fa}) vs lane {lane_b} ({fb})"
                            )
    return errors


def _section_body(text: str, heading: str) -> str:
    pattern = re.compile(rf"^## {re.escape(heading)}(?:\s|\(|$)", re.M)
    m = pattern.search(text)
    if not m:
        return ""
    start = m.end()
    # rewind to end of the heading line
    line_end = text.find("\n", m.start())
    start = line_end + 1 if line_end != -1 else m.end()
    nxt = re.search(r"^## ", text[start:], re.M)
    end = start + nxt.start() if nxt else len(text)
    return text[start:end].strip()


def _bullet_lines(body: str) -> list[str]:
    lines: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("- "):
            lines.append(s[2:].strip())
    return lines


def _is_concrete_path(path: str) -> bool:
    p = path.strip().strip("`")
    if not p or p.lower() in _VAGUE_SCOPE:
        return False
    if "/" not in p and not p.endswith((".py", ".md", ".html", ".js", ".css")):
        return False
    return True


def check_thin_brief(brief_name: str, text: str) -> list[str]:
    """Mirror mow skill step 5 — refuse thin briefs (not ## Git rules)."""
    errors: list[str] = []
    required = (
        "Goal",
        "Context & decisions",
        "Files in scope",
        "Do NOT",
        "Acceptance check",
        "QA contract",
    )
    for heading in required:
        body = _section_body(text, heading)
        if not body:
            errors.append(f"{brief_name}: missing ## {heading}")

    goal = _section_body(text, "Goal")
    if goal and len(goal.split()) < 4:
        errors.append(f"{brief_name}: ## Goal too thin")

    ctx_bullets = _bullet_lines(_section_body(text, "Context & decisions"))
    if len(ctx_bullets) < 2:
        errors.append(f"{brief_name}: ## Context & decisions needs ≥2 bullets")

    scope_paths = _bullet_lines(_section_body(text, "Files in scope"))
    concrete = [p for p in scope_paths if _is_concrete_path(p)]
    if not concrete:
        errors.append(f"{brief_name}: ## Files in scope needs ≥1 concrete path")

    do_not = _bullet_lines(_section_body(text, "Do NOT"))
    if not do_not:
        errors.append(f"{brief_name}: ## Do NOT needs ≥1 scope trap")

    acceptance = _section_body(text, "Acceptance check").lower()
    acc_bullets = _bullet_lines(_section_body(text, "Acceptance check"))
    has_scenario = any(
        "given" in b.lower() and ("when" in b.lower() or "then" in b.lower())
        for b in acc_bullets
    ) or ("given" in acceptance and "when" in acceptance and "then" in acceptance)
    has_verify = any("verify:" in b.lower() for b in acc_bullets)
    shall_count = sum(1 for b in acc_bullets if "shall" in b.lower())
    if shall_count < 1:
        errors.append(f"{brief_name}: ## Acceptance check needs ≥1 SHALL")
    if not has_scenario and not (has_verify and shall_count >= 2):
        errors.append(f"{brief_name}: ## Acceptance check needs GIVEN/WHEN/THEN")
    if any(w in acceptance for w in _THIN_ACCEPTANCE_WEAK):
        errors.append(f"{brief_name}: ## Acceptance check too vague")

    qa = _section_body(text, "QA contract")
    if not qa or not _bullet_lines(qa):
        errors.append(f"{brief_name}: ## QA contract missing runnable checks")

    return errors


def _paths_from_scope_bullets(body: str) -> list[str]:
    paths: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("- "):
            continue
        for m in re.finditer(r"`([^`]+)`", s):
            p = _normalize_scope_path(m.group(1))
            if p:
                paths.append(p)
        if not re.search(r"`", s):
            p = _normalize_scope_path(s[2:])
            if p:
                paths.append(p)
    return paths


def _normalize_path_set(paths: list[str]) -> set[str]:
    return {_normalize_scope_path(p) for p in paths if p.strip()}


def check_brief_index_drift(
    index_text: str,
    briefs: dict[str, str],
) -> list[str]:
    """Ensure each brief ## Files in scope matches INDEX Files owned."""
    errors: list[str] = []
    for row in _split_lanes_table(index_text):
        brief_name = row["brief"]
        if brief_name not in briefs:
            errors.append(f"lane {row['lane']}: missing brief file {brief_name}")
            continue
        index_paths = _normalize_path_set(parse_files_owned(row["files_owned"]))
        scope_paths = _normalize_path_set(
            _paths_from_scope_bullets(_section_body(briefs[brief_name], "Files in scope"))
        )
        if index_paths != scope_paths:
            missing_in_brief = index_paths - scope_paths
            extra_in_brief = scope_paths - index_paths
            parts: list[str] = []
            if missing_in_brief:
                parts.append(f"missing in brief: {sorted(missing_in_brief)}")
            if extra_in_brief:
                parts.append(f"extra in brief: {sorted(extra_in_brief)}")
            errors.append(
                f"lane {row['lane']} brief/INDEX drift ({brief_name}): "
                + "; ".join(parts)
            )
    return errors


def registry_status(registry_text: str, stem: str) -> str | None:
    """Return Status for stem from docs/plans/INDEX.md table."""
    for line in registry_text.splitlines():
        if not line.startswith("|") or line.startswith("| Stem"):
            continue
        if re.match(r"^\|\s*---", line):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 6:
            continue
        if cols[0] == stem:
            return cols[5].lower()
    return None


def all_decisions_specs_dash(lanes: list[tuple[str, str, str]]) -> bool:
    """True when every lane Decisions/Specs cell is `-`."""
    for _lane, cell, _brief in lanes:
        cell = cell.strip()
        if cell and cell not in {"-", "—", "`-`"}:
            return False
    return True


def _stem_name(stem_dir: Path) -> str:
    dispatch = stem_dir / "dispatch" if (stem_dir / "dispatch").is_dir() else stem_dir
    return dispatch.parent.name


def _resolve_dispatch(stem_dir: Path) -> tuple[Path, Path]:
    dispatch = stem_dir / "dispatch" if (stem_dir / "dispatch").is_dir() else stem_dir
    if dispatch.name != "dispatch":
        raise ValueError(f"expected …/<stem> or …/<stem>/dispatch, got {stem_dir}")
    return dispatch, dispatch / "INDEX.md"


def _collect_other_stem_files(
    repo_root: Path,
    target_stem: str,
    active_statuses: frozenset[str],
) -> list[tuple[str, str]]:
    """Return (stem, path) for Files owned from other active stems."""
    registry = repo_root / "docs" / "plans" / "INDEX.md"
    if not registry.is_file():
        return []
    registry_text = registry.read_text(encoding="utf-8")
    owned: list[tuple[str, str]] = []
    for line in registry_text.splitlines():
        if not line.startswith("|") or line.startswith("| Stem"):
            continue
        if re.match(r"^\|\s*---", line):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 6:
            continue
        stem, status = cols[0], cols[5].lower()
        if stem == target_stem or status not in active_statuses:
            continue
        other_index = repo_root / "docs" / "plans" / stem / "dispatch" / "INDEX.md"
        if not other_index.is_file():
            continue
        other_text = other_index.read_text(encoding="utf-8")
        for row in _split_lanes_table(other_text):
            for p in parse_files_owned(row["files_owned"]):
                owned.append((stem, p))
    return owned


def check_cross_plan_overlap(
    repo_root: Path,
    target_stem: str,
    target_index_text: str,
) -> list[str]:
    """Compare target Files owned against other planned|running|paused stems."""
    errors: list[str] = []
    target_paths: list[str] = []
    for row in _split_lanes_table(target_index_text):
        target_paths.extend(parse_files_owned(row["files_owned"]))

    other = _collect_other_stem_files(
        repo_root,
        target_stem,
        frozenset({"planned", "running", "paused"}),
    )
    for other_stem, other_path in other:
        for tp in target_paths:
            if paths_overlap(tp, other_path):
                errors.append(
                    f"cross-plan overlap: {target_stem} ({tp}) vs {other_stem} ({other_path})"
                )
    return errors


def cited_pointers_in_brief(brief_text: str) -> set[tuple[str, int]]:
    """Pointer ids cited in ## Acceptance check or ## Do NOT."""
    body = (
        _section_body(brief_text, "Acceptance check")
        + "\n"
        + _section_body(brief_text, "Do NOT")
    )
    return {(m.group(1).lower(), int(m.group(2))) for m in _CITATION.finditer(body)}


def check_pointer_citations(
    lane: str,
    brief_name: str,
    cell: str,
    brief_text: str,
) -> list[str]:
    """Refuse fan-out when INDEX pointers are uncited in Acceptance/Do NOT (d#853)."""
    from taskman.mow import hydrate_specs as hydrate_mod

    errors: list[str] = []
    pointers = hydrate_mod.parse_pointer_cell(cell)
    for oid in hydrate_mod.unclaimed_ids(cell, pointers):
        errors.append(
            f"lane {lane} ({brief_name}): #{oid} in the Decisions / Specs cell is not "
            "claimed by a d/req/task/cap prefix — write it as `<kind> `#id`` "
            "(silent short-parses must not pass)"
        )
    cited = cited_pointers_in_brief(brief_text)
    for kind, oid in pointers:
        if (kind, oid) not in cited:
            errors.append(
                f"lane {lane}: uncited pointer {kind}#{oid} — cite {kind}#{oid} in "
                f"## Acceptance check or ## Do NOT of {brief_name}"
            )
    return errors


# plan Decision N / plan Decisions N, M — INDEX tokens (not hydrated ids).
_PLAN_DECISION_TOKEN = re.compile(
    r"plan\s+Decisions?\s+\d+(?:\s*,\s*\d+)*",
    re.I,
)
_POINTER_CELL_NOISE = re.compile(r"[\s,·`]+")


def check_index_decisions_pointer_only(lane: str, cell: str) -> list[str]:
    """Refuse INDEX Decisions/Specs cells that are not pointer grammar (d#946).

    Strict grammar-only: after removing known pointer tokens (d/req/task/cap ids,
    plan Decision(s) N lists, waived markers, separators), any residual text fails.
    Bare ``-`` is allowed. Complements citation (d#853) — INDEX must not dump prose.
    """
    from taskman.mow import hydrate_specs as hydrate_mod

    raw = cell.strip()
    if not raw or raw in {"-", "—", "`-`"}:
        return []

    # Mask waived spans (existing INDEX grammar), then strip pointer chunks and
    # plan Decision tokens; leftover non-separator text is prose.
    scan = hydrate_mod._cell_without_waived(raw)
    scan = hydrate_mod._POINTER_CHUNK.sub(" ", scan)
    scan = _PLAN_DECISION_TOKEN.sub(" ", scan)
    residual = _POINTER_CELL_NOISE.sub("", scan)
    if residual:
        preview = residual if len(residual) <= 80 else residual[:77] + "…"
        return [
            f"lane {lane}: Decisions / Specs cell must be pointers only "
            f"(INDEX one-fact-one-home / ICM) — residual text: {preview!r}"
        ]
    return []


def _parse_lane_tags(review_flags_cell: str) -> list[str]:
    cell = (review_flags_cell or "").strip()
    if not cell or cell in {"-", "—", "`-`"}:
        return []
    tags: list[str] = []
    for part in re.split(r"[,|/]", cell):
        t = part.strip().strip("`")
        if t and t not in {"-", "—"}:
            tags.append(t)
    return tags


def _repo_relative_paths(repo_root: Path, limit: int = 20000) -> list[str]:
    """Best-effort file list for dead-glob checks (git ls-files, else walk)."""
    try:
        proc = subprocess.run(  # noqa: S603
            ["git", "-C", str(repo_root), "ls-files"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()][:limit]
    except OSError:
        pass
    out: list[str] = []
    for p in repo_root.rglob("*"):
        if p.is_file():
            try:
                out.append(str(p.relative_to(repo_root)))
            except ValueError:
                continue
            if len(out) >= limit:
                break
    return out


def _dead_glob_warnings(
    decision: Any,
    repo_files: Sequence[str],
) -> list[str]:
    warns: list[str] = []
    tags = getattr(decision, "tags", None) or []
    oid = getattr(decision, "id", "?")
    for tag in tags:
        if not isinstance(tag, str) or not tag.startswith(_PATH_PREFIX):
            continue
        pattern = tag[len(_PATH_PREFIX) :]
        if not pattern:
            continue
        if not any(fnmatch.fnmatch(p, pattern) for p in repo_files):
            warns.append(
                f"decision #{oid}: dead path glob {pattern!r} matches zero repo files"
            )
    return warns


def check_decision_candidates(
    *,
    lane: str,
    cell: str,
    files_in_scope: Sequence[str],
    lane_tags: Sequence[str],
    decisions: Sequence[Any],
    repo_root: Path | None,
) -> tuple[list[str], list[str]]:
    """Surface unmatched path/area decisions; hard-floor when neither accepted nor waived.

    Returns (errors, warnings). Dead-glob warnings are non-blocking (d#852).
    """
    from taskman.matching import decisions_touching
    from taskman.mow import hydrate_specs as hydrate_mod

    accepted = {oid for kind, oid in hydrate_mod.parse_pointer_cell(cell) if kind == "d"}
    waived = {oid for oid, _reason in hydrate_mod.parse_waived(cell)}
    handled = accepted | waived

    candidates = decisions_touching(
        decisions, paths=list(files_in_scope), tags=list(lane_tags)
    )
    errors: list[str] = []
    warnings: list[str] = []
    repo_files = _repo_relative_paths(repo_root) if repo_root is not None else []

    for dec in candidates:
        oid = getattr(dec, "id", None)
        if oid is None:
            continue
        title = getattr(dec, "title", "") or ""
        if oid not in handled:
            errors.append(
                f"lane {lane}: candidate decision #{oid}"
                + (f" ({title})" if title else "")
                + " matches Files in scope / lane tags but is neither in the "
                "Decisions / Specs cell nor waved off — accept it (add d `#N`) or "
                f"wave off with `waived: d#{oid} (<reason>)`"
            )
        if repo_files:
            warnings.extend(_dead_glob_warnings(dec, repo_files))

    # Also warn on accepted-but-not-touching decisions that carry dead globs
    # when they appear in the cell (surfaced via pointer, not path match).
    if repo_files:
        by_id = {getattr(d, "id", None): d for d in decisions}
        for oid in accepted:
            dec = by_id.get(oid)
            if dec is None:
                continue
            if any(getattr(c, "id", None) == oid for c in candidates):
                continue  # already warned above
            warnings.extend(_dead_glob_warnings(dec, repo_files))

    return errors, warnings


def _split_lanes_table_extended(index_text: str) -> list[dict[str, str]]:
    """Lane rows including Decisions/Specs and Review flags when present."""
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    in_table = False
    for line in index_text.splitlines():
        if line.startswith("|") and "Lane" in line and "Brief" in line:
            header = [c.strip() for c in line.strip("|").split("|")]
            in_table = True
            continue
        if in_table and line.startswith("|") and re.match(r"^\|\s*---", line):
            continue
        if in_table and line.startswith("|"):
            if header is None:
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            try:
                lane_i = header.index("Lane")
                brief_i = header.index("Brief")
            except ValueError:
                continue
            files_i = None
            for name in ("Files owned", "Files Owned"):
                if name in header:
                    files_i = header.index(name)
                    break
            dec_i = header.index("Decisions / Specs") if "Decisions / Specs" in header else None
            flags_i = header.index("Review flags") if "Review flags" in header else None
            if len(cols) <= max(lane_i, brief_i):
                continue
            lane = cols[lane_i]
            if not re.fullmatch(r"[A-Z]", lane):
                if not cols[0] or cols[0].startswith("`"):
                    break
                continue
            rows.append(
                {
                    "lane": lane,
                    "files_owned": cols[files_i] if files_i is not None and len(cols) > files_i else "",
                    "brief": cols[brief_i],
                    "decisions": cols[dec_i] if dec_i is not None and len(cols) > dec_i else "",
                    "review_flags": cols[flags_i]
                    if flags_i is not None and len(cols) > flags_i
                    else "",
                }
            )
            continue
        if in_table and not line.startswith("|"):
            break
    return rows


def _load_visible_decisions(project_slug: str | None = None) -> list[Any]:
    """Load decisions from cwd project + workflow (same visibility as hydrate)."""
    from sqlalchemy import select

    from taskman.config import find_project
    from taskman.db import Session
    from taskman.models import Decision, Project
    from taskman.mow.hydrate_specs import WORKFLOW_SLUG

    slug = project_slug or find_project()[0]
    with Session() as session:
        proj = session.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            return []
        ids = {proj.id}
        wf = session.scalar(select(Project).where(Project.slug == WORKFLOW_SLUG))
        if wf is not None:
            ids.add(wf.id)
        return list(
            session.scalars(
                select(Decision).where(Decision.project_id.in_(ids))
            ).all()
        )


def run_preflight(
    stem_dir: Path,
    *,
    repo_root: Path | None = None,
    skip_hydrate: bool = False,
    decisions: Sequence[Any] | None = None,
    skip_candidates: bool = False,
) -> tuple[int, list[str]]:
    """Run all preflight checks. Return (exit_code, errors)."""
    root = repo_root or Path.cwd()
    errors: list[str] = []
    warnings: list[str] = []

    try:
        dispatch, index_path = _resolve_dispatch(stem_dir.resolve())
    except ValueError as exc:
        return 1, [str(exc)]

    if not index_path.is_file():
        return 1, [f"missing dispatch: {index_path}"]

    index_text = index_path.read_text(encoding="utf-8")
    stem_name = _stem_name(stem_dir.resolve())

    registry_path = root / "docs" / "plans" / "INDEX.md"
    status: str | None = None
    if registry_path.is_file():
        status = registry_status(registry_path.read_text(encoding="utf-8"), stem_name)

    active = status in {"planned", "running", "paused"}
    if active:
        from taskman.mow import check_grill_writeback as grill_mod

        errors.extend(grill_mod.check_stem(stem_dir.resolve()))

    from taskman.mow import hydrate_specs as hydrate_mod
    lanes = hydrate_mod._split_index_lanes(index_text)
    needs_hydrate = lanes and not all_decisions_specs_dash(lanes)
    if needs_hydrate and not skip_hydrate:
        proc = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "taskman.mow.hydrate_specs", str(stem_dir)],
            capture_output=True,
            text=True,
            cwd=str(root),
        )
        if proc.returncode != 0:
            for line in proc.stderr.splitlines():
                if line.strip():
                    errors.append(line.strip())
            if not errors:
                errors.append("hydrate check failed")

    briefs: dict[str, str] = {}
    for path in sorted(dispatch.glob("[0-9][0-9]-*.md")):
        briefs[path.name] = path.read_text(encoding="utf-8")
        errors.extend(check_thin_brief(path.name, briefs[path.name]))

    if not briefs:
        errors.append(f"{index_path}: no NN-*.md briefs in dispatch")

    errors.extend(check_brief_index_drift(index_text, briefs))
    errors.extend(check_same_wave_overlap(index_text))
    errors.extend(check_cross_plan_overlap(root, stem_name, index_text))

    # Citation gate (after thin-brief) — d#853 / req#430
    # Pointer-prose lint — d#946 (INDEX cell must fully parse as pointer grammar)
    for lane, cell, brief_name in lanes:
        errors.extend(check_index_decisions_pointer_only(lane, cell))
        if brief_name not in briefs:
            continue
        errors.extend(
            check_pointer_citations(lane, brief_name, cell, briefs[brief_name])
        )

    # Candidate surfacing + dead-glob warnings — d#852
    if not skip_candidates:
        decs: Sequence[Any]
        if decisions is not None:
            decs = decisions
        else:
            try:
                decs = _load_visible_decisions()
            except Exception as exc:  # noqa: BLE001 — surface, do not fail-open
                # d#852: silent omission is the failure mode. Offline suites pass
                # --skip-candidates; unexpected load errors must block fan-out.
                errors.append(
                    "candidate decision load failed "
                    f"({type(exc).__name__}: {exc}) — fix DB access or pass "
                    "--skip-candidates"
                )
                decs = []
        if decs:
            for row in _split_lanes_table_extended(index_text):
                brief_name = row["brief"]
                scope = _paths_from_scope_bullets(
                    _section_body(briefs.get(brief_name, ""), "Files in scope")
                )
                if not scope:
                    scope = parse_files_owned(row["files_owned"])
                cell = row.get("decisions") or ""
                if not cell and lanes:
                    # fall back to hydrate splitter when extended parse missed column
                    for ln, c, bn in lanes:
                        if ln == row["lane"] and bn == brief_name:
                            cell = c
                            break
                e, w = check_decision_candidates(
                    lane=row["lane"],
                    cell=cell,
                    files_in_scope=scope,
                    lane_tags=_parse_lane_tags(row.get("review_flags", "")),
                    decisions=decs,
                    repo_root=root,
                )
                errors.extend(e)
                warnings.extend(w)

    # When any brief scopes a taskman/ path, also fail on sibling taskman/ drift.
    if any(
        p == "taskman" or p.startswith("taskman/")
        for text in briefs.values()
        for p in _paths_from_scope_bullets(_section_body(text, "Files in scope"))
    ):
        from taskman.mow import check_drift as drift_mod

        diffs = drift_mod.check_drift(local_taskman=root / "taskman")
        if diffs:
            errors.append(
                "taskman/ drift vs sibling project: " + ", ".join(diffs)
            )

    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)

    return (1 if errors else 0), errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stem", type=Path, help="docs/plans/<stem> or …/dispatch")
    p.add_argument("--json", action="store_true", help="machine-readable result on stdout")
    p.add_argument(
        "--skip-hydrate",
        action="store_true",
        help="skip hydrate sub-check (all `-` lanes or offline tests)",
    )
    p.add_argument(
        "--skip-candidates",
        action="store_true",
        help="skip decision-candidate surfacing (offline tests)",
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    args = p.parse_args(argv)

    stem = args.stem.resolve()
    if not stem.exists():
        msg = f"not found: {stem}"
        if args.json:
            print(json.dumps({"ok": False, "stem": str(stem), "errors": [msg]}))
        else:
            print(msg, file=sys.stderr)
        return 2

    code, errors = run_preflight(
        stem,
        repo_root=args.repo_root,
        skip_hydrate=args.skip_hydrate,
        skip_candidates=args.skip_candidates,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "ok": code == 0,
                    "stem": str(stem),
                    "errors": errors,
                },
                indent=2,
            )
        )
    elif errors:
        print("mow preflight FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
    else:
        print(f"mow preflight OK: {stem}")

    return code


if __name__ == "__main__":
    raise SystemExit(main())
