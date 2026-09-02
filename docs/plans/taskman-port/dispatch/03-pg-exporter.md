# pg-exporter: one-way Postgres → event-log board exporter

**Role:** code-edit   **Wave:** 2   **AFK:** yes   **Background:** yes

**Decisions / Specs (pointers):** `-` — board-less repo; working decisions d-p3/d-p4/d-p6/
d-p8/d-p9/**d-p10** in `docs/plans/taskman-port/plan.md` §Decisions locked, restated below
where they bind this lane.

## Goal

`python -m taskman.pgexport --slug <slug> --board-dir <dir>` reads one project's rows from
the live Postgres schema with **raw SQL over psycopg** and writes a complete event-log
board via `eventlog.log.bootstrap` — every id preserved, per-entity counters seeded at
max+1, per-entity row counts printed as progress output. The same module's
`--verify` mode re-reads Postgres and diffs it **field-by-field against the replayed
board** — the zero-loss gate d-p10 locked at grill Q1. The lane ships the tool plus
fake-row unit tests; it never touches a live database itself (the cutover lane Z runs it
for real).

## Context & decisions (only what this todo needs)

- **Raw SQL, not models.py (plan d-p3):** lane D deletes `models.py`/`db.py` in this same
  wave. Import `psycopg` lazily inside `main()`/the fetch function with a clear error
  naming the `pgexport` extra, so `import taskman.pgexport` costs nothing and the package
  works without psycopg installed. Table names are stable: `taskman_project`, `taskman_tag`,
  `taskman_feature`, `taskman_feature_tag`, `taskman_pbi`, `taskman_pbi_tag`,
  `taskman_requirement`, `taskman_task`, `taskman_task_dep`, `taskman_decision`,
  `taskman_capture`, `taskman_session` (schema frozen at alembic head 0009 — it will never
  move again).
- **Event construction:** one `<entity>.add` event per row (`session.record` for sessions —
  plan d-p8), `"v": 1`, `ts` = the row's `created_at` in UTC ISO seconds, `id` = the
  original primary key (plan d-p4). Current-state columns ride in the same add event's
  fields — including `claimed_by`/`claimed_at` on tasks, `status`, `brief`, `notes`,
  `source_ref`. Emit events sorted by `(created_at, entity, id)` so the log reads
  chronologically; correctness must not depend on that order since every add is
  self-contained.
- **Relations flattened (plan d-p6, operator-confirmed grill Q2):** `taskman_task_dep`
  becomes a `blocked_by: [ids]` field on the task's add event. Feature/PBI tag M2Ms resolve
  to `tags: [names]` string arrays. `Decision.task_id` / `Capture.task_id` ride as plain
  fields. Project and Tag rows produce **no events** — project identity stays in
  `.taskman.toml`; the exporter selects rows by joining on the project slug given via
  `--slug`. **Orphaned tag rows (a `taskman_tag` name attached to no feature/PBI) are
  elided by design** — the operator accepted this at grill Q2; `--verify` must treat them
  as expected elisions, never as diffs.
- **Transcript paths (plan d-p9):** relativize `taskman_session.transcript_path` through
  lane B's `metrics.portable_transcript_path` (merged before this wave starts) — absolute
  `/Users/...` values from old rows become `~/...`.
- **Counters:** `next_ids` = per entity `max(id) + 1` (1 for an entity with no rows).
- **`--verify` (plan d-p10, grill Q1):** given `--slug` + `--board-dir`, re-fetch every row
  from Postgres, build the *expected* field dict through the **same transform pipeline as
  export** (UTC-second timestamps, `~`-relative transcript paths, M2M→array flattening,
  project/tag-table elision), replay the board with `store.state()`, and diff. Output:
  per-entity totals plus one line per difference naming entity, id, and field; exit 0 only
  on zero diffs, non-zero otherwise. Sharing one transform pipeline between export and
  verify is what makes a diff mean divergence — build the row→fields function once and call
  it from both paths, never two parallel implementations that can disagree.
- **Refusal to clobber:** `bootstrap` (lane A) already raises on a non-empty board dir —
  surface that as a clean CLI error, no `--force` flag; regenerating means the operator
  deletes `board/` first, deliberately.
- Requirement scenarios (`JSONB` list) and `Task.brief` (`JSONB` dict) pass through as-is —
  they are already JSON.
- Datetimes: emit timezone-aware UTC ISO with seconds precision, matching the store's
  `_now()` format.

## Files in scope

- `taskman/taskman/pgexport.py` (new)
- `taskman/tests/test_pgexport.py` (new)

## Depends on

- 01-store-entities (schema + `bootstrap`)
- 02-relativize-transcript-paths (`portable_transcript_path`)

## Do NOT

- Do not recreate `taskman/tests/__init__.py` — it already exists.
- Do not connect to, read, or write any real database in this lane — unit tests feed the
  event-builder fake row dicts; the psycopg fetch layer stays a thin, untested-by-design
  shell (lane Z exercises it against reality, foreground).
- Do not import sqlalchemy, alembic, or `taskman.models` anywhere — lane D is deleting them
  in this wave; raw column lists only.
- Do not touch `pyproject.toml` (lane D owns it, including adding the `pgexport` optional
  extra — coordinate via the seam, not the file).
- Do not write a reverse importer (board → Postgres). Migration is one-way by decision d-p3.
- Do not edit anything under `eventlog/` — if `bootstrap`'s contract doesn't fit, report the
  mismatch in Verification instead of patching around it.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- Prefer **`git commit -- <paths>`** over `git add` + `git commit`; new files must be
  `git add`-ed by name first, then still commit with `-- <paths>`.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.
- Before commit while parallel lanes are active, run `git status` and confirm only intended
  paths are staged.

## Acceptance check

- The exporter SHALL preserve ids: GIVEN fake rows for tasks {3, 17} and features {2} WHEN
  events are built and `bootstrap` writes a board THEN `store.state()` shows exactly those
  ids with matching titles, and `next_ids` reads `{"task": 18, "feature": 3, ...}`.
- The exporter SHALL flatten relations: GIVEN a task dep row (task 17 blocked by 3) and a
  feature tag M2M row THEN task 17's state carries `blocked_by == [3]` and the feature's
  `tags` is the tag-name list.
- The exporter SHALL relativize session paths: GIVEN a fake session row whose
  `transcript_path` is absolute under home THEN the emitted event's path starts with `~/`.
- The exporter SHALL refuse a non-empty target: GIVEN a board dir already holding
  `events.jsonl` WHEN export runs THEN it exits non-zero without modifying the dir.
- The count report SHALL match what was written: printed per-entity counts equal the number
  of events emitted per entity.
- `--verify` SHALL be a real zero-loss gate (d-p10): GIVEN fake rows exported to a board
  and then one field mutated in the fake source (a tag renamed, a `claimed_by` cleared, a
  `blocked_by` id dropped) WHEN `--verify` runs THEN it exits non-zero naming that entity,
  id, and field; GIVEN untouched source and board THEN it exits 0 with per-entity totals.
- Export and verify SHALL share one row→fields transform: the mutation test above must fail
  if verify grows its own divergent copy (assert both code paths call the same function).
- Verify: `cd taskman && uv run pytest tests/test_pgexport.py` exits 0 (no DB needed by the
  tests; `--noconftest` is the documented fallback if the legacy conftest's Postgres probe
  can't reach a server from your worktree).

## QA contract

- Scoped pytest run green (command above).
- `python -c "import taskman.pgexport"` succeeds in an environment without psycopg
  (lazy-import proof).
- tdd: event-builder written test-first (red evidence in Verification).

## Toolkit

- Invoke: `skill:tdd` for the event-builder and refusal paths.

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: <d-p3/d-p4/d-p6/d-p8/d-p9/d-p10: how, file:line — or "none pointed">
