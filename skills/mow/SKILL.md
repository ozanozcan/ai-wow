---
name: mow
description: Multi Agent Orchestration Workflow — plan/list/ready/go modes turn docs/plans into per-todo briefs, wave map, and subagent fan-out. Triggers /mow, /mow plan|list|ready|go, legacy /dispatch-plan and /maow.
---

# MOW — Multi Agent Orchestration Workflow

One skill, four modes, for the moment a `grill-with-docs` + plan-mode session ends with N todos and you don't want to (a) keep building in a heavy chat, or (b) start todos in fresh chats blindly and lose decisions.

| Invocation | Mode | When |
|---|---|---|
| `/mow` or `/mow plan` | **plan** (default) | Run **in the originating chat**, while the decisions are still live. Cheap on context. Writes briefs + index to disk, then **prints the operator summary** (what we'll do / what you'll have) **and** the orchestration map (waves, lanes, AFK, roles). |
| `/mow list` | **list** | Registry + **operator summary** + **full orchestration map** (waves + lanes) for every non-`shipped` run + parallel-safe matrix. Never one-line teasers only. Read-only. |
| `/mow ready` / `/mow ready <stem>` | **ready** | Pre-go preview + **grill-with-docs checkpoint** (catch ambiguities before fan-out). Prints operator summary + orchestration map, then stress-tests the plan one question at a time unless skipped. |
| `/mow go` | **go** | Run from **any** chat. Reads the index, fires subagents / emits paste-ready prompts. Restates the orchestration map before fan-out; **ends with P3 + ship-check gate + human-readable done summary**. |

**Parse the user's message** (first matching wins):
1. contains `go` or legacy `dispatch` → **go**
2. contains `ready` → **ready**
3. contains `list` → **list**
4. otherwise (`plan`, bare `/mow`, bare `/maow`, legacy `decompose`) → **plan**

Legacy `/maow` invocations use the same mode mapping as `/mow`.

**Core idea:** the plan file already persists the high-level decisions. The gap is (1) per-todo briefs carrying only the context each todo needs, (2) a grouping/order map, (3) the actual async fan-out. **plan** closes 1+2 on disk; **list** surveys every active run with full maps; **ready** zooms one stem + grills; **go** executes anywhere.

### Automation hooks (mid-wave — not advisory)

These are **mandatory** when the repo has the named skill/agent. Skip only with an explicit operator "skip X" or a written n/a justification in the Verification / action report. If the repo has `docs/agents/protocols.md`, that file's P0/P3/P4 tables refine triggers (FTM names concrete modules).

| When | Auto-invoke | Owner |
|---|---|---|
| **ready** (before offering go) | `grill-with-docs` against `plan.md` + briefs — one Q at a time; **write-back each answer to plan.md + affected briefs before the next Q**; update INDEX/brief **Decisions / Specs** pointers; mark `done` only after write-back verification gate; refresh `hydrated-specs.md` | orchestrator (interactive) |
| **go** before wave 1 | `python scripts/mow_preflight.py docs/plans/<stem>` — grill → hydrate (when pointers exist) → thin-brief → overlap; **subsumes** the former standalone hydrate gate | orchestrator |
| **go** lane start (`tdd-builder` / code-edit) | `tdd` skill **before** production code (explicit; already in tdd-builder); **Read** lane section of `hydrated-specs.md` | lane |
| **go** lane mid-build | `parallel-debug` when pytest shows **>1 unrelated** failures | lane |
| **go** lane mid-build (UI) | Project **`ui-designer`** (repo stack — FTM: Django templates + Tailwind + htmx; **never** the global Next.js/shadcn agent) · **`impeccable`** when the work is visual (redesign/polish/new screen), not for mechanical markup-only swaps | lane |
| **go** lane Verification (UI) | **`imprint`** after any UI/template change (always after impeccable) → `ui-registry.md` | lane |
| **go** lane Verification (new/changed logic) | `test-coverage` on modified modules | lane (thin → expand) |
| **go** lane Verification (pure math / domain logic) | `adversarial-tester` on named modules | lane when scope matches; else P3 batch |
| **go** §1 + every run event | **live tracker** — copy `tracker.html`, maintain `dispatch/tracker.json` per the write-points table in [`TRACKER.md`](TRACKER.md) (same folder as this skill) | orchestrator |
| **go** Integrate (after final wave) | P3 post-build (`/verify`, `test-coverage`, adversarial batch) then **`ship-check` as auto-gate** before `Status: shipped` | orchestrator |
| **go** Integrate (architecture-heavy / Wave 2+) | `improve-codebase-architecture` quick scan — **deferred by default** unless plan tags `refactor` or operator asks | orchestrator (optional) |

Pass each brief's `## Toolkit` into the lane prompt so tdd-builder reaches for these mid-build rather than only mentioning them afterward.

**Portable paths (Cursor + Claude Code):** canonical home is `docs/plans/<stem>/` in the repo. `.cursor/plans/` is only a Cursor Plan-mode scratch location — never the durable source of truth.

**Folder name:** briefs still live under `docs/plans/<stem>/dispatch/` (on-disk path kept for taskman bridge compatibility). Mentally: dispatch folder = mow run package.

---

## MOW registry (parallel plans guardrail)

Multiple mow runs can coexist on one repo (separate tasks, separate chats). Like **`docs/checkpoints/INDEX.md`** for checkpoints, the registry is the operator's at-a-glance view and the guardrail against silent wrong-plan execution.

**Canonical store:** `docs/plans/INDEX.md` at the repo root (sibling to `docs/plans/<stem>/` folders).

```markdown
# MOW runs

| Stem | Title | Feature | Created | Updated | Status |
|---|---|---|---|---|---|
| play-model | Play Model Wave 2 | #18 | 2026-07-13 | 2026-07-13 | shipped |
| tooling-eval-followups | Tooling eval follow-ups | - | 2026-07-15 | 2026-07-15 | planned |
```

**Status lifecycle:** **`planned`** (dispatch written, not executing) → **`running`** (go started — at least wave 1 fan-out) → **`shipped`** (action report written, all waves done). Optional **`paused`** when the operator explicitly shelves a run without shipping — treat like `planned` for overlap checks.

**Rules (mirror checkpoint discipline):**
- **plan** adds or updates one row — never overwrites another stem's dispatch folder or registry row.
- **go** never silently pick a plan when more than one row is `planned`, `running`, or `paused`. Show full maps (list logic) and ask (or honor an explicit stem the user named, e.g. `/mow go tooling-eval-followups`). **`/mow list`** / **`/mow ready <stem>`** are the operator's pick-and-preview steps.
- **Parallel go is allowed** when cross-plan file sets are disjoint — two `/mow go` sessions in separate chats may both be `running` if (and only if) the overlap check passes against every other `running` stem. File overlap is the hard gate, not a global one-at-a-time lock.
- **Cross-plan file overlap:** before **plan** writes dispatch (step 6) and before **go** starts fan-out, union every `Files owned` cell from all other `planned`|`running`|`paused` dispatches. Overlap = same path, or one path is a prefix of the other (file vs owning directory). If any overlap with the target plan, **stop** — list conflicting stems/paths and ask the user to narrow scope, ship one plan first, or run sequentially. Same-wave disjointness inside one plan is not enough when two plans both touch `taskman/models.py`.
- **Parallel go soft warnings** (print, do not block unless the user opts out): both stems touch the same migration tree (`alembic/`, `taskman/alembic/`); both lanes run repo-wide test suites; either stem has AFK-no / destructive / out-of-repo lanes — parallel is still OK on disjoint files, but the operator should use separate chats and expect shared git noise.
- Create `docs/plans/INDEX.md` on first **plan** if missing. **list** / **ready** are read-only — never one-line wave teasers; always print the full **Orchestration map** (waves + lanes) for every stem they expand.

**Stem resolution (go / ready):** (1) explicit stem in the user's message wins; (2) else if exactly one `planned`|`running`|`paused` row exists, use it; (3) else run **`/mow list`** output (full maps for all active stems) and ask — **do not** fall back to "most recently modified dispatch folder".

---

## Operator summary (required for plan, list, ready; past-tense after go)

Human-readable preview of the run — **not** a restatement of todo titles. Print it **before** the Orchestration map on **plan** / **list** / **ready**. Persist it on disk under `docs/plans/<stem>/plan.md` (and mirror under `dispatch/INDEX.md`) so later **ready** / **go** chats can reuse it without the origin grill.

```markdown
### What we'll do
1. <concrete change #1 — verb + object + why it matters>
2. <…>
3. <…>

### What you'll have at the end
| Area | End state |
|---|---|
| <surface / API / test / board> | <observable done-state in plain language> |
| … | … |

**In one line:** <one sentence a non-agent operator can repeat>
```

**Rules:**
- Prefer numbered steps over task-id laundry lists; mention board ids only as secondary tags (e.g. after the step).
- End-state table must name **observables** (behavior, tests, board status) — not "code merged" or "tests pass".
- If you cannot fill both sections from plan + harvest, you do not have enough — ask before writing dispatch.
- **go** uses the same shape in **past tense** after Integrate (see go §4): `### What we did` / `### What you have now` / `**In one line:**`.

---

## Orchestration map (required output for plan, list, ready; restated at go fan-out)

Whenever **plan** finishes writing, print the **Operator summary** then this map (do not skip either). **list** prints both once per active stem. **ready** prints both for the resolved stem. **go** restates a short version (waves + AFK) immediately before fan-out — full map lives in `docs/plans/<stem>/dispatch/INDEX.md`.

```markdown
## Orchestration map — <plan name>

Source: docs/plans/<stem>/dispatch/INDEX.md

### Waves
| Wave | Parallelism | Lanes | AFK | Gate |
|---|---|---|---|---|
| 1 | parallel | A ‖ B ‖ C(seq: a→b) | yes | review after |
| 2 | after wave 1 | Z | no | foreground / needs-review |

### Lanes
| Lane | Todos (order) | PBI / Feature | Role | AFK | Review flags | Decisions / Specs | Brief |
|---|---|---|---|---|---|---|---|
| A | … | #52 / #65 | code-edit | yes | django | d `#12` · req `#3` | 01-….md |
| Z | … | #55 / #65 | code-edit | no | - | `-` | 0N-….md |

### How to run
- **AFK yes** → safe to background under `/mow go`
- **AFK no** → foreground / with-user (`needs-review`, destructive, out-of-repo, or shell-in-home)
- Next: `/mow list` (all active maps) · `/mow ready <stem>` (one map) · `/mow go <stem>` to fan out
```

**AFK** = Background yes in INDEX/briefs. Derive it; do not invent a third source of truth.

**PBI / Feature** = per-todo PBI id / Feature id (e.g. `#52 / #65`), so a glance at the lane table shows which requirement each task serves — not just the stem-level `Feature` column in `docs/plans/INDEX.md`. Pull from the todo's taskman `Task.pbi_id`/`feature_id` when known, or the plan's per-todo tags; `-` if the plan doesn't track PBIs.

**Decisions / Specs** = **pointers only** for ids that change this lane’s Do / Don’t / Acceptance (not every related decision ever). Prefixes: `d` = decision, `req` = requirement, `task` = parked follow-up board id, `cap` = capture **only** when that capture is the design artifact (`--kind decide` / grill write-up) — prefer `d`/`req` over captures. INDEX never pastes decision prose. Materialize with `python scripts/mow_hydrate_specs.py docs/plans/<stem>` → `dispatch/hydrated-specs.md` (subagents **Read** that file). Use `-` when none apply.

---

## Mode: plan (default)

Run this in the chat where the plan was created — it is the only place that holds in-chat decisions not yet written to the plan file.

**Before you start — right-size check:** state the plan's intent in one sentence. If that sentence needs "and also," or the todos read like several unrelated changes bundled together, tell the user and suggest splitting into separate plans first — planning the wrong-sized work just compounds the cost across every brief and lane.

### 1. Locate the plan

**Prefer (canonical):** `docs/plans/<stem>/plan.md` — git-tracked, works in Cursor and Claude Code.

**Also accept:**
- `docs/plans/<stem>.plan.md`
- `.cursor/plans/*.plan.md` (Cursor Plan-mode scratch — if this is the only copy, **promote** it: write/update `docs/plans/<stem>/plan.md` before or as you plan, and point INDEX `Source plan:` at the `docs/plans/` path)

Use the active plan if known (from chat context or an explicit stem). Otherwise search in order: `docs/plans/**/plan.md`, `docs/plans/*.plan.md`, `.cursor/plans/*.plan.md`. If **multiple** candidates and no clear active one, read `docs/plans/INDEX.md` — prefer the sole `planned` row; if still ambiguous, ask which stem. Do **not** silently default to most-recently-modified when more than one non-`shipped` registry row exists. Read frontmatter `todos` (if any) and the full body (`## Decisions locked`, workstream sections, scope notes).

**Write target:** always `docs/plans/<stem>/dispatch/` (create `docs/plans/<stem>/` if needed). Do **not** write new durable folders under `.cursor/plans/` unless the user explicitly insists on scratch-only.

### 2. Harvest live knowledge (required — do not skip)

Scan **this conversation** for every decision, constraint, file path, API shape, "do not", and acceptance nuance that was settled during grilling but is NOT already in the plan body. These would be lost in a fresh chat — and `taskman plan from-decisions` only persists what the briefs contain.

Produce a short **harvest ledger** (keep it in working memory; do not write `dispatch/` yet):
- bullet list of chat-only facts, each tagged with the todo-id(s) it belongs to
- structure the ledger using [`docs/workflow/mow-compact-template.md`](docs/workflow/mow-compact-template.md) sections when the repo has it: Goal, Constraints, **Progress** (Done / In Progress / Blocked — each item tagged to todo-id), Key Decisions, Next Steps, Read files, Modified files
- if the ledger is empty *and* the plan body already carries full per-todo context, note that explicitly
- if you cannot name at least one concrete file path or acceptance scenario per todo from plan+chat combined, you do not have enough — ask the user before continuing

This is why **plan** must run in the origin chat. A plan pass that only rephrases the plan's todo titles is a failure mode, not a shortcut.

### 3. Build the lane map

Classify every todo, then group:

- **Sequential (same lane, ordered):** two todos whose file-sets overlap, or where one explicitly depends on the other's output. Shared files = shared state = never parallel.
- **Independent (separate parallel lanes):** disjoint file-sets and no dependency.
- **Final wave (alone, last):** any todo that *documents / summarizes / verifies the result of the others* (e.g. a master doc, a final test pass). It depends on everything.
- **Foreground-only / AFK no (do not background):** destructive ops, anything outside the repo (home dir, global config), git history rewrites, or anything `guard-destructive.sh` would block. Mark these `needs-review` and **AFK: no**.

**Lane letters (A→Z rule):** letter lanes in wave order starting at A, but the **final lane of the run is always `Z`** — the plan reads A to Z, whatever the count (e.g. 6 lanes = A B C D E Z). A single-lane run is just `A` (no Z). This caps a run at 26 lanes (A–Y + Z); more than that means the plan is too big — split it.

**Tracer bullet (new subsystems):** when the plan introduces a subsystem that does not exist yet, prefer wave 1 as the thinnest slice that runs end to end — one path through every layer it touches — even when that under-parallelizes the wave. Widen in wave 2, once the seams are real instead of assumed. For work inside an existing subsystem, shape waves for parallelism as usual.

**Hard rule:** lanes that run in the same wave MUST have disjoint file-sets. On Claude Code, `isolation: "worktree"` (see Runtime resolution / go §2a) makes cross-lane corruption structurally impossible for backgrounded AFK-yes `code-edit` lanes — disjoint file-sets is now merge-conflict avoidance, not the only thing standing between two lanes and a shared tree. On any runtime without that isolation (Cursor, or a manually-pasted lane without the worktree setup from go §3), subagents still share one real working tree, so the rule remains load-bearing there.

### 4. Assign a role per lane

Write **semantic roles** — not runtime-specific `subagent_type` strings. Go mode resolves them per app (see **Runtime resolution** below).

| Todo flavor | Role | Notes |
|---|---|---|
| Multi-file code edit / refactor | `code-edit` | default |
| Shell / filesystem / symlinks / git / destructive | `shell` | usually AFK no / foreground |
| Read-only research / "find where X is" | `explore` | |
| UI / design authoring | `ui-design` | a not-yet-created subagent can't build itself — bootstrap with `code-edit` |
| LLM/agent security review (prompts, tools, model endpoints) | `llm-sec-review` | |
| Stack-specific review (if project has the agent) | `backend-review`, `django-review`, `frontend-review` | only when the todo is narrowly scoped to that stack |

**Review is usually not a todo.** Per-wave diff review happens automatically in go mode (see **Review wave** below) — only create a review *lane* when the plan explicitly demands a standalone audit.

### 4b. Attach the QA contract

Each brief gets a `## QA contract` derived from the todo's tags/flavor. **If the repo has `docs/agents/protocols.md`, use its P1 table** (it also defines the repo's tag vocabulary and reviewer roster). Otherwise apply this default:

| Flavor | Contract |
|---|---|
| backend/code-edit | scoped tests for touched modules · linter · typecheck if wired |
| bug fix | regression test written first and failing, then the fix |
| UI | screenshot at the project's target viewport |
| perf | before/after evidence (query counts or timings) + an assertion that locks the win in |
| migration | dry-run/`sqlmigrate` output reviewed · reversibility stated |
| docs/chore | none beyond acceptance check |

The contract is what the lane **runs itself** (deterministic checks only). It is not self-review — judgment review happens in the go-mode review wave, in a separate context.

**Also attach a Toolkit line.** If the repo has `docs/agents/protocols.md` with a Toolkit column in its P1 table, derive the todo's `## Toolkit` from its tags (union across tags, deduped; explicit `skill:<name>` / `agent:<name>` tags pass through verbatim). Otherwise fall back to a minimal generic map: `bug` → `skill:tdd`, `ui` → screenshot tooling, `perf` → profiling. Prefer `Invoke: skill:<name>` or `Invoke: agent:<name>` in Toolkit bullets (Pi progressive disclosure — lanes reach for these mid-build, not only at Verification). Toolkit is advisory ("prefer these tools"), never a gate — an empty or missing Toolkit is not a thin brief.

### 5. Quality gate — refuse thin briefs (before any write)

Draft every brief **in memory** (or a scratchpad). **Do not create** `docs/plans/<stem>/dispatch/` until every brief passes all of the checks below. Thin briefs poison `taskman plan from-decisions`: empty `Files in scope` / weak acceptance become empty `Task.brief` rows and blind agents.

For **each** todo brief, all of these MUST be true:

| Required section | Passes when | Refuse when |
|---|---|---|
| `## Files in scope` | ≥1 concrete repo-relative path the lane owns (file or dir the agent will edit/create) | empty, "TBD", "see plan", or only vague areas ("the backend") |
| `## Acceptance check` | ≥1 SHALL + ≥1 GIVEN/WHEN/THEN scenario + a verify command when one exists | "works correctly", "tests pass", "done when merged", or a single vague bullet |
| `## Context & decisions` | ≥2 bullets that a blind agent needs, drawn from plan **and** the harvest ledger (step 2) | restating the Goal, copying only the plan todo title, or "see plan / see chat" |
| `## Do NOT` | ≥1 real scope trap (files/patterns to leave alone, anti-patterns from grilling) | empty, or generic "don't break things" |
| `## Goal` | concrete done-state in the agent's own words | one-line echo of the todo id/title |
| `## QA contract` | matches the todo's flavor per step 4b (code todos always have ≥1 runnable check) | missing on a code todo, or checks the lane can't actually run |
| **Decisions / Specs pointers** (INDEX cell + brief header line) | ids that change this lane’s Do/Don’t/Acceptance, or `-` if none; pointers only (no pasted prose); captures only if they are the design artifact; **every id in the INDEX cell MUST also be cited** (e.g. `d#812`) inside this brief’s `## Acceptance check` or `## Do NOT` — preflight refuses fan-out on uncited pointers | dumping full decision/capture text into INDEX; tagging every historically related id; omitting ids that the lane’s Acceptance cites; pointing at an id without a citing line in Acceptance/Do NOT |

**`## Signatures` is optional and deliberately absent from this table.** When two lanes meet at a seam — one builds what the other calls — writing the signatures (bodies omitted) into the producing lane's brief settles the interface before either starts. A lane without one is not a thin brief, and this gate gains no row for it.

**Hard refuse:** if any brief fails, **or** the Operator summary (What we'll do / What you'll have at the end) cannot be filled with concrete observables, do **not** write the folder. List the failing todo-ids / missing summary pieces, ask the user (or go back to harvest/plan), then re-gate. Never "ship a stub and fix later" — import will freeze the stub.

**Import consequence:** after a good plan pass, `taskman plan from-decisions <dispatch-dir>` should be able to fill Feature+Tasks (files, deps, role, acceptance, context) without the importer inventing content. If you would not trust import to round-trip a brief, it is too thin.

### 6. Write the dispatch folder

**Peer-session warn (advisory, d#868):** before writing to `docs/plans/<stem>/`, if the runtime exposes session listing (e.g. Claude Code `ccd_session_mgmt` / `list_sessions`), list live sessions sharing this cwd and **warn** the operator when a peer exists — near-clobber risk on shared plan files. Warn-not-block; skip silently when the tool is absent (Cursor).

Only after step 5 passes: create `docs/plans/<stem>/dispatch/` containing `INDEX.md` plus one `NN-<todo-id>.md` brief per todo (NN = wave-ordered). Use the templates below. Ensure `docs/plans/<stem>/plan.md` exists (create/update from grill decisions if missing) and includes the **Operator summary** sections (`## What we'll do`, `## What you'll have at the end`, one-line closer) **plus the two register sections below**.

#### Required `plan.md` register sections

Every `plan.md` carries both. They record what the plan cannot yet see, and what it has ruled out.

```markdown
## Not yet specified

*Sharpness test: can you state the question precisely now — **not** answer it now? Sharp → a `kind:decision` board row. Not sharp → a line here.*

- <the suspected question / the area to revisit — as loose as the view allows>

## Out of scope

*Scope, not sharpness. Never graduates — returns only if this plan's goal is redrawn, and then as a fresh stem.*

- <gist> — <why it is out of scope> (<link: decision id, tracker id, or the disabled task>)
```

**The sharpness test is the discriminator, and the test is whether you can *state* the question — not whether you can *answer* it.**

- **Raise a task** when the question is already sharp, **even if it is blocked and unanswerable today**: `taskman task add "<the question>" -t kind:decision,plan:<stem>` (or the tracker's equivalent). Link anything it blocks with `task link <build-task> --blocked-by <decision-task>`, so the blocked work drops out of "what's next" on its own.
- **Write a fog line** when you cannot phrase it that sharply. Do **not** pre-slice fog into task-sized pieces — one fog line may graduate into several tasks, or none.

**Fog and scope are different axes.** Fog gathers only *toward* the plan's goal, so `## Not yet specified` is in-scope-but-unsharp and graduates. `## Out of scope` is a scoping act: it never graduates, and it stays **out of** `## Decisions locked`, which records the route actually walked — a scope boundary is not a step on it. When an existing task turns out to sit past the goal, retire it (`task move <id> --status disabled` + tag `scope:out` — **not** `done`, which would falsely claim the work happened) and leave one line here.

**Empty sections still get their heading**, carrying a single `*None — <reason>*` line. Never omit an empty section and never leave a bare heading. *"None — the route to the goal is fully visible"* is a claim someone made; an omitted section is indistinguishable from one nobody considered, and a bare heading reads as unfinished and invites the next agent to fill it with speculation. This keeps an **absent** section meaningful: that plan predates the convention.

**Any pass may raise a decision task — `plan`, `ready`, or a standalone grill.** The sharpness test is the gate, not which mode you are in: a plan pass that surfaces a sharp question must be able to raise it, because fog is the wrong home for anything that passes the test. **Graduation** — re-reading existing fog and promoting what has sharpened — belongs to ready mode alone (see ready §2), because that is where fog gets revisited.

These sections are **required to write, never gated on**. Do not add a preflight or write-back check for them — a missing doc section must never refuse a legitimate `/mow go`.

#### Optional `plan.md` section: `## Product`

For **product-facing** stems — ui tags, or any end-user-visible surface — offer this block once at plan time and let the operator decide. It is the "who is this for and how would we know it worked" frame that a lane map alone never carries.

```markdown
## Product

- **Problem:** <the user's problem in their words, not the implementation's>
- **Success metric:** <the observable that tells you it worked — a behavior, not "shipped">
- **Announcement draft:** <what you'd tell the user shipped, and why they'd care>
```

**Trigger is operator-confirmed, never automatic.** Ask once ("this stem looks product-facing — want a `## Product` block?"); on a decline, or on an infra / tooling / refactor stem, write nothing and move on. **Advisory only:** never a preflight gate, never a thin-brief row, and never backfilled into existing plans.

**Cross-plan guardrail (before write):** read `docs/plans/INDEX.md` (create empty table if missing). For every other `planned`|`running`|`paused` stem, read that dispatch's INDEX `Files owned` column. If any path overlaps a lane in this plan, **do not write** — report conflicts and ask the user to narrow scope or ship/pause the other run first.

**Registry (after write):** add or update the row for `<stem>` in `docs/plans/INDEX.md` → `Status: planned`, bump `Updated`, set `Title` from the plan name, `Feature` from taskman id if known.

Each **brief** must be runnable by a blind agent — no reference to "this chat":

```markdown
# <todo-id>: <one-line goal>

**Role:** <role>   **Wave:** <n>   **AFK:** <yes|no>   **Background:** <yes|no>

**Decisions / Specs (pointers):** <d `#…` · req `#…` · optional task/cap ids, or `-`> — ids only. Resolved prose: `docs/plans/<stem>/dispatch/hydrated-specs.md` (this lane’s section). Do not duplicate full decision prose here (that lives in Context / Acceptance + hydrated-specs).

## Goal
<what done looks like, concretely>

## Context & decisions (only what this todo needs)
- <decision + rationale, harvested from plan + this chat's ledger — not "see plan">

## Files in scope
- <paths this lane owns; nothing outside this list>

## Signatures (optional — omit unless the lane needs it)
- <function / model / endpoint signatures this lane must expose, bodies omitted>
- <seam notes: what an adjacent lane will call, and what it may assume>

## Depends on
- <todo-ids that must finish first, or "none">

## Do NOT
- <scope traps, anti-patterns, files to leave alone>

## Git rules
- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.
- Before commit while parallel lanes are active, run `git status` and confirm only intended paths are staged.

## Acceptance check
- <SHALL statement: one observable behavior, e.g. "The endpoint SHALL return 404 for an unknown id">
- <scenario: GIVEN <state> WHEN <action> THEN <observable outcome> — the case you'd be upset to see broken, not just the happy path>
- <command that verifies it, e.g. `pytest workouts/`>

## QA contract
- <checks this lane runs itself before reporting done, per step 4b / the repo's protocols.md P1>

## Toolkit
- <skills/agents recommended for this todo's tags, per step 4b — or "none" if the repo has no Toolkit column and no tag matches the generic fallback>

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: <d#N: how, file:line — one per Decisions/Specs pointer, or "none pointed">
```

`AFK` and `Background` must agree (both yes or both no). Prefer stating **AFK** in operator-facing text; keep **Background** for runtime fan-out compatibility.

Loose one-liners ("works correctly", "tests pass") are not acceptance checks — a blind agent (and a reviewer) needs something they could actually fail. If the repo has `taskman` with a `Requirement` living-spec (`taskman requirement add/list --feature <id>`), prefer lifting the SHALL + scenario from there instead of writing a new one from scratch.

The **INDEX** is the orchestration contract:

```markdown
# Dispatch index — <plan name>

Source plan: docs/plans/<stem>/plan.md

## What we'll do
1. …
2. …

## What you'll have at the end
| Area | End state |
|---|---|
| … | … |

**In one line:** …

## Waves
- **Wave 1 (parallel, AFK):** <lane> | <lane> | <lane(seq: a→b)> ...
- **Wave 2 (after wave 1, foreground):** <final lane — always `Z`>

Each wave ends with a **review gate** (see go mode) before the next starts.

## Lanes
| Lane | Todos (in order) | PBI / Feature | Files owned | Role | Review flags | AFK | Background | Decisions / Specs | Brief |
|---|---|---|---|---|---|---|---|---|---|
| A | ... | #52 / #65 | ... | code-edit | django | yes | yes | d `#12` · req `#3` | 01-....md |

`PBI / Feature`: per-todo PBI id / Feature id (see Orchestration map section above for source) — `-` if untracked.

`Review flags`: which reviewers the wave gate must run for this lane's changes — from the repo's `docs/agents/protocols.md` P2 (e.g. `django`, `llm`, `frontend`), or `-` for none (docs/chore).

`AFK` / `Background`: `yes` = safe to fan out under `/mow go` without the user watching; `no` = foreground / needs-review.

`Decisions / Specs`: **pointers only** — see Orchestration map legend (`d` / `req` / `task` / rare `cap`). INDEX = ids; brief Context = working copy; `scripts/mow_hydrate_specs.py` → `hydrated-specs.md` for lanes to Read. Prefer decision/requirement ids over captures. Only ids that change this lane’s Do / Don’t / Acceptance (not every related decision). `-` if none.

**Hydrated specs:** [`hydrated-specs.md`](hydrated-specs.md) (generate/refresh after pointer changes)

**Grill checkpoint:** pending
**Grill write-back:** pending — fill on `/mow ready` (plan.md + briefs; required before `/mow go`)

## Conflicts check
Confirm: no two same-wave lanes share a file. <list any risk>
```

### 7. Persist + hand off (agent runs taskman — user does not)

**Print the Operator summary, then the Orchestration map** (see top of this skill) — what we'll do / end state, then waves, lanes, AFK, roles, review flags. Tell the user it's safe to close or continue this chat; everything needed is on disk under `docs/plans/<stem>/`. Next: **`/mow ready <stem>`** (preview + grill checkpoint) before **`/mow go <stem>`**. Survey active runs with `/mow list`. Do not skip ready/grill on a fresh multi-lane plan unless the origin chat already locked decisions via `/grill-with-docs`.

**When the repo has `taskman/` + `.taskman.toml`, you (the agent) must:**

1. **Living spec first (if Feature id known):**  
   `taskman requirement list --feature <id>`.  
   If this chat locked durable behaviors that are missing from the list, **`requirement add` / `modify`** them now (SHALL + `name|given|when|then`). Prefer lifting those statements into brief `## Acceptance check` (step 5) rather than inventing weaker ones.  
   If the Feature already has requirements, **prefer citing them** in acceptance instead of paraphrasing.

2. **Import briefs onto the board (mandatory gate):**  
   ```bash
   python scripts/mow_plan_import.py docs/plans/<stem>
   ```  
   Do this yourself — do not only "offer" it. Import is only as good as the briefs (steps 2 and 5). **Refuse to hand off on non-zero exit** (same discipline as preflight before go). Print Feature/Task ids in the operator summary.

3. If board rows already exist (enrich path): set each Task's `source_ref` to its brief path **before** import so import **updates** `Task.brief` in place instead of creating duplicates. Re-import via `mow_plan_import.py` is idempotent for brief content (`from-decisions` semantics unchanged).

4. **Hydrate Decisions / Specs (when the repo has the script and any lane cell is not `-`):**  
   ```bash
   python scripts/mow_hydrate_specs.py docs/plans/<stem>
   ```  
   Writes `dispatch/hydrated-specs.md`. Point INDEX `**Hydrated specs:**` at it. Skip only if every lane’s Decisions / Specs cell is `-`.

5. Report Feature/Task/Requirement ids to the user. Do not leave "run import yourself" as the primary next step.

**All projects:** gates are runtime-agnostic — `mow_plan_import.py` and `mark-shipped` work the same in Cursor and Claude Code. Other taskman repos copy `scripts/mow_plan_import.py` from FTM (or sibling) after first ship; the dotfiles skill is global, scripts are per-repo.

---

## Mode: list

Read-only registry + **full** pre-go preview for every active run. Never collapse an active stem to a one-line wave teaser.

1. Print `docs/plans/INDEX.md`. Sort rows: `running` first, then `planned`, then `paused`, then `shipped`. Highlight non-`shipped` rows.
2. **Registry drift self-heal (the one disk write this mode makes):** for each `planned`|`running` row, check whether `docs/plans/<stem>/action-report.md` exists. If it does, the run finished but the go-Integrate registry flip was missed — a recurring failure mode. Auto-correct it: run `python scripts/mow_set_registry_status.py <stem> shipped` if the repo has the script (else hand-edit the row), tell the user in one line ("auto-corrected registry drift: `<stem>` had a completed action report but was still `<old status>` — set to `shipped`"), and treat it as `shipped` for the rest of this listing (skip printing its full map as an active stem).
3. For **each** remaining `planned`|`running`|`paused` stem (in that sort order): print the **Operator summary** (from `plan.md` or `dispatch/INDEX.md`) then the full **Orchestration map** (Waves table + Lanes table + How to run). Include dispatch path and registry status. If only one active stem exists, still print summary + map — that *is* the preview; do not skip lanes. If the on-disk summary is missing, regenerate it from the plan body before printing (do not invent scope).
4. **Parallel-safe matrix (active runs only):** for every pair of active stems, run the cross-plan overlap check. Print pairs that are **parallel-safe** (disjoint files) vs **blocked** (list conflicting paths). Example: `plan-a ‖ plan-b ✓` · `plan-a ✕ plan-c (taskman/cli.py)`. Skip the matrix when fewer than two active stems.
5. Offer next step: `/mow ready <stem>` to re-focus one map · `/mow go <stem>` to fan out. If exactly one active stem, offer `/mow go` (stem optional). Otherwise, change nothing on disk.

---

## Mode: ready

Focused pre-go preview **plus grill checkpoint** — one stem's operator summary + full orchestration map, then stress-test ambiguities before fan-out.

**Resolve stem** per **Stem resolution** above. If no stem and multiple active runs, print **list** (all maps) and ask which stem — do not guess.

### 1. Preview (always)

Print:
- registry row (status, feature, updated)
- dispatch path
- **Operator summary** (`### What we'll do` / `### What you'll have at the end` / one-liner) from `plan.md` or `dispatch/INDEX.md` — regenerate from the plan body if missing
- full **Orchestration map** (Waves + Lanes + How to run) from `dispatch/INDEX.md`
- grill status from `dispatch/INDEX.md` (`Grill checkpoint: pending|done <date>|skipped`) — if missing, treat as `pending`
- if other stems are active: one-line note to run `/mow list` for the parallel-safe matrix (do not re-dump every map unless the user asked for list)

### 2. Grill checkpoint (default — interactive)

**Peer-session warn (advisory, d#868):** before patching `docs/plans/<stem>/` during write-back, if the runtime exposes session listing (e.g. `ccd_session_mgmt` / `list_sessions`), warn when another live session shares this cwd. Warn-not-block; skip silently when the tool is absent (Cursor).

**Skip only when:** user says `skip grill` / `ready --skip-grill`, **or** INDEX already has `Grill checkpoint: done <date>` **and** a valid `**Grill write-back:**` line (see gate below), **or** user confirms the plan was grilled in the origin chat and decisions are already locked in `plan.md` *with write-back verified*.

Otherwise follow the **`grill-with-docs`** procedure against this stem's `plan.md` + briefs (read that skill and run it — do not invent a weaker Q&A):

1. One question at a time; recommend an answer each time; wait for the user.
2. Focus on ambiguities that would poison a blind lane: acceptance gaps, file-boundary conflicts, mobile/edge cases, Do-NOT traps missing from briefs.
3. **Per-answer write-back (mandatory — before asking the next question):**
   - Patch `docs/plans/<stem>/plan.md` `## Decisions locked` (or add/update `## Grill write-back`) with the locked answer — not only chat memory. When the repo has [`docs/workflow/mow-compact-template.md`](docs/workflow/mow-compact-template.md), align write-back with its sections (Key Decisions → locked bullets; Progress → todo statuses).
   - Patch **every affected brief** (`## Context & decisions`, `## Acceptance check`, `## Do NOT`, `## Goal` as needed). Remove hedges the answer killed ("prefer X if simpler", "MAY …"). Update the brief’s **Decisions / Specs (pointers)** line with any new `d`/`req` ids (pointers only — no prose dump).
   - Update `dispatch/INDEX.md` **Decisions / Specs** cells for every affected lane the same way (ids only). Re-run `python scripts/mow_hydrate_specs.py docs/plans/<stem>` so `dispatch/hydrated-specs.md` matches.
   - If the repo has taskman: `decision add` (and `requirement add`/`modify` when durable SHALL changes). Prefer citing decision/requirement ids in the plan bullet. Do **not** default to tagging chatty captures — only `cap #…` when that capture *is* the design artifact (`--kind decide` / grill write-up); still prefer `d`/`req`.
   - **Graduate the fog this answer cleared.** Re-read `plan.md` `## Not yet specified` and apply the sharpness test (plan §6) to each line: anything the answer made precisely *stateable* becomes `taskman task add "<the question>" -t kind:decision,plan:<stem>`, linked with `task link` to whatever it blocks — then **delete that fog line**, so the question lives in exactly one place. Graduate as answers land, not in one sweep at the end, so a sharpened question is never carried past the answer that sharpened it. If the answer instead reveals something sits past the plan's goal, retire it to `## Out of scope` (`task move <id> --status disabled` + `scope:out`) rather than resolving it on the route.
   - Tell the user which paths changed in one line, then ask Q(n+1).
4. **Write-back verification gate (before marking done):** refuse to set `Grill checkpoint: done` until all of:
   - `plan.md` contains each locked grill answer (searchable text — not "see chat").
   - Every brief whose scope the answer touched was patched on disk.
   - `dispatch/INDEX.md` will get **both** lines below.
   - If taskman is present: re-run `python scripts/mow_plan_import.py docs/plans/<stem>` so board rows stay current after brief patches (restore board priority/tags if the importer clobbers them).
5. When the gate passes, set in `dispatch/INDEX.md`:
   ```markdown
   **Grill checkpoint:** done <YYYY-MM-DD>
   **Grill write-back:** plan.md ✓ · briefs: <01-…, 02-… or "none — plan held"> · taskman: decision #… / capture #… (or n/a)
   ```
   If the grill found nothing to change: `**Grill write-back:** no changes — plan held <YYYY-MM-DD>`.
   Re-run `python scripts/mow_hydrate_specs.py docs/plans/<stem>` so `hydrated-specs.md` matches final pointers (skip if all cells are `-`).

**Mockup offer (ui lanes only — operator may decline):** when the stem has a ui-tagged lane, offer once during the grill to write `docs/plans/<stem>/dispatch/mockups/<lane>.html` — plain HTML, no build step, at the project's target viewport (FTM: 390px mobile-first). Approving a layout in a browser before a lane starts is far cheaper than re-approving it out of a diff. When the operator approves one, point that lane's `## Acceptance check` at the file ("the built screen SHALL match `dispatch/mockups/<lane>.html` in structure and hierarchy"). On a decline, write nothing — the mockup is an option, never a gate, and a ui lane without one still passes the thin-brief gate.

**Hard refuse:** never mark `done` after a grill that only summarized decisions in chat. `/mow go` lanes read **disk** (plan + briefs), not this conversation.

If the user skips: write `**Grill checkpoint:** skipped <YYYY-MM-DD> — <reason>` and `**Grill write-back:** skipped` so go can see it.

### 3. Hand off

Only after grill is `done` or `skipped` **with write-back lines present**, offer: `/mow go <stem>`.  
Do **not** fan out from ready — go owns execution.

---

## Runtime resolution

**plan** writes semantic **roles**. **go** maps each role to the executing app's real agent roster at fan-out time. Never hardcode one app's `subagent_type` strings into briefs or INDEX.

**Detect runtime:** inspect your available tools/agents. Cursor exposes `Task` with `subagent_type` including `shell`. Claude Code exposes an Agent tool with `general-purpose`, `Explore`, etc., and has **no** `shell` agent — shell work runs via Bash in the foreground.

| Role | Cursor `subagent_type` | Claude Code agent |
|---|---|---|
| `code-edit` | `tdd-builder` (fall back to `generalPurpose` if not in the roster) | `tdd-builder` (fall back to `general-purpose` if not in the roster) |
| `explore` | `explore` | `Explore` |
| `shell` | `shell` | *(none — run in foreground with Bash; do not Task)* |
| `llm-sec-review` | `llm-sec-review` | `llm-sec-review` |
| `ui-design` | `ui-designer` | `ui-designer` |
| `backend-review` | `backend-reviewer` | `backend-reviewer` |
| `django-review` | `django-reviewer` | `django-reviewer` |
| `frontend-review` | `frontend-reviewer` | `frontend-reviewer` |

If a role has no mapping in the current runtime, fall back to `code-edit` / `general-purpose` / `generalPurpose` and note the downgrade in the go summary.

**Worktree isolation (Claude Code only).** Claude Code's `Agent` tool takes an `isolation: "worktree"` param: it creates a temporary git worktree so the agent works on an isolated copy of the repo, auto-cleaned if the agent makes no changes, otherwise returning the worktree path + branch for the orchestrator to merge back (go §2a owns the merge-back, conflict, and teardown rules). Set it on every backgrounded AFK-yes `code-edit` lane's `Agent` call. This is a Claude-Code-only capability — do not build a Cursor-side shim. Cursor's `Task` tool has no documented equivalent, so Cursor lanes keep today's shared-tree behavior; note that downgrade in the go summary exactly like a missing role mapping.

**tdd-builder on Cursor (unverified as of 2026-07-15):** tdd-builder's contract depends on invoking skills mid-build (the `tdd` skill before production code, Toolkit skills during). If the Cursor subagent runtime does not expose skill invocation to subagents, the agent's own red-green instructions still apply but skill runs silently no-op — on the first Cursor `/mow go` with a `code-edit` lane, check the lane's `## Verification` block for red-test evidence; if absent, downgrade the Cursor mapping back to `generalPurpose` and note it here.

**Legacy INDEX/briefs:** if `Subagent` column or brief header still has old runtime strings (`generalPurpose`, `explore`, etc.), translate before fan-out:

| Legacy value | Role |
|---|---|
| `generalPurpose` | `code-edit` |
| `explore` | `explore` |
| `shell` | `shell` |
| `security-review` (retired role) | `llm-sec-review` for LLM-scoped audits; general security → the runtime's built-in security review (e.g. `/security-review`) run by the orchestrator |

If INDEX has `Background` but no `AFK` column, treat Background as AFK.

---

## Mode: go

Reads the dispatch folder and runs it. Works from a fresh chat — it relies only on disk. If multiple active runs exist and no stem was named, run **list** logic first (full maps for every active stem) or ask.

### 1. Load

**Resolve stem** per **MOW registry** rules. Read `docs/plans/INDEX.md`.

**Parallel go gate:** if other stems are `running`, run the cross-plan overlap check against each one. **Disjoint → proceed** — tell the user which runs are parallel-safe (e.g. "safe alongside `other-stem` in a separate chat"). **Any overlap → refuse** — list stems and conflicting paths; user must ship/pause one or narrow scope. Do not block parallel go merely because another stem is already `running`.

**Cross-plan guardrail (planned/paused too):** also check overlap against `planned`|`paused` stems if you would advise starting go while those wait — warn that a future go on the overlapping stem cannot run in parallel.

Apply **parallel go soft warnings** from the registry section when relevant.

Set this stem's registry row → `Status: running`, bump `Updated` (before wave 1 fan-out). **Run the repo script if present** (`python scripts/mow_set_registry_status.py <stem> running`) instead of hand-editing the table — this is a scripted flip, not a step to remember; fall back to a manual edit only if the script is absent.

**Grill gate:** if `dispatch/INDEX.md` has no `Grill checkpoint: done|skipped` line, **warn** and ask whether to run `/mow ready` first or proceed with `skipped` (write the skip line with reason). Do not silently fan out on an ungrilled multi-lane plan.

**Grill write-back gate (hard):** if checkpoint is `done`, INDEX **must** also have a `**Grill write-back:**` line (plan.md ✓ / briefs listed / taskman ids, or `no changes — plan held`). If `done` without write-back → **refuse fan-out**, tell the operator to finish `/mow ready` write-back (or run the repo check script if present: `python scripts/mow_check_grill_writeback.py docs/plans/<stem>`). Spot-check: open `plan.md` and confirm at least one grill-locked decision appears in `## Decisions locked` / `## Grill write-back` — chat-only locks are not enough for blind lanes.

**Optional (taskman):** if `taskman plan to-dispatch` is available for the target work
(repo has `taskman/` + `.taskman.toml`), prefer that export as the brief source —
it reflects live statuses/deps. Write/export to `docs/plans/<stem>/dispatch/` when creating a fresh folder.

Otherwise locate `docs/plans/<stem>/dispatch/` (canonical). Fall back to `.cursor/plans/<stem>.dispatch/` only if that is where an older run left briefs.

Read `INDEX.md` and every brief. Re-verify the conflicts check (no same-wave file overlap). If a brief is stale vs the plan, flag it. Briefly restate the Operator summary one-liner + Orchestration map (waves + AFK + Decisions / Specs pointers) before fan-out so the operator knows what is about to run. Reminder for lanes: tdd before production code; parallel-debug if >1 unrelated test fails; imprint / test-coverage / adversarial per Automation hooks.

**Preflight gate (before wave 1):** if the repo has `scripts/mow_preflight.py`, run:

```bash
python scripts/mow_preflight.py docs/plans/<stem>
```

**Live tracker (after preflight passes — Claude Code, or any runtime with a browser pane):** set up the run's live visual before wave 1 fan-out. Copy `~/.claude/skills/mow/tracker.html` → `dispatch/tracker.html`, write the initial `dispatch/tracker.json` skeleton from INDEX (every wave/lane/todo `pending`, `run_status: running`), then serve and open it:

```bash
# one stable port per repo, so two projects' runs never land on each other
PORT=$(python3 -c "import hashlib,os;print(8300+int(hashlib.md5(os.getcwd().encode()).hexdigest(),16)%80)")
# clear this repo's own stale tracker from an earlier run (matches only that server)
if command -v pkill >/dev/null 2>&1; then
  pkill -f "http.server $PORT" || true
elif command -v taskkill >/dev/null 2>&1; then
  # Git Bash: netstat's local-address column gives the listener's PID
  TRACKER_PID=$(netstat -ano | grep ":$PORT" | awk -v p=":$PORT" '$2 ~ p"$" {print $NF; exit}')
  [ -n "$TRACKER_PID" ] && taskkill //F //PID "$TRACKER_PID" || true
else
  echo "warn: no pkill or taskkill — a stale server on $PORT may still be serving an older run"
fi
python3 -m http.server $PORT -d docs/plans/<stem>/dispatch
# printed in every shell, so the board is always reachable by hand
echo "tracker: http://localhost:$PORT/tracker.html"
# terminal Claude Code has no pane to open it in — hand the page to the real browser
if [ -n "$TERM_PROGRAM$SSH_TTY" ]; then
  if command -v open >/dev/null 2>&1; then open "http://localhost:$PORT/tracker.html"
  elif command -v start >/dev/null 2>&1; then start "http://localhost:$PORT/tracker.html"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "http://localhost:$PORT/tracker.html"
  fi
fi
```

(background the server). **Every runtime that can run that shell gets the board**, terminal Claude Code included — the page is a plain local server, nothing about it needs an in-app pane, and a real browser window on a second screen is the better home anyway (a hidden pane freezes the animation clock). Open the URL that `echo` printed in the browser pane — the page polls `tracker.json` every 2s. **Never skip the kill cascade and never hardcode 8377**: a server left running by an earlier run keeps serving *that* run's folder, so the board loads, looks live, and shows the wrong run. Because the port is derived from the repo path it is stable — the same project always gets the same URL, worth bookmarking on a second screen, where animation keeps running even when the browser pane is hidden. From here on, **update `tracker.json` at every run event** (fan-out, agent spawn, lane done/error/issues, gate verdicts, artifacts, findings) per the schema + write-points table in `~/.claude/skills/mow/TRACKER.md`. Findings render only with their taskman task ids — a lane goes `issues` only when its findings are filed on the board (§2b.3). Tracker files are disposable run state; never a gate — a missing tracker must not block fan-out.

**Chat board (required when your tool list has a widget/visualization tool such as `show_widget`; if it has none, skip — the URL line already gave the operator the board):** post the board into the chat itself at **wave boundaries** — after fan-out, after each gate verdict, and at close-out. This is a row in TRACKER.md's write-points table, not an optional flourish: an FTM run crossed five boundaries posting nothing, and the operator watched an empty chat while the board was live on its port. Not per write, though — a widget per event buries the conversation. Do not hand-build a card: the board already exists, so embed it.

```
<h2 class="sr-only">Live mow board — <stem>, wave N of M</h2>
<iframe src="http://localhost:$PORT/tracker.html?view=compact"
  style="width:100%;height:380px;border:0.5px solid var(--border);border-radius:12px"
  referrerpolicy="no-referrer"></iframe>
```

That is the whole widget — the page renders itself, stays live between posts, and can never drift from what the browser shows, because it *is* what the browser shows. Compact is the chat default: it carries each lane's todo id and title and the gate's status word, which is what the glance view is for. The reader can flip to detailed inside the frame.

The iframe dies with the server, so old transcripts would show an empty box. At **close-out only**, after the final `tracker.json` write and before the server is stopped, post a frozen snapshot instead — `python3 ~/.claude/skills/mow/widget.py docs/plans/<stem>/dispatch/tracker.json` prints a self-contained fragment (the same renderer, font stripped, board inlined) to pass as the widget. It is ~15k tokens, so it is worth it exactly once, as the run's record.

**In-progress pulse (operator chat):** seed `dispatch/tracker.json` with `"pulse": true`. If the operator asks to turn the heartbeat/pulse on or off (e.g. "pulse off", "turn the shine pulse back on"), Edit `pulse` in `tracker.json` **immediately** — do not wait for a wave event. Spin stays on; only the lub-dub glow toggles.

Refuse fan-out on exit 1. Preflight is the **single** go §1 gate — grill write-back (unless stem is `shipped`) → hydrate (when Decisions/Specs pointers exist) → thin-brief validation → same-wave and cross-plan file overlap. It **subsumes** the former standalone hydrate step; do not also call `mow_hydrate_specs.py` separately after preflight passes. When hydrate runs inside preflight, confirm `dispatch/hydrated-specs.md` exists. Subagents **Read** `hydrated-specs.md` for their Lane section — they do not need live taskman for the lock set. If the script is absent, fall back to manual grill + hydrate + overlap checks.

### 2. Run wave by wave

For each wave, in order:

- **Background / AFK fan-out:** issue all of the wave's AFK-yes lanes as Task/Agent subagents **in a single message** so they run concurrently. Resolve each lane's **Role** via **Runtime resolution** above, then set `subagent_type` (or the Claude Code equivalent) and `run_in_background: true`. On Claude Code, an AFK-yes `code-edit` lane also gets `isolation: "worktree"` on its `Agent` call (see **Worktree isolation** in Runtime resolution) so parallel lanes are actually isolated, not just conventionally disjoint — Cursor and any other runtime with no equivalent primitive keep today's shared-tree behavior; note that downgrade in the go summary. A sequential lane's brief instructs the subagent to do its steps in order internally. Pass the brief file path + its contents as the prompt — and instruct the lane to **Read** `docs/plans/<stem>/dispatch/hydrated-specs.md` (its Lane section) — including its `## Toolkit` section, when present, so the subagent knows which skills/agents to reach for mid-build rather than after; never assume inherited context.
- **`shell` role in Claude Code:** do not Task — run the lane yourself in the foreground with Bash, with the user watching.
- **Foreground / AFK-no / `needs-review` lanes:** do these yourself or one at a time, with the user watching — do not background destructive or out-of-repo work.
- Do not start wave N+1 until wave N's lanes report done **and the review gate passes**.
- **Budget hard-stop (optional):** if a lane's brief or its imported taskman `Task.brief` carries `{"budget": {"max_tool_calls": N}}`, track that lane's subagent tool-call activity against N. If exceeded, stop/flag the lane (do not keep running it) and record the outcome with `taskman capture add --kind qa` when the repo has taskman. No `budget` key → no enforcement (same as today).

### 2a. Merge-back (isolated lanes only, before the review gate)

When any of the wave's lanes ran with `isolation: "worktree"` (Claude Code, AFK-yes `code-edit`), do this **before** 2b's combined-diff review — reviewers must see one integrated diff, not per-lane worktree fragments. **The mechanism below is dogfooded (a real 2-lane + a real conflict were run through it, not inferred from the tool's doc alone)** — `isolation: "worktree"` does **not** auto-commit a lane's changes (they sit as uncommitted/untracked files in that worktree), so a plain `git merge <lane-branch>` is a no-op, and merging 2+ lanes sequentially with `git merge --no-commit` breaks after the first (`MERGE_HEAD` stays open and blocks the next). A disposable integration branch is what actually composes for any number of lanes:

1. Create one disposable integration worktree + branch from the wave's starting commit (e.g. `git worktree add .claude/worktrees/<stem>-integrate -b mow/<stem>/integrate HEAD`) — fully throwaway, deleted at the end of this procedure.
2. For each isolated lane that reports done and returned a worktree path + branch: commit that lane's own changes on its own worktree branch (`git -C <lane-worktree> add <files>` then `commit` with a throwaway message) — this commit never leaves the disposable worktree/branch and is never pushed, so it does not touch the operator's real history any more than the worktree itself does. Then merge that lane's branch into the integration branch with a real commit (`git -C <integrate-worktree> merge --no-ff <lane-branch> -m "..."`) — a real commit here is required for the *next* lane's merge to compose cleanly; skip a lane that made no changes (the `Agent` tool already auto-cleaned it — no path/branch was returned).
3. **Real merge conflict on any lane's integration step → stop the wave right there and ask the operator.** Never auto-resolve — not with a `Files in scope` tie-breaker, not with any other silent rule, and do not proceed to merge remaining lanes. A conflict here means the plan-time disjoint-`Files in scope` check failed, or isolation was applied to lanes that weren't actually independent; that's an upstream planning bug to surface, not a routine event to smooth over. Show the conflicting hunks (the integration worktree is left mid-merge, exactly as git normally shows a conflict) and wait.
4. Once every lane has merged into the integration branch cleanly: diff the integration branch against the wave's starting commit (`git diff <start-commit> <integrate-branch>`) and apply that single combined diff to the operator's actual working tree with `git apply` — this lands the result as plain uncommitted changes, never a commit on the operator's real branch, exactly like a non-isolated lane's edit would look. If `git apply` itself fails (should not happen given the conflict check in step 3, but is a real possible edge case if the wave's tree diverged mid-run), stop and ask — do not force it.
5. **Fail-closed teardown:** never discard/remove a lane's worktree (or the integration worktree) while it holds unmerged commits or uncommitted changes. Only remove worktrees and delete every throwaway branch (lane branches + the integration branch) after the diff has landed in step 4 and this wave's review gate has passed (or the lane reported failure and the orchestrator has explicitly decided to abandon it — say so and preserve the branch rather than silently deleting work).

### 2b. Review gate (end of every wave)

When a wave's lanes report done:

1. **Check each lane's `## Verification` block** against its brief's QA contract **and** its Decisions / Specs pointers: every pointed id must have a `Decisions honored:` line (`d#N: how, file:line`, or `none pointed`). A lane without Verification (or with unmet contract items / missing honored lines and no justification) is **not done** — send it back or finish the checks yourself in the foreground.
2. **Spawn the wave's reviewers in parallel, in isolated contexts, on the combined wave diff** — union of the INDEX `Review flags` for the wave's lanes (roster per the repo's `docs/agents/protocols.md` P2; default: the stack reviewer for code changes, `llm-sec-review` when prompts/tools/model endpoints changed). Builder lanes never review their own work.
3. **Triage findings:** Critical → fix now (new lane or foreground) and re-review the fix before the next wave. Warning/Suggestion → file to the tracker (taskman: tasks tagged `review-finding`, severity in title); they queue, they don't block.
4. Record the gate: per verified lane, `taskman capture add --kind verify --summary "<task-id>: <one-line>" --source-ref <brief path>` (when the repo has taskman).

### 3. Paste-ready alternative

Also surface, per lane, a copy-pasteable prompt block (path to `hydrated-specs.md` + brief contents) so the user can open separate chats manually instead of/alongside background subagents. Default is to offer both: fire background subagents AND print the prompts.

**Worktree setup for AFK-yes `code-edit` lanes:** a manually-pasted lane typically just `cd`s into the same repo checkout in a new terminal, which would silently drop the isolation guarantee the backgrounded path gets. Prepend worktree setup to that lane's prompt block: `git worktree add ../<repo>-<stem>-<lane> -b mow/<stem>/<lane>`, then `cd` into it before starting on the brief — so a manual lane is isolated exactly like a backgrounded one.

### 4. Integrate

When lanes return: read each summary, check for cross-lane file conflicts, run the acceptance checks (and the repo's canonical tests, e.g. `pytest`), then handle the final-wave "documents-all" todo as the orchestrator since it synthesizes the others' results.

After the final build wave, run the repo's post-build testing protocol if defined (`docs/agents/protocols.md` P3 — e.g. `/verify` on the affected flow, `/test-coverage` on new modules, adversarial batch on math/domain modules) **before** ship-check and the action report. Record each P3 step in the action report Verify section (or an explicit n/a with reason).

**Ship-check gate (required):** invoke the `ship-check` skill against this stem's `plan.md` + shipped diff. Do **not** set registry `Status: shipped` until ship-check has run and Critical Layer-1 (spec) misses are either fixed or explicitly deferred by the operator. Paste the ship-check summary into the action report (or link a capture). Architecture deepening (`improve-codebase-architecture`) is **not** part of this gate by default — queue it post-ship when the plan tagged `refactor` or the operator asks (Wave 2+).

When **all** lanes are **done** and ship-check has passed (or operator deferred Criticals in writing):

1. **Finding-triage (required — before the action report):** for every Critical/Major finding from this run's review gates, classify before writing the action report:
   - **(a) mechanizable** — the check is **added in this same run** (rule file / pytest / protocols P1 row). A follow-up task instead of adding the check is only acceptable with an operator-approved deferral reason.
   - **(b) convention** — `decision add -t <area/path tags>` (d#852 conventions) so Q5 surfacing carries it into future briefs.
   - **(c) one-off** — capture only (`taskman capture add --kind qa` — wave-gate verify records; this CLI has no separate `verify` kind).
   The action report's **Verify** section records each finding → classification ((a)/(b)/(c)).

2. **Write the action report (required — do not skip):** create or update `docs/plans/<stem>/action-report.md` next to the plan. You do **not** need a separate todo for this — Integrate always owns it.

   Mirror an existing report shape (e.g. `docs/plans/platform-foundation/action-report.md`):
   - Frontmatter block: Date, Project slug, Plan + Dispatch links, optional session-report link
   - **Outcome** — one table or bullets of what shipped vs skipped/deferred
   - **Wave results** — per wave/lane: task ids, concrete deliverables
   - **Decisions locked** — choices that matter for later work
   - **Open / deferred** — follow-ups still on the board
   - **Verify** — tests/commands run

   Add or update a line in `docs/plans/<stem>/dispatch/INDEX.md`:
   `**Action report:** [`../action-report.md`](../action-report.md)`

   **Board sync (required when taskman present):** before the registry flip, run:
   ```bash
   python -m taskman plan mark-shipped docs/plans/<stem>/dispatch
   ```
   Skip with n/a only if the repo has no taskman. Moves Tasks linked by brief `source_ref` to `done` per action-report Outcome (or all dispatch `NN-*.md` brief tasks with stderr warning when no report).

   **Flip the registry (required — same step, not a follow-up):** run `python scripts/mow_set_registry_status.py <stem> shipped` if the repo has the script — this is the recurring miss (action report written, registry row left `planned`/`running`, so `/mow list` shows a finished run as still active). Do not treat this as "then hand-edit the table later" — run the command now, in this same Integrate pass, right after board sync. Fall back to manually editing `docs/plans/INDEX.md`'s `Status`/`Updated` cells only if the script is absent from the repo.

   **Tracker reconcile (required when a tracker ran):** before closing it out, spawn one `general-purpose` subagent to audit the board against reality. It is deliberately a *fresh* reader: the orchestrator wrote `tracker.json` from memory and is blind to its own dropped writes. Brief it to read `dispatch/tracker.json` plus every lane's `## Verification` block, the gate verdicts, and the findings filed on the board, then report **only discrepancies** — lanes/agents left `running` that actually finished, missing or invented artifacts, findings without taskman ids, skills never reconciled, `tokens` the runtime reported but the board never got, **any agent missing `started`/`ended`** (the per-subagent duration beside its name comes from nothing else), wave `started`/`ended` gaps. It reports; it does not edit. Apply its list yourself, then close out. A clean report is a one-line "board matches".

   **Tracker close-out:** set `tracker.json` → `run_status: shipped`, finalize remaining statuses, and stop the tracker HTTP server if you started one — same cascade as §1, never a bare `pkill` (Git Bash has none):

   ```bash
   if command -v pkill >/dev/null 2>&1; then
     pkill -f "http.server $PORT" || true
   elif command -v taskkill >/dev/null 2>&1; then
     TRACKER_PID=$(netstat -ano | grep ":$PORT" | awk -v p=":$PORT" '$2 ~ p"$" {print $NF; exit}')
     [ -n "$TRACKER_PID" ] && taskkill //F //PID "$TRACKER_PID" || true
   else
     echo "warn: no pkill or taskkill — stop the server on port $PORT by hand"
   fi
   ```

3. **Print the done summary (required — do not skip):** a short human-readable block matching the Operator summary shape, in past tense. Prefer rewriting from what actually shipped (lanes + review gate + verify), not only copying the forward-looking plan text.

```markdown
### What we did
1. …
2. …

### What you have now
| Area | End state |
|---|---|
| … | … |

**In one line:** …

Next: `/wrap-up` (board sync + session report).
```

4. **Close the session yourself — but only when it is provably safe.** Run the repo's
   wrap-up evidence gate if it has one (`python scripts/wrapup_reconcile.py`), then check
   the three safety conditions below. All three green → follow
   `~/.claude/skills/wrap-up/SKILL.md` directly (that skill is
   `disable-model-invocation: true`, so read it from disk and execute its steps; do not try
   to invoke it with the Skill tool). Any condition red → **stop**, print which one and why,
   and tell the user to run `/wrap-up` themselves.

   | Condition | Green when | Why it blocks |
   |---|---|---|
   | Evidence gate | exits 0 (no unattributed files, no stale in_progress) | Clearing it yourself means attributing files you may not own |
   | Sole writer | `git status` shows no uncommitted/untracked work outside this stem's paths | A parallel session's files in the tree cannot be attributed for them |
   | No competing handoff | no `open`/`in-progress` checkpoint in `docs/checkpoints/INDEX.md` names this stem | That checkpoint's owner closes it, not you |

   **Never auto-run harvest** — it costs provider calls and needs a human yes; offer it and
   stop. Suggest **`/checkpoint`** only if handing off unfinished work to a future agent.

   After any `taskman plan mark-shipped`, **audit what it closed**: it matches on
   `source_ref` prefix, so follow-up tasks filed *during* the run that merely cite a brief
   path as provenance get swept to `done` with the run's own briefs. Re-open anything that
   is not actually shipped before you write the report.

Do **not** write to `docs/agents/agent-work-log.md` — plan action reports supersede it.

---

## Notes

- **plan** is read-mostly + writes small files → run it even at high context; it's the cheap insurance against losing decisions. The cost of a thin brief is paid every later chat — refuse stubs.
- **Operator summary** (what we'll do / what you'll have) is mandatory on **plan** and **ready** (and each active stem in **list**); **go** ends with the past-tense twin. Do not leave the operator with only wave tables.
- **`/mow list`** = registry + **full** waves/lanes maps for every active stem + parallel-safe matrix. **`/mow ready <stem>`** = same map for one stem **plus grill-with-docs checkpoint**. Never teaser-only previews — the operator picks with eyes on lanes.
- **Automation hooks** (grill → tdd → parallel-debug → imprint/coverage/adversarial → ship-check) are gates, not suggestions — see the table near the top of this skill.
- **Grill write-back:** `/mow ready` answers that stay only in chat are a failure mode — plan.md + briefs (+ taskman brief JSON) are what `/mow go` agents read. INDEX needs both `Grill checkpoint: done` and `Grill write-back:` before go.
- **Refer to work by name, not a bare id.** In prose an operator reads — narration, plan bodies, brief context, action reports — first mention is `"Title" (#id)`, later mentions are the name alone. A wall of `#3074, #3075, #3076` is illegible six weeks later; names read at a glance. The id never disappears, it rides *inside* the first mention. Tables keyed by id (INDEX lanes, Decisions / Specs cells, registry rows) are exempt — that is what those columns are for.
- **Decisions / Specs:** INDEX + brief headers carry **id pointers** only; materialize with `scripts/mow_hydrate_specs.py` → `dispatch/hydrated-specs.md` for subagents to **Read**. Prefer `d`/`req` over captures; tag only ids that change that lane’s Do/Don’t/Acceptance; never duplicate full decision prose into INDEX. Live taskman mid-lane is optional deepen only — not required.
- **Parallel plans:** separate stems are fine; **parallel go** is fine too when file sets are disjoint (`/mow list` shows safe pairs). Overlap is the hard gate — not a one-at-a-time lock.
- Keep each lane's file ownership disjoint within a wave. On Claude Code, `isolation: "worktree"` (go §2a) is the hard backstop that makes parallel go safe even if this slips; disjoint file-sets is what keeps merges conflict-free, not the only thing preventing a corrupted shared tree. On runtimes without that isolation, this single rule is still what makes parallel go safe in a shared tree.
- A subagent that is itself being created by a todo cannot be the one to build it — bootstrap with `code-edit`.
- This skill does not replace the plan file as source of truth; it reads it and writes `docs/plans/<stem>/dispatch/`. Promote Cursor scratch plans into `docs/plans/<stem>/plan.md`.
- Shared Work-Item format is `taskman-plan.json` — see `docs/workflow/taskman-dispatch-bridge.md` in the repo.
- Legacy aliases: `/dispatch-plan` → `/mow plan`, `/dispatch-plan decompose` → `/mow plan`, `/dispatch-plan dispatch` → `/mow go`; `/maow` → `/mow` (same modes).
