# Dispatch index — Publish hygiene

Source plan: [`../plan.md`](../plan.md)

## What we'll do

1. **Repoint the three `wrapup_reconcile` references at the entry point that exists**, so the first
   instruction a work-PC session receives is one it can follow.
2. **Make the copy-install diagnosis correct** — a stale copy reports that it is stale, not that it
   was never linked.
3. **Stop asserting an agent we do not ship**, and gitignore the worktree directory so isolation
   stops depending on the orchestrator remembering.
4. **Write the board-less decision down as a decision**, so `Board sync: n/a` reads as a choice
   rather than an omission.

## What you'll have at the end

| Area | End state |
|---|---|
| First session on a work-PC clone | The SessionStart notice names no command the clone cannot run — board present, it names the gate; board-less, it says nothing about wrap-up, and still writes its marker |
| `/wrap-up` in a board-less repo | No reference to a missing `scripts/` path or a repo-root `.venv/` survives in any shipped file |
| Drifted copy install | `ai-sync status` distinguishes "copied but stale" from "never linked"; a regression test pins both |
| Agent roster | No table asserts an agent absent from `agents/` |
| Worktrees | `.claude/worktrees/` is gitignored; `git status` is clean immediately after a worktree run |
| Board posture | The docs state ai-wow is deliberately board-less and why, with the revisit condition named |

**In one line:** Make every instruction the harness ships followable in a fresh clone, and every
claim it makes about itself true.

## Waves

- **Wave 1 (parallel):** A ‖ B ‖ C — A and B backgrounded in isolated worktrees; **C runs foreground**
  (it inspects a tree holding a peer session's uncommitted work).
- **Wave 2 (after wave 1, foreground):** Z — depends on A's shipped wording.

Each wave ends with a **review gate** before the next starts.

## Lanes

| Lane | Todos (in order) | PBI / Feature | Files owned | Role | Model | Review flags | AFK | Background | Decisions / Specs | Brief |
|---|---|---|---|---|---|---|---|---|---|---|
| A | reference honesty | - / - | `hooks/session-start-marker.py`, `hooks/tests/test_session_start_marker.py` (new), `githooks/pre-push`, `skills/wrap-up/SKILL.md`, `skills/mow/SKILL.md`, `skills/checkpoint/SKILL.md` | code-edit | inherit | - | yes | yes | `-` | [01-reference-honesty.md](01-reference-honesty.md) |
| B | copy-drift diagnosis | - / - | `bin/ai-sync`, `bin/tests/test_ai_sync_status.py` | code-edit | inherit | - | yes | yes | `-` | [02-copy-drift-diagnosis.md](02-copy-drift-diagnosis.md) |
| C | tree hygiene | - / - | `.gitignore`, `docs/session-reports/2026-08-21-…-mow-go-and-harness-fixes.md` | shell | inherit | - | no | no | `-` | [03-tree-hygiene.md](03-tree-hygiene.md) |
| Z | board posture | - / - | `HOW-TO-USE.human.md` | code-edit | inherit | - | no | no | `-` | [04-board-posture.md](04-board-posture.md) |

`PBI / Feature` is `-` throughout: this repo is deliberately board-less (see `plan.md` →
Decisions locked), so no taskman rows exist and no import gate runs.

`Review flags` are `-` throughout. No roster agent owns this diff — it is shell scripting, skill
markdown, one hook string and one guide section. The wave gate still reads every lane's
`## Verification` block against its QA contract; it simply spawns no stack reviewer.

## Conflicts check

**Within this plan:** no two same-wave lanes share a file.

- Wave 1: A owns `hooks/` + `hooks/tests/` + `githooks/` + `skills/`, B owns `bin/`, C owns `.gitignore` — disjoint. (A's `githooks/pre-push` and `hooks/tests/` ownership was added by grill Q3; no other lane touches either.)
- Wave 2: Z owns `HOW-TO-USE.human.md`, touched by no other lane.

**Across plans:** `docs/plans/INDEX.md` lists no other `planned`/`running`/`paused` stem at the
time of writing. **However — a live peer session is planning `taskman-no-db` in this same
checkout** (confirmed via session listing, 2026-09-01). Its dispatch folder does not exist yet, so
a real `Files owned` comparison is impossible. This plan was scoped defensively to avoid the paths
that stem will obviously own:

| Path | Owner | Why this plan stays out |
|---|---|---|
| `taskman/**` | `taskman-no-db` | The storage rewrite's whole surface |
| `README.md` | `taskman-no-db` | Line 161 asserts Postgres outright |
| `HOW-TO-USE.agent.md` | `taskman-no-db` | Invariant I10, "Never propose SQLite" |

**Before `/mow go` on either stem, re-run the cross-plan overlap check** — `HOW-TO-USE.human.md`
(owned here by lane Z) is the most likely genuine collision, since the storage stem may want §6's
bootstrap steps. Sequential execution is safe; **parallel go is not, until that is checked.**

**Grill checkpoint:** done 2026-09-01
**Grill write-back:** plan.md ✓ (4 answers in `## Decisions locked`) · briefs: 01-reference-honesty,
02-copy-drift-diagnosis, 03-tree-hygiene, 04-board-posture · INDEX lanes A + C `Files owned`
updated · taskman: n/a (board-less by decision)

**Grill findings worth carrying:** Q1 caught that this plan's *own* replacement command
(`python -m taskman wrapup gate`) fails on a fresh clone — the lane would have shipped the same
class of defect it was written to remove. Q3 caught that lane A's new test had no owner for
`githooks/pre-push`, so it would have shipped unregistered.
