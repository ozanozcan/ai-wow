# work-type-commands: /fix-bug, /refactor, /incident

**Role:** code-edit   **Wave:** 1   **AFK:** yes   **Background:** yes

**Decisions / Specs (pointers):** `-`

## Goal

Three slash commands exist next to `/diagnose`. Each is a thin workflow: iron rule, then point at existing skills. A blind agent running `/fix-bug` does not get a second copy of diagnose.

## Context & decisions (only what this todo needs)

- Precedent: `commands/diagnose.md` is body-only (no YAML required). Match that shape unless the runtime in this repo's other commands shows otherwise — diagnose is the only one, so **body-only, first line is the job**.
- `/fix-bug` — iron rule: **no fix before a failing reproduction**. Then: `tdd` (red test first); if there is no loop yet, `/diagnose` phase 1. After the fix, suite green; the repro test stays. If the fix caused a new failure, `/recover R-04` (revert-to-green **order**; stop for the operator before `git revert` unless AFK-no + just-approved). Independent review of the fix diff (builder ≠ reviewer). Small bugs do not need `/mow`. Behavior-changing fixes are features — say so and point at `/grill-with-docs` / `/mow`, do not silently widen.
- `/refactor` — iron rule: **structure changes, behavior does not**. Baseline: the project's test command is green before starting; if the area has no tests, write characterization tests first (pin current behavior, warts included). Plan boundaries: what improves, what is untouched, the sentence "no observable behavior change". Mixed refactor+feature is forbidden — split. Zero test-expectation edits to "make the refactor green" (that is a feature). Perf-sensitive: R-12. Drift off the plan: R-07 (list + stop; do not revert files from the command).
- `/incident` — iron rule: **stabilize first, learn second**. Agents do not touch production unilaterally — human executes or explicitly approves. Prefer revert/flag/rate-limit (R-11: name `git revert`, stop unless AFK-no + just-approved) over a clever hotfix. Capture evidence before it evaporates. Then run `/fix-bug` (the incident is not done at mitigation). Postmortem is short and written: timeline, cause, **which gate would have caught it**. Outcomes land in the project's durable ledger (`LESSONS.md` if the repo has one, else `docs/`). This harness has no production; write the command so it works in a *product* repo that happens to use this harness.
- Do not create `/recover` as a command — that is the skill in lane A. Commands may say "if the loop is stuck, `/recover R-xx`".
- Lane A is parallel and will create `skills/recover/SKILL.md`. You may cite `/recover R-04` etc. by code; do not wait for A's file to exist on disk in your worktree if you are isolated — the codes are locked in `plan.md`.

## Files in scope

- `commands/fix-bug.md` (create)
- `commands/refactor.md` (create)
- `commands/incident.md` (create)

## Depends on

- none (codes locked in plan.md; recover skill is a parallel lane)

## Do NOT

- Do not edit `commands/diagnose.md`.
- Do not paste diagnose's nine-phase list into `/fix-bug`.
- Do not paste the tdd skill into `/refactor`.
- Do not add YAML frontmatter unless diagnose grows it — stay consistent.
- Do not touch `skills/` (A owns recover, C owns mow).
- Do not mention employer/product names. Keep commands stack-agnostic.
- Do not tell `/fix-bug` or `/incident` to run `git revert` itself. Point at R-04 / R-11; those ramps stop for the operator.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- Prefer **`git commit -- <paths>`** over `git add` + `git commit`. New files must be `git add`-ed by name first, then committed with `-- <paths>`.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.
- Before commit while parallel lanes are active, run `git status` and confirm only intended paths are staged.

## Acceptance check

- Each of the three files SHALL open with an iron rule a skimming agent cannot miss, and SHALL name at least one existing skill or command to run rather than restating that skill.
- GIVEN `commands/fix-bug.md` WHEN an agent is asked to fix a bug via `/fix-bug` THEN the file forbids writing a fix before a failing reproduction, and tells the agent to invoke `tdd` and/or `/diagnose` rather than listing diagnose phases.
- GIVEN `commands/refactor.md` WHEN the area under change has no tests THEN the file requires characterization tests before structural edits, and forbids mixing a behavior change into the same pass.
- GIVEN `commands/incident.md` WHEN production is degraded THEN the file requires a human-approved stabilize step before a fix, and requires a written postmortem after.
- Verify: `ls commands/fix-bug.md commands/refactor.md commands/incident.md` and `wc -l commands/diagnose.md commands/fix-bug.md` — fix-bug is shorter than diagnose (thin, not a clone).

## QA contract

- Three files exist under `commands/`.
- `grep -i diagnose commands/fix-bug.md` hits (it points at diagnose).
- `grep -i characterization commands/refactor.md` hits.
- `grep -i postmortem commands/incident.md` hits (or "post-mortem").
- No file contains a copy of diagnose Phase 1–5 headings.

## Toolkit

- Invoke: skill:docs
- Invoke: agent:llm-sec-review (wave gate)

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: none pointed

**Also write that block to** `docs/plans/anew-harvest/dispatch/verification/02-work-type-commands.md`. Chat is not a record. Create the `verification/` folder if missing.
