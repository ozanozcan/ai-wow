---
name: grill-with-docs
description: Stress-test a plan or task before building — one question at a time, recommended answer each time, updates CONTEXT.md and ADRs inline. Use via /grill-with-docs with the plan or task in the message. Works for backlog items, handoff tasks, or ad-hoc ideas.
disable-model-invocation: true
---

# Grill With Docs

Stress-test a plan before implementation. Same discipline as the old **`grill-me`** skill, plus domain doc updates.

## How to invoke

Always user-triggered:

```
/grill-with-docs [task or plan description]
```

Examples:

```
/grill-with-docs Add rest timer to buddy page
/grill-with-docs Task 2 from tasks.mdc — video thumbnails for exercises
/grill-with-docs Review the plan in docs/plans/foo/plan.md before we build
```

If no task is given, read **`handoff.md`** `## Next task`. If that's empty, read **`.cursor/rules/tasks.mdc`** and ask which backlog item to grill.

## Non-negotiable behavior (consistency)

1. **One question at a time** — wait for user response before the next question.
2. **Recommend an answer** before each question — "I'd suggest X because Y. Do you agree?"
3. **Explore the codebase** when a question can be answered from code — don't ask what code already shows.
4. **Do not write implementation code** during grilling — decisions and docs only.
5. **End with a short locked-decisions summary** — bullet list the user can paste into a plan or handoff.
6. **Lock durable behavior as SHALL + scenario** — not only task titles. When a decision is product behavior that must stay true after the work ships, draft it as a living-spec requirement (see below). The agent writes it to taskman when the repo has taskman; the user does not run CLI.

## Interview loop

For each aspect of the plan (behavior, files, edge cases, mobile, permissions, data model):

- State your recommended answer
- Ask one focused question
- Wait for feedback
- **Write the locked answer to durable docs immediately** (do not batch "write everything at the end" — a dropped session loses chat-only locks)
- Then ask the next question

### When invoked from `/mow ready` (or against `docs/plans/<stem>/`)

Write-back target is the **mow package on disk**, not only CONTEXT/ADR:

1. After each accepted answer → patch `docs/plans/<stem>/plan.md` (`## Decisions locked` / `## Grill write-back`).
2. Patch every affected `docs/plans/<stem>/dispatch/NN-*.md` brief (Context, Acceptance, Do NOT, Goal). Kill hedges the answer superseded.
3. Taskman `decision add` / `requirement add|modify` when the repo has taskman.
4. For a **ui-tagged lane**, offer once to write `docs/plans/<stem>/dispatch/mockups/<lane>.html` — plain HTML at the project's target viewport — and point that lane's Acceptance at it when the operator approves. Operator may decline; it is an option, never a gate (see mow skill ready mode).
5. Only after the full grill: help mow set INDEX `Grill checkpoint: done` **and** `Grill write-back:` (see mow skill ready mode). Never claim the grill is done if plan/briefs were not updated.

Standalone `/grill-with-docs` (no mow stem): still update CONTEXT.md / ADRs per below; if a plan path was named in the invoke, treat it like the mow case.

Cover at minimum:

- Desired behavior (happy path + failure modes) — as **SHALL + GIVEN/WHEN/THEN** when durable
- Files / components involved
- Edge cases and blockers first
- Mobile: how does this work at ~390px portrait?
- Domain terms: align with `CONTEXT.md` vocabulary

## Living-spec discipline (OpenSpec-style, taskman-backed)

**Task** = work to do. **Requirement** = what the system SHALL keep doing after that work is done.

During the grill, keep a running **requirement draft list** (in working memory):

| Field | Rule |
|---|---|
| Title | Short name for the behavior |
| Statement | One keyword: `SHALL` / `MUST` / `SHOULD` / `MAY`. If it needs "and also," split into two requirements |
| Scenario | At least one `name` + GIVEN / WHEN / THEN — prefer the edge case you'd be upset to see broken |
| Feature | Board Feature id when known (e.g. Feature #16); ask once if unclear and taskman is present |

Do **not** invent requirements for pure refactors with no behavior change. Do invent them for auth, tenancy, API contracts, data invariants, and user-visible rules locked in this grill.

## Domain awareness

During exploration, read existing documentation:

### File structure

```
/
├── CONTEXT.md
├── docs/adr/
└── src/ (or app modules)
```

If `CONTEXT-MAP.md` exists, follow it for multi-context repos.

Create `CONTEXT.md` and `docs/adr/` lazily — only when there is something to write.

### During the session

**Challenge glossary conflicts** — if the user's term conflicts with `CONTEXT.md`, call it out immediately.

**Sharpen fuzzy language** — propose precise canonical terms.

**Stress-test with scenarios** — invent edge-case scenarios that force precise boundaries.

**Cross-reference code** — if the user states how something works, verify against code.

**Update CONTEXT.md inline** — when a term is resolved, update immediately (glossary only, no implementation detail). Format: [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md) if present.

**Offer ADRs sparingly** — only when hard to reverse, surprising without context, and result of a real trade-off. Format: [ADR-FORMAT.md](./ADR-FORMAT.md) if present.

## After grilling

### A. Summarize for the user

```markdown
## Locked decisions
- ...

## Living-spec requirements (drafted)
- <title> — The system SHALL … | Scenario: …

## Open questions
- <sharp> — raised as a decision task (see B)
- <fuzzy> — filed to the plan's ## Not yet specified

## Suggested next step
/mow plan   # agent writes docs/plans/<stem>/dispatch/ + import; or /architect if complex
```

**Every open question gets a durable home — none may end as chat text only.** Split the list with the sharpness test: *can you state the question precisely now — **not** answer it now?*

- **Sharp** → a decision task on the board (commands in **B**), **even if it is blocked and unanswerable today**. Link it to whatever it blocks so that work drops out of "what's next" until the question is answered.
- **Not sharp** → one line in the plan's `## Not yet specified` section. Do not pre-slice it into task-sized pieces; one fog line may later graduate into several tasks, or none.

If the question turns out to sit past the plan's goal, it is neither — it belongs in `## Out of scope`, which never graduates.

### B. Persist to taskman (agent runs CLI — user does not)

If the repo has `.taskman.toml` + `taskman/`, **you** (the agent) run these from project root before ending. Do not ask the user to paste commands.

```bash
.venv/bin/python -m taskman capture add --kind grill --summary "…" [--body "…"] [--source "…"]
.venv/bin/python -m taskman decision add "…" --why "…" [--alternatives "…"] [--implications "…"] [--source "…"] \
  -t area,path:<glob>
# Tags (d#852): plain area tags match lane Review flags / area tags; path:<glob>
# matches Files in scope (fnmatch). Prefer tagging at add time so mow preflight
# can surface candidates per lane.

# For each drafted durable requirement:
.venv/bin/python -m taskman requirement list --feature <id>   # skip / modify if duplicate
.venv/bin/python -m taskman requirement add "<title>" --feature <id> \
  --statement "The system SHALL …" \
  --scenario "name|given|when|then" [--pbi <id>]

# For each SHARP open question — the title IS the question:
.venv/bin/python -m taskman task add "<the question>" -t kind:decision[,plan:<stem>] \
  [--notes "<why it matters / what it blocks>"] [--source "…"]
.venv/bin/python -m taskman task link <build-task-id> --blocked-by <decision-id>   # if it blocks work
```

Rules:
- Prefer `.venv/bin/python -m taskman`. Never write Postgres directly.
- A **decision task** is a question, not work: its title is the question, it is resolved by an answer rather than a diff, and its `blocked_by` edges are what stop dependent build work being recommended. Resolve it with `task set <id> --notes "Answer: …"` → `decision add "<answer>" --why "…"` → `task move <id> --status done`, then write the answer into the plan's `## Decisions locked`. If it turns out to sit past the plan's goal, `task move <id> --status disabled` + tag `scope:out` — **not** `done`, which would falsely claim the work happened.
- Before `requirement add`, always `requirement list --feature <id>` — `modify` if the behavior already exists.
- If Feature id is unknown and the grill was about existing board work, resolve via `taskman board` / `feature list`.
- If taskman is absent: keep the living-spec list in the summary only; say sync is unavailable.
- Tell the user what you wrote (capture/decision/requirement ids). Do **not** dump a "run these yourself" checklist as the primary path.

### C. Do not start coding

Do not start coding unless the user explicitly asks after the summary. Prefer suggesting `/mow plan` so briefs + `plan from-decisions` happen in the same hot context.
