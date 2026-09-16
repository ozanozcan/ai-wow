# recover-skill: Write the recover catalog

**Role:** code-edit   **Wave:** 1   **AFK:** yes   **Background:** yes

**Decisions / Specs (pointers):** `-`

## Goal

`skills/recover/SKILL.md` exists, is invocable as `/recover`, indexes R-01–R-12, and a blind agent can pick a ramp without reading ANEW.

## Context & decisions (only what this todo needs)

- ANEW's distinctive artifact is the indexed failure catalog, not the feature workflow. We already have diagnose, tdd, checkpoint, wrap-up, grill. The skill is a **map plus the missing ramps**.
- Keep R-01–R-12 numbering for lineage. Header cites [ANEW](https://github.com/engindemirog/ai-native-engineering-workspace) as inspiration. Rewrite bodies in our voice — do not paste their prompt files.
- `recover` is a **skill** with YAML frontmatter (`name: recover`, `description:` that mentions `/recover` and R-01–R-12). **Do not** set `disable-model-invocation` — the point is the model can reach for it when a loop is stuck.
- One file: `skills/recover/SKILL.md`. No `ramps/` subdirectory.
- Pointer-only ramps (name the existing skill, one-line "when", do not duplicate the procedure): R-01 → `/diagnose`; R-02 → `tdd` (code vs test vs spec; never weaken/skip); R-05 → diagnose / `adversarial-tester` (repro before fix); R-09 → `/checkpoint` + `/wrap-up`; R-10 → `/grill-with-docs` + `kind:decision` task.
- Full ramps (situation, steps, **protection rule**): R-03 flaky (make deterministic; no skip/retry; evidence is several consecutive greens — house lesson L43); R-04 regression (order is revert-to-green, then narrow fix + permanent regression test. **Name** `git revert` — never `reset --hard` / force-push. **Stop for the operator** before running it, unless already AFK-no and they just approved that command); R-06 fix-round limit (**N=3 counts only orchestrator-dispatched fix attempts on the same finding** — wave-gate or Integrate re-review that failed. A lane's internal tdd loop does not count. Different findings do not share a counter. After 3, stop coding on that finding; verdict is spec vs plan vs code; human decides; other findings may still be patched); R-07 plan drift (deviation list vs the stem's plan/briefs — file + why. **Stop for the operator.** Do not `checkout` / `reset` / `revert` the drifted files yourself. Operator picks: plan amendment write-back, or a revert they run / watch as AFK-no. Unapproved continuation is forbidden); R-08 spec changed mid-work (update `docs/plans/<stem>/plan.md` and affected `dispatch/` briefs first — and taskman requirements when that repo has a board — then a delta plan; **no code** until that write-back exists. Never `specs/active/` or `specs/done/`).
- Short ramps: R-11 rollback (procedure is `git revert`, never history rewrite / force-push — `guard-destructive` already asks. Same stop-for-operator rule as R-04/R-07 unless AFK-no + just-approved); R-12 perf miss (measure first, one change, re-measure the same way; point at `complexity-audit`).
- Modes: `/recover` or `/recover list` prints the table; `/recover R-06` (or a named situation) runs that ramp. If the user describes a stuck loop without a code, pick the ramp and say the code.
- This repo is board-less. The skill must still work in a product repo that has taskman (R-10 may raise a decision task) and in one that does not (then the ramp writes the decision into the plan file only).
- Lane C will point mow's automation table at R-06/R-07. Use those exact codes so the pointer resolves.

## Files in scope

- `skills/recover/SKILL.md` (create)

## Depends on

- none

## Do NOT

- Do not edit `commands/diagnose.md`, `skills/tdd/`, `skills/checkpoint/`, `skills/wrap-up/`, `skills/grill-with-docs/`, or `skills/mow/SKILL.md` (lane C owns mow).
- Do not copy ANEW prompt files or add ANEW to `THIRD-PARTY.md`.
- Do not create twelve ramp files.
- Do not set `disable-model-invocation`.
- Do not invent SHALL/requirements for product code — this is a harness procedure.
- Do not define an R-06 round as a lane's internal red–green cycle.
- Do not mention `specs/active/` or `specs/done/` in any ramp. R-08's write-back target is `docs/plans/<stem>/` (and taskman requirements when present).
- Do not have R-07 (or any ramp) silently `git checkout` / `reset` / `revert` in a shared tree. Deviation list + stop. R-04 and R-11 name `git revert` and stop unless AFK-no + just-approved.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- Prefer **`git commit -- <paths>`** over `git add` + `git commit`. New files must be `git add`-ed by name first, then committed with `-- <paths>`.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.
- Before commit while parallel lanes are active, run `git status` and confirm only intended paths are staged.

## Acceptance check

- The skill SHALL expose a table of R-01 through R-12 where each covered ramp names an existing skill/command and each gap ramp states a protection rule that forbids test-silencing or silent plan mutation.
- GIVEN three failed orchestrator fix attempts on the same wave-gate finding WHEN the agent loads R-06 THEN it stops writing code for that finding, analyses spec vs plan vs code, and does not treat a lane's internal tdd cycles as rounds.
- GIVEN a requirement change mid-build WHEN the agent runs R-08 THEN it patches `docs/plans/<stem>/plan.md` and affected briefs before any new code, and the skill text does not contain `specs/active` or `specs/done`.
- GIVEN a lane that edited a file not in any brief WHEN the agent runs R-07 THEN it produces a deviation list and stops; it does not run `git checkout`, `git reset`, or `git revert` itself.
- GIVEN R-04 or R-11 WHEN git must move THEN the ramp names `git revert` and forbids `reset --hard` / force-push, and it does not run that command until the operator has approved (or is already AFK-no and just approved).
- Verify: `test -f skills/recover/SKILL.md` and `grep -E '^\\| R-0[1-9]|^\\| R-1[0-2]' skills/recover/SKILL.md` lists twelve codes; `grep disable-model-invocation skills/recover/SKILL.md` is empty; `grep -i 'orchestrator' skills/recover/SKILL.md` hits in the R-06 section; `grep -E 'specs/active|specs/done' skills/recover/SKILL.md` is empty.

## QA contract

- File exists with YAML `name: recover`.
- Twelve ramp codes present.
- Pointer ramps contain the target skill/command name (`diagnose`, `tdd`, `checkpoint`, `grill`).
- Gap ramps contain the word `PROTECTION` or an equivalent bold protection rule.
- `grep -E 'specs/active|specs/done' skills/recover/SKILL.md` is empty.

## Toolkit

- Invoke: skill:docs (house voice, TOC if the file is long enough to need one)
- Invoke: agent:llm-sec-review (wave gate; this is an agent-facing procedure)

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: none pointed

**Also write that block to** `docs/plans/anew-harvest/dispatch/verification/01-recover-skill.md`. Chat is not a record. Create the `verification/` folder if missing.
