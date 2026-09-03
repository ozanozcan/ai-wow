"""Canonical Work-Item document shared by taskman and mow.

DB-free, side-effect-free serialization + pure helpers. See
``docs/workflow/taskman-dispatch-bridge.md`` §2.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from pydantic import BaseModel, Field

from taskman.eventlog.schema import LANES, PRIORITIES, STATUSES, SURFACES

log = logging.getLogger("taskman.plan")

ROLE_TAG_PREFIX = "role:"

_BRIEF_NAME_RE = re.compile(r"^(\d{2})-(.+)\.md$")
_HEADER_META_RE = re.compile(
    r"\*\*Role:\*\*\s*(?P<role>\S+)"
    r"(?:\s+\*\*Wave:\*\*\s*(?P<wave>\d+))?"
    r"(?:\s+\*\*AFK:\*\*\s*(?P<afk>\S+))?"
    r"(?:\s+\*\*Background:\*\*\s*(?P<bg>\S+))?",
    re.IGNORECASE,
)
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_SOURCE_PLAN_RE = re.compile(
    r"(?:\*\*)?Source plan(?:\*\*)?:\s*(?:\[.*?\]\((?P<link>[^)]+)\)|`?(?P<path>\S+?)`?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_MOVED_TO_RE = re.compile(
    r"\*\*Moved to:\*\*\s*(?:\[.*?\]\((?P<link>[^)]+)\)|`(?P<path>[^`]+)`)",
    re.IGNORECASE,
)
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


class DispatchMeta(BaseModel):
    role: str = ""
    wave: int = 0
    background: bool = False
    files: list[str] = Field(default_factory=list)
    acceptance: str = ""
    do_not: list[str] = Field(default_factory=list)
    context: list[str] = Field(default_factory=list)


class PlanMeta(BaseModel):
    slug: str
    title: str
    lane: str = ""
    surface: str = ""
    source_ref: str = ""


class WorkItem(BaseModel):
    id: str
    title: str
    priority: str = "med"
    status: str = "backlog"
    tags: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    source_ref: str = ""
    dispatch: DispatchMeta = Field(default_factory=DispatchMeta)


class WorkItemDoc(BaseModel):
    plan: PlanMeta
    items: list[WorkItem] = Field(default_factory=list)


def to_json(doc: WorkItemDoc) -> str:
    return doc.model_dump_json(indent=2)


def from_json(raw: str) -> WorkItemDoc:
    return WorkItemDoc.model_validate_json(raw)


def role_tag(role: str) -> str:
    return f"{ROLE_TAG_PREFIX}{role}"


def role_from_tags(tags: list[str]) -> str | None:
    for tag in tags:
        if tag.startswith(ROLE_TAG_PREFIX):
            return tag[len(ROLE_TAG_PREFIX) :] or None
    return None


def recompute_waves(items: list[WorkItem]) -> dict[str, int]:
    """Topological wave levels from ``depends_on``.

    Items with no in-set dependencies are wave 1. Dependencies whose ids are
    not in ``items`` are ignored. Raises ``ValueError`` on a cycle.
    """
    by_id = {item.id: item for item in items}
    ids = set(by_id)
    waves: dict[str, int] = {}
    visiting: set[str] = set()

    def wave_of(item_id: str) -> int:
        if item_id in waves:
            return waves[item_id]
        if item_id in visiting:
            raise ValueError(f"dependency cycle involving {item_id!r}")
        visiting.add(item_id)
        in_set_deps = [d for d in by_id[item_id].depends_on if d in ids]
        if not in_set_deps:
            w = 1
        else:
            w = 1 + max(wave_of(d) for d in in_set_deps)
        visiting.remove(item_id)
        waves[item_id] = w
        return w

    for item_id in by_id:
        wave_of(item_id)
    return waves


def validate(doc: WorkItemDoc) -> None:
    """Raise ``ValueError`` if the document violates vocab or dependency rules."""
    lane = doc.plan.lane
    if lane and lane not in LANES:
        raise ValueError(f"invalid plan.lane {lane!r}; expected one of {LANES} or ''")
    surface = doc.plan.surface
    if surface and surface not in SURFACES:
        raise ValueError(
            f"invalid plan.surface {surface!r}; expected one of {SURFACES} or ''"
        )

    item_ids = {item.id for item in doc.items}
    for item in doc.items:
        if item.priority not in PRIORITIES:
            raise ValueError(
                f"item {item.id!r}: invalid priority {item.priority!r}; "
                f"expected one of {PRIORITIES}"
            )
        if item.status not in STATUSES:
            raise ValueError(
                f"item {item.id!r}: invalid status {item.status!r}; "
                f"expected one of {STATUSES}"
            )
        for dep in item.depends_on:
            if dep not in item_ids:
                raise ValueError(
                    f"item {item.id!r}: depends_on id {dep!r} not found in items"
                )


# --- Markdown .dispatch/ folder parser (pure, best-effort) ---


def _repo_relative(path: Path, repo_root: Path | None = None) -> str:
    path = path.resolve()
    root = (repo_root or Path.cwd()).resolve()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"yes", "true", "y", "1"}


def _section_body(text: str, heading: str) -> str | None:
    """Return body text under ``## <heading>`` (case-insensitive), or None."""
    matches = list(_SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        if m.group(1).strip().lower() == heading.lower():
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            return text[start:end].strip()
    return None


def _bullet_lines(body: str | None) -> list[str]:
    if not body:
        return []
    out: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith(("- ", "* ")):
            item = s[2:].strip()
            if item.lower() in {"none", "n/a", "—", "-"}:
                continue
            # Strip trailing parenthetical notes: `foo` (brief) → foo
            item = re.sub(r"\s*\([^)]*\)\s*$", "", item).strip()
            item = item.strip("`")
            if item:
                out.append(item)
    return out


_DEP_SKIP = frozenset(
    {
        "none",
        "n/a",
        "all",
        "prior",
        "todos",
        "todo",
        "and",
        "or",
        "the",
        "a",
        "an",
    }
)
# Todo ids: kebab-case or a single lowercase word (e.g. harvest)
_DEP_TOKEN_RE = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")


def _parse_depends_on(body: str | None) -> list[str]:
    """Extract todo-ids from a Depends-on section (backticks, bullets, or prose lists)."""
    if not body:
        return []
    flat = body.strip().lower()
    if flat in {"none", "n/a", "—", "-"}:
        return []

    deps: list[str] = []
    seen: set[str] = set()

    def add(tok: str) -> None:
        tok = tok.strip().strip("`").strip().rstrip(".,;")
        if not tok or tok.lower() in _DEP_SKIP or tok in seen:
            return
        # Reject multi-word prose accidentally captured
        if " " in tok:
            return
        seen.add(tok)
        deps.append(tok)

    # Prefer explicit backtick spans anywhere in the body
    for m in re.finditer(r"`([^`]+)`", body):
        add(m.group(1))

    if deps:
        return deps

    # Prose / bullet lines without backticks
    for line in body.splitlines():
        s = line.strip()
        if not s or s.lower() in {"none", "n/a"}:
            continue
        if s.startswith(("- ", "* ")):
            s = s[2:].strip()
        # "All prior todos: a, b, c" → focus on the list after the colon
        if ":" in s:
            s = s.split(":", 1)[1]
        # Comma-separated list first (handles single-word ids like harvest)
        parts = re.split(r"\s*,\s*|\s+and\s+", s)
        if len(parts) > 1:
            for part in parts:
                m = _DEP_TOKEN_RE.fullmatch(part.strip().lower())
                if m:
                    add(m.group(0))
            continue
        for m in _DEP_TOKEN_RE.finditer(s.lower()):
            tok = m.group(0)
            if tok in _DEP_SKIP:
                continue
            # Prefer kebab-case; allow single words only when the whole line is one token
            if "-" in tok or (len(parts) == 1 and s.strip().lower() == tok):
                add(tok)
    return deps


def _parse_files(body: str | None) -> list[str]:
    return _bullet_lines(body)


def _parse_do_not(body: str | None) -> list[str]:
    return _bullet_lines(body)


def _parse_context(body: str | None) -> list[str]:
    return _bullet_lines(body)


def _slug_from_dispatch_dir(folder: Path) -> str:
    name = folder.name
    if name.endswith(".dispatch"):
        return name[: -len(".dispatch")]
    return name


def _title_from_index(index_text: str, slug: str) -> str:
    m = _H1_RE.search(index_text)
    if m:
        title = m.group(1).strip()
        title = re.sub(r"^Dispatch index\s*[—–-]\s*", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s*\(ARCHIVED\)\s*$", "", title, flags=re.IGNORECASE).strip()
        if title:
            return title
    return slug.replace("-", " ").replace("_", " ").title()


def _source_ref_from_index(index_text: str, folder: Path, repo_root: Path | None) -> str:
    m = _SOURCE_PLAN_RE.search(index_text)
    if not m:
        return ""
    raw = (m.group("link") or m.group("path") or "").strip()
    if not raw:
        return ""
    # Drop markdown title fragments / trailing punctuation
    raw = raw.rstrip(").,;")
    candidate = Path(raw)
    if candidate.is_absolute():
        return _repo_relative(candidate, repo_root)
    # Relative to INDEX.md location
    resolved = (folder / candidate).resolve()
    if resolved.is_file():
        return _repo_relative(resolved, repo_root)
    return raw.lstrip("./")


def _follow_moved_to(index_text: str, folder: Path) -> Path | None:
    m = _MOVED_TO_RE.search(index_text)
    if not m:
        return None
    raw = (m.group("link") or m.group("path") or "").strip()
    if not raw:
        return None
    # link may point at INDEX.md inside the new folder
    target = (folder / raw).resolve()
    if target.is_file() and target.name.lower() == "index.md":
        return target.parent
    if target.is_dir() and (target / "INDEX.md").is_file():
        return target
    if target.is_file():
        return target.parent
    return None


def parse_brief(path: Path, *, repo_root: Path | None = None) -> WorkItem | None:
    """Parse one ``NN-<todo-id>.md`` brief into a WorkItem. Warn+skip on failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        log.warning("skip brief %s: cannot read (%s)", path, e)
        return None

    name_m = _BRIEF_NAME_RE.match(path.name)
    if not name_m:
        log.warning("skip brief %s: filename not NN-<id>.md", path)
        return None
    item_id = name_m.group(2)

    # Archived stub pointing elsewhere — skip (canonical lives at Moved/Canonical path)
    if re.search(r"(?i)^#\s*Archived\s*$", text, re.MULTILINE) and "Canonical brief:" in text:
        log.warning("skip brief %s: archived stub", path)
        return None

    h1 = _H1_RE.search(text)
    if h1:
        h1_text = h1.group(1).strip()
        # "# <id>: <title>" or "# <title>"
        if ":" in h1_text:
            left, right = h1_text.split(":", 1)
            if left.strip() == item_id or left.strip().replace("_", "-") == item_id:
                title = right.strip() or item_id
            else:
                title = h1_text
        else:
            title = h1_text
    else:
        title = item_id

    role = ""
    wave = 0
    background = False
    meta_m = _HEADER_META_RE.search(text)
    if meta_m:
        role = (meta_m.group("role") or "").strip()
        if meta_m.group("wave") is not None:
            wave = int(meta_m.group("wave"))
        if meta_m.group("bg") is not None:
            background = _parse_bool(meta_m.group("bg"))
        elif meta_m.group("afk") is not None:
            background = _parse_bool(meta_m.group("afk"))
    else:
        # Legacy: "Gate: auto" / "Subagent:" style — best-effort
        gate_m = re.search(r"(?i)\*\*Gate:\*\*\s*(\w+)", text)
        if gate_m and gate_m.group(1).lower() == "review":
            background = False
        elif gate_m:
            background = True
        sub_m = re.search(r"(?i)\*\*Subagent:\*\*\s*(\S+)", text)
        if sub_m:
            legacy = sub_m.group(1).strip()
            role = {
                "generalpurpose": "code-edit",
                "explore": "explore",
                "shell": "shell",
            }.get(legacy.lower(), legacy)

    goal = _section_body(text, "Goal") or ""
    # Prefer first non-empty paragraph of Goal as title refinement only if H1 was bare id
    if title == item_id and goal:
        first = next((ln.strip() for ln in goal.splitlines() if ln.strip()), "")
        if first and not first.startswith("#"):
            title = first[:120]

    files = _parse_files(_section_body(text, "Files in scope"))
    depends_on = _parse_depends_on(_section_body(text, "Depends on"))
    acceptance = (_section_body(text, "Acceptance check") or "").strip()
    do_not = _parse_do_not(_section_body(text, "Do NOT"))
    context = _parse_context(_section_body(text, "Context & decisions (only what this todo needs)"))
    if not context:
        context = _parse_context(_section_body(text, "Context & decisions"))

    tags: list[str] = []
    if role:
        tags.append(role_tag(role))

    # Prefer an explicit source_ref embedded in the brief (export round-trip);
    # otherwise use the brief's own path.
    source_ref = _repo_relative(path, repo_root)
    _SRC_REF_LINE = re.compile(
        r"^(?:prior\s+)?source_ref:\s*`?([^`\s]+)`?\s*$", re.IGNORECASE
    )
    for c in context:
        m = _SRC_REF_LINE.match(c.strip())
        if m:
            source_ref = m.group(1).strip().strip("`")
            break

    return WorkItem(
        id=item_id,
        title=title,
        priority="med",
        status="backlog",
        tags=tags,
        depends_on=depends_on,
        source_ref=source_ref,
        dispatch=DispatchMeta(
            role=role,
            wave=wave,
            background=background,
            files=files,
            acceptance=acceptance,
            do_not=do_not,
            context=context,
        ),
    )


def load_dispatch_folder(folder: Path, *, repo_root: Path | None = None) -> WorkItemDoc:
    """Parse a ``.dispatch/`` directory (INDEX.md + NN-*.md briefs) into a WorkItemDoc.

    Follows a ``**Moved to:**`` pointer in INDEX.md when present. Malformed briefs
    are warned and skipped.
    """
    folder = folder.resolve()
    if not folder.is_dir():
        raise ValueError(f"not a directory: {folder}")

    index_path = folder / "INDEX.md"
    if not index_path.is_file():
        raise ValueError(f"missing INDEX.md in {folder}")

    index_text = index_path.read_text(encoding="utf-8")
    moved = _follow_moved_to(index_text, folder)
    if moved is not None and moved != folder:
        return load_dispatch_folder(moved, repo_root=repo_root)

    slug = _slug_from_dispatch_dir(folder)
    # Prefer stem from original .dispatch name if we followed a move into docs/
    # Caller may pass the archived .cursor path; slug from that folder name is fine
    # when INDEX was not a stub. If we are inside docs/plans/.../dispatch, derive
    # slug from parent plan folder when folder.name == "dispatch".
    if folder.name == "dispatch" and folder.parent.name:
        slug = folder.parent.name

    title = _title_from_index(index_text, slug)
    source_ref = _source_ref_from_index(index_text, folder, repo_root)

    items: list[WorkItem] = []
    for brief_path in sorted(folder.glob("[0-9][0-9]-*.md")):
        item = parse_brief(brief_path, repo_root=repo_root)
        if item is not None:
            items.append(item)

    if not items:
        raise ValueError(f"no parseable briefs in {folder}")

    # Soft-validate depends_on: drop dangling refs with a warning (import still works)
    ids = {i.id for i in items}
    for item in items:
        kept = []
        for dep in item.depends_on:
            if dep in ids:
                kept.append(dep)
            else:
                log.warning(
                    "item %s: dropping unknown depends_on %r", item.id, dep
                )
        item.depends_on = kept

    return WorkItemDoc(
        plan=PlanMeta(
            slug=slug,
            title=title,
            lane="",
            surface="",
            source_ref=source_ref,
        ),
        items=items,
    )


def load_plan_path(path: Path, *, repo_root: Path | None = None) -> WorkItemDoc:
    """Load a WorkItemDoc from a ``.json`` file or a ``.dispatch/`` directory."""
    path = path.resolve()
    if path.is_file() and path.suffix.lower() == ".json":
        return from_json(path.read_text(encoding="utf-8"))
    if path.is_dir():
        return load_dispatch_folder(path, repo_root=repo_root)
    raise ValueError(
        f"expected a .dispatch/ directory or a .json file, got: {path}"
    )


# --- Export: pack lanes + render INDEX/briefs (pure) ---


class ExportLane(BaseModel):
    """One dispatch lane after wave packing (may hold multiple sequential todos)."""

    letter: str
    wave: int
    item_ids: list[str]
    files: list[str] = Field(default_factory=list)
    role: str = "code-edit"
    background: bool = True
    needs_review: bool = False
    brief_names: list[str] = Field(default_factory=list)


_OUTSIDE_REPO_RE = re.compile(r"^(?:~|/|\$HOME\b)")


def is_outside_repo_path(path: str) -> bool:
    """True for home/global paths that must stay foreground / needs-review."""
    s = path.strip()
    if not s:
        return False
    if _OUTSIDE_REPO_RE.match(s):
        return True
    # Absolute path that is not clearly in-repo relative
    p = Path(s)
    return p.is_absolute() and not s.startswith("./")


def item_id_from_source_ref(source_ref: str) -> str | None:
    """Extract todo-id from an ``NN-<id>.md`` source_ref filename."""
    if not source_ref:
        return None
    m = _BRIEF_NAME_RE.match(Path(source_ref).name)
    return m.group(2) if m else None


def _normalize_item_for_export(item: WorkItem) -> None:
    """Fill role/background defaults in-place for export."""
    role = (item.dispatch.role or "").strip() or role_from_tags(item.tags) or "code-edit"
    item.dispatch.role = role
    if role_tag(role) not in item.tags:
        item.tags = list(item.tags) + [role_tag(role)]

    # Explicit False stays False; None-ish / unset uses defaults.
    # DispatchMeta.background is bool — treat shell / outside-repo as forced foreground.
    outside = any(is_outside_repo_path(f) for f in item.dispatch.files)
    if role == "shell" or outside:
        item.dispatch.background = False
    # else keep whatever was stored (True/False from brief)


def _files_overlap(a: list[str], b: list[str]) -> bool:
    if not a or not b:
        return False
    return bool(set(a) & set(b))


def _order_ids_by_deps(item_ids: list[str], by_id: dict[str, WorkItem]) -> list[str]:
    """Stable topo order within a lane; fall back to input order on cycle."""
    id_set = set(item_ids)
    remaining = list(item_ids)
    ordered: list[str] = []
    while remaining:
        ready = [
            i
            for i in remaining
            if not any(d in id_set and d not in ordered for d in by_id[i].depends_on)
        ]
        if not ready:
            ordered.extend(remaining)
            break
        # Preserve original relative order among ready
        ready_set = set(ready)
        next_id = next(i for i in remaining if i in ready_set)
        ordered.append(next_id)
        remaining.remove(next_id)
    return ordered


def pack_lanes(items: list[WorkItem]) -> list[ExportLane]:
    """Recompute waves and pack same-wave items into disjoint-file lanes.

    Hard rule: lanes in the same wave must not share files. Overlapping file-sets
    are merged into one sequential lane. Items with no recorded files (legacy /
    unknown) each get their own needs-review lane.

    Raises ``ValueError`` if the packed result still violates the hard rule.
    """
    if not items:
        return []

    for item in items:
        _normalize_item_for_export(item)

    waves = recompute_waves(items)
    for item in items:
        item.dispatch.wave = waves[item.id]

    by_id = {item.id: item for item in items}
    # Preserve input order as tie-break within a wave
    input_order = {item.id: i for i, item in enumerate(items)}

    by_wave: dict[int, list[str]] = {}
    for item in items:
        by_wave.setdefault(waves[item.id], []).append(item.id)
    for w in by_wave:
        by_wave[w].sort(key=lambda i: input_order[i])

    lanes: list[ExportLane] = []
    letter_ord = 0

    def next_letter() -> str:
        nonlocal letter_ord
        # A..Z then AA, AB, …
        n = letter_ord
        letter_ord += 1
        s = ""
        while True:
            s = chr(ord("A") + (n % 26)) + s
            n = n // 26 - 1
            if n < 0:
                break
        return s

    for wave in sorted(by_wave):
        ids = by_wave[wave]
        # Partition: unknown files vs known
        unknown = [i for i in ids if not by_id[i].dispatch.files]
        known = [i for i in ids if by_id[i].dispatch.files]

        # Union-find merge on file overlap for known items
        parent = {i: i for i in known}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for i, a in enumerate(known):
            for b in known[i + 1 :]:
                if _files_overlap(by_id[a].dispatch.files, by_id[b].dispatch.files):
                    union(a, b)

        groups: dict[str, list[str]] = {}
        for i in known:
            groups.setdefault(find(i), []).append(i)

        # Emit known groups first (stable by earliest input_order member), then unknowns
        group_list = sorted(
            groups.values(),
            key=lambda g: min(input_order[x] for x in g),
        )
        for group in group_list:
            ordered = _order_ids_by_deps(group, by_id)
            files: list[str] = []
            seen_f: set[str] = set()
            for iid in ordered:
                for f in by_id[iid].dispatch.files:
                    if f not in seen_f:
                        seen_f.add(f)
                        files.append(f)
            roles = [by_id[iid].dispatch.role for iid in ordered]
            role = roles[0] if len(set(roles)) == 1 else roles[0]
            background = all(by_id[iid].dispatch.background for iid in ordered)
            lanes.append(
                ExportLane(
                    letter=next_letter(),
                    wave=wave,
                    item_ids=ordered,
                    files=files,
                    role=role,
                    background=background,
                    needs_review=not background,
                )
            )

        for iid in unknown:
            # Legacy / no files → own lane, needs-review (unknown conflict)
            by_id[iid].dispatch.background = False
            lanes.append(
                ExportLane(
                    letter=next_letter(),
                    wave=wave,
                    item_ids=[iid],
                    files=[],
                    role=by_id[iid].dispatch.role,
                    background=False,
                    needs_review=True,
                )
            )

    # Assign brief filenames in wave order (global NN)
    nn = 1
    for lane in lanes:
        names: list[str] = []
        for iid in lane.item_ids:
            names.append(f"{nn:02d}-{iid}.md")
            nn += 1
        lane.brief_names = names

    # Hard-rule verify: no same-wave cross-lane file overlap
    verify_lane_file_disjoint(lanes)

    return lanes


def verify_lane_file_disjoint(lanes: list[ExportLane]) -> None:
    """Raise ``ValueError`` if two same-wave lanes share a file."""
    by_wave: dict[int, list[ExportLane]] = {}
    for lane in lanes:
        by_wave.setdefault(lane.wave, []).append(lane)
    for wave, wave_lanes in by_wave.items():
        owned: dict[str, str] = {}
        for lane in wave_lanes:
            for f in lane.files:
                if f in owned:
                    raise ValueError(
                        f"dispatch hard rule violated: wave {wave} lanes "
                        f"{owned[f]} and {lane.letter} both own {f!r}"
                    )
                owned[f] = lane.letter


def _format_files_cell(files: list[str]) -> str:
    if not files:
        return "_(unknown — needs-review)_"
    return ", ".join(f"`{f}`" for f in files)


def _format_todos_cell(item_ids: list[str]) -> str:
    if len(item_ids) == 1:
        return item_ids[0]
    return " → ".join(item_ids)


def _wave_label(wave: int, wave_lanes: list[ExportLane]) -> str:
    if len(wave_lanes) > 1:
        kind = "parallel"
    elif wave_lanes and not wave_lanes[0].background:
        kind = "foreground"
    else:
        kind = "background"
    if wave <= 1:
        return f"Wave {wave} ({kind})"
    return f"Wave {wave} ({kind})"


def _wave_lane_phrase(lane: ExportLane) -> str:
    if len(lane.item_ids) == 1:
        return f"Lane {lane.letter} — `{lane.item_ids[0]}`"
    seq = "→".join(lane.item_ids)
    return f"Lane {lane.letter} (seq: {seq})"


def render_brief(item: WorkItem) -> str:
    """Render one brief using the mow SKILL template."""
    role = (item.dispatch.role or role_from_tags(item.tags) or "code-edit").strip()
    wave = item.dispatch.wave
    bg = "yes" if item.dispatch.background else "no"
    lines: list[str] = [
        f"# {item.id}: {item.title}",
        "",
        f"**Role:** {role}   **Wave:** {wave}   **Background:** {bg}",
        "",
        "## Goal",
        item.title,
        "",
        "## Context & decisions (only what this todo needs)",
    ]
    # Deduplicate source_ref lines already in context
    ctx_lines = list(item.dispatch.context)
    has_src = any(
        re.match(r"^(?:prior\s+)?source_ref:\s*`", c.strip(), re.I) for c in ctx_lines
    )
    if item.source_ref and not has_src:
        ctx_lines.append(f"source_ref: `{item.source_ref}`")
    if ctx_lines:
        for c in ctx_lines:
            lines.append(f"- {c}")
    else:
        lines.append("- _(none recorded)_")

    lines.extend(["", "## Files in scope"])
    if item.dispatch.files:
        for f in item.dispatch.files:
            lines.append(f"- `{f}`")
    else:
        lines.append("- _(none recorded — needs-review)_")

    lines.extend(["", "## Depends on"])
    if item.depends_on:
        for d in item.depends_on:
            lines.append(f"- `{d}`")
    else:
        lines.append("- none")

    lines.extend(["", "## Do NOT"])
    if item.dispatch.do_not:
        for d in item.dispatch.do_not:
            lines.append(f"- {d}")
    else:
        lines.append("- _(none)_")

    lines.extend(["", "## Acceptance check"])
    if item.dispatch.acceptance:
        # Preserve multi-line acceptance as-is when it already looks like bullets
        acc = item.dispatch.acceptance.strip()
        if acc.startswith(("- ", "* ")) or "\n" in acc:
            lines.append(acc)
        else:
            lines.append(f"- {acc}")
    else:
        lines.append("- _(none)_")

    lines.append("")
    return "\n".join(lines)


def render_index(doc: WorkItemDoc, lanes: list[ExportLane] | None = None) -> str:
    """Render INDEX.md using the mow SKILL template."""
    if lanes is None:
        lanes = pack_lanes(list(doc.items))

    source = doc.plan.source_ref or f".cursor/plans/{doc.plan.slug}.plan.md"

    lines: list[str] = [
        f"# Dispatch index — {doc.plan.title}",
        "",
        f"Source plan: `{source}`",
        "",
    ]
    if doc.plan.lane or doc.plan.surface:
        meta_bits = []
        if doc.plan.lane:
            meta_bits.append(f"lane=`{doc.plan.lane}`")
        if doc.plan.surface:
            meta_bits.append(f"surface=`{doc.plan.surface}`")
        lines.append(f"**Plan meta:** {' · '.join(meta_bits)}")
        lines.append("")

    lines.append("## Waves")
    by_wave: dict[int, list[ExportLane]] = {}
    for lane in lanes:
        by_wave.setdefault(lane.wave, []).append(lane)
    for wave in sorted(by_wave):
        wave_lanes = by_wave[wave]
        label = _wave_label(wave, wave_lanes)
        if len(wave_lanes) > 1:
            parts = " ‖ ".join(_wave_lane_phrase(l) for l in wave_lanes)
        else:
            parts = _wave_lane_phrase(wave_lanes[0])
        lines.append(f"- **{label}:** {parts}")

    lines.extend(
        [
            "",
            "## Lanes",
            "| Lane | Todos (in order) | Files owned | Role | Background | Brief |",
            "|---|---|---|---|---|---|",
        ]
    )
    for lane in lanes:
        bg = "yes" if lane.background else "NO"
        briefs = ", ".join(lane.brief_names)
        lines.append(
            f"| {lane.letter} | {_format_todos_cell(lane.item_ids)} | "
            f"{_format_files_cell(lane.files)} | {lane.role} | {bg} | {briefs} |"
        )

    lines.extend(["", "## Conflicts check"])
    try:
        verify_lane_file_disjoint(lanes)
        lines.append(
            "Confirm: no two same-wave lanes share a file. "
            "Overlaps were serialized into sequential lanes where needed."
        )
    except ValueError as e:
        lines.append(f"FAIL: {e}")

    review = [l for l in lanes if not l.files]
    if review:
        ids = ", ".join(f"`{iid}`" for l in review for iid in l.item_ids)
        lines.append(f"Needs-review (unknown files): {ids}.")
    fg = [l for l in lanes if l.needs_review and l.files]
    if fg:
        ids = ", ".join(f"`{iid}`" for l in fg for iid in l.item_ids)
        lines.append(f"Foreground / needs-review: {ids}.")

    # Note any same-wave sequential merges
    merged = [l for l in lanes if len(l.item_ids) > 1]
    if merged:
        for l in merged:
            lines.append(
                f"Lane {l.letter} is sequential ({' → '.join(l.item_ids)}) "
                f"due to shared files within wave {l.wave}."
            )

    lines.append("")
    return "\n".join(lines)


def write_dispatch_folder(doc: WorkItemDoc, dest: Path) -> list[ExportLane]:
    """Write ``INDEX.md`` + ``NN-<id>.md`` briefs under ``dest``.

    Recomputes waves, packs lanes (enforcing the disjoint-file hard rule), and
    renders using the mow templates. Each brief embeds the item's
    ``source_ref`` so a later re-import upserts the same Task rows.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)

    items = [item.model_copy(deep=True) for item in doc.items]
    working = WorkItemDoc(plan=doc.plan.model_copy(deep=True), items=items)

    lanes = pack_lanes(working.items)
    by_id = {i.id: i for i in working.items}

    for lane in lanes:
        for iid, brief_name in zip(lane.item_ids, lane.brief_names):
            item = by_id[iid]
            (dest / brief_name).write_text(render_brief(item), encoding="utf-8")

    (dest / "INDEX.md").write_text(render_index(working, lanes), encoding="utf-8")

    # Sync wave numbers back onto caller's doc for convenience
    wave_by_id = {i.id: i.dispatch.wave for i in working.items}
    for item in doc.items:
        if item.id in wave_by_id:
            item.dispatch.wave = wave_by_id[item.id]

    return lanes
