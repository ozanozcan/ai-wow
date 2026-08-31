# stamp-tracker-parity: ai-wow gets the backgrounded-agent fix and its regression test

**Role:** code-edit   **Wave:** 1   **AFK:** yes   **Background:** yes

**Decisions / Specs (pointers):** `-` — this repo has no taskman board (`.taskman.toml` absent), so there are no `d`/`req` ids. The binding decisions are in [`../plan.md`](../plan.md) → `## Decisions locked`, first bullet (scrub discipline). Read it before you start.

## Goal

`hooks/stamp-tracker.py` in **ai-wow** stops writing an `ended` timestamp for a subagent
spawn whose `PostToolUse` fires at *launch* rather than at completion, and ai-wow carries
the regression test that proves it. After this lane, a fresh clone of ai-wow on any
machine has both the fix and the test — today it has neither.

## Context & decisions (only what this todo needs)

- **The bug.** `on_task` wrote `"ended": _now()` on every `PostToolUse`. For a
  backgrounded spawn that event fires when the *launch* returns, so an AFK lane is
  stamped as finishing seconds after it started. That freezes the lane's clock on the mow
  board and makes a live run read as dead. It is only visible on a still-running lane,
  because the orchestrator's own write overwrites the bad value once a report lands.
- **The load-bearing subtlety.** Claude Code's `Agent` tool **backgrounds by default** —
  an *absent* `run_in_background` key still means async. Cursor's `Task` is the opposite.
  Testing `flag == True` would leave the bug in place for most calls. An explicit value
  wins in both runtimes.
- **The fix already exists**, written test-first in the predecessor run, but it landed in
  `~/Desktop/dotfiles-ai` and never propagated. `bin/ai-sync`'s `foreign_repo_root()`
  guard makes `_copy_scripts` return 0 when the source symlinks into another repo, which
  is this Mac's exact layout — so no sync will ever carry it. It has to be ported by hand.
- **ai-wow is the scrubbed, publishable repo.** dotfiles-ai's copy names a real employer
  project in prose where ai-wow's working tree reads the generic "A live run was
  observed…". **Take the code, keep
  ai-wow's wording.** Do not let the port re-introduce a project name — that is a
  publication defect, not a style nit.
- The test file itself was checked and is already scrub-clean: no project names, no
  absolute paths. It resolves the hook relative to its own location, so it is portable
  as-is.

## Files in scope

- `hooks/stamp-tracker.py` — modify
- `hooks/tests/test_stamp_tracker.py` — create (the `hooks/tests/` directory does not exist yet)

## Source to port from (read-only, outside this worktree)

- `~/Desktop/dotfiles-ai/hooks/stamp-tracker.py` — has `_returns_at_launch`
  (definition near line 121, call site near line 297)
- `~/Desktop/dotfiles-ai/hooks/tests/test_stamp_tracker.py` — 115 lines, 7 checks

**Read those paths. Never write to them.** Another lane in wave 2 owns dotfiles-ai; a
write from here is a cross-lane collision.

## Depends on

- none

## Do NOT

- **Do NOT write anything under `~/Desktop/dotfiles-ai/`.** Read-only source.
- **Do NOT copy the whole file over.** ai-wow's `hooks/stamp-tracker.py` has scrubbed
  prose that dotfiles-ai's does not. Port the `_returns_at_launch` helper and its call
  site; leave every other line of ai-wow's file alone. A wholesale copy silently reverts
  the scrub and any other ai-wow-only edit.
- **Do NOT introduce pytest.** These hooks run under an interpreter with no third-party
  packages; the test is plain `python3` with a module-level failure list, and stays that way.
- Do NOT touch `hooks/guard-destructive.sh`, `hooks/session-start-marker.py`,
  `hooks/guard-migrations.sh`, `hooks.def.json`, or `bin/ai-sync` — other lanes or
  deliberate divergence.
- Do NOT "fix" `session-start-marker.py`'s comment to match dotfiles-ai. The difference
  is the scrub, and ai-wow's side is correct.
- Do NOT run `python3 bin/ai-sync` in any form. It rewrites `~/.claude` and can push.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- `hooks/tests/test_stamp_tracker.py` is a **new file**, so a path-limited commit cannot
  see it until it is added by name: `git add hooks/tests/test_stamp_tracker.py`, then
  still commit with `git commit -- hooks/stamp-tracker.py hooks/tests/test_stamp_tracker.py`.
- **Forbidden:** `git stash`, `git reset --hard`, `git clean -fd`.
- Run `git status` before committing and confirm only your two paths are staged.

## Acceptance check

- The hook SHALL leave `ended` unset for a spawn whose `PostToolUse` fires at launch, and
  SHALL still stamp `ended` for a synchronous one.
- GIVEN a `PostToolUse` payload for tool `Agent` with **no** `run_in_background` key,
  WHEN the hook processes it, THEN the appended span's `ended` is `None` — because
  `Agent` backgrounds by default.
- GIVEN a `PostToolUse` payload for tool `Task` with `run_in_background` absent or false,
  WHEN the hook processes it, THEN the span's `ended` carries a timestamp.
- **Red evidence is required.** Run the ported test against ai-wow's *unfixed*
  `stamp-tracker.py` first and paste the failures into your Verification block. Expect two,
  naming the backgrounded cases. A lane that reports only green has not proved anything.
- Verify: `python3 hooks/tests/test_stamp_tracker.py` → exit 0, 7/7 pass.
- Verify: `grep -c _returns_at_launch hooks/stamp-tracker.py` → `2` or more.
- Verify: the employer-string scrub grep (the `LEAK` pattern in
  `bin/tests/test_repo_shape.py`) over `hooks/` → **no matches** (scrub intact).
- Verify: `python3 -m py_compile hooks/stamp-tracker.py` → exit 0.

## QA contract

- The ported test, red before the fix and green after — both pasted, not summarized.
- The four `grep` / compile checks above, with their actual output.
- Confirm the four synchronous-path assertions pass **both** before and after the fix.
  That is what pins down that the fix did not trade one bug for another.

## Toolkit

- `Invoke: skill:tdd` — red before production code. The test already exists upstream, so
  "write the test" here means *port it and run it red*; do not skip to the fix.
- `Invoke: skill:test-coverage` only if you find an untested branch you had to touch.
  Do not expand scope to cover the hook's other two jobs.

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: <the scrub decision: how, file:line — or "none pointed">
