# Named work-paths — recover catalog + bug/refactor/incident entry points

**Stem:** `anew-harvest`
**Created:** 2026-09-14
**Brainstorm:** [`../../brainstorms/anew-harvest.md`](../../brainstorms/anew-harvest.md) (pursue, shape B)
**Source compared:** [engindemirog/ai-native-engineering-workspace](https://github.com/engindemirog/ai-native-engineering-workspace) (MIT; last push 2026-08-17)

## Goal

Give agents a named procedure when the work is a bug, a refactor, an incident, or the loop itself has broken — using our skill/command/hook mechanisms, not ANEW's project-local operating system.

## Why now

The comparison session produced a canvas instead of a loop. The two gaps that survived steelmanning: (1) no indexed "the loop broke, run this" catalog; (2) only `/diagnose` exists as a work-type slash command. Independent review, spec-before-code, evidence gates, and session handoff are already stronger here.

## What we'll do

1. **Ship a `recover` skill** that indexes R-01–R-12, writes the gap ramps in our voice, and points the covered ones at diagnose / tdd / checkpoint / grill.
2. **Add three thin commands** — `/fix-bug`, `/refactor`, `/incident` — that pick intensity and iron rules, then invoke existing skills. Do not clone diagnose.
3. **Hook the catalog into mow** so a third failed fix round stops coding (R-06) instead of spawning a fourth lane.
4. **Stamp the ceremony and the inventory** so work-loop, routing, and `test_repo_shape` all agree with the new skill and commands.

## What you'll have at the end

| Area | End state |
|---|---|
| Loop broken | `/recover` (or model-invoked `recover`) names a ramp and a protection rule; it does not re-teach diagnose |
| Bug / refactor / incident | A slash command exists for each; first paragraph is the iron rule |
| Stuck mow review round | The mow skill tells the orchestrator to stop after 3 fix rounds and run R-06 |
| Operator map | `work-loop.md` "What to invoke when" lists recover + the three commands, and says when *not* to mow |
| Published inventory | `python3 bin/tests/test_repo_shape.py` is green; HOW-TO-USE.agent `inventory:` line matches disk |

**In one line:** Named paths for the work types and failure modes mow does not cover, without importing ANEW.

## Decisions locked

- **Shape B, not A or C** (bs, 2026-09-14). ANEW stays inspiration. We do not copy `workflows/`, `specs/`, adapters, lite/strict flags, or `scripts/check` into this repo.
- **Keep R-01–R-12 numbering** for lineage; rewrite bodies in our voice; cite ANEW in the `recover` skill header. Do not vendor their files. Do not list ANEW in `THIRD-PARTY.md` (that file is unmodified bundled skills).
- **`recover` is a skill** (model may invoke it — no `disable-model-invocation`). `/fix-bug`, `/refactor`, `/incident` are **commands**, matching `/diagnose`.
- **One file:** `skills/recover/SKILL.md`. Not a `ramps/` directory of twelve prompts.
- **Ramp split:** full write R-03, R-04, R-06, R-07, R-08; short R-11, R-12; pointer-only R-01 (diagnose), R-02 (tdd), R-05 (diagnose / adversarial-tester), R-09 (checkpoint / wrap-up), R-10 (grill + `kind:decision`).
- **Commands point, they do not copy.** `/fix-bug` does not paste diagnose phases. `/refactor` does not paste tdd. `/incident` does not invent a production-ops stack this harness does not have.
- **Ceremony is prose, not a mode flag.** Small work still gets independent review + `/wrap-up`. `/mow` is for multi-todo or cross-file work.
- **Proposal rule** is one line in `global/CLAUDE.md` Think-before-coding, not a skill.
- **Board-less:** this repo has no root `.taskman.toml`. No `mow_plan_import`. PBI/Feature cells are `-`.
- **Do not touch** `commands/diagnose.md`, `docs/brainstorms/copilot-only-harness.md`, `taskman/`, `templates/BOOTSTRAP.md`, `templates/protocols.template.md`.
- **Wave-gate review is `llm`.** These files are agent-facing procedures (prompts/tool-calling), so `llm-sec-review` runs even though there is no stack reviewer for markdown skills.
- **R-06 counts orchestrator re-dispatches, not tdd cycles** (grill Q1, 2026-09-14). N=3 is the number of wave-gate or Integrate **fix attempts on the same finding** (fix-and-re-review that failed). A lane's internal red–green loop does not count. Different findings do not share a counter — R-06 stops further patches on *that* finding and waits for the operator; other findings may still be fixed. The fourth attempt is analysis only (spec vs plan vs code), no code.
- **R-08 writes our plan files, not ANEW's spec folders** (grill Q2, 2026-09-14). Mid-work requirement change: update `docs/plans/<stem>/plan.md` and the affected `dispatch/` briefs first (and taskman requirements when that repo has a board). No code against the new requirement until that write-back exists. Never mention `specs/active/` or `specs/done/`.
- **R-07 lists deviations and stops; it does not revert** (grill Q3, 2026-09-14). Produce a deviation list (file + why). Unapproved continuation is forbidden. Silent `checkout` / `reset` / `revert` is also forbidden — shared-checkout clobber. The operator chooses: amend the plan (write-back) or revert (they run it, or an AFK-no foreground step they can see).
- **Git-mutating ramps name the procedure and stop** (grill Q4, 2026-09-14). R-04, R-07, and R-11 may name `git revert` (never `reset --hard`, never force-push) as the procedure. They stop for the operator before running it, unless the operator is already in an AFK-no foreground session and has just approved that command. R-04's order is still revert-to-green then narrow fix — not an agent-unilateral revert.

## Grill write-back

- Q1: fix-round = same finding, orchestrator-dispatched, N=3. Locked as above.
- Q2: R-08 target = `docs/plans/<stem>/plan.md` + affected briefs (+ taskman requirements if present). No `specs/` paths.
- Q3: R-07 = deviation list + stop for operator. No silent revert.
- Q4: R-04 / R-07 / R-11 = name `git revert`, stop unless AFK-no + just-approved.

## Not yet specified

*None — every open question for this stem is sharp enough to be a scoping call, and those are in Out of scope.*

## Out of scope

- Consuming-repo single `scripts/check` contract — belongs in `templates/BOOTSTRAP.md` / protocols on a later stem, not in ai-wow's own tree (`githooks/pre-push` already is this repo's contract).
- Ship scorecard / criterion↔evidence table in action-report — process metrics, not a named work-path.
- Project-memory interview (architecture/domain/conventions templates) — ANEW bootstrap; different job from harness adoption.
- Lite/strict as a stored mode line in AGENTS.md — we rejected the flag; the prose dial is in.
- Specs `active/` → `done/` + immutable-shipped hook — would fork the board.
- Shortening `global/CLAUDE.md` to a 40-line signpost — opposite of the lessons-in-the-autoload bet.
- `copilot-only-harness` — open cousin, different itch.

## Todos

| id | title | flavor |
|---|---|---|
| recover-skill | Write `skills/recover/SKILL.md` | docs / llm |
| work-type-commands | Write `/fix-bug`, `/refactor`, `/incident` | docs / llm |
| mow-recover-hooks | Point mow's automation table at R-06 (and R-07) | docs / llm |
| docs-routing-inventory | Ceremony + routing + published inventory stamp | docs / llm |

## Key files

```
skills/recover/SKILL.md          (new)
commands/fix-bug.md              (new)
commands/refactor.md             (new)
commands/incident.md             (new)
skills/mow/SKILL.md
docs/workflow/work-loop.md
global/CLAUDE.md
README.md
HOW-TO-USE.human.md
HOW-TO-USE.agent.md
THIRD-PARTY.md                   (original-skill word count only)
bin/tests/test_repo_shape.py     (read, do not edit — it counts disk)
```
