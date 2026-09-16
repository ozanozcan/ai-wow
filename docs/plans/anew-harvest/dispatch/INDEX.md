# Dispatch index — Named work-paths

Source plan: docs/plans/anew-harvest/plan.md

## What we'll do

1. **Ship a `recover` skill** that indexes R-01–R-12, writes the gap ramps in our voice, and points the covered ones at diagnose / tdd / checkpoint / grill.
2. **Add three thin commands** — `/fix-bug`, `/refactor`, `/incident` — that pick intensity and iron rules, then invoke existing skills. Do not clone diagnose.
3. **Hook the catalog into mow** so a third failed fix round stops coding (R-06) instead of spawning a fourth lane.
4. **Stamp the ceremony and the inventory** so work-loop, routing, and `test_repo_shape` all agree with the new skill and commands.

## What you'll have at the end

| Area | End state |
|---|---|
| Loop broken | `/recover` names a ramp and a protection rule; it does not re-teach diagnose |
| Bug / refactor / incident | A slash command exists for each; first paragraph is the iron rule |
| Stuck mow review round | The mow skill tells the orchestrator to stop after 3 fix rounds and run R-06 |
| Operator map | `work-loop.md` lists recover + the three commands, and says when *not* to mow |
| Published inventory | `python3 bin/tests/test_repo_shape.py` is green |

**In one line:** Named paths for the work types and failure modes mow does not cover, without importing ANEW.

## Waves

- **Wave 1 (parallel, AFK):** A ‖ B ‖ C
- **Wave 2 (after wave 1, AFK):** Z

Each wave ends with a **review gate** (see go mode) before the next starts.

## Lanes

| Lane | Todos (in order) | PBI / Feature | Files owned | Role | Model | Review flags | AFK | Background | Decisions / Specs | Brief |
|---|---|---|---|---|---|---|---|---|---|---|
| A | recover-skill | - / - | `skills/recover/SKILL.md` | code-edit | inherit | llm | yes | yes | `-` | 01-recover-skill.md |
| B | work-type-commands | - / - | `commands/fix-bug.md`, `commands/refactor.md`, `commands/incident.md` | code-edit | inherit | llm | yes | yes | `-` | 02-work-type-commands.md |
| C | mow-recover-hooks | - / - | `skills/mow/SKILL.md` | code-edit | inherit | llm | yes | yes | `-` | 03-mow-recover-hooks.md |
| Z | docs-routing-inventory | - / - | `docs/workflow/work-loop.md`, `global/CLAUDE.md`, `HOW-TO-USE.human.md`, `HOW-TO-USE.agent.md`, `README.md`, `THIRD-PARTY.md`, `bin/tests/test_repo_shape.py`, `templates/copilot-instructions.template.md` | code-edit | inherit | llm | yes | yes | `-` | 04-docs-routing-inventory.md |

`PBI / Feature` is `-` throughout: this repo is deliberately board-less, so no taskman rows exist and no import gate runs.

`Review flags`: `llm` — these files are agent-facing procedures. Wave gate runs `llm-sec-review`. No stack reviewer owns markdown skills.

## Conflicts check

Confirm: no two same-wave lanes share a file.

- Wave 1: A owns `skills/recover/`, B owns three new `commands/*.md` (not `diagnose.md`), C owns `skills/mow/SKILL.md` — disjoint.
- Wave 2: Z owns published docs + `global/CLAUDE.md` + `work-loop.md`. Brief also *may* touch `bin/tests/test_repo_shape.py` and `templates/copilot-instructions.template.md` only if a count sentence forces it; no wave-1 lane owns those.

**Across plans:** `docs/plans/INDEX.md` has no other `planned`/`running`/`paused` stem.

**Grill checkpoint:** done 2026-09-14
**Grill write-back:** plan.md ✓ · briefs: 01-recover-skill.md, 02-work-type-commands.md, 03-mow-recover-hooks.md · taskman: n/a

**Action report:** [`../action-report.md`](../action-report.md)
