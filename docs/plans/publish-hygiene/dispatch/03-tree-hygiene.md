# 03-tree-hygiene: worktrees stop depending on the orchestrator remembering

**Role:** shell   **Wave:** 1   **AFK:** no   **Background:** no

**Decisions / Specs (pointers):** `-` — board-less repo, no `d`/`req` ids. Context below is the full lock set.

**AFK is `no` deliberately.** This lane inspects a working tree that currently holds a *peer
session's* uncommitted work. Backgrounding it would put an unattended agent next to files it must
not touch. Run it in the foreground, with the operator watching.

## Goal

`.claude/worktrees/` is gitignored, so `git status` is clean straight after a worktree run
instead of depending on whoever is driving to stage around it. The orphaned 2026-08-21 session
report is committed into the record. Every other loose file is triaged and reported to the
operator with a recommendation — **not** acted on unilaterally.

## Context & decisions (only what this todo needs)

- **`.claude/worktrees/` has never been gitignored** — carried as open item 5 in the
  `work-pc-readiness-followups` action report and still open today. Two worktrees were created on
  2026-09-01 and kept out of commits by explicitly staging paths, which is discipline, not a
  mechanism. mow's go mode creates worktrees routinely (`isolation: "worktree"`), so this recurs
  on every isolated run.
- **`.claude/` also holds tracked or operator-managed content** — `settings.json` and similar live
  there in some installs. Ignore the `worktrees/` subdirectory specifically, **not** `.claude/`
  wholesale, or a future session silently stops tracking real config.
- **The scrub gate now scans git-tracked files only** (changed 2026-09-01, `1693827`). Adding a
  gitignore entry therefore *removes* paths from the gate's view. That is correct here — an
  ignored worktree cannot publish — but it is worth understanding before adding entries.
- **A peer session is live in this checkout**, planning `taskman-no-db`. `git status` currently
  shows three modified files and several untracked ones. `docs/plans/work-pc-readiness/action-report.md`
  carries ~49 uncommitted lines belonging to an **earlier run, not this one** — the
  2026-08-29 session report explicitly records them as "not this session's to attribute".
- The untracked items were checked for employer strings on 2026-09-01 and are **clean**, so none
  of them is a publication risk. They are untidiness, not exposure.

## Files in scope

- `.gitignore` — add the worktrees entry
- `docs/session-reports/2026-08-21-1913-work-pc-readiness-mow-go-and-harness-fixes.md` — commit
  this **untracked** file into the record (grill Q4). It is currently untracked, so a path-limited
  commit cannot see it: `git add` that exact path first, confirm with
  `git diff --cached --name-only` that the index holds **only** it, then
  `git commit -- <that path> .gitignore`. Once tracked it falls under the widened `docs/` scrub —
  confirm `python3 bin/tests/test_repo_shape.py` still passes after adding it.

Everything else in this brief is **read-and-report only**.

## Depends on

- none

## Do NOT

- **Do not delete, stash, or restore anything you did not create**, and commit nothing beyond the
  two paths in `## Files in scope`. Specifically: leave
  `docs/plans/work-pc-readiness/action-report.md`'s uncommitted changes exactly as they are — they
  belong to another run and a peer session is live in this checkout.
- **Do not run `git stash`, `git reset --hard`, `git clean -fd`, `git add -A`, or `git add .`.**
  All of them reach the whole tree, including the peer's work.
- **Do not gitignore `.claude/` wholesale** — only the `worktrees/` subdirectory.
- **Do not delete the stray screenshot or `dispatch/.agent-times.json`.** Report them with a
  recommendation; the operator decides. An untracked file is nobody's to remove on their behalf.
  Committing the session report (above) is the *only* action this lane takes on a file it did not
  create, and it is additive — nothing is removed.
- Do not add speculative entries "while you're in there" — `.gitignore` changes what the scrub
  gate can see, so each line needs a reason.

## Acceptance check

- **SHALL:** A git worktree created under `.claude/worktrees/` SHALL NOT appear in `git status`.
  - Verify: `git worktree add .claude/worktrees/_probe -b tmp/_probe HEAD && git status --porcelain | grep -c "^?? \.claude"`
    → `0`; then `git worktree remove .claude/worktrees/_probe --force && git branch -D tmp/_probe`.
    **Prove it by making it fire**: confirm the same probe *does* show up before the edit.
- **SHALL:** Tracked content under `.claude/` SHALL still be visible to git.
  - Verify: `git check-ignore -v .claude/settings.json` → **no match** (exit 1), if that path exists.
- **GIVEN** the peer's uncommitted work, **WHEN** this lane finishes, **THEN**
  `git status --porcelain -- docs/plans/work-pc-readiness/action-report.md` still reports ` M`,
  unchanged and uncommitted.
- **GIVEN** the untracked 2026-08-21 session report, **WHEN** this lane finishes, **THEN**
  `git log --oneline -1 -- docs/session-reports/2026-08-21-1913-work-pc-readiness-mow-go-and-harness-fixes.md`
  names a commit, and `python3 bin/tests/test_repo_shape.py` still reports 0 failures with it tracked.
- Report — do not action — each remaining loose path with a one-line recommendation: the stray
  screenshot at the repo root, and `dispatch/.agent-times.json`.

## QA contract

- The gitignore probe above, run **both** before and after the edit, with both results quoted
- `git status --porcelain` captured before and after, differing **only** by `.gitignore` and by the
  2026-08-21 session report moving from untracked to committed
- `git diff --cached --name-only` shown to hold only this lane's own paths at commit time
- `python3 bin/tests/test_repo_shape.py` → 0 failures, run **after** the report becomes tracked
- No git command run by this lane mutates tracked content other than the two paths in scope

## Toolkit

- none — this is a one-line config edit plus a read-only report. Note that in `## Verification`
  rather than reaching for a skill that does not fit.

## Git rules

- Stage **explicit paths only** — here, exactly `.gitignore` and the 2026-08-21 session report.
- The session report is **untracked**, so a path-limited commit cannot see it. `git add` that one
  path by name, then verify with `git diff --cached --name-only` that the index holds only it
  before committing. This is the documented exception to preferring `git commit -- <paths>`.
- **Forbidden:** `git stash`, `git reset --hard`, `git clean -fd`, `git add -A`, `git add .`.
- Run `git status` before any commit and confirm nothing outside `## Files in scope` is staged —
  a peer session's work is in this tree.

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail, including the before/after probe>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: none pointed (board-less repo — see header)
