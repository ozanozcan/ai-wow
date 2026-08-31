---
name: bs
description: Brainstorm ("bs") an idea to a durable verdict — pursue, reject, or park. Divergent front-end of the work loop, runs before grill-with-docs and mow. Every session ends written to docs/brainstorms/ — never chat-only. Triggers /bs <idea>, /bs <stem> (resume), /bs list, or an explicit "brainstorm this with me".
---

# BS — Brainstorm

The divergent front-end of the work loop. `grill-with-docs` assumes the idea is worth doing and converges on *how*; **bs owns the step before that: is this worth doing at all, and what shape would it take?**

```
idea → /bs (diverge, verdict) → pursue → /grill-with-docs → /mow plan → ready → go
                              → reject | park → recorded, done
```

| Invocation | Mode | When |
|---|---|---|
| `/bs <idea>` | **session** | Explore a fuzzy idea to a verdict. Conversational; writes as it goes. |
| `/bs <stem>` | **session (resume)** | Message matches an `open` registry row → reload that doc and continue. |
| `/bs list` | **list** | Registry view: open sessions, parked ideas + re-triggers, past verdicts. Read-only. |

**Parse:** message is exactly `list` → **list**; else **session** (resume when it names an open stem).

**The contract (the whole point):** a bs session may not end as chat only. It ends in exactly one of:

| Verdict | Means | Durable output |
|---|---|---|
| **pursue** | Worth doing — chosen shape + next step | Doc updated · registry row `pursue` · hand off to `/grill-with-docs` (or `/mow plan` if decisions are already sharp) |
| **reject** | Not doing this — and we won't re-litigate it | Doc records **why** + **what would change our mind** · registry row `reject` · taskman `decision add` when present |
| **park** | Not now — with an explicit re-trigger | Doc records the **re-trigger condition** ("revisit when Z ships") · registry row `park` · taskman `kind:decision` task when present |

A dropped session leaves an honest `open` row that `/bs <stem>` resumes — never evaporated chat. This mirrors mow's sharpness discipline ("no open question ends as chat text only"), applied one stage earlier, to whole ideas.

**Canonical store:** `docs/brainstorms/<stem>.md` + `docs/brainstorms/INDEX.md` (mirror of `docs/plans/INDEX.md`). Stems are kebab-case; a pursued idea **reuses its stem** for `docs/plans/<stem>/` so lineage is greppable.

---

## Registry — `docs/brainstorms/INDEX.md`

Create on first session if missing.

```markdown
# Brainstorms

| Stem | Idea | Created | Updated | Verdict |
|---|---|---|---|---|
| offline-mode | Offline-first sync for workouts | 2026-08-12 | 2026-08-12 | open |
```

**Verdict lifecycle:** `open` → `pursue` | `reject` | `park`. A `park` row may reopen (`/bs <stem>`) when its re-trigger fires — set it back to `open`, note why.

---

## Mode: session

### 1. Resolve stem + check history

New idea → mint a stem, add an `open` registry row. Resume → read the doc, restate where the discussion stood in two lines.

**Before exploring, check both registries** (`docs/brainstorms/INDEX.md`, `docs/plans/INDEX.md`): if this idea (or a close cousin) was already rejected, parked, or planned, **surface that verdict and its why immediately** — re-surfacing past verdicts is why bs persists anything at all. The user can still overrule; then the old doc gets a "reopened" note, not a silent duplicate.

### 2. Ground in reality

Read the code/docs/board the idea touches before opining — don't speculate about what the repo already answers (same rule as grill). Name concretely **where the idea would fit the existing structure**: files, skills, flows, plans it would touch or collide with.

### 3. Diverge

This is the anti-grill: explore before narrowing.

- Restate the idea sharper than the user said it; confirm that's the itch.
- Put **2–4 distinct shapes** on the table, including **"do nothing"** with its real cost. Steelman each, then attack each.
- Challenge: what breaks, what it costs, what it competes with, simpler-thing-that-gets-80%.
- Follow the user's lead — bs is a conversation, not a questionnaire. Your job: sharpen fuzzy language, connect to existing structure, keep the ledger.

### 4. Write as you go

Keep `docs/brainstorms/<stem>.md` current **during** the session, not in one batch at the end (grill's write-back discipline — a dropped session must lose nothing). Template:

```markdown
# <stem>: <idea in one line>

**Verdict:** open   **Created:** <date>   **Updated:** <date>

## Idea
<the itch, in the operator's words>

## Where it fits
<existing files/skills/flows it touches; overlapping plans or past brainstorms>

## Shapes considered
### A — <name>
<gist · for · against>
### Do nothing
<what skipping costs>

## Decisions so far
- <locked bullets — these feed the grill if pursued>

## Open questions
- <...>

## Verdict & why
<empty until close>
```

### 5. Converge to a verdict

When the discussion plateaus — options stop changing, objections repeat — **push for the verdict and recommend one** ("I'd pursue shape B because…", "I'd park this until X"). Do not let the session trail off. Fill `## Verdict & why`:

- **pursue** — chosen shape, the one-line why, and the next step. Prefer continuing **in this same chat** with `/grill-with-docs` (then `/mow plan`) so the hot context feeds the grill; `## Decisions so far` is its seed.
- **reject** — why, plus **what would change our mind** (the condition that reopens it).
- **park** — the re-trigger condition, stated so a future session can test it ("revisit when Z ships", not "maybe later").

Update the registry row. Then persist to taskman (below).

### 6. Taskman (agent runs CLI — user does not)

When the repo has `.taskman.toml` + `taskman/`:

```bash
# reject — so the board carries the "don't" and mow surfacing can cite it:
taskman decision add "Don't <idea>" --why "<why>" \
  --implications "reopen if: <condition>" --source docs/brainstorms/<stem>.md -t <area>

# park — a sharp re-trigger is a decision task, so the board resurfaces it:
taskman task add "<re-trigger question>" \
  -t kind:decision,brainstorm:<stem> --source docs/brainstorms/<stem>.md
```

**pursue** writes nothing to the board here — the grill and `/mow plan` own decisions/requirements/tasks, and duplicating them from bs would fork the source of truth. Taskman absent → the doc + registry are the record; say sync is unavailable. Tell the user what you wrote (ids), don't hand them a CLI checklist.

---

## Mode: list

1. Print `docs/brainstorms/INDEX.md`, sorted `open` → `park` → `pursue` → `reject`.
2. For each `open` row: idea + last-updated + the top open question. For each `park` row: idea + re-trigger condition — **flag any re-trigger that looks already met**.
3. Offer: `/bs <stem>` to resume or reopen. Change nothing on disk.

---

## Boundaries

- **bs is not grill.** No SHALL/scenario drafting, no briefs, no per-file acceptance. If the user starts locking implementation decisions rapidly, say so and hand off to `/grill-with-docs`.
- **bs never creates `docs/plans/<stem>/`** — that's `/mow plan`'s write, after a grill.
- **No implementation code.** Reading code to ground the discussion: yes. Writing it: no.
- One idea per session — "and also" means a second stem.
