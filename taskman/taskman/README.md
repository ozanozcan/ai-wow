# taskman

A per-project task board, **by agents, for agents**. Self-contained plugin
folder — not a separate product. It lives inside the project (`demo/taskman`),
uses the project's **own Postgres**, and adds nothing to maintain centrally.

Full design rationale: the project's own design notes (Scope note v0.3).

## How it's wired

- **Identity:** `.taskman.toml` at the repo root names the project (`slug = "demo"`).
  If it's missing, taskman **stops** rather than guess — that's how projects
  never mix.
- **Storage:** reuses this repo's Postgres. Prefer `TASKMAN_DATABASE_URL` (sync
  `postgresql+psycopg://…`); otherwise if `DATABASE_URL` is asyncpg it is rewritten
  to psycopg (same credentials/host/db); else `DATABASE_URL` as-is; else the demo
  docker-compose default. Tables are prefixed `taskman_`, isolated from app tables.
  Schema evolves via Alembic (`python -m taskman init-db` → `alembic upgrade head`).
- **Interface:** one CLI, run as a module — argparse + SQLAlchemy/psycopg, no runtime
  dependency beyond those. The `mow` gate scripts ship as separate console entry points
  (see [Gate scripts](#gate-scripts)).

## Implemented

| Area | Commands / artifacts |
|---|---|
| Session cost metrics | `session record`, `session backfill`, `session list` + `*.meta.json` sidecars |
| Hierarchy | Feature → PBI → Task; Decision; Capture |
| Living spec | Feature → Requirement (SHALL + GIVEN/WHEN/THEN scenarios); ADDED/MODIFIED/REMOVED |
| Board | Hierarchical (default) or `--flat` |
| Plan bridge | `plan from-decisions` / `plan to-dispatch` ⇄ `mow` (Work-Item JSON) |
| Gate scripts | `mow-preflight` refuses fan-out; `mow-closeout` refuses the `shipped` flip (exit 3) |
| Capture hook | `scripts/archive-session.sh` + SessionEnd hooks → `project=<slug>/…` hive paths |
| End-of-chat | `/wrap-up` skill (home) — **evidence gate** (`taskman wrapup gate` / `scripts/wrapup_reconcile.py`) then report + board sync (incl. in-context capture of unbooked chat items). Session markers from Claude `SessionStart` / Cursor `sessionStart`. |

## Usage

```bash
# DB must be up:  docker compose up -d db
.venv/bin/python -m taskman init-db

# Hierarchy
.venv/bin/python -m taskman feature add "Onboarding" -t onboarding
.venv/bin/python -m taskman pbi add "Sign-up API" --feature 1
.venv/bin/python -m taskman pbi move 1 --status in_progress
.venv/bin/python -m taskman task add "Wire email verification" --pbi 1 -t onboarding,api
.venv/bin/python -m taskman task add "Overnight CI check" --lane platform --surface prod-internal --afk overnight --notes "check CI"
.venv/bin/python -m taskman task show 1     # status, tags, toolkit, notes, brief ref
.venv/bin/python -m taskman task move 1 --status in_progress
.venv/bin/python -m taskman task link 2 --blocked-by 1
.venv/bin/python -m taskman decision add "Use Postgres not markdown" --why "single source of truth"
.venv/bin/python -m taskman capture add --kind grill --summary "Locked Alembic for taskman_*"
.venv/bin/python -m taskman capture link 370 --task 2142   # attach capture to a task
.venv/bin/python -m taskman capture list --unlinked --kind plan
.venv/bin/python -m taskman task add --from-capture 370    # promote plan capture → task + link

# Living spec (requirements + scenarios, scoped to a Feature)
.venv/bin/python -m taskman requirement add "Session Timeout" --feature 1 \
  --statement "The system SHALL expire a session after 30 minutes of inactivity." \
  --scenario "Idle timeout|an authenticated session|30 minutes pass with no activity|the session is invalidated"
.venv/bin/python -m taskman requirement list --feature 1
.venv/bin/python -m taskman requirement modify 1 --statement "..." --pbi 3   # MODIFIED, in place
.venv/bin/python -m taskman requirement remove 1                             # REMOVED (soft delete)
.venv/bin/python -m taskman board
.venv/bin/python -m taskman board --flat
.venv/bin/python -m taskman board --status todo,in_progress

# Session metrics (after SessionEnd archive, or backfill existing jsonl)
.venv/bin/python -m taskman session backfill
.venv/bin/python -m taskman session list
.venv/bin/python -m taskman session record --file path/to/archived.jsonl
```

Statuses: `backlog → todo → in_progress → blocked → done`, plus `disabled` — retired
until explicitly revisited. It sits off the main line on purpose: marking something
`done` that never happened is a lie the board carries forever.

`source_ref` format: `{relative_transcript_path}#L{line_number}`.

### Captures ↔ tasks

Captures (`qa` / `grill` / `plan`) are session notes; optional `task_id` links them to board work.

- **Auto-link on add:** summary prefix `#123:` → task `#123` (QA verify records).
- **Manual:** `capture link <id> --task <task_id>`.
- **Promote:** `task add --from-capture <id>` copies summary/body into a new task and links the capture.
- **Read back:** `task show <id>` lists linked captures; `capture list --task <id>` or `--unlinked --kind plan`.

### Tags

- **Task:** Postgres `ARRAY` on the row (v1 compat).
- **Feature / PBI:** normalized `taskman_tag` + M2M join tables.

### Toolkit recommendations

`.taskman.toml [toolkit]` maps a tag to recommended skills/agents, e.g.
`bug = ["skill:tdd", "skill:diagnose", "skill:parallel-debug"]`. `task show <id>`
prints a `toolkit:` line derived from the task's tags at render time — union
across tags, deduped, stable order; nothing is stored on the row. Tags of the
form `skill:<name>` / `agent:<name>` pass through verbatim as explicit
recommendations; unmapped tags (e.g. `docs`) contribute nothing and the line is
omitted. Human-readable source of truth: the **Toolkit** column in
[`docs/agents/protocols.md`](../docs/agents/protocols.md) (P1). Display-only —
taskman never auto-runs a skill.

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

## Session archive

See [`docs/infra/taskman-capture.md`](../docs/infra/taskman-capture.md).

Hive path:

```
docs/chat-history/agent-sessions/project=<slug>/source={claude|cursor}/year=…/month=…/day=…/<ts>-<session>.jsonl
```

Global Claude/Cursor SessionEnd hooks call thin wrappers that exec this repo's
`scripts/archive-session.sh` when `.taskman.toml` is present. Fail-open always.

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
2. Sync via `python -m taskman …` (never writes Postgres directly)
3. Write `docs/session-reports/<YYYY-MM-DD-HHMM>-<slug>.md`
4. Close an active checkpoint if one was picked up

If `.taskman.toml` is missing, it still writes a report when possible and skips
board sync.

## Dropping it into another project

1. Copy the `taskman/` folder and `scripts/archive-session.sh`.
2. Add `.taskman.toml` with that project's `slug`.
3. Commit or reuse SessionEnd hooks (see `docs/infra/taskman-capture.md`).
4. If the project's DB isn't the demo default, set `TASKMAN_DATABASE_URL`
   (preferred) or sync-compatible `DATABASE_URL`.
5. `python -m taskman init-db`.

Each copy is **independent on purpose** — except when copies share one physical
Postgres (demo + web-app deliberately do). Then the `taskman_*` schema is shared state:

> **Migration rule:** any new Alembic revision must land in **every** repo's
> `taskman/alembic/versions/` (copy the file to all embedded taskman copies in
> the same change). A migration applied from one repo but missing in another
> leaves that other copy unable to resolve the DB's head — `alembic upgrade head`
> and the test fixtures fail with "Can't locate revision". This bit for real with
> `0006_task_lens` (2026-07-11).

## Plan bridge

**Operator guide (when to invoke what):** [`docs/workflow/work-loop.md`](../docs/workflow/work-loop.md).

Shared Work-Item format (`taskman-plan.json`) closes the loop with the
`mow` skill. Spec: [`docs/workflow/taskman-dispatch-bridge.md`](../docs/workflow/taskman-dispatch-bridge.md).

```bash
# Pull a decomposed plan (.dispatch/ folder or taskman-plan.json) → Feature + Tasks
.venv/bin/python -m taskman plan from-decisions .cursor/plans/<stem>.dispatch
# (or an archived copy under docs/plans/<stem>/dispatch/)

# Push a board slice → runnable .dispatch/ folder
.venv/bin/python -m taskman plan to-dispatch --feature <id> --dir /tmp/out
.venv/bin/python -m taskman plan to-dispatch --status todo,in_progress --lane platform --dir /tmp/out
```

`from-decisions` is idempotent on `source_ref` (re-run updates title/brief/tags/deps in
place; **does not overwrite** board status — use `task move` / `/wrap-up`).
`to-dispatch` recomputes waves from `blocked_by` and enforces the dispatch hard rule
(same-wave lanes own disjoint file-sets). Role travels as a `role:` tag and in
`Task.brief` JSONB.

## Deliberately deferred

- **Recommender / planner** — "what to work on next" (spec Phase 2).
- **Kanban web UI**
- **Cross-project `board --all-projects`**
- **Phase 3 bridge** — wrap-up capture → plan → dispatch as one flow; status-close on wrap-up
  (see spec §8; still design-only).
