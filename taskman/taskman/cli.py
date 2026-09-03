from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import re
import sys
from pathlib import Path

from taskman.config import find_project, find_toolkit
from taskman.eventlog import store
from taskman.eventlog.schema import (
    CAPTURE_KINDS,
    LANES,
    PRIORITIES,
    REQUIREMENT_STATUSES,
    STATUSES,
    SURFACES,
)
from taskman.matching import decision_matches
from taskman.metrics import (
    build_meta,
    detect_project_slug,
    iter_transcripts,
    meta_path_for,
    parse_jsonl,
    portable_transcript_path,
    write_meta,
)
from taskman.plan import (
    DispatchMeta,
    PlanMeta,
    WorkItem,
    WorkItemDoc,
    item_id_from_source_ref,
    load_plan_path,
    parse_brief,
    role_from_tags,
    role_tag,
    validate,
    write_dispatch_folder,
)

log = logging.getLogger("taskman")

# keystone first, low last, unknown after (derived from the schema tuple —
# eventlog exports no ordering map by contract).
PRIORITY_ORDER = {p: i for i, p in enumerate(PRIORITIES)}


def _now_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def _parse_iso(raw) -> dt.datetime | None:
    """Board timestamps are ISO strings; tolerate absent/naive values."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        when = dt.datetime.fromisoformat(raw.strip())
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.UTC)
    return when


def _project_root() -> Path:
    """Directory holding the nearest .taskman.toml (the project, per d-p6)."""
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / ".taskman.toml").exists():
            return d
    raise SystemExit(
        "taskman: no .taskman.toml found above cwd — refusing to guess the project."
    )


def _board() -> tuple[str, Path]:
    """(slug, board_dir) for the cwd project.

    Identity still comes from the marker (find_project stops loudly on a
    missing marker or slug — d-p6); the board lives next to it.
    """
    slug, _name = find_project()
    board_dir = _project_root() / "board"
    if not board_dir.is_dir():
        raise SystemExit(f"taskman: {board_dir} missing — run `taskman init` first.")
    return slug, board_dir


def _require_status(status: str) -> None:
    if status not in STATUSES:
        raise SystemExit(f"taskman: invalid status '{status}'. choose from {', '.join(STATUSES)}.")


def _require_capture_kind(kind: str) -> None:
    if kind not in CAPTURE_KINDS:
        raise SystemExit(
            f"taskman: invalid kind '{kind}'. choose from {', '.join(CAPTURE_KINDS)}."
        )


def _require_priority(priority: str) -> None:
    if priority not in PRIORITIES:
        raise SystemExit(
            f"taskman: invalid priority '{priority}'. choose from {', '.join(PRIORITIES)}."
        )


def _require_lane(lane: str) -> None:
    if lane and lane not in LANES:
        raise SystemExit(f"taskman: invalid lane '{lane}'. choose from {', '.join(LANES)}.")


def _require_surface(surface: str) -> None:
    if surface and surface not in SURFACES:
        raise SystemExit(
            f"taskman: invalid surface '{surface}'. choose from {', '.join(SURFACES)}."
        )


def _require_requirement_status(status: str) -> None:
    if status not in REQUIREMENT_STATUSES:
        raise SystemExit(
            f"taskman: invalid status '{status}'. choose from {', '.join(REQUIREMENT_STATUSES)}."
        )


def _parse_scenarios(raw: list[str] | None) -> list[dict[str, str]]:
    """Parse repeated ``--scenario "name|given|when|then"`` into dicts."""
    scenarios: list[dict[str, str]] = []
    for entry in raw or []:
        parts = [p.strip() for p in entry.split("|")]
        if len(parts) != 4:
            raise SystemExit(
                "taskman: --scenario must be 'name|given|when|then' "
                f"(got {len(parts)} part(s)): {entry!r}"
            )
        name, given, when, then = parts
        scenarios.append({"name": name, "given": given, "when": when, "then": then})
    return scenarios


def _priority_rank(row: dict) -> int:
    """Sort key: keystone first, low last, unknown after."""
    return PRIORITY_ORDER.get(row.get("priority") or "", len(PRIORITIES))


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _get_task(state: dict, slug: str, task_id: int) -> dict:
    task = state["task"].get(task_id)
    if task is None:
        raise SystemExit(f"taskman: task #{task_id} not found in project '{slug}'.")
    return task


def _get_capture(state: dict, slug: str, capture_id: int) -> dict:
    cap = state["capture"].get(capture_id)
    if cap is None:
        raise SystemExit(
            f"taskman: capture #{capture_id} not found in project '{slug}'."
        )
    return cap


def _get_decision(state: dict, slug: str, decision_id: int) -> dict:
    dec = state["decision"].get(decision_id)
    if dec is None:
        raise SystemExit(
            f"taskman: decision #{decision_id} not found in project '{slug}'."
        )
    return dec


_TASK_ID_IN_SUMMARY = re.compile(r"^#(\d+)\b")


def _task_id_from_summary(summary: str) -> int | None:
    match = _TASK_ID_IN_SUMMARY.match(summary.strip())
    if match is None:
        return None
    return int(match.group(1))


def _format_capture_line(cap: dict) -> str:
    task_s = f"  task=#{cap['task_id']}" if cap.get("task_id") is not None else ""
    tags = ",".join(cap.get("tags") or [])
    tag_s = f"  tags={tags}" if tags else ""
    return f"#{cap['id']} [{cap.get('kind', '')}]{task_s}{tag_s}  {cap.get('summary', '')}"


def _format_decision_line(dec: dict) -> str:
    task_s = f"  task=#{dec['task_id']}" if dec.get("task_id") is not None else ""
    tags = ",".join(dec.get("tags") or [])
    tag_s = f"  tags={tags}" if tags else ""
    return f"#{dec['id']}{task_s}{tag_s}  {dec.get('title', '')}"


def _get_feature(state: dict, slug: str, feature_id: int) -> dict:
    feat = state["feature"].get(feature_id)
    if feat is None:
        raise SystemExit(
            f"taskman: feature #{feature_id} not found in project '{slug}'."
        )
    return feat


def _get_pbi(state: dict, slug: str, pbi_id: int) -> dict:
    pbi = state["pbi"].get(pbi_id)
    if pbi is None or pbi.get("deleted"):
        raise SystemExit(f"taskman: pbi #{pbi_id} not found in project '{slug}'.")
    return pbi


def _live_pbis(state: dict) -> list[dict]:
    """PBIs minus removed ones — the log has no delete verb, so `pbi remove`
    is a CLI-level soft delete (``deleted: true``) every reader filters."""
    return [p for p in state["pbi"].values() if not p.get("deleted")]


def _get_requirement(state: dict, slug: str, requirement_id: int) -> dict:
    req = state["requirement"].get(requirement_id)
    if req is None:
        raise SystemExit(
            f"taskman: requirement #{requirement_id} not found in project '{slug}'."
        )
    return req


TOOLKIT_TAG_PREFIXES = ("skill:", "agent:")


def toolkit_for_tags(tags: list[str], mapping: dict[str, list[str]]) -> list[str]:
    """Recommended skills/agents for a task's tags (derived at render time).

    Union of the `.taskman.toml [toolkit]` entries for each tag, in tag order,
    deduped. Tags of the form ``skill:<name>`` / ``agent:<name>`` pass through
    verbatim as explicit recommendations. Unmapped tags contribute nothing.
    """
    out: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        recs = [tag] if tag.startswith(TOOLKIT_TAG_PREFIXES) else mapping.get(tag, [])
        for rec in recs:
            if rec not in seen:
                seen.add(rec)
                out.append(rec)
    return out


def _budget_max_tool_calls(brief: dict | None) -> int | None:
    if not isinstance(brief, dict):
        return None
    budget = brief.get("budget")
    if not isinstance(budget, dict):
        return None
    raw = budget.get("max_tool_calls")
    if isinstance(raw, bool) or not isinstance(raw, int):
        return None
    return raw


BLOCKER_TITLE_MAX = 40


def _blocker_title(title: str) -> str:
    """Blocker title clipped to BLOCKER_TITLE_MAX, ellipsis appended when cut."""
    title = title or ""
    return title if len(title) <= BLOCKER_TITLE_MAX else title[:BLOCKER_TITLE_MAX] + "…"


def _format_task_line(t: dict, tasks_by_id: dict[int, dict], *, indent: str = "  ") -> str:
    tags = "  " + ",".join(t.get("tags") or []) if t.get("tags") else ""
    blocked = t.get("blocked_by") or []
    blk = (
        "  blocked-by:"
        + ",".join(
            f'"{_blocker_title((tasks_by_id.get(b) or {}).get("title", ""))}" (#{b})'
            for b in blocked
        )
        if blocked
        else ""
    )
    lens = _lens_str(t.get("lane") or "", t.get("surface") or "")
    lens_s = f"  {lens}" if lens else ""
    afk_s = f"  afk={t['afk']}" if t.get("afk") else ""
    claimed_s = f"  claimed={t['claimed_by']}" if t.get("claimed_by") else ""
    budget_n = _budget_max_tool_calls(t.get("brief"))
    budget_s = f"  budget={budget_n}" if budget_n is not None else ""
    return (
        f"{indent}#{t['id']} [{t.get('status', '')}] [{t.get('priority', '')}] {t.get('title', '')}"
        f"{tags}{lens_s}{afk_s}{claimed_s}{budget_s}{blk}"
    )


def _acceptance_from_brief(brief: dict | None) -> str:
    if not isinstance(brief, dict):
        return ""
    acc = brief.get("acceptance") or ""
    return acc.strip() if isinstance(acc, str) else str(acc).strip()


def _sync_pbi_acceptance_from_tasks(board_dir: Path, pbi_ids: set[int]) -> None:
    """Aggregate task brief acceptance strings onto linked PBIs (import backfill)."""
    state = store.state(board_dir)
    for pbi_id in pbi_ids:
        pbi = state["pbi"].get(pbi_id)
        if pbi is None or pbi.get("deleted"):
            continue
        parts: list[str] = []
        seen: set[str] = set()
        for t in sorted(state["task"].values(), key=lambda r: r["id"]):
            if t.get("pbi_id") != pbi_id:
                continue
            acc = _acceptance_from_brief(t.get("brief"))
            if acc and acc not in seen:
                seen.add(acc)
                parts.append(acc)
        if parts:
            store.update(
                board_dir,
                "pbi",
                pbi_id,
                {"acceptance_criteria": "\n\n".join(parts), "updated_at": _now_iso()},
            )


def _upsert_session(board_dir: Path, meta: dict, transcript: Path) -> None:
    """One session row per (session_id, transcript_path), portable form (d-p9)."""
    totals = meta.get("totals") or {}
    path_str = portable_transcript_path(transcript)
    recorded = meta.get("recorded_at")
    if not isinstance(recorded, str) or _parse_iso(recorded) is None:
        recorded = _now_iso()
    fields = {
        "session_id": meta["session_id"],
        "source": meta.get("source") or "unknown",
        "transcript_path": path_str,
        "tokens_status": meta.get("tokens_status") or "unknown",
        "input_tokens": int(totals.get("input_tokens") or 0),
        "output_tokens": int(totals.get("output_tokens") or 0),
        "cache_read_tokens": int(totals.get("cache_read_tokens") or 0),
        "cache_creation_tokens": int(totals.get("cache_creation_tokens") or 0),
        "api_calls": int(totals.get("api_calls") or 0),
        "models": meta.get("models") or {},
        "effort": meta.get("effort") or {},
        "recorded_at": recorded,
    }
    existing = next(
        (
            row
            for row in store.state(board_dir)["session"].values()
            if row.get("session_id") == meta["session_id"]
            and row.get("transcript_path") == path_str
        ),
        None,
    )
    if existing is None:
        store.add(board_dir, "session", fields)  # emits session.record (d-p8)
    else:
        store.update(board_dir, "session", existing["id"], fields)


def _record_one(transcript: Path, slug: str, board_dir: Path, *, skip_existing_meta: bool) -> str:
    """Write meta.json + record the board event. Returns status label."""
    transcript = transcript.resolve()
    if not transcript.is_file():
        raise SystemExit(f"taskman: file not found: {transcript}")

    sidecar = meta_path_for(transcript)
    if skip_existing_meta and sidecar.is_file():
        return "skipped"

    slug = detect_project_slug(transcript, default=slug) or slug
    parsed = parse_jsonl(transcript)
    meta = build_meta(transcript, project_slug=slug, parsed=parsed)
    write_meta(transcript, meta)
    _upsert_session(board_dir, meta, transcript)
    return meta.get("tokens_status") or "ok"


def cmd_init(args) -> None:
    """Create ``board/`` next to the nearest .taskman.toml (init-db successor)."""
    slug, _name = find_project()
    board_dir = _project_root() / "board"
    board_dir.mkdir(exist_ok=True)
    keep = board_dir / ".gitkeep"
    if not keep.exists():
        # An empty board must still exist in git; the store writes events.jsonl
        # on first append, so a fresh board carries only this placeholder.
        keep.write_text("", encoding="utf-8")
    print(f"taskman: board ready at {board_dir} (project '{slug}').")


def cmd_session_record(args) -> None:
    path = Path(args.file)
    slug, board_dir = _board()
    status = _record_one(path, slug, board_dir, skip_existing_meta=False)
    print(f"taskman: recorded {path} [{status}]")


def cmd_session_backfill(args) -> None:
    root = Path(args.root) if args.root else Path("docs/chat-history")
    files = iter_transcripts(root)
    recorded = skipped = errors = 0
    slug, board_dir = _board()
    for path in files:
        try:
            status = _record_one(path, slug, board_dir, skip_existing_meta=True)
            if status == "skipped":
                skipped += 1
            else:
                recorded += 1
        except Exception as e:
            errors += 1
            log.warning("backfill failed for %s: %s", path, e)
            print(f"taskman: warning: skipped corrupt/failed {path}: {e}")
    print(
        f"taskman: backfill done — recorded={recorded} skipped={skipped} errors={errors} "
        f"(root={root})"
    )


def cmd_session_list(args) -> None:
    since = None
    if args.since:
        try:
            since = dt.date.fromisoformat(args.since)
        except ValueError as e:
            raise SystemExit(f"taskman: invalid --since DATE (use YYYY-MM-DD): {e}") from e

    slug, board_dir = _board()
    rows = sorted(
        store.state(board_dir)["session"].values(),
        key=lambda r: (r.get("recorded_at") or "", r["id"]),
        reverse=True,
    )
    if since is not None:
        rows = [
            r
            for r in rows
            if (when := _parse_iso(r.get("recorded_at"))) is not None
            and when.date() >= since
        ]

    print(f"# sessions: {slug} ({len(rows)})")
    if not rows:
        print("  (none)")
        return

    sum_in = sum_out = sum_calls = 0
    for r in rows:
        sum_in += r.get("input_tokens") or 0
        sum_out += r.get("output_tokens") or 0
        sum_calls += r.get("api_calls") or 0
        models = r.get("models") or {}
        if r.get("tokens_status") == "unknown":
            model_s = "tokens=unknown"
        elif models:
            parts = []
            for name, bucket in sorted(models.items()):
                if isinstance(bucket, dict):
                    parts.append(
                        f"{name}:in={bucket.get('input_tokens', 0)}/"
                        f"out={bucket.get('output_tokens', 0)}/"
                        f"calls={bucket.get('api_calls', 0)}"
                    )
                else:
                    parts.append(str(name))
            model_s = "; ".join(parts)
        else:
            model_s = "(no models)"
        print(
            f"  {r.get('session_id')}  source={r.get('source')}  status={r.get('tokens_status')}  "
            f"in={r.get('input_tokens', 0)} out={r.get('output_tokens', 0)} "
            f"calls={r.get('api_calls', 0)}  {model_s}"
        )
    print(
        f"\n# totals: input={sum_in} output={sum_out} api_calls={sum_calls}"
    )


# --- Feature ---


def _lens_str(lane: str, surface: str) -> str:
    parts = []
    if lane:
        parts.append(f"lane={lane}")
    if surface:
        parts.append(f"surface={surface}")
    return "  " + " ".join(parts) if parts else ""


def cmd_feature_add(args) -> None:
    _require_status(args.status)
    _require_lane(args.lane)
    _require_surface(args.surface)
    tag_names = _parse_tags(args.tags)
    _slug, board_dir = _board()
    now = _now_iso()
    fields = {
        "title": args.title,
        "description": args.description or "",
        "status": args.status,
        "lane": args.lane,
        "surface": args.surface,
        "tags": tag_names,
        "created_at": now,
        "updated_at": now,
    }
    feat_id = store.add(board_dir, "feature", fields)
    tags = ",".join(tag_names)
    tag_s = f"  tags={tags}" if tags else ""
    print(
        f"feature #{feat_id}  {args.title}  [{args.status}]"
        f"{_lens_str(args.lane, args.surface)}{tag_s}"
    )


def cmd_feature_list(args) -> None:
    slug, board_dir = _board()
    rows = sorted(store.state(board_dir)["feature"].values(), key=lambda r: r["id"])
    print(f"# features: {slug} ({len(rows)})")
    if not rows:
        print("  (none)")
        return
    for f in rows:
        tags = ",".join(f.get("tags") or [])
        tag_s = f"  {tags}" if tags else ""
        print(
            f"  #{f['id']}  {f.get('title', '')}  [{f.get('status', '')}]"
            f"{_lens_str(f.get('lane') or '', f.get('surface') or '')}{tag_s}"
        )


def cmd_feature_move(args) -> None:
    _require_status(args.status)
    slug, board_dir = _board()
    feat = _get_feature(store.state(board_dir), slug, args.id)
    store.update(board_dir, "feature", args.id, {"status": args.status, "updated_at": _now_iso()})
    print(f"feature #{feat['id']}  {feat.get('title', '')}  -> {args.status}")


# --- PBI ---


def cmd_pbi_add(args) -> None:
    _require_status(args.status)
    _require_priority(args.priority)
    tag_names = _parse_tags(args.tags)
    slug, board_dir = _board()
    _get_feature(store.state(board_dir), slug, args.feature)
    now = _now_iso()
    fields = {
        "feature_id": args.feature,
        "title": args.title,
        "acceptance_criteria": "",
        "status": args.status,
        "priority": args.priority,
        "tags": tag_names,
        "created_at": now,
        "updated_at": now,
    }
    pbi_id = store.add(board_dir, "pbi", fields)
    tags = ",".join(tag_names)
    tag_s = f"  tags={tags}" if tags else ""
    print(
        f"pbi #{pbi_id}  {args.title}  feature=#{args.feature}  "
        f"[{args.priority}] [{args.status}]{tag_s}"
    )


def cmd_pbi_list(args) -> None:
    slug, board_dir = _board()
    state = store.state(board_dir)
    rows = sorted(_live_pbis(state), key=lambda r: (_priority_rank(r), r["id"]))
    if args.feature is not None:
        _get_feature(state, slug, args.feature)
        rows = [p for p in rows if p.get("feature_id") == args.feature]
    scope = f" feature=#{args.feature}" if args.feature is not None else ""
    print(f"# pbis: {slug}{scope} ({len(rows)})")
    if not rows:
        print("  (none)")
        return
    for p in rows:
        tags = ",".join(p.get("tags") or [])
        tag_s = f"  {tags}" if tags else ""
        print(
            f"  #{p['id']}  {p.get('title', '')}  feature=#{p.get('feature_id')}  "
            f"[{p.get('priority', '')}] [{p.get('status', '')}]{tag_s}"
        )


def cmd_pbi_move(args) -> None:
    _require_status(args.status)
    slug, board_dir = _board()
    pbi = _get_pbi(store.state(board_dir), slug, args.id)
    store.update(board_dir, "pbi", args.id, {"status": args.status, "updated_at": _now_iso()})
    print(f"pbi #{pbi['id']}  {pbi.get('title', '')}  -> {args.status}")


def cmd_pbi_remove(args) -> None:
    """Retire a PBI. Refuses when tasks remain unless ``--force`` (d#856).

    The event log has no delete verb, so removal is a ``deleted: true`` field
    every reader filters — same soft-delete idea as requirement remove.
    """
    slug, board_dir = _board()
    state = store.state(board_dir)
    pbi = _get_pbi(state, slug, args.id)
    tasks = [t for t in state["task"].values() if t.get("pbi_id") == pbi["id"]]
    if tasks and not getattr(args, "force", False):
        raise SystemExit(
            f"taskman: pbi #{pbi['id']} still has {len(tasks)} task(s) — "
            "reparent or pass --force to delete and unlink them."
        )
    now = _now_iso()
    for t in tasks:
        store.update(board_dir, "task", t["id"], {"pbi_id": None, "updated_at": now})
    for req in state["requirement"].values():
        if req.get("source_pbi_id") == pbi["id"]:
            store.update(
                board_dir, "requirement", req["id"],
                {"source_pbi_id": None, "updated_at": now},
            )
    store.update(board_dir, "pbi", pbi["id"], {"deleted": True, "updated_at": now})
    print(f"pbi #{pbi['id']}  {pbi.get('title', '')}  removed")


# --- Task ---


def cmd_add(args) -> None:
    _require_status(args.status)
    _require_priority(args.priority)
    _require_lane(args.lane)
    _require_surface(args.surface)
    tags = _parse_tags(args.tags)
    brief = None
    if args.budget_tool_calls is not None:
        brief = {"budget": {"max_tool_calls": args.budget_tool_calls}}

    title = args.title
    notes = args.notes or ""
    from_capture_id = args.from_capture

    slug, board_dir = _board()
    state = store.state(board_dir)
    if from_capture_id is not None:
        cap = _get_capture(state, slug, from_capture_id)
        if not title:
            title = cap.get("summary") or ""
        if not notes:
            notes = cap.get("body") or ""
        footer = f"Promoted from capture #{cap['id']}."
        notes = f"{notes}\n\n{footer}".strip() if notes else footer
        if cap.get("source_ref") and not args.source:
            args.source = cap["source_ref"]

    if not title:
        raise SystemExit(
            "taskman: title required (or use --from-capture with a capture that has a summary)."
        )

    if args.pbi is None and not args.source:
        print(
            "taskman: warning: task has no pbi and no source — it won't trace back to a goal"
        )
    pbi_id = args.pbi
    if pbi_id is not None:
        _get_pbi(state, slug, pbi_id)
    now = _now_iso()
    fields = {
        "pbi_id": pbi_id,
        "title": title,
        "status": args.status,
        "priority": args.priority,
        "tags": tags,
        "lane": args.lane or "",
        "surface": args.surface or "",
        "afk": args.afk or "",
        "notes": notes,
        "source_ref": args.source,
        "brief": brief,
        "created_at": now,
        "updated_at": now,
    }
    task_id = store.add(board_dir, "task", fields)
    if from_capture_id is not None:
        store.link(board_dir, "capture", from_capture_id, "task_id", task_id)
    pbi_s = f"  pbi=#{pbi_id}" if pbi_id is not None else ""
    lens_s = _lens_str(args.lane or "", args.surface or "")
    lens_out = f"  {lens_s}" if lens_s else ""
    cap_s = f"  capture=#{from_capture_id}" if from_capture_id is not None else ""
    print(f"#{task_id}  {title}  [{args.status}]{pbi_s}{lens_out}{cap_s}")


def cmd_task_claim(args) -> None:
    slug, board_dir = _board()
    if store.claim(board_dir, args.id, args.agent):
        # claimed_at/updated_at ride on the claim event itself (same lock).
        print(f"#{args.id} claimed by {args.agent}")
        return
    # Lost (or no such task): the store's False carries no claimant — replay
    # state to report who holds it.
    task = store.state(board_dir)["task"].get(args.id)
    if task is None:
        raise SystemExit(
            f"taskman: task #{args.id} not found in project '{slug}'."
        )
    raise SystemExit(
        f"taskman: task #{args.id} already claimed by {task.get('claimed_by')}."
    )


def cmd_task_release(args) -> None:
    slug, board_dir = _board()
    task = _get_task(store.state(board_dir), slug, args.id)
    store.release(board_dir, args.id)
    print(f"#{task['id']} released")


def cmd_move(args) -> None:
    _require_status(args.status)
    slug, board_dir = _board()
    task = _get_task(store.state(board_dir), slug, args.id)
    store.update(board_dir, "task", args.id, {"status": args.status, "updated_at": _now_iso()})
    print(f"#{task['id']}  {task.get('title', '')}  -> {args.status}")


# Editable-after-creation task fields. status is deliberately absent — `task move`
# owns it. Flags default to None (not ""), so "" stays usable to clear a field.
TASK_SET_FIELDS = ("priority", "tags", "lane", "surface", "afk", "notes", "pbi")


def cmd_task_set(args) -> None:
    requested = {
        field: getattr(args, field)
        for field in TASK_SET_FIELDS
        if getattr(args, field) is not None
    }
    add_raw = getattr(args, "add_tag", None) or []
    rm_raw = getattr(args, "rm_tag", None) or []
    add_tags = [t.strip() for t in add_raw if t and str(t).strip()]
    rm_tags = [t.strip() for t in rm_raw if t and str(t).strip()]

    if not requested and not add_tags and not rm_tags:
        flags = ", ".join(f"--{f}" for f in TASK_SET_FIELDS)
        raise SystemExit(
            f"taskman: no fields to set — pass at least one of {flags}, "
            "--add-tag, --rm-tag (status changes go through `task move`)."
        )
    # Validate every field before touching the row, so a bad value in one flag
    # can't leave a half-applied edit behind.
    if "priority" in requested:
        _require_priority(requested["priority"])
    if "lane" in requested:
        _require_lane(requested["lane"])
    if "surface" in requested:
        _require_surface(requested["surface"])

    slug, board_dir = _board()
    state = store.state(board_dir)
    task = _get_task(state, slug, args.id)
    changes = []
    fields: dict = {}

    if "pbi" in requested:
        pbi_id = requested.pop("pbi")
        old_pbi = task.get("pbi_id")
        if pbi_id is not None:
            _get_pbi(state, slug, pbi_id)
        fields["pbi_id"] = pbi_id
        changes.append(f"  pbi: {old_pbi or '-'} -> {pbi_id or '-'}")

    for field, value in requested.items():
        if field == "tags":
            old_s = ",".join(task.get("tags") or []) or "-"
            value = _parse_tags(value)
            new_s = ",".join(value) or "-"
        else:
            old_s = task.get(field) or "-"
            new_s = value or "-"
        fields[field] = value
        changes.append(f"  {field}: {old_s} -> {new_s}")

    if add_tags or rm_tags:
        old_tags = list(fields.get("tags", task.get("tags") or []))
        new_tags = list(old_tags)
        for t in add_tags:
            if t not in new_tags:
                new_tags.append(t)
        if rm_tags:
            rm_set = set(rm_tags)
            new_tags = [t for t in new_tags if t not in rm_set]
        fields["tags"] = new_tags
        changes.append(
            f"  tags: {','.join(old_tags) or '-'} -> {','.join(new_tags) or '-'}"
        )

    fields["updated_at"] = _now_iso()
    store.update(board_dir, "task", args.id, fields)
    print(f"#{task['id']}  {task.get('title', '')}")
    for line in changes:
        print(line)


def cmd_show(args) -> None:
    slug, board_dir = _board()
    state = store.state(board_dir)
    task = _get_task(state, slug, args.id)
    print(f"#{task['id']}  {task.get('title', '')}")
    print(f"  status: {task.get('status', '')}")
    print(f"  priority: {task.get('priority', '')}")
    if task.get("tags"):
        print("  tags: " + ",".join(task["tags"]))
    toolkit = toolkit_for_tags(list(task.get("tags") or []), find_toolkit())
    if toolkit:
        print("  toolkit: " + " ".join(toolkit))
    if task.get("notes"):
        print(f"  notes: {task['notes']}")
    if task.get("source_ref"):
        print(f"  brief: {task['source_ref']}")
    if task.get("claimed_by"):
        print(f"  claimed={task['claimed_by']}")
    budget_n = _budget_max_tool_calls(task.get("brief"))
    if budget_n is not None:
        print(f"  budget={budget_n}")
    caps = sorted(
        (c for c in state["capture"].values() if c.get("task_id") == task["id"]),
        key=lambda c: c["id"],
    )
    if caps:
        print("  captures:")
        for cap in caps:
            print(f"    {_format_capture_line(cap)}")


def cmd_link(args) -> None:
    slug, board_dir = _board()
    state = store.state(board_dir)
    task = _get_task(state, slug, args.id)
    blocker = _get_task(state, slug, args.blocked_by)
    if blocker["id"] == task["id"]:
        raise SystemExit("taskman: a task cannot block itself.")
    if blocker["id"] not in (task.get("blocked_by") or []):
        store.link(board_dir, "task", task["id"], "blocked_by", blocker["id"])
    print(f"#{task['id']} blocked-by #{blocker['id']}")


# --- Decision / Capture ---


def cmd_decision_add(args) -> None:
    tags = _parse_tags(getattr(args, "tags", None) or "")
    slug, board_dir = _board()
    task_id = getattr(args, "task", None)
    if task_id is not None:
        _get_task(store.state(board_dir), slug, task_id)
    fields = {
        "task_id": task_id,
        "title": args.title,
        "why": args.why or "",
        "alternatives": args.alternatives or "",
        "implications": args.implications or "",
        "tags": tags,
        "source_ref": args.source,
        "created_at": _now_iso(),
    }
    dec_id = store.add(board_dir, "decision", fields)
    print(_format_decision_line({"id": dec_id, **fields}))


def cmd_decision_show(args) -> None:
    """Print one decision for mow go hydrate / agent lookup."""
    slug, board_dir = _board()
    dec = _get_decision(store.state(board_dir), slug, args.id)
    print(f"#{dec['id']}  {dec.get('title', '')}")
    if dec.get("task_id") is not None:
        print(f"task: #{dec['task_id']}")
    if dec.get("tags"):
        print("tags: " + ",".join(dec["tags"]))
    if dec.get("why"):
        print(f"why: {dec['why']}")
    if dec.get("implications"):
        print(f"implications: {dec['implications']}")
    if dec.get("alternatives"):
        print(f"alternatives: {dec['alternatives']}")
    if dec.get("source_ref"):
        print(f"source: {dec['source_ref']}")


def cmd_decision_list(args) -> None:
    _slug, board_dir = _board()
    tag_filter = (getattr(args, "tag", None) or "").strip()
    touching = (getattr(args, "touching", None) or "").strip()

    decisions = sorted(
        store.state(board_dir)["decision"].values(),
        key=lambda d: d["id"],
        reverse=True,
    )
    if args.id:
        wanted = set(args.id)
        decisions = [d for d in decisions if d["id"] in wanted]
    if tag_filter:
        decisions = [d for d in decisions if tag_filter in (d.get("tags") or [])]
    if touching:
        decisions = [
            d
            for d in decisions
            if decision_matches(d.get("tags"), paths=[touching], tags=[])
        ]
    if args.limit is not None:
        decisions = decisions[: args.limit]

    if not decisions:
        print("taskman: no decisions match.")
        return
    for dec in decisions:
        print(_format_decision_line(dec))


def cmd_decision_link(args) -> None:
    slug, board_dir = _board()
    state = store.state(board_dir)
    dec = _get_decision(state, slug, args.id)
    _get_task(state, slug, args.task)
    store.link(board_dir, "decision", dec["id"], "task_id", args.task)
    print(f"decision #{dec['id']} linked to task #{args.task}")


def cmd_capture_show(args) -> None:
    """Print one capture (rare — prefer decision/requirement for mow hydrate)."""
    slug, board_dir = _board()
    cap = _get_capture(store.state(board_dir), slug, args.id)
    print(f"#{cap['id']}  [{cap.get('kind', '')}]  {cap.get('summary', '')}")
    if cap.get("task_id") is not None:
        print(f"task: #{cap['task_id']}")
    if cap.get("tags"):
        print("tags: " + ",".join(cap["tags"]))
    if cap.get("source_ref"):
        print(f"source: {cap['source_ref']}")
    if cap.get("body"):
        print(cap["body"])


def cmd_capture_add(args) -> None:
    _require_capture_kind(args.kind)
    tags = _parse_tags(getattr(args, "tags", None) or "")
    slug, board_dir = _board()
    task_id = args.task
    if task_id is None:
        task_id = _task_id_from_summary(args.summary or "")
    if task_id is not None:
        _get_task(store.state(board_dir), slug, task_id)
    fields = {
        "task_id": task_id,
        "kind": args.kind,
        "summary": args.summary or "",
        "body": args.body or "",
        "tags": tags,
        "source_ref": args.source,
        "created_at": _now_iso(),
    }
    cap_id = store.add(board_dir, "capture", fields)
    print(_format_capture_line({"id": cap_id, **fields}))


def cmd_capture_link(args) -> None:
    slug, board_dir = _board()
    state = store.state(board_dir)
    cap = _get_capture(state, slug, args.id)
    _get_task(state, slug, args.task)
    store.link(board_dir, "capture", cap["id"], "task_id", args.task)
    print(f"capture #{cap['id']} linked to task #{args.task}")


def cmd_capture_unlink(args) -> None:
    slug, board_dir = _board()
    cap = _get_capture(store.state(board_dir), slug, args.id)
    current = cap.get("task_id")
    if current is not None:
        store.unlink(board_dir, "capture", cap["id"], "task_id", current)
    print(f"capture #{cap['id']} unlinked")


def cmd_capture_list(args) -> None:
    slug, board_dir = _board()
    state = store.state(board_dir)
    tag_filter = (getattr(args, "tag", None) or "").strip()
    touching = (getattr(args, "touching", None) or "").strip()

    caps = sorted(state["capture"].values(), key=lambda c: c["id"], reverse=True)
    if args.task is not None:
        _get_task(state, slug, args.task)
        caps = [c for c in caps if c.get("task_id") == args.task]
    if args.kind:
        _require_capture_kind(args.kind)
        caps = [c for c in caps if c.get("kind") == args.kind]
    if args.unlinked:
        caps = [c for c in caps if c.get("task_id") is None]
    if tag_filter:
        caps = [c for c in caps if tag_filter in (c.get("tags") or [])]
    if touching:
        caps = [
            c
            for c in caps
            if decision_matches(c.get("tags"), paths=[touching], tags=[])
        ]
    if args.limit is not None:
        caps = caps[: args.limit]

    if not caps:
        print("taskman: no captures match.")
        return
    for cap in caps:
        print(_format_capture_line(cap))


# --- Requirement (living spec) ---


def cmd_requirement_add(args) -> None:
    scenarios = _parse_scenarios(args.scenario)
    slug, board_dir = _board()
    state = store.state(board_dir)
    _get_feature(state, slug, args.feature)
    if args.pbi is not None:
        _get_pbi(state, slug, args.pbi)
    now = _now_iso()
    fields = {
        "feature_id": args.feature,
        "title": args.title,
        "statement": args.statement,
        "scenarios": scenarios,
        "status": "active",
        "source_pbi_id": args.pbi,
        "created_at": now,
        "updated_at": now,
    }
    req_id = store.add(board_dir, "requirement", fields)
    print(f"requirement #{req_id}  {args.title}  feature=#{args.feature}  [added]")


def cmd_requirement_modify(args) -> None:
    slug, board_dir = _board()
    state = store.state(board_dir)
    req = _get_requirement(state, slug, args.id)
    fields: dict = {}
    if args.title is not None:
        fields["title"] = args.title
    if args.statement is not None:
        fields["statement"] = args.statement
    if args.scenario:
        fields["scenarios"] = _parse_scenarios(args.scenario)
    if args.pbi is not None:
        _get_pbi(state, slug, args.pbi)
        fields["source_pbi_id"] = args.pbi
    fields["updated_at"] = _now_iso()
    store.update(board_dir, "requirement", args.id, fields)
    print(f"requirement #{req['id']}  {fields.get('title', req.get('title', ''))}  [modified]")


def cmd_requirement_remove(args) -> None:
    slug, board_dir = _board()
    req = _get_requirement(store.state(board_dir), slug, args.id)
    store.update(
        board_dir, "requirement", args.id,
        {"status": "removed", "updated_at": _now_iso()},
    )
    print(f"requirement #{req['id']}  {req.get('title', '')}  [removed]")


def cmd_requirement_show(args) -> None:
    slug, board_dir = _board()
    req = _get_requirement(store.state(board_dir), slug, args.id)
    for line in _format_requirement(req, indent=""):
        print(line)
    print(f"feature=#{req.get('feature_id')}")


def _format_requirement(req: dict, *, indent: str = "  ") -> list[str]:
    lines = [f"{indent}#{req['id']} [{req.get('status', '')}] {req.get('title', '')}"]
    if req.get("statement"):
        lines.append(f"{indent}  {req['statement']}")
    for sc in req.get("scenarios") or []:
        name = sc.get("name", "")
        lines.append(f"{indent}  Scenario: {name}")
        lines.append(f"{indent}    GIVEN {sc.get('given', '')}")
        lines.append(f"{indent}    WHEN {sc.get('when', '')}")
        lines.append(f"{indent}    THEN {sc.get('then', '')}")
    return lines


def cmd_requirement_list(args) -> None:
    status_filter = args.status or "active"
    _require_requirement_status(status_filter)
    slug, board_dir = _board()
    state = store.state(board_dir)
    _get_feature(state, slug, args.feature)
    rows = sorted(
        (
            r
            for r in state["requirement"].values()
            if r.get("feature_id") == args.feature and r.get("status") == status_filter
        ),
        key=lambda r: r["id"],
    )
    print(f"# requirements: feature=#{args.feature} [{status_filter}] ({len(rows)})")
    if not rows:
        print("  (none)")
        return
    for req in rows:
        for line in _format_requirement(req):
            print(line)


# --- Board ---


def _board_flat(slug: str, state: dict, statuses: list[str]) -> None:
    tasks_by_id = state["task"]
    rows = sorted(
        (t for t in tasks_by_id.values() if t.get("status") in statuses),
        key=lambda t: (_priority_rank(t), t["id"]),
    )
    print(f"# board: {slug}")
    if not rows:
        print("  (no tasks)")
        return
    for status in statuses:
        group = [t for t in rows if t.get("status") == status]
        if not group:
            continue
        print(f"\n{status} ({len(group)})")
        for t in group:
            print(_format_task_line(t, tasks_by_id, indent="  "))


def _board_hierarchical(slug: str, state: dict, statuses: list[str]) -> None:
    tasks_by_id = state["task"]
    features = sorted(state["feature"].values(), key=lambda f: f["id"])
    pbis = sorted(_live_pbis(state), key=lambda p: (_priority_rank(p), p["id"]))
    tasks = sorted(
        (t for t in tasks_by_id.values() if t.get("status") in statuses),
        key=lambda t: (_priority_rank(t), t["id"]),
    )

    pbis_by_feature: dict[int, list[dict]] = {}
    for p in pbis:
        pbis_by_feature.setdefault(p.get("feature_id"), []).append(p)

    live_pbi_by_id = {p["id"]: p for p in pbis}
    feature_ids = {f["id"] for f in features}
    tasks_by_pbi: dict[int, list[dict]] = {}
    orphans: list[dict] = []
    for t in tasks:
        pid = t.get("pbi_id")
        pbi = live_pbi_by_id.get(pid) if pid is not None else None
        # Deleted, missing, or feature-less PBIs are omitted from the feature
        # walk — those tasks must still render (Orphan tasks), not vanish.
        if pbi is None or pbi.get("feature_id") not in feature_ids:
            orphans.append(t)
        else:
            tasks_by_pbi.setdefault(pid, []).append(t)

    print(f"# board: {slug}")
    shown = False
    for feat in features:
        feat_pbis = pbis_by_feature.get(feat["id"], [])
        # Show feature if it has any PBI (even empty) — keeps hierarchy visible.
        # Skip features with zero PBIs and no linked filtered tasks.
        if not feat_pbis:
            continue
        shown = True
        print(f"\n## Feature: {feat.get('title', '')} [{feat.get('status', '')}]")
        for pbi in feat_pbis:
            print(f"  PBI #{pbi['id']}: {pbi.get('title', '')} [{pbi.get('status', '')}]")
            for t in tasks_by_pbi.get(pbi["id"], []):
                print(_format_task_line(t, tasks_by_id, indent="    "))

    if orphans:
        shown = True
        print("\n## Orphan tasks")
        for t in orphans:
            print(_format_task_line(t, tasks_by_id, indent="  "))

    if not shown:
        print("  (empty)")


def cmd_board(args) -> None:
    statuses = (
        [s.strip() for s in args.status.split(",") if s.strip()]
        if args.status
        else [s for s in STATUSES if s != "disabled"]
    )
    for s in statuses:
        _require_status(s)
    slug, board_dir = _board()
    state = store.state(board_dir)
    if args.flat:
        _board_flat(slug, state, statuses)
    else:
        _board_hierarchical(slug, state, statuses)


# --- Plan bridge: from-decisions / to-dispatch ---


def _plan_feature_tag(slug: str) -> str:
    return f"plan:{slug}"


def _upsert_feature_for_plan(board_dir: Path, state: dict, doc: WorkItemDoc) -> tuple[int, bool]:
    """Upsert Feature keyed by tag ``plan:<slug>``; returns (feature_id, created)."""
    tag_name = _plan_feature_tag(doc.plan.slug)
    feat = next(
        (f for f in state["feature"].values() if tag_name in (f.get("tags") or [])),
        None,
    )
    if feat is None:
        # Fallback: exact title match (pre-tag imports / manual features)
        feat = next(
            (f for f in state["feature"].values() if f.get("title") == doc.plan.title),
            None,
        )
    if feat is None:
        now = _now_iso()
        feat_id = store.add(
            board_dir,
            "feature",
            {
                "title": doc.plan.title,
                "description": doc.plan.source_ref or "",
                "status": "backlog",
                "lane": doc.plan.lane or "",
                "surface": doc.plan.surface or "",
                "tags": [tag_name],
                "created_at": now,
                "updated_at": now,
            },
        )
        return feat_id, True

    fields: dict = {"title": doc.plan.title, "updated_at": _now_iso()}
    if doc.plan.lane:
        fields["lane"] = doc.plan.lane
    if doc.plan.surface:
        fields["surface"] = doc.plan.surface
    if doc.plan.source_ref and not feat.get("description"):
        fields["description"] = doc.plan.source_ref
    tags = list(feat.get("tags") or [])
    if tag_name not in tags:
        tags.append(tag_name)
        fields["tags"] = tags
    store.update(board_dir, "feature", feat["id"], fields)
    return feat["id"], False


def _item_tags(item) -> list[str]:
    tags = list(item.tags or [])
    if item.dispatch.role:
        rt = role_tag(item.dispatch.role)
        if rt not in tags:
            tags.append(rt)
    return tags


def import_work_item_doc(
    board_dir: Path,
    doc: WorkItemDoc,
    *,
    feature_id: int | None = None,
) -> dict[str, int]:
    """Upsert Feature + Tasks from a WorkItemDoc. Returns counts.

    Idempotent on Task.source_ref (update-in-place). Resolves depends_on → blocked_by
    in a second pass.

    When ``feature_id`` is set (``plan from-decisions --feature``), attach under that
    existing Feature and mint nothing (d#856).
    """
    validate(doc)
    state = store.state(board_dir)
    if feature_id is not None:
        feat = state["feature"].get(feature_id)
        if feat is None:
            slug, _name = find_project()
            raise SystemExit(
                f"taskman: feature #{feature_id} not found in project '{slug}'."
            )
        feat_created = False
        feat_id = feature_id
        # Still ensure plan:<slug> tag for to-dispatch round-trip — does not mint a Feature.
        tag_name = _plan_feature_tag(doc.plan.slug)
        tags = list(feat.get("tags") or [])
        if tag_name not in tags:
            store.update(
                board_dir, "feature", feat_id,
                {"tags": [*tags, tag_name], "updated_at": _now_iso()},
            )
    else:
        feat_id, feat_created = _upsert_feature_for_plan(board_dir, state, doc)

    existing_by_ref: dict[str, dict] = {
        t["source_ref"]: t
        for t in state["task"].values()
        if t.get("source_ref")
    }

    item_id_to_task: dict[str, int] = {}
    blocked_by_current: dict[int, list[int]] = {}
    created = 0
    updated = 0
    for item in doc.items:
        if not item.source_ref:
            raise ValueError(f"item {item.id!r}: missing source_ref")
        task = existing_by_ref.get(item.source_ref)
        tags = _item_tags(item)
        brief = item.dispatch.model_dump()
        if task is None:
            now = _now_iso()
            task_id = store.add(
                board_dir,
                "task",
                {
                    "pbi_id": None,
                    "title": item.title,
                    "status": item.status,
                    "priority": item.priority,
                    "tags": tags,
                    "lane": doc.plan.lane or "",
                    "surface": doc.plan.surface or "",
                    "afk": "",
                    "notes": "",
                    "source_ref": item.source_ref,
                    "brief": brief,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            blocked_by_current[task_id] = []
            created += 1
        else:
            # Board owns status and priority after create. Markdown briefs always
            # parse as backlog/med (there is no priority field in brief markdown),
            # so overwriting either here would clobber wrap-up / task move / a
            # human-set severity. Tags are merged, not replaced: the role tag is
            # real new info from the brief, but a brief only ever encodes `role:*`
            # -- replacing wholesale would drop any richer tags (e.g. `security`,
            # `bug`) a human or an earlier task add had already set.
            task_id = task["id"]
            fields: dict = {
                "title": item.title,
                "tags": list(dict.fromkeys([*(task.get("tags") or []), *tags])),
                "brief": brief,
                "updated_at": _now_iso(),
            }
            if doc.plan.lane:
                fields["lane"] = doc.plan.lane
            if doc.plan.surface:
                fields["surface"] = doc.plan.surface
            store.update(board_dir, "task", task_id, fields)
            blocked_by_current[task_id] = list(task.get("blocked_by") or [])
            updated += 1
        item_id_to_task[item.id] = task_id

    # Second pass: depends_on (item ids) → blocked_by. Replace the set to match
    # the plan (idempotent) — relations move only via link/unlink.
    for item in doc.items:
        task_id = item_id_to_task[item.id]
        desired = [item_id_to_task[d] for d in item.depends_on if d in item_id_to_task]
        current = blocked_by_current.get(task_id, [])
        for target in desired:
            if target not in current:
                store.link(board_dir, "task", task_id, "blocked_by", target)
        for target in current:
            if target not in desired:
                store.unlink(board_dir, "task", task_id, "blocked_by", target)

    pbi_ids = {
        t.get("pbi_id")
        for tid in item_id_to_task.values()
        if (t := state["task"].get(tid)) is not None and t.get("pbi_id") is not None
    }
    if pbi_ids:
        _sync_pbi_acceptance_from_tasks(board_dir, pbi_ids)

    return {
        "feature_id": feat_id,
        "feature_created": int(feat_created),
        "tasks_created": created,
        "tasks_updated": updated,
        "tasks_total": len(doc.items),
    }


def cmd_plan_from_decisions(args) -> None:
    path = Path(args.path)
    if not path.exists():
        raise SystemExit(f"taskman: path not found: {path}")
    try:
        doc = load_plan_path(path)
    except (ValueError, OSError) as e:
        raise SystemExit(f"taskman plan from-decisions: {e}") from e

    _slug, board_dir = _board()
    feature_id = getattr(args, "feature", None)
    try:
        counts = import_work_item_doc(board_dir, doc, feature_id=feature_id)
    except ValueError as e:
        raise SystemExit(f"taskman plan from-decisions: {e}") from e

    feat_id = counts["feature_id"]
    minted = "minted" if counts["feature_created"] else "existing"
    print(
        f"taskman plan from-decisions: feature #{feat_id}  {doc.plan.title}  "
        f"(slug={doc.plan.slug}, {minted})  "
        f"created={counts['tasks_created']} updated={counts['tasks_updated']} "
        f"total={counts['tasks_total']}"
    )
    # Board slice: tasks for this import (by source_ref)
    refs = {i.source_ref for i in doc.items if i.source_ref}
    state = store.state(board_dir)
    tasks = sorted(
        (t for t in state["task"].values() if t.get("source_ref") in refs),
        key=lambda t: (_priority_rank(t), t["id"]),
    )
    print(f"\n## Feature: {doc.plan.title} [#{feat_id}]")
    for t in tasks:
        print(_format_task_line(t, state["task"], indent="  "))


def _plan_slug_from_feature(feat: dict) -> str | None:
    for name in feat.get("tags") or []:
        if name.startswith("plan:") and len(name) > len("plan:"):
            return name[len("plan:") :]
    return None


def _dispatch_meta_from_task(task: dict) -> DispatchMeta:
    brief = task.get("brief") if isinstance(task.get("brief"), dict) else {}
    role = (
        (brief.get("role") or "").strip()
        or role_from_tags(list(task.get("tags") or []))
        or "code-edit"
    )
    files = brief.get("files") if isinstance(brief.get("files"), list) else []
    do_not = brief.get("do_not") if isinstance(brief.get("do_not"), list) else []
    context = brief.get("context") if isinstance(brief.get("context"), list) else []
    acceptance = brief.get("acceptance") or ""
    if not isinstance(acceptance, str):
        acceptance = str(acceptance)
    wave = brief.get("wave") if isinstance(brief.get("wave"), int) else 0
    if "background" in brief:
        background = bool(brief.get("background"))
    else:
        background = role != "shell"
    return DispatchMeta(
        role=role,
        wave=wave,
        background=background,
        files=[str(f) for f in files],
        acceptance=acceptance,
        do_not=[str(d) for d in do_not],
        context=[str(c) for c in context],
    )


def tasks_to_work_item_doc(
    tasks: list[dict],
    *,
    plan: PlanMeta,
) -> WorkItemDoc:
    """Convert a task board slice (+ blocked_by graph) into a WorkItemDoc.

    In-set ``blocked_by`` links become ``depends_on``. Blockers outside the
    selected set are omitted (``recompute_waves`` ignores them). Status is
    preserved on each item; wave levels come from the dependency graph, not
    from done/todo — selecting only incomplete tasks naturally drops done
    blockers as "outside the set".
    """
    # Stable item ids from source_ref stem; fall back to task-<id>
    used: set[str] = set()
    id_by_task: dict[int, str] = {}
    for t in tasks:
        raw = item_id_from_source_ref(t.get("source_ref") or "") or f"task-{t['id']}"
        item_id = raw
        n = 2
        while item_id in used:
            item_id = f"{raw}-{n}"
            n += 1
        used.add(item_id)
        id_by_task[t["id"]] = item_id

    items: list[WorkItem] = []
    for t in tasks:
        item_id = id_by_task[t["id"]]
        deps: list[str] = []
        for b in t.get("blocked_by") or []:
            if b not in id_by_task:
                continue
            deps.append(id_by_task[b])
        tags = list(t.get("tags") or [])
        dispatch = _dispatch_meta_from_task(t)
        if role_tag(dispatch.role) not in tags:
            tags.append(role_tag(dispatch.role))
        items.append(
            WorkItem(
                id=item_id,
                title=t.get("title") or "",
                priority=t.get("priority") or "med",
                status=t.get("status") or "backlog",
                tags=tags,
                depends_on=deps,
                source_ref=t.get("source_ref") or "",
                dispatch=dispatch,
            )
        )
    return WorkItemDoc(plan=plan, items=items)


DECISION_TAG = "kind:decision"


def _refuse_if_gated_by_open_decision(tasks: list[dict], dropped_ids: set[int]) -> None:
    """Abort the export when a selected task is blocked by a filtered-out decision.

    ``tasks_to_work_item_doc`` drops blockers outside the selected set, which is only
    safe for *done* blockers. A filtered-out decision is by definition unresolved, so
    dropping it silently would sever the edge and let ``recompute_waves`` promote the
    blocked task into wave 1 — dispatching a blind lane to build the very thing the
    open question governs.

    Checking only direct edges is sufficient *because* the remedy is a hard exit: a
    gated task anywhere in a chain aborts the whole command, so nothing downstream of
    it ships either. Changing this to "skip the gated task and export the rest" would
    silently reintroduce the transitive hole.
    """
    gated = [
        t for t in tasks if any(b in dropped_ids for b in (t.get("blocked_by") or []))
    ]
    if not gated:
        return
    detail = "; ".join(f"#{t['id']} {t.get('title')!r}" for t in gated)
    raise SystemExit(
        f"taskman plan to-dispatch: blocked by an open decision: {detail} "
        "— resolve the decision(s), unlink the blocker, or re-run with "
        "--include-decisions"
    )


def _select_tasks_for_export(state: dict, slug: str, args) -> tuple[list[dict], PlanMeta]:
    """Apply --feature / --status / --lane / --tag selectors; return tasks + plan meta.

    Also enforces the decision-task gate: ``kind:decision`` rows are questions, not
    build work, so they are dropped unless explicitly requested — and the export is
    refused outright when dropping one would strand work that depends on it.
    """
    statuses: list[str] | None = None
    if getattr(args, "status", None):
        statuses = [s.strip() for s in args.status.split(",") if s.strip()]
        for s in statuses:
            _require_status(s)

    tag_filter = (getattr(args, "tag", None) or "").strip() or None
    lane_filter = (getattr(args, "lane", None) or "").strip() or None
    if lane_filter:
        _require_lane(lane_filter)

    feature_id = getattr(args, "feature", None)
    feat: dict | None = None
    plan_slug: str | None = None
    slugs: list[str] = []

    tasks = sorted(
        state["task"].values(), key=lambda t: (_priority_rank(t), t["id"])
    )

    if feature_id is not None:
        feat = state["feature"].get(feature_id)
        if feat is None:
            raise SystemExit(
                f"taskman: feature #{feature_id} not found in project '{slug}'."
            )
        plan_slug = _plan_slug_from_feature(feat)
        if plan_slug:
            needle = plan_slug
            tasks = [
                t
                for t in tasks
                if t.get("source_ref") and needle in t["source_ref"].replace("\\", "/")
            ]
        else:
            # No plan: tag — fall back to tasks under this feature's PBIs
            pbi_ids = {
                p["id"]
                for p in _live_pbis(state)
                if p.get("feature_id") == feat["id"]
            }
            tasks = [t for t in tasks if t.get("pbi_id") is not None and t["pbi_id"] in pbi_ids]

    if lane_filter:
        # Restrict to tasks whose plan feature (via source_ref slug / plan: tag) matches lane
        feat_rows = [
            f for f in state["feature"].values() if (f.get("lane") or "") == lane_filter
        ]
        slugs = []
        for f in feat_rows:
            s = _plan_slug_from_feature(f)
            if s:
                slugs.append(s)
        if feature_id is None and not slugs and not feat_rows:
            tasks = []
        elif feature_id is None:
            if slugs:
                tasks = [
                    t
                    for t in tasks
                    if t.get("source_ref")
                    and any(s in t["source_ref"].replace("\\", "/") for s in slugs)
                ]
            else:
                # Features with lane but no plan tag: PBI-linked tasks
                fids = {f["id"] for f in feat_rows}
                pbi_ids = {
                    p["id"]
                    for p in _live_pbis(state)
                    if p.get("feature_id") in fids
                }
                tasks = [
                    t for t in tasks if t.get("pbi_id") is not None and t["pbi_id"] in pbi_ids
                ]
        elif feat is not None and feat.get("lane") and feat.get("lane") != lane_filter:
            tasks = []

    if statuses is not None:
        tasks = [t for t in tasks if t.get("status") in statuses]

    if tag_filter:
        tasks = [t for t in tasks if tag_filter in (t.get("tags") or [])]

    # A kind:decision task is an open question, not a slice of build work — never
    # hand one to a blind subagent as a brief. The filter exists to stop a question
    # being swept up *incidentally* by a plan/feature selector, so naming the tag in
    # --tag counts as asking for decisions outright, same as --include-decisions.
    matched_before_decisions = len(tasks)
    if not getattr(args, "include_decisions", False) and tag_filter != DECISION_TAG:
        dropped_ids = {t["id"] for t in tasks if DECISION_TAG in (t.get("tags") or [])}
        tasks = [t for t in tasks if t["id"] not in dropped_ids]
        _refuse_if_gated_by_open_decision(tasks, dropped_ids)

    if not tasks:
        if matched_before_decisions:
            raise SystemExit(
                f"taskman plan to-dispatch: {matched_before_decisions} task(s) matched "
                f"the selector but all are {DECISION_TAG} — resolve them, or pass "
                "--include-decisions"
            )
        raise SystemExit("taskman plan to-dispatch: no tasks matched the selector")

    # Plan meta from feature when available; else synthesize from first task
    if feat is not None:
        plan = PlanMeta(
            slug=plan_slug or f"feature-{feat['id']}",
            title=feat.get("title") or "",
            lane=feat.get("lane") or "",
            surface=feat.get("surface") or "",
            source_ref=(feat.get("description") or "").strip(),
        )
    elif lane_filter and slugs:
        plan = PlanMeta(
            slug=slugs[0],
            title=slugs[0].replace("-", " ").title(),
            lane=lane_filter,
            surface="",
            source_ref="",
        )
    else:
        plan = PlanMeta(
            slug="export",
            title="Board export",
            lane=lane_filter or "",
            surface="",
            source_ref="",
        )
    return tasks, plan


def cmd_plan_to_dispatch(args) -> None:
    dest = Path(args.dir)
    if not getattr(args, "feature", None) and not (
        getattr(args, "status", None)
        or getattr(args, "lane", None)
        or getattr(args, "tag", None)
    ):
        raise SystemExit(
            "taskman plan to-dispatch: provide --feature and/or --status/--lane/--tag"
        )

    slug, board_dir = _board()
    state = store.state(board_dir)
    tasks, plan = _select_tasks_for_export(state, slug, args)
    doc = tasks_to_work_item_doc(tasks, plan=plan)
    try:
        validate(doc)
        lanes = write_dispatch_folder(doc, dest)
    except ValueError as e:
        raise SystemExit(f"taskman plan to-dispatch: {e}") from e

    print(
        f"taskman plan to-dispatch: wrote {len(lanes)} lane(s) / {len(doc.items)} brief(s) "
        f"→ {dest}/INDEX.md"
    )
    for lane in lanes:
        bg = "bg" if lane.background else "fg"
        print(
            f"  Wave {lane.wave} Lane {lane.letter} [{lane.role}/{bg}]: "
            f"{' → '.join(lane.item_ids)}"
        )


_MARK_SHIPPED_STATUSES = frozenset({"done", "shipped"})
_BRIEF_FILE_RE = re.compile(r"\b(\d{2}-[\w-]+\.md)\b")


def _repo_root_from_path(start: Path) -> Path | None:
    for d in (start.resolve(), *start.resolve().parents):
        if (d / ".taskman.toml").is_file():
            return d
    return None


def _parse_index_lane_briefs(index_text: str) -> list[str]:
    """Brief filenames listed in the dispatch INDEX Lanes table."""
    m = re.search(r"^## Lanes\s*$", index_text, re.MULTILINE | re.IGNORECASE)
    if not m:
        return []
    section = index_text[m.end() :]
    stop = re.search(r"^## ", section, re.MULTILINE)
    if stop:
        section = section[: stop.start()]
    briefs: list[str] = []
    seen: set[str] = set()
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        parts = [c.strip() for c in line.strip("|").split("|")]
        if not parts or parts[0].lower() == "lane":
            continue
        brief_cell = parts[-1]
        for bm in _BRIEF_FILE_RE.finditer(brief_cell):
            name = bm.group(1)
            if name not in seen:
                seen.add(name)
                briefs.append(name)
    return briefs


def _parse_outcome_rows(report_text: str) -> list[dict[str, str | int | None]]:
    m = re.search(r"^## Outcome\s*$", report_text, re.MULTILINE | re.IGNORECASE)
    if not m:
        return []
    section = report_text[m.end() :]
    stop = re.search(r"^## ", section, re.MULTILINE)
    if stop:
        section = section[: stop.start()]
    rows: list[dict[str, str | int | None]] = []
    header: list[str] | None = None
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        if re.match(r"^\|[-| :]+\|$", line.replace(" ", "")):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if len(cells) != len(header):
            continue
        row = dict(zip(header, cells, strict=True))
        todo = str(row.get("todo", "") or "")
        task_raw = str(row.get("task", "") or "")
        status = str(row.get("status", "") or "").strip().strip("*")
        task_id: int | None = None
        tm = re.search(r"#(\d+)", task_raw)
        if tm:
            task_id = int(tm.group(1))
        rows.append({"todo": todo, "task_id": task_id, "status": status})
    return rows


def _dispatch_brief_filenames(dispatch_dir: Path, index_text: str) -> list[str]:
    """All dispatch brief filenames: INDEX Lanes table plus every NN-*.md on disk.

    Preflight may list only one brief per lane when todos are sequential in one lane;
    scanning the dispatch folder ensures mark-shipped still sees every brief source_ref.
    """
    index_briefs = _parse_index_lane_briefs(index_text)
    scanned = sorted(p.name for p in dispatch_dir.glob("[0-9][0-9]-*.md"))
    seen: set[str] = set()
    merged: list[str] = []
    for name in (*index_briefs, *scanned):
        if name not in seen:
            seen.add(name)
            merged.append(name)
    return merged


def _dispatch_brief_source_refs(
    dispatch_dir: Path,
    brief_names: list[str],
    repo_root: Path | None,
) -> dict[str, str]:
    refs: dict[str, str] = {}
    for name in brief_names:
        path = dispatch_dir / name
        if not path.is_file():
            continue
        item = parse_brief(path, repo_root=repo_root)
        if item is not None and item.source_ref:
            refs[name] = item.source_ref
    return refs


def _outcome_is_shipped(status: str) -> bool:
    return status.lower() in _MARK_SHIPPED_STATUSES


def cmd_plan_mark_shipped(args) -> None:
    dispatch_dir = Path(args.dispatch_dir).resolve()
    if not dispatch_dir.is_dir():
        raise SystemExit(f"taskman plan mark-shipped: not a directory: {dispatch_dir}")
    index_path = dispatch_dir / "INDEX.md"
    if not index_path.is_file():
        raise SystemExit(f"taskman plan mark-shipped: missing INDEX.md in {dispatch_dir}")

    index_text = index_path.read_text(encoding="utf-8")
    brief_names = _dispatch_brief_filenames(dispatch_dir, index_text)
    if not brief_names:
        raise SystemExit("taskman plan mark-shipped: no NN-*.md briefs in dispatch")

    repo_root = _repo_root_from_path(dispatch_dir)
    source_refs = _dispatch_brief_source_refs(dispatch_dir, brief_names, repo_root)
    ref_values = set(source_refs.values())
    if not ref_values:
        raise SystemExit("taskman plan mark-shipped: no source_ref values from dispatch briefs")

    report_path = dispatch_dir.parent / "action-report.md"
    has_report = report_path.is_file()
    shipped_task_ids: set[int] = set()
    shipped_todos: set[str] = set()
    if has_report:
        for row in _parse_outcome_rows(report_path.read_text(encoding="utf-8")):
            if not _outcome_is_shipped(str(row["status"])):
                continue
            if row["task_id"] is not None:
                shipped_task_ids.add(int(row["task_id"]))
            todo = str(row["todo"] or "").strip()
            if todo:
                shipped_todos.add(todo)
    else:
        print(
            "taskman plan mark-shipped: warning: no action-report.md found; "
            "moving all dispatch brief tasks to done",
            file=sys.stderr,
        )

    force = bool(getattr(args, "force", False))
    moved = 0

    _slug, board_dir = _board()
    tasks = sorted(
        (
            t
            for t in store.state(board_dir)["task"].values()
            if t.get("source_ref") in ref_values
        ),
        key=lambda t: t["id"],
    )

    for task in tasks:
        if task.get("status") == "done":
            continue
        # req #433 / d#856: kind:decision rows are open questions, not build
        # slices — never sweep them to done (even under --force).
        if DECISION_TAG in (task.get("tags") or []):
            continue
        if has_report:
            todo_id = item_id_from_source_ref(task.get("source_ref") or "")
            if task["id"] not in shipped_task_ids and (
                not todo_id or todo_id not in shipped_todos
            ):
                continue
        if task.get("status") == "blocked" and not force:
            print(
                f"taskman plan mark-shipped: skipping blocked task #{task['id']}",
                file=sys.stderr,
            )
            continue
        store.update(
            board_dir, "task", task["id"],
            {"status": "done", "updated_at": _now_iso()},
        )
        moved += 1
        print(f"#{task['id']}  {task.get('title', '')}  -> done")

    if moved:
        print(f"taskman plan mark-shipped: moved {moved} task(s) to done")
    else:
        print("taskman plan mark-shipped: no tasks moved")


# --- Recommend next (rule-based) ---

RECOMMEND_PRIORITY_SCORE = {
    "keystone": 100,
    "high": 75,
    "med": 50,
    "low": 25,
}
RECOMMEND_IN_PROGRESS_BONUS = 20
RECOMMEND_STALE_PENALTY_PER_DAY = 2
RECOMMEND_STALE_GRACE_DAYS = 7
RECOMMEND_SOLE_STEM_BONUS = 15

RECOMMEND_HELP_WEIGHTS = (
    "Scoring weights: priority keystone +100 / high +75 / med +50 / low +25; "
    "status in_progress +20; stale in_progress −2/day after 7 days; "
    "sole mow stem +15 when exactly one planned|running row in docs/plans/INDEX.md "
    "and the task belongs to that feature."
)


def _parse_mow_registry_rows(index_text: str) -> list[tuple[str, int | None, str]]:
    rows: list[tuple[str, int | None, str]] = []
    for line in index_text.splitlines():
        if not line.startswith("|") or "---" in line or "Stem" in line:
            continue
        parts = [c.strip() for c in line.strip("|").split("|")]
        if len(parts) < 6:
            continue
        stem, _title, feature, _created, _updated, status = parts[:6]
        if stem.lower() == "stem":
            continue
        feat_id: int | None = None
        fm = re.search(r"#(\d+)", feature)
        if fm:
            feat_id = int(fm.group(1))
        rows.append((stem, feat_id, status.lower()))
    return rows


def _sole_active_mow_stem(repo_root: Path) -> tuple[str | None, int | None]:
    index_path = repo_root / "docs" / "plans" / "INDEX.md"
    if not index_path.is_file():
        return None, None
    active = [
        (stem, feat_id)
        for stem, feat_id, status in _parse_mow_registry_rows(
            index_path.read_text(encoding="utf-8")
        )
        if status in {"planned", "running"}
    ]
    if len(active) == 1:
        return active[0]
    return None, None


def _task_matches_feature(
    task: dict,
    feat: dict,
    slug: str | None,
    pbi_ids: set[int] | None = None,
) -> bool:
    if slug and task.get("source_ref") and slug in task["source_ref"].replace("\\", "/"):
        return True
    plan_tag = f"plan:{slug}" if slug else ""
    if plan_tag and plan_tag in (task.get("tags") or []):
        return True
    if pbi_ids is not None and task.get("pbi_id") in pbi_ids:
        return True
    return False


def _is_recommend_eligible(task: dict, tasks_by_id: dict[int, dict]) -> bool:
    if task.get("status") not in {"backlog", "todo", "in_progress"}:
        return False
    for blocker_id in task.get("blocked_by") or []:
        blocker = tasks_by_id.get(blocker_id)
        if blocker is None:
            continue  # dangling id (other-project dep, deleted task) is not a live block
        if blocker.get("status") != "done":
            return False
    return True


def _score_recommend_task(
    task: dict,
    *,
    now: dt.datetime,
    sole_stem: str | None,
    sole_feature_id: int | None,
    feat_by_id: dict[int, dict],
    slug_by_feature: dict[int, str | None],
) -> tuple[int, str]:
    priority = task.get("priority") or "med"
    score = RECOMMEND_PRIORITY_SCORE.get(priority, RECOMMEND_PRIORITY_SCORE["med"])
    reasons = [f"{priority} priority (+{score})"]

    if task.get("status") == "in_progress":
        score += RECOMMEND_IN_PROGRESS_BONUS
        reasons.append(f"in progress (+{RECOMMEND_IN_PROGRESS_BONUS})")
        updated = _parse_iso(task.get("updated_at"))
        if updated is not None:
            now_aware = now if now.tzinfo else now.replace(tzinfo=dt.UTC)
            days_stale = (now_aware.date() - updated.date()).days
            if days_stale > RECOMMEND_STALE_GRACE_DAYS:
                penalty = (days_stale - RECOMMEND_STALE_GRACE_DAYS) * RECOMMEND_STALE_PENALTY_PER_DAY
                score -= penalty
                reasons.append(f"stale {days_stale}d (−{penalty})")

    if sole_stem and sole_feature_id is not None:
        feat = feat_by_id.get(sole_feature_id)
        slug = slug_by_feature.get(sole_feature_id) if feat else None
        if feat is not None and _task_matches_feature(task, feat, slug):
            score += RECOMMEND_SOLE_STEM_BONUS
            reasons.append(f"sole active mow stem {sole_stem} (+{RECOMMEND_SOLE_STEM_BONUS})")

    return score, "; ".join(reasons)


def _filter_tasks_for_recommend(
    tasks: list[dict],
    *,
    feature_id: int | None,
    lane: str | None,
    tag: str | None,
    feat_by_id: dict[int, dict],
    slug_by_feature: dict[int, str | None],
    state: dict,
) -> list[dict]:
    filtered = tasks
    live_pbis = _live_pbis(state)
    if feature_id is not None:
        feat = feat_by_id.get(feature_id)
        if feat is None:
            return []
        slug = slug_by_feature.get(feature_id)
        pbi_ids = {p["id"] for p in live_pbis if p.get("feature_id") == feature_id}
        filtered = [
            t for t in filtered if _task_matches_feature(t, feat, slug, pbi_ids)
        ]
    if lane:
        feat_rows = [
            f for f in feat_by_id.values() if (f.get("lane") or "") == lane
        ]
        fids = {f["id"] for f in feat_rows}
        pbi_ids = {p["id"] for p in live_pbis if p.get("feature_id") in fids}
        slugs = [s for s in (_plan_slug_from_feature(f) for f in feat_rows) if s]
        def _lane_match(t: dict) -> bool:
            if (t.get("lane") or "") == lane:
                return True
            if t.get("pbi_id") in pbi_ids:
                return True
            src = (t.get("source_ref") or "").replace("\\", "/")
            return any(s in src for s in slugs)
        filtered = [t for t in filtered if _lane_match(t)]
    if tag:
        filtered = [t for t in filtered if tag in (t.get("tags") or [])]
    return filtered


def cmd_wrapup_open(args) -> None:
    """Write a worktree session marker (hook fallback)."""
    from taskman.wrapup import MARKER_DIRNAME, find_repo_root

    root = find_repo_root()
    import subprocess
    from datetime import datetime, timezone

    sha = (args.since or "").strip()
    if not sha:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        sha = proc.stdout.strip() if proc.returncode == 0 else "UNKNOWN"
    branch_proc = subprocess.run(
        ["git", "-C", str(root), "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=False,
    )
    branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else ""
    session_id = (args.session_id or "").strip() or (
        "wrapup-manual-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    marker_dir = root / MARKER_DIRNAME
    marker_dir.mkdir(parents=True, exist_ok=True)
    (marker_dir / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
    path = marker_dir / f"{session_id}.json"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "schema": 1,
        "session_id": session_id,
        "started_at": now,
        "updated_at": now,
        "start_sha": sha,
        "branch": branch,
        "worktree": str(root),
        "runtime": "manual",
        "source": "wrapup-open",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"taskman wrapup open: {path}")
    print(f"  start_sha={sha}  session_id={session_id}")


def cmd_wrapup_gate(args) -> None:
    """Evidence gate for /wrap-up. Exit 1 while worklists remain."""
    from taskman.wrapup import format_gate_report, run_gate

    try:
        result = run_gate(
            marker_path=Path(args.marker) if args.marker else None,
            session_id=args.session_id or None,
            since=args.since or None,
            all_stale=bool(args.all_stale),
        )
    except FileNotFoundError as exc:
        print(f"taskman wrapup gate: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except Exception as exc:
        print(f"taskman wrapup gate: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    if args.json:
        payload = {
            "ok": result.ok,
            "unattributed": result.unattributed,
            "stale": result.stale,
            "marker": str(result.marker.path) if result.marker else None,
            "receipt": str(result.receipt_path) if result.receipt_path else None,
            "start_sha": result.marker.start_sha if result.marker else None,
            "session_id": result.marker.session_id if result.marker else None,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(format_gate_report(result))
    if not result.ok:
        raise SystemExit(1)


def cmd_wrapup_record(args) -> None:
    """Append a clearance to the session receipt."""
    from taskman.wrapup import load_marker, load_receipt, receipt_path_for, save_receipt

    try:
        marker = load_marker(
            marker_path=Path(args.marker) if args.marker else None,
            session_id=args.session_id or None,
        )
    except FileNotFoundError as exc:
        print(f"taskman wrapup record: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    path = receipt_path_for(marker)
    receipt = load_receipt(path)
    receipt.setdefault("session_id", marker.session_id)
    receipt.setdefault("unattributed", {})
    receipt.setdefault("stale", {})

    wrote = False
    if args.attach or args.opened or args.ignore:
        target = args.attach or args.opened or args.ignore
        if args.ignore:
            if not args.reason:
                raise SystemExit("taskman wrapup record: --ignore requires --reason")
            receipt["unattributed"][target] = {
                "action": "ignore",
                "reason": args.reason,
            }
        else:
            if not args.task:
                raise SystemExit("taskman wrapup record: --attach/--opened require --task")
            receipt["unattributed"][target] = {
                "action": "attach" if args.attach else "opened",
                "task_id": int(args.task),
            }
        wrote = True

    if args.stale is not None:
        if not args.verdict or not args.citation:
            raise SystemExit(
                "taskman wrapup record: --stale requires --verdict and --citation"
            )
        entry = {
            "verdict": args.verdict,
            "citation": args.citation,
        }
        if args.verify_ok:
            entry["verify_ok"] = True
        if args.operator_ack:
            entry["operator_ack"] = True
        receipt["stale"][str(args.stale)] = entry
        wrote = True

    if not wrote:
        raise SystemExit(
            "taskman wrapup record: pass --attach/--opened/--ignore or --stale"
        )

    save_receipt(path, receipt)
    print(f"taskman wrapup record: wrote {path}")


def cmd_recommend_next(args) -> None:
    feature_id = getattr(args, "feature", None)
    lane = (getattr(args, "lane", None) or "").strip() or None
    tag = (getattr(args, "tag", None) or "").strip() or None
    if lane:
        _require_lane(lane)

    repo_root = _repo_root_from_path(Path.cwd())
    sole_stem, sole_feature_id = (
        _sole_active_mow_stem(repo_root) if repo_root is not None else (None, None)
    )
    now = dt.datetime.now(dt.UTC)

    slug, board_dir = _board()
    state = store.state(board_dir)
    if feature_id is not None:
        _get_feature(state, slug, feature_id)

    feat_by_id = dict(state["feature"])
    slug_by_feature = {fid: _plan_slug_from_feature(f) for fid, f in feat_by_id.items()}
    tasks_by_id = state["task"]

    candidates = _filter_tasks_for_recommend(
        list(tasks_by_id.values()),
        feature_id=feature_id,
        lane=lane,
        tag=tag,
        feat_by_id=feat_by_id,
        slug_by_feature=slug_by_feature,
        state=state,
    )
    eligible = [t for t in candidates if _is_recommend_eligible(t, tasks_by_id)]

    if not eligible:
        if getattr(args, "json", False):
            print("[]")
        else:
            print("taskman recommend next: none")
        return

    scored: list[tuple[int, dict, str]] = []
    for task in eligible:
        score, reason = _score_recommend_task(
            task,
            now=now,
            sole_stem=sole_stem,
            sole_feature_id=sole_feature_id,
            feat_by_id=feat_by_id,
            slug_by_feature=slug_by_feature,
        )
        scored.append((score, task, reason))

    scored.sort(key=lambda row: (-row[0], row[1]["id"]))
    top = scored[:3]

    if getattr(args, "json", False):
        payload = [
            {"id": t["id"], "title": t.get("title"), "reason": reason, "score": score}
            for score, t, reason in top
        ]
        print(json.dumps(payload))
        return

    print("taskman recommend next:")
    for rank, (score, task, reason) in enumerate(top, start=1):
        print(f"  {rank}. #{task['id']}  {task.get('title', '')}  (score {score}) — {reason}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="taskman", description="Per-project task board, by agents for agents."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="create board/ next to the nearest .taskman.toml")
    p_init.set_defaults(func=cmd_init)

    # feature
    p_feat = sub.add_parser("feature", help="feature operations")
    fsub = p_feat.add_subparsers(dest="featurecmd", required=True)

    p_fadd = fsub.add_parser("add", help="add a feature")
    p_fadd.add_argument("title")
    p_fadd.add_argument("-d", "--description", default="")
    p_fadd.add_argument("-t", "--tags", default="", help="comma-separated")
    p_fadd.add_argument("--status", default="backlog")
    p_fadd.add_argument("--lane", default="", help="product|platform|workforce")
    p_fadd.add_argument("--surface", default="", help="end-user|prod-internal|workforce")
    p_fadd.set_defaults(func=cmd_feature_add)

    p_flist = fsub.add_parser("list", help="list features")
    p_flist.set_defaults(func=cmd_feature_list)

    p_fmove = fsub.add_parser("move", help="change a feature's status")
    p_fmove.add_argument("id", type=int)
    p_fmove.add_argument("--status", required=True)
    p_fmove.set_defaults(func=cmd_feature_move)

    # pbi
    p_pbi = sub.add_parser("pbi", help="PBI operations")
    psub = p_pbi.add_subparsers(dest="pbicmd", required=True)

    p_padd = psub.add_parser("add", help="add a PBI under a feature")
    p_padd.add_argument("title")
    p_padd.add_argument("--feature", type=int, required=True)
    p_padd.add_argument("-t", "--tags", default="", help="comma-separated")
    p_padd.add_argument("-p", "--priority", default="med", help="keystone|high|med|low")
    p_padd.add_argument("--status", default="backlog")
    p_padd.set_defaults(func=cmd_pbi_add)

    p_plist = psub.add_parser("list", help="list PBIs")
    p_plist.add_argument("--feature", type=int, default=None)
    p_plist.set_defaults(func=cmd_pbi_list)

    p_pmove = psub.add_parser("move", help="change a PBI's status")
    p_pmove.add_argument("id", type=int)
    p_pmove.add_argument("--status", required=True)
    p_pmove.set_defaults(func=cmd_pbi_move)

    p_prem = psub.add_parser(
        "remove",
        help="delete a PBI (refuses if tasks remain unless --force)",
    )
    p_prem.add_argument("id", type=int)
    p_prem.add_argument(
        "--force",
        action="store_true",
        help="unlink remaining tasks (set pbi_id NULL) and delete the PBI",
    )
    p_prem.set_defaults(func=cmd_pbi_remove)

    # task
    p_task = sub.add_parser("task", help="task operations")
    tsub = p_task.add_subparsers(dest="taskcmd", required=True)

    p_add = tsub.add_parser("add", help="add a task")
    p_add.add_argument("title", nargs="?", default=None, help="title (optional with --from-capture)")
    p_add.add_argument("--pbi", type=int, default=None, help="link to a PBI (optional)")
    p_add.add_argument("-p", "--priority", default="med", help="keystone|high|med|low")
    p_add.add_argument("-t", "--tags", default="", help="comma-separated")
    p_add.add_argument("--status", default="backlog")
    p_add.add_argument("--lane", default="", help="product|platform|workforce")
    p_add.add_argument("--surface", default="", help="end-user|prod-internal|workforce")
    p_add.add_argument("--afk", default="", help="AFK/delegation hint")
    p_add.add_argument("--notes", default="", help="freeform notes")
    p_add.add_argument("--source", default=None, help="provenance ref (chat/transcript)")
    p_add.add_argument(
        "--from-capture",
        type=int,
        default=None,
        dest="from_capture",
        help="promote a capture: copy summary/body into task and link capture",
    )
    p_add.add_argument(
        "--budget-tool-calls",
        type=int,
        default=None,
        dest="budget_tool_calls",
        help="store budget.max_tool_calls in task brief",
    )
    p_add.set_defaults(func=cmd_add)

    p_claim = tsub.add_parser("claim", help="claim a task for exclusive execution")
    p_claim.add_argument("id", type=int)
    p_claim.add_argument("--agent", required=True, help="claimant agent name")
    p_claim.set_defaults(func=cmd_task_claim)

    p_release = tsub.add_parser("release", help="clear a task's claim lock")
    p_release.add_argument("id", type=int)
    p_release.set_defaults(func=cmd_task_release)

    p_show = tsub.add_parser("show", help="show one task (status, tags, toolkit, notes)")
    p_show.add_argument("id", type=int)
    p_show.set_defaults(func=cmd_show)

    p_move = tsub.add_parser("move", help="change a task's status")
    p_move.add_argument("id", type=int)
    p_move.add_argument("--status", required=True)
    p_move.set_defaults(func=cmd_move)

    p_tset = tsub.add_parser("set", help="edit a task's fields (status: use `move`)")
    p_tset.add_argument("id", type=int)
    p_tset.add_argument("-p", "--priority", default=None, help="|".join(PRIORITIES))
    p_tset.add_argument(
        "-t",
        "--tags",
        default=None,
        help="comma-separated (replaces entire tag list; use --add-tag/--rm-tag to edit)",
    )
    p_tset.add_argument(
        "--add-tag",
        action="append",
        default=None,
        dest="add_tag",
        help="append a tag (repeatable); does not replace existing tags",
    )
    p_tset.add_argument(
        "--rm-tag",
        action="append",
        default=None,
        dest="rm_tag",
        help="remove a tag (repeatable)",
    )
    p_tset.add_argument(
        "--pbi",
        type=int,
        default=None,
        help="reparent under this PBI (and its Feature)",
    )
    p_tset.add_argument("--lane", default=None, help="|".join(LANES))
    p_tset.add_argument("--surface", default=None, help="|".join(SURFACES))
    p_tset.add_argument("--afk", default=None, help="AFK/delegation hint")
    p_tset.add_argument("--notes", default=None, help="freeform notes (replaces)")
    p_tset.set_defaults(func=cmd_task_set)

    p_link = tsub.add_parser("link", help="mark a task blocked by another")
    p_link.add_argument("id", type=int)
    p_link.add_argument("--blocked-by", dest="blocked_by", type=int, required=True)
    p_link.set_defaults(func=cmd_link)

    # decision
    p_dec = sub.add_parser("decision", help="decision log")
    dsub = p_dec.add_subparsers(dest="decisioncmd", required=True)
    p_dadd = dsub.add_parser("add", help="record a decision")
    p_dadd.add_argument("title")
    p_dadd.add_argument("--why", required=True)
    p_dadd.add_argument("--alternatives", default="")
    p_dadd.add_argument("--implications", default="")
    p_dadd.add_argument("--source", default=None)
    p_dadd.add_argument(
        "-t",
        "--tags",
        default="",
        help="comma-separated scope tags (area, path:<glob>, feature:N)",
    )
    p_dadd.add_argument(
        "--task",
        type=int,
        default=None,
        help="owner task id (accountability link; d#865)",
    )
    p_dadd.set_defaults(func=cmd_decision_add)

    p_dshow = dsub.add_parser("show", help="show one decision (why / implications)")
    p_dshow.add_argument("id", type=int)
    p_dshow.set_defaults(func=cmd_decision_show)

    p_dlist = dsub.add_parser("list", help="list recent decisions")
    p_dlist.add_argument(
        "--id",
        type=int,
        action="append",
        default=[],
        help="filter to these ids (repeatable)",
    )
    p_dlist.add_argument("--tag", default="", help="filter: decision must carry this tag")
    p_dlist.add_argument(
        "--touching",
        default="",
        help="filter: path:<glob> tags that fnmatch this path",
    )
    p_dlist.add_argument("--limit", type=int, default=50)
    p_dlist.set_defaults(func=cmd_decision_list)

    p_dlink = dsub.add_parser("link", help="link a decision to an owner task")
    p_dlink.add_argument("id", type=int)
    p_dlink.add_argument("--task", type=int, required=True)
    p_dlink.set_defaults(func=cmd_decision_link)

    # requirement (living spec)
    p_req = sub.add_parser("requirement", help="living spec: SHALL requirements + scenarios")
    rsub = p_req.add_subparsers(dest="requirementcmd", required=True)

    p_radd = rsub.add_parser("add", help="add a requirement under a feature")
    p_radd.add_argument("title")
    p_radd.add_argument("--feature", type=int, required=True)
    p_radd.add_argument("--statement", required=True, help="SHALL/MUST/SHOULD/MAY behavior")
    p_radd.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="'name|given|when|then' — repeatable",
    )
    p_radd.add_argument("--pbi", type=int, default=None, help="PBI this requirement came from")
    p_radd.set_defaults(func=cmd_requirement_add)

    p_rmod = rsub.add_parser("modify", help="update a requirement in place (MODIFIED)")
    p_rmod.add_argument("id", type=int)
    p_rmod.add_argument("--title", default=None)
    p_rmod.add_argument("--statement", default=None)
    p_rmod.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="'name|given|when|then' — repeatable; replaces existing scenarios",
    )
    p_rmod.add_argument("--pbi", type=int, default=None, help="PBI that made this change")
    p_rmod.set_defaults(func=cmd_requirement_modify)

    p_rrm = rsub.add_parser("remove", help="retire a requirement (REMOVED — soft delete)")
    p_rrm.add_argument("id", type=int)
    p_rrm.set_defaults(func=cmd_requirement_remove)

    p_rshow = rsub.add_parser("show", help="show one requirement + scenarios")
    p_rshow.add_argument("id", type=int)
    p_rshow.set_defaults(func=cmd_requirement_show)

    p_rlist = rsub.add_parser("list", help="show a feature's living spec")
    p_rlist.add_argument("--feature", type=int, required=True)
    p_rlist.add_argument("--status", default="", help="active|removed (default: active)")
    p_rlist.set_defaults(func=cmd_requirement_list)

    # capture
    p_cap = sub.add_parser("capture", help="capture notes (qa/grill/plan)")
    csub = p_cap.add_subparsers(dest="capturecmd", required=True)
    p_cadd = csub.add_parser("add", help="add a capture")
    p_cadd.add_argument("--kind", required=True, help="qa|grill|plan")
    p_cadd.add_argument("--summary", required=True)
    p_cadd.add_argument("--body", default="")
    p_cadd.add_argument("--source", default=None)
    p_cadd.add_argument(
        "-t",
        "--tags",
        default="",
        help="comma-separated scope tags (area, path:<glob>, feature:N)",
    )
    p_cadd.add_argument(
        "--task",
        type=int,
        default=None,
        help="link to task (also auto-detected from summary prefix #123)",
    )
    p_cadd.set_defaults(func=cmd_capture_add)

    p_clink = csub.add_parser("link", help="link a capture to a task")
    p_clink.add_argument("id", type=int)
    p_clink.add_argument("--task", type=int, required=True)
    p_clink.set_defaults(func=cmd_capture_link)

    p_cunlink = csub.add_parser("unlink", help="remove capture→task link")
    p_cunlink.add_argument("id", type=int)
    p_cunlink.set_defaults(func=cmd_capture_unlink)

    p_clist = csub.add_parser("list", help="list captures")
    p_clist.add_argument("--task", type=int, default=None, help="filter by linked task")
    p_clist.add_argument("--kind", default="", help="qa|grill|plan")
    p_clist.add_argument(
        "--unlinked",
        action="store_true",
        help="only captures with no task link",
    )
    p_clist.add_argument("--tag", default="", help="filter: capture must carry this tag")
    p_clist.add_argument(
        "--touching",
        default="",
        help="filter: path:<glob> tags that fnmatch this path",
    )
    p_clist.add_argument("--limit", type=int, default=50)
    p_clist.set_defaults(func=cmd_capture_list)

    p_cshow = csub.add_parser("show", help="show one capture (body)")
    p_cshow.add_argument("id", type=int)
    p_cshow.set_defaults(func=cmd_capture_show)

    # board
    p_board = sub.add_parser("board", help="show the board (current project)")
    p_board.add_argument("--status", default="", help="comma-separated filter")
    p_board.add_argument(
        "--flat",
        action="store_true",
        help="legacy flat view (group by status only)",
    )
    p_board.set_defaults(func=cmd_board)

    # session
    p_session = sub.add_parser("session", help="session metrics (Phase 1)")
    ssub = p_session.add_subparsers(dest="sessioncmd", required=True)
    p_rec = ssub.add_parser("record", help="emit meta.json + session.record event for one transcript")
    p_rec.add_argument("--file", required=True, help="path to archived .jsonl")
    p_rec.set_defaults(func=cmd_session_record)

    p_bf = ssub.add_parser("backfill", help="scan docs/chat-history/; skip if meta.json exists")
    p_bf.add_argument(
        "--root",
        default="",
        help="chat-history root (default: docs/chat-history)",
    )
    p_bf.set_defaults(func=cmd_session_backfill)

    p_list = ssub.add_parser("list", help="list sessions + cost summary")
    p_list.add_argument("--since", default="", help="YYYY-MM-DD filter on recorded_at")
    p_list.set_defaults(func=cmd_session_list)

    # plan (dispatch bridge)
    p_plan = sub.add_parser("plan", help="from-decisions/to-dispatch Work-Item plans (dispatch bridge)")
    plansub = p_plan.add_subparsers(dest="plan_cmd", required=True)
    p_import = plansub.add_parser(
        "from-decisions",
        help="pull a .dispatch/ folder or taskman-plan.json into Feature+Tasks",
    )
    p_import.add_argument(
        "path",
        help="path to a .dispatch/ directory or a taskman-plan.json file",
    )
    p_import.add_argument(
        "--feature",
        type=int,
        default=None,
        help="attach under this existing Feature id (mint nothing)",
    )
    p_import.set_defaults(func=cmd_plan_from_decisions)

    p_export = plansub.add_parser(
        "to-dispatch",
        help="push a board slice out to a runnable .dispatch/ folder",
    )
    p_export.add_argument(
        "--dir",
        required=True,
        help="destination directory (created if missing)",
    )
    p_export.add_argument("--feature", type=int, default=None, help="feature id")
    p_export.add_argument(
        "--status",
        default="",
        help="comma-separated task status filter (e.g. todo,in_progress)",
    )
    p_export.add_argument(
        "--lane",
        default="",
        help="feature lane filter (product|platform|workforce)",
    )
    p_export.add_argument(
        "--tag",
        default="",
        help="task tag filter (exact match, e.g. role:code-edit)",
    )
    p_export.add_argument(
        "--include-decisions",
        action="store_true",
        help=f"also export tasks tagged {DECISION_TAG} (skipped by default)",
    )
    p_export.set_defaults(func=cmd_plan_to_dispatch)

    p_shipped = plansub.add_parser(
        "mark-shipped",
        help="move tasks linked to shipped dispatch briefs to done",
    )
    p_shipped.add_argument(
        "dispatch_dir",
        help="path to dispatch/ folder (INDEX.md + briefs)",
    )
    p_shipped.add_argument(
        "--force",
        action="store_true",
        help="also move blocked tasks to done",
    )
    p_shipped.set_defaults(func=cmd_plan_mark_shipped)

    # recommend
    p_recommend = sub.add_parser(
        "recommend",
        help="rule-based next-work suggestions",
        description=RECOMMEND_HELP_WEIGHTS,
    )
    recsub = p_recommend.add_subparsers(dest="recommend_cmd", required=True)
    p_next = recsub.add_parser(
        "next",
        help="print top 1–3 ranked task suggestions",
        description=RECOMMEND_HELP_WEIGHTS,
    )
    p_next.add_argument("--feature", type=int, default=None, help="feature id filter")
    p_next.add_argument(
        "--lane",
        default="",
        help="task lane filter (product|platform|workforce)",
    )
    p_next.add_argument("--tag", default="", help="task tag filter (exact match)")
    p_next.add_argument(
        "--json",
        action="store_true",
        help="JSON array of {id, title, reason, score}",
    )
    p_next.set_defaults(func=cmd_recommend_next)

    # wrapup — session marker + reconcile gate
    p_wrap = sub.add_parser(
        "wrapup",
        help="session-start marker + evidence gate for /wrap-up",
    )
    wrapsub = p_wrap.add_subparsers(dest="wrapup_cmd", required=True)

    p_wopen = wrapsub.add_parser(
        "open",
        help="write a session marker (manual fallback when the hook did not run)",
    )
    p_wopen.add_argument("--session-id", default="", help="stable id (default: wrapup-manual-<ts>)")
    p_wopen.add_argument(
        "--since",
        default="",
        help="start sha (default: HEAD)",
    )
    p_wopen.set_defaults(func=cmd_wrapup_open)

    p_wgate = wrapsub.add_parser(
        "gate",
        help="reconcile unattributed paths + stale in_progress; exit 1 if nonempty",
    )
    p_wgate.add_argument("--marker", default="", help="path to session marker JSON")
    p_wgate.add_argument("--session-id", default="", help="lookup under .session-markers/")
    p_wgate.add_argument("--since", default="", help="manual start sha (no marker required)")
    p_wgate.add_argument(
        "--all-stale",
        action="store_true",
        help="include every in_progress task (default: session-touched only)",
    )
    p_wgate.add_argument("--json", action="store_true", help="machine-readable report")
    p_wgate.set_defaults(func=cmd_wrapup_gate)

    p_wrec = wrapsub.add_parser(
        "record",
        help="clear a gate item by writing the session receipt",
    )
    p_wrec.add_argument("--marker", default="", help="path to session marker JSON")
    p_wrec.add_argument("--session-id", default="", help="lookup under .session-markers/")
    p_wrec.add_argument("--attach", default="", help="path claimed by an existing task")
    p_wrec.add_argument("--opened", default="", help="path covered by a newly opened task")
    p_wrec.add_argument("--ignore", default="", help="path to ignore with --reason")
    p_wrec.add_argument("--reason", default="", help="required with --ignore")
    p_wrec.add_argument("--task", type=int, default=None, help="task id for attach/opened")
    p_wrec.add_argument("--stale", type=int, default=None, help="in_progress task id")
    p_wrec.add_argument(
        "--verdict",
        default="",
        choices=["", "done", "still-open", "blocked"],
        help="required with --stale",
    )
    p_wrec.add_argument("--citation", default="", help="required with --stale (commit/file/evidence)")
    p_wrec.add_argument(
        "--verify-ok",
        action="store_true",
        help="code ticket done: verify command was run and passed",
    )
    p_wrec.add_argument(
        "--operator-ack",
        action="store_true",
        help="design/spike ticket done: operator confirmed",
    )
    p_wrec.set_defaults(func=cmd_wrapup_record)

    args = parser.parse_args(argv)
    args.func(args)
