"""One-way Postgres -> event-log board exporter, plus the --verify gate (d-p10).

`python -m taskman.pgexport --slug <slug> --board-dir <dir>` reads one
project's rows over raw SQL (d-p3: no models.py, no sqlalchemy — those die in
this same wave) and writes a complete board via `eventlog.log.bootstrap`,
every id preserved (d-p4). `--verify` re-reads Postgres and diffs it
field-by-field against the replayed board.

The row->fields transform (`row_fields`, via `transform`) is built ONCE and
called from BOTH the export path and the verify path — that sharing is what
makes a verify diff mean real divergence rather than two pipelines drifting
apart (d-p10).

psycopg is imported lazily inside the fetch layer: `import taskman.pgexport`
must work without it (it is the optional `pgexport` extra).
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

from .eventlog import log, schema
from .metrics import portable_transcript_path

# Columns fetched (and exported) per entity, schema frozen at alembic head
# 0009. `id` rides in the event envelope; `project_id` is only the WHERE
# filter — the board dir is the project (d-p6) — so neither appears here.
COLUMNS = {
    "feature": ("id", "title", "description", "status", "lane", "surface",
                "created_at", "updated_at"),
    "pbi": ("id", "feature_id", "title", "acceptance_criteria", "status",
            "priority", "created_at", "updated_at"),
    "requirement": ("id", "feature_id", "title", "statement", "scenarios",
                    "status", "source_pbi_id", "created_at", "updated_at"),
    "task": ("id", "pbi_id", "title", "status", "priority", "tags", "lane",
             "surface", "afk", "notes", "source_ref", "brief", "claimed_by",
             "claimed_at", "created_at", "updated_at"),
    "decision": ("id", "task_id", "title", "why", "alternatives",
                 "implications", "tags", "source_ref", "created_at"),
    "capture": ("id", "task_id", "kind", "summary", "body", "tags",
                "source_ref", "created_at"),
    "session": ("id", "session_id", "source", "transcript_path",
                "tokens_status", "input_tokens", "output_tokens",
                "cache_read_tokens", "cache_creation_tokens", "api_calls",
                "models", "effort", "recorded_at", "created_at"),
}


def _iso(value: dt.datetime) -> str:
    """UTC ISO with seconds precision — the store's `_now()` format."""
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds")


def _home_relative_strings(value):
    """Rewrite this-machine home prefixes to '~' in any string (portable board).

    Transcript paths already go through `portable_transcript_path`; live task
    notes/briefs/`source_ref` also embed `/Users/...` from Files-in-scope
    lists. Same rewrite on export and verify, so a remaining diff is real.
    """
    home = Path.home().as_posix()
    if isinstance(value, str):
        if value == home:
            return "~"
        if home + "/" in value or value.startswith(home + "/"):
            return value.replace(home, "~")
        return value
    if isinstance(value, list):
        return [_home_relative_strings(v) for v in value]
    if isinstance(value, dict):
        return {k: _home_relative_strings(v) for k, v in value.items()}
    return value


def merge_relations(raw: dict) -> dict[str, list[dict]]:
    """Flatten relation tables onto their owning rows (d-p6).

    `task_dep` pairs become `blocked_by: [ids]` on the task; `feature_tag` /
    `pbi_tag` (already joined to tag *names* by the fetch) become
    `tags: [names]`. Both sorted for a deterministic log. Project and Tag rows
    produce no events — an orphaned tag name reaches no row here, which is the
    designed elision, not a loss.
    """
    deps: dict[int, list[int]] = {}
    for task_id, blocked_by_id in raw.get("task_dep", ()):
        deps.setdefault(task_id, []).append(blocked_by_id)
    tags: dict[str, dict[int, list[str]]] = {"feature": {}, "pbi": {}}
    for entity, key in (("feature", "feature_tag"), ("pbi", "pbi_tag")):
        for owner_id, name in raw.get(key, ()):
            tags[entity].setdefault(owner_id, []).append(name)
    merged: dict[str, list[dict]] = {}
    for entity in schema.ENTITIES:
        rows = []
        for row in raw.get(entity, ()):
            row = dict(row)
            if entity == "task":
                row["blocked_by"] = sorted(deps.get(row["id"], []))
            elif entity in tags:
                row["tags"] = sorted(tags[entity].get(row["id"], []))
            rows.append(row)
        merged[entity] = rows
    return merged


def row_fields(entity: str, row: dict) -> dict:
    """THE shared row->fields transform — export builds add events from it and
    verify rebuilds its expected values through it (d-p10). Datetimes become
    UTC-second ISO strings (`created_at` stays in fields as well as riding as
    the envelope `ts`, so verify sees it in replayed state); session transcript
    paths go home-relative (d-p9). JSONB values pass through as-is.
    """
    fields = {}
    for key, value in row.items():
        if key == "id":
            continue  # envelope-only: bootstrap refuses an id inside fields
        if isinstance(value, dt.datetime):
            value = _iso(value)
        elif entity == "session" and key == "transcript_path":
            value = portable_transcript_path(Path(value))
        else:
            value = _home_relative_strings(value)
        fields[key] = value
    return fields


def transform(raw: dict) -> dict[str, dict[int, dict]]:
    """entity -> id -> expected board fields, through the one shared pipeline."""
    return {entity: {row["id"]: row_fields(entity, row) for row in rows}
            for entity, rows in merge_relations(raw).items()}


def build_events(raw: dict) -> tuple[list[dict], dict[str, int], dict[str, int]]:
    """(events, next_ids, per-entity counts) from raw table rows.

    One create event per row — `<entity>.add`, `session.record` (d-p8) — with
    the original primary key as the envelope id (d-p4) and the row's
    `created_at` as `ts`. Sorted by (created_at, entity, id) so the log reads
    chronologically; every add is self-contained, so correctness never depends
    on that order.
    """
    transformed = transform(raw)
    keyed = []
    for entity, by_id in transformed.items():
        for eid, fields in by_id.items():
            event = {"v": schema.SUPPORTED_VERSION,
                     "type": f"{entity}.{schema.CREATE_VERBS[entity]}",
                     "id": eid, "ts": fields["created_at"], "fields": fields}
            keyed.append((fields["created_at"], entity, eid, event))
    keyed.sort(key=lambda item: item[:3])
    events = [event for *_key, event in keyed]
    next_ids = {entity: max(by_id, default=0) + 1
                for entity, by_id in transformed.items()}
    counts = {entity: len(by_id) for entity, by_id in transformed.items()}
    return events, next_ids, counts


def export_board(raw: dict, board_dir: Path) -> dict[str, int]:
    """Write the full board; returns per-entity counts. Raises ValueError on a
    non-empty board dir (bootstrap's refusal — regenerating means the operator
    deletes board/ first, deliberately; no --force)."""
    events, next_ids, counts = build_events(raw)
    log.bootstrap(board_dir, events, next_ids)
    return counts


def verify_board(raw: dict, board_dir: Path) -> tuple[dict[str, int], list[str]]:
    """The zero-loss gate (d-p10): rebuild every expected field dict through
    the SAME `transform` pipeline export used, replay the board, and diff.
    Returns (per-entity row totals, diff lines each naming entity, id, field).
    Zero diffs is the cutover gate; totals are progress output only.
    """
    expected = transform(raw)
    actual = log.replay(board_dir)
    totals = {entity: len(by_id) for entity, by_id in expected.items()}
    diffs = []
    for entity in schema.ENTITIES:
        exp_rows, act_rows = expected[entity], actual[entity]
        for eid in sorted(exp_rows.keys() | act_rows.keys()):
            if eid not in act_rows:
                diffs.append(f"{entity} #{eid}: missing from the board")
                continue
            if eid not in exp_rows:
                diffs.append(f"{entity} #{eid}: on the board but not in Postgres")
                continue
            exp, act = exp_rows[eid], act_rows[eid]
            for field in sorted((exp.keys() | act.keys()) - {"id"}):
                if exp.get(field) != act.get(field):
                    diffs.append(
                        f"{entity} #{eid}: field {field!r} differs —"
                        f" postgres {exp.get(field)!r} vs board {act.get(field)!r}")
    return totals, diffs


# ---- the thin psycopg fetch layer (untested by design — lane Z runs it) ----

def _default_dsn() -> str:
    """TASKMAN_DATABASE_URL, else DATABASE_URL, else the project default —
    with any sqlalchemy driver suffix stripped, since raw psycopg wants a
    plain postgresql:// scheme. (taskman.config is not imported: it drags in
    python-dotenv, which dies with the database this same wave — d-p7.)"""
    dsn = (os.environ.get("TASKMAN_DATABASE_URL")
           or os.environ.get("DATABASE_URL")
           or "postgresql://taskman:taskman@localhost:5432/taskman")
    for driver in ("+psycopg", "+asyncpg"):
        dsn = dsn.replace(driver, "", 1)
    return dsn


def _fetch_raw(dsn: str, slug: str) -> dict:
    """Read one project's rows into the plain dict/tuple shape the pure
    pipeline consumes. Raw SQL only (d-p3). The Project and Tag tables are
    touched only to resolve the slug and the tag *names* on live M2M pairs —
    an orphaned tag row is never selected, which is its designed elision."""
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:  # lazy: `import taskman.pgexport` costs nothing
        raise SystemExit(
            "pgexport needs psycopg — install the 'pgexport' extra"
            " (uv sync --extra pgexport)") from exc
    raw: dict = {}
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM taskman_project WHERE slug = %s", (slug,))
            found = cur.fetchone()
            if found is None:
                raise SystemExit(f"pgexport: no project with slug {slug!r}")
            project_id = found[0]
            cur.execute(
                "SELECT d.task_id, d.blocked_by_id FROM taskman_task_dep d"
                " JOIN taskman_task t ON t.id = d.task_id"
                " WHERE t.project_id = %s", (project_id,))
            raw["task_dep"] = cur.fetchall()
            for key, owner in (("feature_tag", "feature"), ("pbi_tag", "pbi")):
                cur.execute(
                    f"SELECT m.{owner}_id, t.name FROM taskman_{key} m"
                    f" JOIN taskman_tag t ON t.id = m.tag_id"
                    f" JOIN taskman_{owner} o ON o.id = m.{owner}_id"
                    f" WHERE o.project_id = %s", (project_id,))
                raw[key] = cur.fetchall()
        with conn.cursor(row_factory=dict_row) as cur:
            for entity, columns in COLUMNS.items():
                cur.execute(
                    f"SELECT {', '.join(columns)} FROM taskman_{entity}"
                    f" WHERE project_id = %s ORDER BY id", (project_id,))
                raw[entity] = cur.fetchall()
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m taskman.pgexport",
        description="Export one project from Postgres to an event-log board.")
    parser.add_argument("--slug", required=True, help="project slug in Postgres")
    parser.add_argument("--board-dir", required=True, type=Path,
                        help="empty board directory to write")
    parser.add_argument("--dsn", default=None,
                        help="Postgres DSN (default: TASKMAN_DATABASE_URL /"
                             " DATABASE_URL / project default)")
    parser.add_argument("--verify", action="store_true",
                        help="diff Postgres field-by-field against the"
                             " replayed board instead of exporting (d-p10)")
    args = parser.parse_args(argv)
    raw = _fetch_raw(args.dsn or _default_dsn(), args.slug)
    if args.verify:
        totals, diffs = verify_board(raw, args.board_dir)
        for entity in schema.ENTITIES:
            print(f"{entity}: {totals[entity]} rows checked")
        for diff in diffs:
            print(f"diff: {diff}")
        if diffs:
            print(f"pgexport --verify: {len(diffs)} difference(s)", file=sys.stderr)
            return 1
        print("pgexport --verify: zero differences")
        return 0
    try:
        args.board_dir.mkdir(parents=True, exist_ok=True)
        counts = export_board(raw, args.board_dir)
    except ValueError as exc:
        print(f"pgexport: {exc}", file=sys.stderr)
        return 1
    for entity in schema.ENTITIES:
        print(f"{entity}: {counts[entity]} events")
    return 0


if __name__ == "__main__":
    sys.exit(main())
