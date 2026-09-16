# mow-recover-hooks: Stop the fourth fix round

**Role:** code-edit   **Wave:** 1   **AFK:** yes   **Background:** yes

**Decisions / Specs (pointers):** `-`

## Goal

The mow skill's automation-hooks table tells the orchestrator to stop after three fix rounds on the same finding and run recover R-06 (analysis only). Plan-drift mid-go points at R-07. No fourth patch lane by habit.

## Context & decisions (only what this todo needs)

- `skills/mow/SKILL.md` already has an **Automation hooks (mid-wave — not advisory)** table near the top. That is the insertion point — a guarantee implemented only in recover would be a suggestion at go time.
- Existing row to sit next to: **"go fix round (closing gate findings)"** (mutation-check every guard). Add a sibling row, do not overload that one.
- New row (wording up to you, meaning locked): when the **same finding** has already had **3 orchestrator-dispatched fix attempts** in this run (wave-gate or Integrate fix-and-re-review that failed), do **not** dispatch a fourth fix lane for that finding. Invoke `recover` R-06 (stop coding on that finding; spec vs plan vs code; wait for the operator). Other findings keep their own counters and may still be patched. Owner: orchestrator. A lane's internal tdd loop is not a round.
- Second row or a clause on go mid-build: if the change set has drifted off the stem's plan/briefs (files or behavior not in any brief), invoke R-07 before continuing. R-07 **lists deviations and stops for the operator** — it does not revert files. Do not silently amend the plan in chat. Do not `checkout` / `reset` the drifted paths.
- R-06's N=3 is locked in the recover skill (lane A). This lane only *points*. If A's file is not in your worktree, still use the code `R-06`.
- Do not invent a scripted counter in `taskman.mow.closeout`. This stem is prose in the mow skill. A later stem may mechanize it; that is out of scope here (see plan.md Out of scope).
- Match the table's existing voice and column layout (When / Auto-invoke / Owner). Do not reformat the whole table.
- A one-line mention in go §2b Review gate (triage / fix-now) that the third failed Critical-fix round is R-06, not another foreground patch, is in scope if it is a small insert. Do not rewrite §2b.

## Files in scope

- `skills/mow/SKILL.md`

## Depends on

- none

## Do NOT

- Do not edit `skills/recover/` (lane A).
- Do not edit `commands/` (lane B).
- Do not add a Python closeout check for fix-round count.
- Do not retitle mow, change modes, or "improve" adjacent hook rows.
- Do not set `disable-model-invocation` on anything.
- Do not count a lane's internal tdd / red–green cycles toward N=3.
- Do not tell the orchestrator to revert drifted files. R-07 is list + stop.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- Prefer **`git commit -- <paths>`** over `git add` + `git commit`.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.
- Before commit while parallel lanes are active, run `git status` and confirm only intended paths are staged.

## Acceptance check

- The mow skill SHALL instruct the orchestrator to refuse a fourth **orchestrator-dispatched** fix attempt on the same finding and to invoke recover R-06 instead; other findings are unaffected.
- GIVEN a wave-gate Critical that has already been patched and re-reviewed three times in this run WHEN the orchestrator reads the automation-hooks table THEN it finds an R-06 row whose owner is the orchestrator and whose action is stop-coding on that finding, not "dispatch another lane", and that does not mention a lane's internal tdd loop as a round.
- Verify: `grep -n 'R-06' skills/mow/SKILL.md` hits the automation-hooks table (near the top of the file, not only a buried note).

## QA contract

- `grep R-06 skills/mow/SKILL.md` and `grep R-07 skills/mow/SKILL.md` both hit.
- The new row(s) sit in the Automation hooks table (the one whose heading contains `Automation hooks`).
- `python3 -c "from pathlib import Path; t=Path('skills/mow/SKILL.md').read_text(); assert t.count('# MOW')>=1"` — file still parses as the mow skill (heading intact).

## Toolkit

- Invoke: agent:llm-sec-review (wave gate; agent-orchestration procedure)

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: none pointed

**Also write that block to** `docs/plans/anew-harvest/dispatch/verification/03-mow-recover-hooks.md`. Chat is not a record. Create the `verification/` folder if missing.
