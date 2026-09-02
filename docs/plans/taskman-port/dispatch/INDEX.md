# Dispatch index — taskman-port (land the dbless board)

Source plan: docs/plans/taskman-port/plan.md

## What we'll do

1. Grow the event-log store from one entity to the full board — versioned envelope,
   fail-closed replay, per-entity id counters, public `transaction()` seam, stale-debris
   sweep (lane A).
2. Relativize transcript paths so a committed board carries nothing machine-absolute (lane B).
3. Build the one-way raw-SQL Postgres exporter that turns a live board into an event
   stream with every id preserved (lane C).
4. Rewire all 42 CLI subcommands and the wrapup gate onto the store; delete `db.py`,
   `models.py`, and the alembic tree; convert the 17-file pytest suite to tmp-board
   fixtures and add it to the CI matrix (lane D).
5. Cut over: migrate project-a + project-b for real, mirror `taskman/` into dotfiles-ai in lockstep,
   rebuild its venv, amend I10 / README Requirements / the work-PC artifact (lane Z,
   foreground).

## What you'll have at the end

| Area | End state |
|---|---|
| The CLI | Every subcommand works against `board/` with no database process anywhere |
| Live boards | project-a and project-b each hold a committed `board/`, ids preserved, `taskman board` renders them from each repo |
| Dependencies | Core deps: pydantic only; psycopg demoted to the `pgexport` optional extra |
| Windows | Converted pytest suite runs in the CI matrix on both runners; eventlog plain-script suites unchanged |
| The mirror | dotfiles-ai byte-identical on match paths, drift guards green, venv rebuilt, PATH command live |
| Guarantees | I10, README Requirements, work-PC artifact amended; L05 grep sweep clean |

**In one line:** The board taskman serves is a text file in git — on both machines, for
both live projects, with the old guarantees rewritten instead of quietly falsified.

## Waves

- **Wave 1 (parallel, AFK):** A ‖ B
- **Wave 2 (after wave 1, parallel, AFK):** C ‖ D
- **Wave 3 (after wave 2, foreground):** Z

Each wave ends with a **review gate** (see mow go mode) before the next starts. No stack
reviewer in the roster covers plain-Python stdlib work (spike precedent) — gates run the
built-in `/code-review` on the combined wave diff plus orchestrator verification; wave 2's
gate should also re-run the eventlog concurrency suite against D's merged tree.

## Lanes

| Lane | Todos (in order) | PBI / Feature | Files owned | Role | Model | Review flags | AFK | Background | Decisions / Specs | Brief |
|---|---|---|---|---|---|---|---|---|---|---|
| A | store-entities | - | `taskman/taskman/eventlog/log.py`, `taskman/taskman/eventlog/store.py`, `taskman/taskman/eventlog/locking.py`, `taskman/taskman/eventlog/schema.py`, `taskman/taskman/eventlog/__init__.py`, `taskman/taskman/eventlog/tests/` | code-edit | inherit | code-review | yes | yes | - | 01-store-entities.md |
| B | relativize-transcript-paths | - | `taskman/taskman/metrics.py`, `taskman/tests/test_metrics_paths.py` | code-edit | inherit | code-review | yes | yes | - | 02-relativize-transcript-paths.md |
| C | pg-exporter | - | `taskman/taskman/pgexport.py`, `taskman/tests/test_pgexport.py` | code-edit | inherit | code-review | yes | yes | - | 03-pg-exporter.md |
| D | cli-wiring | - | `taskman/taskman/cli.py`, `taskman/taskman/wrapup.py`, `taskman/taskman/config.py`, `taskman/taskman/plan.py`, `taskman/taskman/matching.py`, `taskman/taskman/db.py`, `taskman/taskman/models.py`, `taskman/taskman/alembic.ini`, `taskman/taskman/alembic/`, `taskman/taskman/README.md`, `taskman/conftest.py`, `taskman/tests/**`, `taskman/pyproject.toml`, `.github/workflows/ci.yml` | code-edit | fable | code-review | yes | yes | - | 04-cli-wiring.md |
| Z | cutover-and-amend | - | `~/Desktop/dev/board/`, `~/Desktop/project-b/board/`, `~/Desktop/dotfiles-ai/taskman/**`, `~/Desktop/dotfiles-ai/bin/tests/tree-drift.json`, `HOW-TO-USE.agent.md`, `README.md`, `artifact:ai-wow-on-the-work-pc`, `docs/plans/taskman-port/` | shell | inherit (foreground) | - | no | no | - | 05-cutover-and-amend.md |

`Decisions / Specs`: this repo is deliberately board-less (no `.taskman.toml`), so no
`d#`/`req#` ids exist; the binding decisions are the d-p1…d-p9 entries in `plan.md`
§Decisions locked, and each brief restates the ones it depends on in full. Hydrated specs:
n/a — every pointer cell is `-`.

**Hydrated specs:** n/a (all Decisions / Specs cells `-`; nothing to materialize)

**Grill checkpoint:** done 2026-09-03
**Grill write-back:** plan.md ✓ (d-p1…d-p9 operator-confirmed Q1–Q5; d-p10 zero-loss gate added at Q1; per-question log in `## Grill write-back`) · briefs: 03-pg-exporter.md (`--verify`, orphan-tag rule), 05-cutover-and-amend.md (quiesced cutover, zero-diff gate) — 01/02/04 held as written · taskman: n/a (repo is board-less)

## Conflicts check

No two same-wave lanes share a file:
- Wave 1: A owns `eventlog/**`; B owns `metrics.py` + one new test file — disjoint.
- Wave 2: C owns `pgexport.py` + `tests/test_pgexport.py`; D owns everything else it
  lists and is explicitly barred from C's two files and from `eventlog/**` — disjoint.
  Seam risk named: D deletes `models.py` while C reads the same tables via raw SQL —
  by design (d-p3), no shared file.
- `taskman/tests/__init__.py` already exists; no lane recreates it.
- Cross-plan: registry has no other `planned`/`running`/`paused` stem (all shipped) — no
  cross-plan overlap possible at write time.
