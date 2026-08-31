# fresh-clone-verify: prove the merged tree installs on a machine that is not this one

**Role:** shell   **Wave:** 2   **AFK:** no   **Background:** no

**Decisions / Specs (pointers):** `-` — no taskman board. This lane is the run's evidence gate; it changes no product file.

**Foreground, orchestrator-run.** Writes only under the scratch directory.

## Goal

The state that is about to be pushed is proven to install and run from a clone, in both
link modes, by a `HOME` that has never seen this harness — the same check the audit ran
before this plan existed, now against the merged result rather than the pre-fix tree.

## Context & decisions (only what this todo needs)

- This exact procedure was run on 2026-08-26 against the pre-fix tree and passed: 8 links,
  hooks rendered for all three editors, 16 skills, both modes. So a failure here is a
  regression introduced by wave 1, not a pre-existing condition — that is the whole value
  of re-running it.
- The clone must carry the **working tree** state, not `HEAD` — `HEAD` still bundles
  `impeccable` and predates every fix in this run. Clone, then apply the staged +
  unstaged diff, or clone and copy the tree; either way assert `skills/impeccable` is
  absent and the skill count is 16 before trusting anything downstream.
- `ai-sync` pushes by default. The clone's `origin` is a local path, so a push would
  target the operator's real repo. **Write `{"push": false}` into the clone's
  `local.config.json` before the first run** — the audit did this and the run reported
  `git: push disabled (local.config.json)`.
- `ai-sync` will not create `~/.agents/skills`; without it the skill step returns early
  and reports zero skills with no error. Create the symlink in the sandbox HOME first.

## Files in scope

- none in the repo — scratch directory only. Evidence goes into this run's action report,
  which the orchestrator owns at Integrate.

## Depends on

- Lane A (stamp-tracker parity), Lane B (copy-mode truth) — both merged into the working tree.

## Do NOT

- Do NOT run any `ai-sync` invocation without a sandboxed `HOME=`.
- Do NOT push, and do NOT remove the `{"push": false}` guard.
- Do NOT edit any repo file to make a check pass — report the failure instead. This lane
  is evidence, not repair.
- Do NOT leave the sandbox clone on disk at the end; it holds a git remote pointing at the
  real repo.

## Acceptance check

- A clone of the merged tree SHALL install into an empty `HOME` in symlink mode and in
  copy mode, with no manual repair.
- GIVEN a fresh sandbox HOME with `~/.agents/skills` symlinked to the clone's `skills/`,
  WHEN `HOME=<sandbox> python3 bin/ai-sync` runs, THEN status reports 8 managed targets
  `linked`, hooks `present` for Claude, Cursor and Copilot, and **16** shared skills.
- GIVEN a second fresh sandbox HOME, WHEN `HOME=<sandbox> python3 bin/ai-sync --copy` then
  `status` run, THEN the mode reads copy, every target reads `copied (in sync)`, and
  **no** line reads `NOT linked` — this is lane B's fix observed from outside its own worktree.
- GIVEN the clone, WHEN `python3 hooks/tests/test_stamp_tracker.py` runs, THEN 7/7 pass —
  lane A's test proven to ship *in the clone*, not merely to exist on this Mac.
- Verify: `ls skills | wc -l` → 16; `test ! -d skills/impeccable`; `ls agents/*.md | wc -l` → 8.
- Verify: the two `guard-destructive` payload smoke tests against the **clone's** copy.
- Verify: the employer/personal-string scrub grep (the `LEAK` pattern in
  `bin/tests/test_repo_shape.py`) over `hooks/ bin/ *.md` in the clone → no hits.

## QA contract

- The full matrix above, with real pasted output per check — not a summary table.
- Sandbox removed afterwards (`rm -rf` the clone and both fake HOMEs), confirmed.
- Any check that fails is reported as a failure and sent back to the owning lane. Do not
  patch around it here.

## Toolkit

- none — shell verification against a throwaway clone.
