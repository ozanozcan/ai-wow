# mow compact template — Pi-style session handoff

**Status:** reference · **Audience:** operator + mow skill (harvest / grill write-back)

Pi compacts long sessions into a fixed shape before context rolls off. mow uses the same sections so origin-chat harvest and `/mow ready` write-back produce predictable input for `docs/plans/<stem>/plan.md`, dispatch briefs, and taskman — not ad-hoc bullets in chat memory.

**When to fill:** at the end of a grilling/planning chat (before `/mow plan`), and again during `/mow ready` write-back when decisions or scope changed since the plan was written.

Copy the block below into the chat (or session note) and fill each section. One line per item is enough; link files by path.

---

## Goal

<!-- What this plan or slice is trying to achieve. One paragraph max. -->

**How mow uses this:** Becomes plan intent in `docs/plans/<stem>/plan.md` and the Operator summary at the top of dispatch briefs.

---

## Constraints & Preferences

<!-- Hard limits, stack choices, "do not" items, AFK/background prefs, review gates. -->

**How mow uses this:** Feeds `## Do NOT`, `## Context & decisions`, and lane AFK/background flags when `/mow plan` expands todos into briefs.

---

## Progress

### Done

<!-- Completed items from this session. -->

### In Progress

<!-- Started but not finished. -->

### Blocked

<!-- Waiting on a decision, dependency, or external input. -->

**How mow uses this:** Maps to taskman todo statuses (`done`, `in_progress`, `blocked`) and wave ordering when `plan from-decisions` or `/wrap-up` syncs the board.

---

## Key Decisions

<!-- Locked choices with brief rationale. Prefer SHALL-style when testable. -->

**How mow uses this:** Becomes `## Decisions locked` in `plan.md`; durable rows via `taskman decision add "…" --why "…"`. Grill write-back must not contradict these without an explicit unlock.

---

## Not yet specified

<!-- In-scope questions still too fuzzy to phrase — the plan's fog, not its answers.
     Sharpness test: can you state the question precisely now — **not** answer it now.
     If you can state it precisely, it is not fog: raise it as a decision task
     (`task add "<the question>" -t kind:decision,plan:<stem>`) and leave it out of here.
     Always write this heading. When there is no fog, write a single italic line:
     *None — every open question is sharp enough to be on the board.*
     An absent section means "this compact predates the convention", not "there was no fog". -->

**How mow uses this:** Becomes `## Not yet specified` in `plan.md`. `/mow ready`'s grill checkpoint re-reads it and **graduates** anything that has since sharpened into a `kind:decision` task, deleting the graduated line so it lives in exactly one place. Never lands in `## Key Decisions` — fog is the absence of a decision.

---

## Out of scope

<!-- What this run deliberately will not do — a scoping act, not an open question.
     One line each: gist + why + link where one exists.
     These never graduate onto the board; an out-of-scope item comes back only by an
     explicit later decision to take it on.
     Always write this heading. When nothing was ruled out, write a single italic line:
     *None — nothing was ruled out of this slice.*
     An absent section means "this compact predates the convention", not "nothing was excluded". -->

**How mow uses this:** Becomes `## Out of scope` in `plan.md` and seeds lane `## Do NOT` items when `/mow plan` expands todos into briefs. Stays out of `## Decisions locked` — a scoping call is not a locked decision. Board equivalent: `task move <id> --status disabled` plus the `scope:out` tag, never `done`.

---

## Next Steps

<!-- Ordered actions the next chat or `/mow go` should take. -->

**How mow uses this:** Seeds dispatch todo list and `## Goal` / acceptance checks when `/mow plan` splits work into lane briefs.

---

## Critical Context

<!-- Facts, paths, IDs, or edge cases the next agent must not re-discover. -->

**How mow uses this:** Copied into brief `## Context & decisions (only what this todo needs)` — keep each lane's slice minimal.

---

## Read files

<!-- Paths the session relied on (specs, ADRs, prior plans). -->

```
<!-- e.g. docs/domain.md, docs/plans/foo/plan.md -->
```

**How mow uses this:** Informs hydrated specs and brief background; operators paste into `<read-files>` style tags during harvest. Not every path becomes `## Files in scope` — only files a lane may edit.

---

## Modified files

<!-- Paths touched or proposed in this session (even if uncommitted). -->

```
<!-- e.g. workouts/service.py, docs/plans/foo/dispatch/01-foo.md -->
```

**How mow uses this:** Cross-check against INDEX **Files owned** and each brief's `## Files in scope` before `/mow go`; overlap across same-wave lanes is a preflight failure.
