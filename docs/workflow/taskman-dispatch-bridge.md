# TaskMan ⇄ mow — Shared Work-Item Format (Spec, Draft v0.1)

**Status:** design draft · **Date:** 2026-07-11 · **Owner:** maintainer
**Depends on:** taskman v1 (Feature→PBI→Task, Postgres) · `mow` skill
(`~/.agents/skills/mow/SKILL.md`; legacy aliases `dispatch-plan`, `maow`)

## 1. Why

Today the two halves of the planning loop don't share a data format:

- **`mow`** (Multi Agent Orchestration Workflow) turns a finished plan into markdown **briefs** under
  `docs/plans/<stem>/dispatch/` (an `INDEX.md` + one `NN-<todo>.md` per todo)
  and fans them out to subagents (`/mow plan` → `/mow go`). It is file-based and ephemeral.
- **taskman** stores a **Feature→PBI→Task** hierarchy in Postgres with statuses,
  dependencies, tags, priority, and `source_ref` provenance. It is durable and
  queryable.

A grilled plan that becomes mow briefs is never recorded as tracked work;
a taskman board slice can't be executed. This spec defines **one interchange
schema** so the loop closes both ways:

- **from-decisions (plan → taskman):** a planned mow run's todos become taskman rows.
- **to-dispatch (taskman → dispatch):** a board slice fans out as a `dispatch/` folder.

Round-tripping is lossless and idempotent (keyed on `source_ref`).

## 2. The canonical Work-Item document

A single JSON document is the contract. Both tools serialize to/from it; neither
reads the other's native storage directly. Call it `taskman-plan.json` (it can
also live as the frontmatter of a plan file).

```jsonc
{
  "plan": {
    "slug": "taskman-phases",              // stable key; → Feature dedup
    "title": "TaskMan Phases",             // → Feature.title
    "lane": "platform",                    // → Feature.lane   (product|platform|workforce)
    "surface": "prod-internal",            // → Feature.surface (end-user|prod-internal|workforce|"")
    "source_ref": ".cursor/plans/taskman-phases.plan.md"
  },
  "items": [
    {
      "id": "capture-global",              // dispatch todo-id — stable within plan
      "title": "Globalize session capture",// → Task.title
      "priority": "high",                  // → Task.priority (keystone|high|med|low)
      "status": "backlog",                 // → Task.status
      "tags": ["devops", "role:shell"],    // → Task.tags[]  (type tags + role: tag)
      "depends_on": [],                     // → Task.blocked_by (resolved by item id)
      "source_ref": ".cursor/plans/taskman-phases.dispatch/01-capture-global.md",
      "dispatch": {                         // dispatch-only fields (→ Task.brief JSONB)
        "role": "shell",                   // code-edit|shell|explore|ui-design|security-review|…
        "wave": 0,
        "background": false,                // false ⇒ needs-review gate
        "files": ["scripts/archive-session.sh", ".cursor/hooks.json"],
        "acceptance": "archive writes project=<slug>/ path; pytest tests/",
        "do_not": ["do not background — touches global config"],
        "context": ["identity via .taskman.toml; stop if missing"]
      }
    }
  ]
}
```

### Design choices

- **plan = Feature, todo = Task.** A dispatch plan is one Feature; each brief is
  one Task. Waves are *not* stored as a separate entity — they are **recomputed**
  from `depends_on` (topological levels). `dispatch.wave` is kept only as an
  advisory hint / tie-break.
- **PBI is optional.** For a flat plan, todos hang directly off the Feature
  (Task.pbi_id may be null, already supported). A plan that groups todos into
  named workstreams maps each workstream to a PBI; `acceptance` then lands in
  `PBI.acceptance_criteria`.
- **Role travels as a `role:` tag** *and* in `dispatch.role`. The tag keeps the
  board filterable (`board --tag role:shell`) without reading JSONB; the JSONB
  keeps export lossless.
- **Dependencies are the source of truth for ordering.** `blocked_by` in taskman
  ⇄ `depends_on` in the plan ⇄ wave structure in dispatch. One graph, three views.

## 3. Field mapping

| Work-Item field | taskman | dispatch brief / INDEX |
|---|---|---|
| `plan.title` | `Feature.title` | INDEX H1 / plan name |
| `plan.lane` | `Feature.lane` | (new: surfaced in INDEX header) |
| `plan.surface` | `Feature.surface` | (new: surfaced in INDEX header) |
| `plan.source_ref` | `Feature` provenance* | `Source plan:` line |
| `item.id` | — (matched via `source_ref`) | brief filename stem / todo-id |
| `item.title` | `Task.title` | brief H1 goal |
| `item.priority` | `Task.priority` | (advisory; ordering is by wave) |
| `item.status` | `Task.status` | done-gate in INDEX status column |
| `item.tags` | `Task.tags[]` | Role + type, `## Do NOT` hints |
| `item.depends_on` | `Task.blocked_by` | `## Depends on` + wave grouping |
| `item.source_ref` | `Task.source_ref` | brief file path |
| `dispatch.role` | `role:` tag + `brief.role` | INDEX Lane "Role" column |
| `dispatch.wave` | recomputed (hint in `brief`) | INDEX "Wave" |
| `dispatch.background` | `brief.background` | INDEX "Background"; false ⇒ needs-review |
| `dispatch.files` | `brief.files` | `## Files in scope` + Conflicts check |
| `dispatch.acceptance` | `PBI.acceptance_criteria` or `brief.acceptance` | `## Acceptance check` |
| `dispatch.do_not` | `brief.do_not` | `## Do NOT` |
| `dispatch.context` | `brief.context` | `## Context & decisions` |

\* Feature has no `source_ref` column today — carry plan provenance in a Decision
row (`decision add "<plan> planned" --source <plan.md>`) or add the column in
Phase 2 (see §7).

## 4. Direction A — from-decisions (plan → taskman rows)

`taskman plan from-decisions <dispatch-dir | taskman-plan.json>`

1. Resolve the Work-Item doc: if given a `.dispatch/` folder, parse `INDEX.md`
   (lanes/waves/files) + each `NN-*.md` brief into items; if given JSON, use it
   directly.
2. Upsert the **Feature** by `plan.slug` (idempotent).
3. For each item, upsert a **Task** keyed on `source_ref` (never duplicate — same
   dedup rule as `harvest`). Set title/priority/status/tags; write `dispatch.*`
   into `Task.brief` (JSONB, Phase 2) or fold `role:`/`wave:` into tags (Phase 1).
4. Second pass: resolve `depends_on` (item ids) → `Task.blocked_by` links now that
   all tasks have real ids.
5. Print a summary board slice.

**Idempotency:** re-importing an edited plan updates existing rows in place and
adds only new items. Matches `harvest`'s `source_ref`-keyed dedup.

## 5. Direction B — to-dispatch (taskman board slice → dispatch)

`taskman plan to-dispatch <feature-id | --selector> --dir <dir>`

Selector examples: `--feature 14`, `--status todo,in_progress`, `--lane platform`,
`--tag role:code-edit`.

1. Collect the Task set + their `blocked_by` graph.
2. **Recompute waves** by topological level: tasks whose blockers are all `done`
   or outside the set → wave 1; their dependents → wave 2; etc.
3. **Enforce the dispatch hard rule:** within a wave, every lane must own a
   **disjoint file-set** (`dispatch.files`). If two same-wave tasks share a file,
   serialize them into one sequential lane (or mark `needs-review`). This is the
   one invariant export must never violate — it's why `files` is a first-class
   field.
4. Assign background/foreground from `dispatch.background` (default: foreground /
   `needs-review` for `role:shell` and anything touching home/global paths).
5. Emit `<dir>/INDEX.md` + `NN-<item.id>.md` briefs using the exact templates in
   the `mow` SKILL (§"Write the dispatch folder"). Write `source_ref`
   back into each brief so a later re-import round-trips to the same rows.
6. Hand off: `/mow go` runs the emitted folder unchanged.

## 6. Where each piece of logic lives

- **Serialization + import/export CLI:** taskman (`taskman/plan.py`, new
  `plan from-decisions|to-dispatch` subcommands). taskman owns the durable format.
- **Brief/INDEX rendering + runtime fan-out:** stays in the `mow`
  skill. The skill gains a note: "if a `taskman-plan.json` or `taskman plan
  export` is available, prefer it as the brief source." Roles stay semantic
  (never hardcode a runtime's `subagent_type`) — unchanged from today.
- **No new coupling of storage:** dispatch never touches Postgres; taskman never
  spawns agents. The JSON doc is the only shared surface.

## 7. Schema deltas (Phase 2, small)

- `Task.brief JSONB NULL` — round-trips `role/wave/background/files/acceptance/
  do_not/context` losslessly. Until then, Phase 1 stores `role:` + `wave:N` as
  tags (lossy on files/acceptance) and keeps acceptance in `PBI.acceptance_criteria`.
- (Optional) `Feature.source_ref VARCHAR NULL` — plan provenance without abusing
  the Decision log.

Both are additive, mirror the `0003_strategic_lens` migration style, and are
**not** required for a Phase-1 tags-only prototype.

## 8. Phasing

1. **Phase 1 (prototype):** define `taskman-plan.json`; implement
   `taskman plan from-decisions` from an existing `.dispatch/` folder into Feature+Tasks
   using tags for role/wave; resolve deps. Prove the round-trip on
   `taskman-phases.dispatch`.
2. **Phase 2:** add `Task.brief` JSONB; implement `taskman plan to-dispatch` with wave
   recomputation + the disjoint-file-set guard; teach `mow` to prefer a
   taskman export as its brief source.
3. **Phase 3:** harvest → plan → dispatch as one flow (a grilled plan is captured,
   imported, executed, and its task statuses close automatically on wrap-up).

## 9. Open questions

- **Wave as PBI?** Flat (todo→Task under Feature) is simplest and matches the
  current `.dispatch` INDEX. Revisit if plans routinely need a named middle tier.
- **Feature provenance:** dedicated `Feature.source_ref` column vs. a Decision row.
- **Status back-propagation on export:** should export mark exported tasks
  `in_progress`, or leave status untouched until `/wrap-up` reconciles? (Lean:
  leave untouched; wrap-up owns status moves.)
- **Cross-repo plans:** taskman is per-project (`.taskman.toml`); a plan spanning
  repos would need one Feature per project. Out of scope for v1.
```
