# taskman

A per-project task board, **by agents, for agents**. Self-contained package —
not a separate product. The board is a **committed text file** in the project's
own git tree; there is no database, no server, and nothing to maintain
centrally.

## How it's wired

- **Identity:** `.taskman.toml` at the repo root names the project (`slug = "demo"`).
  If it's missing, taskman **stops** rather than guess — that's how projects
  never mix.
- **Storage:** `board/` next to `.taskman.toml` — an append-only event log
  (`board/events.jsonl`, one JSON event per line) plus per-entity id counters
  (`board/next_ids`). State is rebuilt by replay on every command; mutations
  serialize through an `O_EXCL` lockfile (`board/board.lock`), safe on Windows.
  Replay is **fail-closed**: an event this reader does not recognise (unknown
  entity/verb, missing or future `v`) stops the command loudly, naming the
  line — that refusal is the schema-drift guard.
- **Interface:** one CLI, run as a module or the `taskman` script. argparse +
  the stdlib-only `taskman.eventlog` store; pydantic only for the plan bridge's
  Work-Item documents. The `mow` gate scripts ship as separate console entry
  points (see [Gate scripts](#gate-scripts)).
- **Dependencies:** `pydantic` — that's all. `pip install "taskman[pgexport]"`
  adds psycopg for the one-way legacy-Postgres exporter (`pgexport`).

## Implemented

| Area | Commands / artifacts |
|---|---|
| Session cost metrics | `session record`, `session backfill`, `session list` — one `session.record` board event per transcript + `*.meta.json` sidecars |
| Hierarchy | Feature → PBI → Task; Decision; Capture |
| Living spec | Feature → Requirement (SHALL + GIVEN/WHEN/THEN scenarios); ADDED/MODIFIED/REMOVED |
| Board | Hierarchical (default) or `--flat` |
| Plan bridge | `plan from-decisions` / `plan to-dispatch` ⇄ `mow` (Work-Item JSON) |
| Recommend | `recommend next` — rule-based top-3 suggestions |
| Gate scripts | `mow-preflight` refuses fan-out; `mow-closeout` refuses the `shipped` flip (exit 3) |
| Capture hook | `scripts/archive-session.sh` + SessionEnd hooks → `project=<slug>/…` hive paths |
| End-of-chat | `/wrap-up` skill (home) — **evidence gate** (`taskman wrapup gate` / `scripts/wrapup_reconcile.py`) then report + board sync (incl. in-context capture of unbooked chat items). Session markers from Claude `SessionStart` / Cursor `sessionStart`. |

## Usage

```bash
# One-time per repo: create the board next to .taskman.toml
python -m taskman init

# Hierarchy
python -m taskman feature add "Onboarding" -t onboarding
python -m taskman pbi add "Sign-up API" --feature 1
python -m taskman pbi move 1 --status in_progress
python -m taskman task add "Wire email verification" --pbi 1 -t onboarding,api
python -m taskman task add "Overnight CI check" --lane platform --surface prod-internal --afk overnight --notes "check CI"
python -m taskman task show 1     # status, tags, toolkit, notes, brief ref
python -m taskman task move 1 --status in_progress
python -m taskman task link 2 --blocked-by 1
python -m taskman task claim 2 --agent lane-a   # atomic checkout lock (CAS)
python -m taskman task release 2
python -m taskman decision add "Use the event log, not markdown" --why "single source of truth"
python -m taskman capture add --kind grill --summary "Locked replay to fail closed"
python -m taskman capture link 370 --task 2142   # attach capture to a task
python -m taskman capture list --unlinked --kind plan
python -m taskman task add --from-capture 370    # promote plan capture → task + link

# Living spec (requirements + scenarios, scoped to a Feature)
python -m taskman requirement add "Session Timeout" --feature 1 \
  --statement "The system SHALL expire a session after 30 minutes of inactivity." \
  --scenario "Idle timeout|an authenticated session|30 minutes pass with no activity|the session is invalidated"
python -m taskman requirement list --feature 1
python -m taskman requirement modify 1 --statement "..." --pbi 3   # MODIFIED, in place
python -m taskman requirement remove 1                             # REMOVED (soft delete)
python -m taskman board
python -m taskman board --flat
python -m taskman board --status todo,in_progress

# Session metrics (after SessionEnd archive, or backfill existing jsonl)
python -m taskman session backfill
python -m taskman session list
python -m taskman session record --file path/to/archived.jsonl
```

Statuses: `backlog → todo → in_progress → blocked → done`, plus `disabled` — retired
until explicitly revisited. It sits off the main line on purpose: marking something
`done` that never happened is a lie the board carries forever.

`source_ref` format: `{relative_transcript_path}#L{line_number}`.

### The board is committed

`board/` travels in git like source. Two consequences:

- **No machine-absolute paths on the board.** Session transcript paths are
  stored home-relative (`~/...`, posix separators); every reader expands them.
- **Board and code share one tree**, so an older CLI meeting a newer board
  refuses at replay rather than silently dropping events.

Removal semantics: the log is append-only, so `pbi remove` and
`requirement remove` are soft deletes (a `deleted: true` / `status: removed`
field every reader filters) — history stays replayable.

### Captures ↔ tasks

Captures (`qa` / `grill` / `plan`) are session notes; optional `task_id` links them to board work.

- **Auto-link on add:** summary prefix `#123:` → task `#123` (QA verify records).
- **Manual:** `capture link <id> --task <task_id>`.
- **Promote:** `task add --from-capture <id>` copies summary/body into a new task and links the capture.
- **Read back:** `task show <id>` lists linked captures; `capture list --task <id>` or `--unlinked --kind plan`.

### Tags

Plain string arrays on every entity (Feature/PBI/Task/Decision/Capture) — the
old normalized tag tables died with the database.

### Toolkit recommendations

`.taskman.toml [toolkit]` maps a tag to recommended skills/agents, e.g.
`bug = ["skill:tdd", "skill:diagnose", "skill:parallel-debug"]`. `task show <id>`
prints a `toolkit:` line derived from the task's tags at render time — union
across tags, deduped, stable order; nothing is stored on the row. Tags of the
form `skill:<name>` / `agent:<name>` pass through verbatim as explicit
recommendations; unmapped tags (e.g. `docs`) contribute nothing and the line is
omitted. Display-only — taskman never auto-runs a skill.

### Requirement conventions (living spec)

A `Requirement` is capability-level truth for a Feature — separate from
`PBI.acceptance_criteria`, which scopes one unit of work. Write it like a
test someone could run, not a summary:

- **One `statement`, one keyword.** `SHALL`/`MUST` = non-negotiable, `SHOULD`
  = default-with-exception, `MAY` = optional. If a statement needs "and
  also," it's two requirements — add a second row.
- **At least one scenario**, as `name|given|when|then`. GIVEN sets up the
  case, WHEN is the trigger, THEN is the observable outcome. Cover the edge
  case you'd be upset to see broken, not just the happy path.
- **`add`** = a brand-new requirement (ADDED). **`modify`** = editing an
  existing one in place (MODIFIED) — pass `--pbi` to record which PBI's work
  changed it. **`remove`** = retiring one (REMOVED) — flips `status` to
  `removed` rather than deleting the row, so `requirement list --status
  removed` still shows what used to be true.
- `requirement list --feature <id>` **is** the current spec for that
  Feature — read it before writing a new requirement to avoid a duplicate.

## Migrating from the legacy Postgres board

`python -m taskman.pgexport` (needs the `pgexport` extra) reads a legacy
`taskman_*` schema over raw SQL and writes a complete `board/` with **every id
preserved**; `--verify` re-reads every row and diffs it field-by-field against
the replayed board — zero diffs is the cutover gate. One-way by design: the
old database stays untouched as its own archive.

## Gate scripts

The `mow` gates ship as console entry points rather than `taskman` subcommands. Each is
equally runnable as `python -m taskman.mow.<module>`, which is how the skills call them.

| Script | Refuses |
|---|---|
| `mow-preflight` | fan-out, when a run is not fit to start |
| `mow-closeout` | the `Status: shipped` flip — exit 3, writing nothing |
| `mow-check-ship-check` | — reports on the ship-check verdict alone |
| `mow-check-action-report` | — reports on the action report alone |
| `mow-check-tracker` | — reports on `tracker.json` alone |
| `mow-hydrate-specs`, `mow-plan-import`, `mow-check-grill-writeback`, `mow-set-registry-status` | plan/board plumbing for `/mow plan` and `/mow go` |
| `wrapup-reconcile` | the wrap-up evidence gate |

`mow-closeout` composes the three `check-*` scripts. Run it directly at any point:

```bash
python -m taskman.mow.closeout docs/plans/<stem>          # add --json for machine-readable
```

Exit 3 means the run is not finished: no ship-check verdict (or one stale against
`plan.md`), a missing, skeletal or unlinked action report, or a tracker still holding
running lanes and untriaged findings. Warnings print but never block.

> Harvest — the LLM transcript miner — was retired. Its job moved into `/wrap-up`, which
> books unlanded work from the live session while the chat is still in context. No API
> key or model configuration is needed anywhere in this package any more.

## End-of-chat ritual

Invoke **`/wrap-up`** (Claude Code skill at `~/.claude/skills/wrap-up/SKILL.md`).

It will:

1. Scan the chat for tasks / decisions / captures / status moves
2. Sync via `python -m taskman …` (never writes the log directly)
3. Write `docs/session-reports/<YYYY-MM-DD-HHMM>-<slug>.md`
4. Close an active checkpoint if one was picked up

If `.taskman.toml` is missing, it still writes a report when possible and skips
board sync.

## Dropping it into another project

1. `pip install` the package (or copy the `taskman/` folder).
2. Add `.taskman.toml` with that project's `slug`.
3. `python -m taskman init` — then commit `board/` with the repo.

Each copy is **independent on purpose**: one repo, one board, no shared state.

## Plan bridge

Shared Work-Item format (`taskman-plan.json`) closes the loop with the
`mow` skill.

```bash
# Pull a decomposed plan (.dispatch/ folder or taskman-plan.json) → Feature + Tasks
python -m taskman plan from-decisions docs/plans/<stem>/dispatch

# Push a board slice → runnable .dispatch/ folder
python -m taskman plan to-dispatch --feature <id> --dir /tmp/out
python -m taskman plan to-dispatch --status todo,in_progress --lane platform --dir /tmp/out
```

`from-decisions` is idempotent on `source_ref` (re-run updates title/brief/tags/deps in
place; **does not overwrite** board status — use `task move` / `/wrap-up`).
`to-dispatch` recomputes waves from `blocked_by` and enforces the dispatch hard rule
(same-wave lanes own disjoint file-sets). Role travels as a `role:` tag and in
the task's `brief` field.

## Deliberately deferred

- **Kanban web UI**
- **Cross-project `board --all-projects`** — one board per repo is the model now (d-p6)
- **Log compaction** — replay of thousands of events is milliseconds; revisit above ~50k events or ~5 MB
