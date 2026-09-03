# taskman-port — land the dbless board

**Stem:** `taskman-port`
**Created:** 2026-09-01
**Predecessor stem:** `taskman-no-db` (the spike — verdict in [`../taskman-no-db/spike-result.md`](../taskman-no-db/spike-result.md): **C3 is viable on Windows. Build the port.** Shape B retired, green ×4 consecutive on `windows-latest`)
**Origin brainstorm:** `dotfiles-ai/docs/brainstorms/taskman-no-db.md` (verdict: pursue, shape C3, 2026-08-12)

## Goal

The whole taskman CLI runs on the committed event-log store: every entity, every subcommand,
no Postgres, no SQLAlchemy, no alembic. The two live boards (`<board-a>` at `<repo-a>`,
`<board-b>` at `<repo-b>`) are migrated onto committed `board/` directories
and keep working through the same `taskman ...` commands. The shipped guarantees that say
"taskman requires Postgres" are amended in the same change that makes them false.

## What we'll do

1. **Grow the store from one entity to the full board** — feature, PBI, requirement, decision,
   capture, session alongside task; per-entity id counters; a versioned event envelope that
   replay refuses when it doesn't recognise; the public `log.transaction()` seam the spike's
   ship-check asked for.
2. **Relativize the paths a committed board would leak** — `AgentSession.transcript_path`
   stores `str(transcript)` verbatim today (`taskman/taskman/metrics.py:250`); a committed
   board carrying absolute paths is wrong on every machine but the one that wrote it.
3. **Build the one-way Postgres exporter** — raw-SQL reader that turns each live board into an
   event stream plus seeded id counters, preserving every existing id.
4. **Rewire the CLI** — all 42 subcommands and 38 `Session()` sites in `cli.py`, plus
   `wrapup.py`'s three, moved onto the store; `db.py`, `models.py`, and the 9-revision alembic
   tree deleted; the 17-file pytest suite converted from throwaway-Postgres to tmp-board
   fixtures and added to the CI matrix, so the port is proven on Windows like the spike was.
5. **Cut over and tell the truth** — migrate both live boards for real, mirror `taskman/` into
   dotfiles-ai in lockstep (the live `taskman` on PATH is dotfiles-ai's venv — the tree the
   store is *not* in today), and amend invariant I10, `README.md`'s Requirements, and the
   work-PC artifact.

## What you'll have at the end

| Area | End state |
|---|---|
| The CLI | `taskman board`, `task add/claim/...`, `decision`, `requirement`, `capture`, `plan`, `wrap` — every subcommand works against `board/` with no database process running |
| The two live boards | `<board-a>` and `<board-b>` each have a committed `board/` (events.jsonl + counters) with every existing id preserved; `taskman board` from each repo shows the same rows Postgres did |
| Dependencies | `pyproject.toml` core deps shrink from five to one (`pydantic`); `psycopg` survives only as the exporter's optional extra; the store's stdlib-only AST test still green |
| Windows | The converted pytest suite runs in the CI matrix on `ubuntu-latest` + `windows-latest`; eventlog plain-script suites keep running there unchanged |
| The mirror | dotfiles-ai's `taskman/` is byte-identical for match paths, `tree-drift.json` knows the new files, its venv rebuilt, and `taskman board` works from <board-a>/<board-b> via the PATH that exists today |
| The guarantees | I10 and `README.md` Requirements say what is now true; the work-PC artifact's "prototyped but not landed" sentence updated; grep finds no stale "requires Postgres" claim |

**In one line:** The board taskman serves is a text file in git — on both machines, for both
live projects, with the old guarantees rewritten instead of quietly falsified.

## Decisions locked

Inherited from the spike (see `../taskman-no-db/plan.md` — restated, not reopened):

- **Shape C3** — append-only event log; B (SQLite) retired by the spike verdict.
- **The board is committed, top-level `board/` in the consuming repo.** Discovery: the
  directory holding the nearest `.taskman.toml`, plus `board/`. Auto-push hazard and
  path-relativization consequences named there.
- **Concurrency primitive is the `O_EXCL` lockfile**, `PermissionError` treated as contention
  (the Windows delete-pending fix). Proven; not reopened here.
- **Stale locks break by mtime age; the holder keeps its fd open.** Windows-safe by design.
- **The spike amended no shipped guarantee — this run does.** I10 (`HOW-TO-USE.agent.md`) and
  `README.md` Requirements are amended in the change that lands the port. That is this change.

Taken at the plan pass and **operator-confirmed one by one at the `/mow ready` grill,
Q1–Q5, 2026-09-02/03** (d-p10 added by the grill itself):

- **d-p1 · Event envelope + fail-closed replay.** (operator-confirmed, 2026-09-02 grill Q3)
  Every event is one JSON line
  `{"v": 1, "type": "<entity>.<verb>", "id": N, "ts": "<utc iso>", ...}`. Replay raises on:
  a malformed line with a newline (existing rule), an unknown entity or verb, a missing `v`,
  or `v > SUPPORTED_VERSION`. Rationale: board and code travel in the same git tree, so an
  older reader meeting a newer board should stop loudly, never silently drop events. The
  spike's `task.add` format without `"v"` has no live users — no legacy tolerance needed.
- **d-p2 · Compaction: never, with a `# debt:` marker.** (operator-confirmed, 2026-09-02
  grill Q3) Replay of thousands of events is
  milliseconds; the marker's trigger: revisit above ~50k events or ~5 MB log. Also close the
  spike ship-check's finding: the full-replay-under-lock `claim` gets its own `# debt:` line.
- **d-p3 · Migration is one-way, exporter reads raw SQL via psycopg.** (operator-confirmed,
  2026-09-03 grill Q5) No SQLAlchemy, no
  `models.py` import — so the CLI lane can delete those files in the same wave without
  breaking the exporter. `psycopg` moves to `[project.optional-dependencies] pgexport`.
  Old Postgres data stays untouched as its own archive; nothing drops tables.
- **d-p4 · Ids are preserved and per-entity.** (operator-confirmed, 2026-09-03 grill Q5)
  The single `next_id` counter becomes a
  `next_ids` JSON file keyed by entity. The exporter writes original ids into `*.add` events
  and seeds each counter at max(id)+1 — task #868 stays #868 after migration.
- **d-p5 · Build in ai-wow, mirror to dotfiles-ai in lockstep at cutover.** (operator-confirmed,
  2026-09-03 grill Q4) ai-wow has the CI
  matrix (the Windows proof lives here); dotfiles-ai has the live venv on PATH. The cutover
  lane copies the tree, adds the new paths to `tree-drift.json` as `match`, reruns that
  guard, and rebuilds the venv. Neither drift guard can see a one-tree-only directory —
  measured in the spike session's addendum 2 — so the mirror step is explicit, not assumed.
- **d-p6 · Project and Tag entities die; the board dir is the project.** (operator-confirmed,
  2026-09-02 grill Q2) Identity stays in `.taskman.toml` (slug check unchanged). Feature/PBI
  tags become string arrays like `Task.tags` already is; the Tag M2M tables are not ported.
  **Orphaned tag rows — names attached to no feature/PBI — are elided by design** (operator
  accepted at Q2); `--verify` must not report them as diffs.
- **d-p7 · Dependencies: keep pydantic, drop the other four.** (operator-confirmed,
  2026-09-03 grill Q4) sqlalchemy, alembic, psycopg
  (core), python-dotenv all die with Postgres. pydantic stays — it is `plan.py`'s
  `WorkItemDoc` only, and rewriting a 970-line validated parser is scope creep, not porting.
  The stdlib-only AST rule stays scoped to `eventlog/` — the property that matters is "an
  agent with no runtime can read the board", not "the CLI has zero deps".
- **d-p8 · Sessions are board events too.** (operator-confirmed, 2026-09-02 grill Q2)
  `session record` emits one `session.record` event (plus the existing meta.json sidecar);
  `session list` replays. One log, one lock — no second store.
- **d-p9 · Transcript paths are stored home-relative (`~/...`).** (operator-confirmed,
  2026-09-02 grill Q2) Transcripts live under
  `~/.claude/projects/...`, outside any repo, so repo-relative is impossible; home-relative
  survives a different username on the work PC. Every reader expanduser's. Lane B owns the
  helper; the exporter reuses it when migrating existing session rows.

- **d-p10 · Zero-loss migration gate: full parity check + quiesced cutover.** (operator,
  2026-09-02 grill Q1) Two halves, both blocking:
  - `pgexport --verify` re-reads every Postgres row and diffs it field-by-field against the
    replayed board — every entity, every field, both boards. Any diff → non-zero exit naming
    entity/id/field. Counts + spot-checks are demoted to progress output; **zero diffs is the
    cutover gate.** Verify applies the same transforms as export (UTC-second timestamps,
    `~`-relative transcript paths, M2M→array flattening), so a diff means real divergence.
  - **Quiesced cutover:** no agent sessions working <board-a>/<board-b> during lane Z's flip; export is
    re-run fresh immediately before the dotfiles-ai venv rebuild, then `--verify` runs
    *after* that final export. Closes the window where a Postgres write after export would
    exist only in the old world.

## Port requirements (drafted living spec)

No board in this repo, so these live here. Briefs lift them into `## Acceptance check`.

- **Parity** — Every taskman subcommand SHALL work with no database available.
  *Scenario:* `dbless parity` | GIVEN a repo with `.taskman.toml` and a `board/` | WHEN the
  converted pytest suite runs with no `TASKMAN_DATABASE_URL` and no Postgres | THEN all 17
  test files pass against tmp-board fixtures.
- **Version refusal** — Replay SHALL refuse an event it does not recognise rather than skip it.
  *Scenario:* `future event` | GIVEN a log containing `{"v": 2, ...}` or an unknown type |
  WHEN any command replays the board | THEN it exits non-zero naming the line, and no state
  is returned.
- **Id preservation** — Migration SHALL preserve every existing entity id.
  *Scenario:* `ids survive` | GIVEN the `<board-a>` Postgres board | WHEN the exporter runs and the
  new CLI replays | THEN every task/feature/pbi/requirement/decision/capture id present in
  Postgres exists with the same title, and the next allocated id is max+1.
- **Migration equivalence** — The migration SHALL prove full field-level parity, not sampled
  parity: `pgexport --verify` compares every row of every entity against the replayed board
  and exits non-zero on any difference (d-p10).
  *Scenario:* `zero-diff gate` | GIVEN a freshly exported board | WHEN `--verify` runs |
  THEN it reports per-entity totals and exits 0 only when no field of any row differs; a
  single mutated field makes it exit non-zero naming entity, id, and field.
  *Scenario:* `no stale cutover` | GIVEN export ran earlier in the session | WHEN the venv
  flip approaches | THEN export is re-run fresh and `--verify` passes after that final
  export, inside the quiesced window.
- **No absolute paths** — A committed board SHALL contain no machine-absolute path.
  *Scenario:* `portable board` | GIVEN a migrated + newly-written board | WHEN grepping
  `board/` for `/Users/` and `C:\\` | THEN zero matches.
- **Store purity** — The eventlog package SHALL import only the standard library (unchanged
  spike rule, enforced by the committed AST test).

## Not yet specified

*Sharpness test: can you state the question precisely now — **not** answer it now? Sharp → a `kind:decision` board row. Not sharp → a line here.*

- **Sharp, but unbookable — this repo has no board.** Recorded so they are not lost:
  - When (if ever) do the old `taskman_*` Postgres tables and databases get dropped, and who
    decides? (The port deliberately leaves them as archive — d-p3.)
- **Still fog.** Personal board vs squad board — inherited from the spike plan, still deferred
  behind distribution.
- **Still fog.** Whether dotfiles-ai's mirrored tree ever gets CI of its own, or stays covered
  by ai-wow's matrix plus the drift guards.

## Out of scope

*Scope, not sharpness. Never graduates — returns only if this plan's goal is redrawn, and then as a fresh stem.*

- **The single self-contained board page** — its own stem (`board-single-page`) per the origin
  brainstorm; orthogonal to storage.
- **Squad-shared Postgres (shape A) / board-less working (shape E)** — rejected in the origin
  brainstorm; unchanged.
- **`bin/ai-sync`'s 11 bare `read_text()` calls** — the highest-value follow-up named by the
  spike session report, but harness work, not taskman; separate run.
- **Mechanizing the drift guards' one-tree-only blind spot** — design work recorded in the
  spike session report's addendum; the cutover lane compensates by hand here.
- **Rewriting `plan.py` off pydantic** — refused at d-p7; returns only if a true zero-dep CLI
  becomes a goal of its own.

## Grill write-back

- **Q1 (2026-09-02): yes to both zero-loss hardening measures** → locked as d-p10 above.
  Patched: `dispatch/03-pg-exporter.md` (`--verify` mode: goal, context, acceptance, QA),
  `dispatch/05-cutover-and-amend.md` (quiesced window, fresh re-export before venv flip,
  zero-diff gate replaces counts+spot-checks as the blocking check), `dispatch/INDEX.md`
  (C and Z pointer cells).
- **Q2 (2026-09-02): yes to all three data-model reshapings** — d-p6 (Project/Tag entities
  die; orphaned tag names elided, accepted), d-p8 (sessions as board events), d-p9
  (home-relative transcript paths) — all marked operator-confirmed above. Patched:
  `dispatch/03-pg-exporter.md` (orphan-tag elision made an explicit export/verify rule).
  Briefs 01/02 already carried these as working decisions; no hedges to kill.
- **Q3 (2026-09-02): yes to both replay-edge policies** — d-p1 (fail-closed replay: an
  unrecognised or newer event stops every command loudly; the "update your tool" stop is
  accepted as the price of never rendering a silently-incomplete board) and d-p2 (no
  compaction, `# debt:` marker with ~50k events / ~5MB trigger). Both marked
  operator-confirmed above. Brief 01 already binding on both; no brief patch needed.
- **Q4 (2026-09-03): yes to the two-machine and dependency story** — d-p5 (build in ai-wow
  where the CI matrix proves Windows; dotfiles-ai untouched until lane Z's supervised flip)
  and d-p7 (deps 5→1: keep pydantic, psycopg demoted to the `pgexport` extra; the CLI still
  installs via one `uv sync`, the board itself needs no runtime to read). Both marked
  operator-confirmed above. Briefs 04/05 already binding; no brief patch needed.
- **Q5 (2026-09-03): yes to the migration mechanics** — d-p3 (one-way, raw SQL, Postgres
  kept forever as archive; decommission stays a parked separate decision) and d-p4 (every
  id preserved verbatim, per-entity `next_ids` seeded at max+1 — what keeps `blocked_by`
  edges, decision/capture links, and doc references valid). Both marked operator-confirmed
  above. Briefs 01/03/05 already binding; no brief patch needed. **Grill complete: all ten
  decisions (d-p1…d-p10) operator-confirmed.**
