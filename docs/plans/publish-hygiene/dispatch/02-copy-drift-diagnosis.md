# 02-copy-drift-diagnosis: a stale copy says it is stale, not that it was never linked

**Role:** code-edit   **Wave:** 1   **AFK:** yes   **Background:** yes

**Decisions / Specs (pointers):** `-` — board-less repo, no `d`/`req` ids. Context below is the full lock set.

## Goal

`ai-sync status` currently reports `NOT linked (real dir)` for a copy-mode install whose files
have drifted from the repo. That is the wrong diagnosis, and it appears **precisely when
something is actually wrong**. After this lane, a drifted copy reports that it is a drifted copy,
a never-linked directory still reports that, and a regression test pins both apart.

## Context & decisions (only what this todo needs)

- **The exact mechanism**, in `bin/ai-sync` → `_dir_link_state()` (around line 951): when
  `mode == "copy"` and the path is a directory, the function tests `_trees_equal(canonical, link)`.
  On a match it returns `copied (in sync)`. On a **mismatch** it falls through to
  `if link.exists(): return "NOT linked (real dir)"` — the same branch a genuinely unmanaged
  directory hits. The two states are indistinguishable in the output.
- **The same bug exists for files**, inline in `do_status()` (around line 982): copy mode plus a
  byte mismatch falls through to `NOT linked (real file)`.
- **This was found and correctly left alone by the predecessor run** (`work-pc-readiness-followups`
  lane B, 2026-08-26), which fixed the *reporting mode* but scoped the drift wording out. It is
  logged as open item 1 in that run's action report. This lane closes it.
- **Why it matters more than it reads:** the audience is a locked-down Windows box where copy mode
  is the only install path. "NOT linked" there reads as a failed install, so the operator re-runs
  the installer instead of re-syncing — the one response that does not fix drift.
- **Do not confuse drift with the foreign-repo case.** `foreign_repo_root(link)` is checked first
  and returns `OTHER REPO (...)`; that branch is correct and unrelated.
- `_trees_equal` already exists and is the right comparison — reuse it, do not write a second one.

## Files in scope

- `bin/ai-sync` — `_dir_link_state()` and the file-state branch inside `do_status()`
- `bin/tests/test_ai_sync_status.py` — extend the existing suite

## Depends on

- none

## Do NOT

- **Do not change the `linked`, `copied (in sync)`, `missing`, or `OTHER REPO` strings**, and
  **do not remove `NOT linked (real dir)` / `NOT linked (real file)`** — they remain correct for a
  path that was genuinely never linked (symlink mode, or a foreign real directory). Only the
  *copy-mode drift* fall-through changes. `bin/tests/test_ai_sync_status.py` asserts
  `out.count("copied (in sync)") == 8` and `"NOT linked" in out → False` for a healthy copy
  install; both must still hold afterward.
- **Do not touch `installed_mode()` or `_is_copy_of()`** — they were fixed last run and are correct.
- **Do not touch `can_symlink()`'s two install-time callers.**
- **Do not widen this into a "repair drift" feature.** Status reports; it does not fix.
- Do not rewrite historical wording in `docs/` that quotes the old output — those are records of
  what happened, and the scrub gate now covers `docs/`, so edits there risk unrelated failures.

## Acceptance check

- **SHALL:** `ai-sync status` SHALL print exactly `copied (stale — re-run ai-sync)` for a
  copy-mode install whose contents have drifted — **locked wording, grill Q2, 2026-09-01**. Applies
  to both the directory branch in `_dir_link_state()` and the file branch in `do_status()`. Note
  the em dash (—), not a hyphen.
- **GIVEN** a copy-mode install that is complete and in sync, **WHEN** `ai-sync status` runs,
  **THEN** it prints 8 × `copied (in sync)` and **zero** occurrences of `NOT linked` — unchanged
  from today.
- **GIVEN** a copy-mode install where one managed directory's contents have been modified after
  install, **WHEN** `ai-sync status` runs, **THEN** that line reads `copied (stale — re-run ai-sync)`
  and the output contains no `NOT linked` for it.
- **GIVEN** a copy-mode install where a managed *file*'s bytes differ, **WHEN** status runs,
  **THEN** it prints the same `copied (stale — re-run ai-sync)` string — the two branches must not
  drift apart in wording.
- **GIVEN** a real directory at a managed path that was never installed by `ai-sync` (symlink
  mode), **WHEN** status runs, **THEN** it still reports `NOT linked (real dir)`.
- Verify: `python3 bin/tests/test_ai_sync_status.py` → all checks pass, including a **new** drift
  case. Run it against the **unfixed** code first and record the failure — a test that has never
  failed has not been shown to test anything.

## QA contract

- `python3 bin/tests/test_ai_sync_status.py` → exit 0, with red evidence from the pre-fix run
  quoted in `## Verification`
- `python3 -m py_compile bin/ai-sync` → exit 0
- `python3 bin/tests/test_ai_sync_commit.py` → exit 0 (proves no collateral damage to the sibling suite)

## Toolkit

- `Invoke: skill:tdd` — write the drift case first, run it red against the current `bin/ai-sync`,
  then fix. The red run is the deliverable evidence, not a formality.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- Prefer **`git commit -- <paths>`** over `git add` + `git commit`.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.
- A peer session is live in this checkout planning `taskman-no-db`. Before any commit, run
  `git status` and confirm only your own paths are staged.

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail, including the pre-fix red run>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: none pointed (board-less repo — see header)
