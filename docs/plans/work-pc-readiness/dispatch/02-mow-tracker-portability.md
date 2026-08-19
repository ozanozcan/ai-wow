# 02-mow-tracker-portability: make the mow live tracker start and stop in Git Bash

**Role:** code-edit   **Wave:** 1   **AFK:** yes   **Background:** yes

**Decisions / Specs (pointers):** `-` — no taskman board in this repo. Read `docs/plans/work-pc-readiness/plan.md` → `## Decisions locked` and `## Operator note`.

## Goal

The tracker setup and close-out blocks in the bundled mow skill run to completion on
macOS **and** in Git Bash on Windows. No `pkill: command not found`, no silently reused
stale server from a previous run, and a printed URL the operator can open by hand when
no auto-open command exists.

## Context & decisions (only what this todo needs)

- **The tracker assets are already committed and pushed** — `skills/mow/tracker.html`,
  `TRACKER.md`, `widget.py`, `SKILL.md` are all tracked and `master` is in sync with
  `origin/master`. Nothing needs to be *added* to the repo; this lane fixes shell
  portability only.
- **Three non-portable calls, all in [`skills/mow/SKILL.md`](../../../../skills/mow/SKILL.md):**
  `pkill -f "http.server $PORT" || true` at **line 579** (guarded by `|| true`, so it
  degrades, but it never actually kills the stale server on Windows);
  `[ -n "$TERM_PROGRAM$SSH_TTY" ] && command -v open >/dev/null && open "..."` at
  **line 583** (`open` is macOS-only; the guard means Windows silently gets no browser);
  and `pkill -f "http.server $PORT"` at **line 679** in Tracker close-out (**unguarded**
  — this one errors on Windows).
- **The stale-server failure is the dangerous one, not cosmetic.** SKILL.md's own
  warning says it: a server left running by an earlier run keeps serving *that* run's
  folder, so the board loads, looks live, and shows the wrong run. On Windows the kill
  currently never happens, so this failure is the default there, not an edge case.
- **The fix is a `command -v` cascade — locked, not a choice to make inside the lane**
  (grilled 2026-08-19; see plan.md `## Decisions locked`). Kill: `pkill` → `taskkill`
  (find the PID with `netstat -ano | grep :$PORT`, then `taskkill //F //PID <pid>`) →
  skip with a printed warning. Open: `open` → `start` → `xdg-open` → skip.
  **Print the URL unconditionally in every branch**, so a shell with none of the three
  still leaves the operator able to open the board by hand. Probe for the command, not
  the platform — no `uname` / `$OSTYPE` branch. Documenting the gap in Appendix B
  instead was considered and rejected, as was collision-detect-without-kill.
- **The port derivation must not change.** `PORT=$(python3 -c "import hashlib,os;print(8300+int(hashlib.md5(os.getcwd().encode()).hexdigest(),16)%80)")`
  is deliberately stable per repo path so the operator can bookmark the URL. Keep it.
- **Editing this file cannot break the run in progress.** `~/.agents/skills` points at
  `~/Desktop/dotfiles-ai/skills`, not at this repo, so the live mow procedure is read
  from elsewhere. The fix lands where the work PC will clone it.

## Files in scope

- `skills/mow/SKILL.md` — the tracker serving block (§ go 1) and Tracker close-out (§ go 4)
- `skills/mow/TRACKER.md` — the mirrored serving block under `## Serving (go §1, after preflight)`

## Depends on

- none

## Do NOT

- **Do not edit `skills/mow/tracker.html` or `skills/mow/widget.py`.** They are
  browser/Python code with no shell portability problem, and `tracker.html` is 107 KB —
  an incidental reformat would bury the real diff.
- **Do not change the port derivation formula or the `?view=compact` iframe contract.**
  Both are load-bearing for the chat board.
- **Do not introduce a dependency on `bash` arrays, `pgrep`, `lsof`, or `ss`** — the
  target is stock Git Bash on a locked-down Windows box with no admin rights.
- **Do not touch any other skill.** `skills/` has 15 entries; this lane owns `mow` only.
- **Do not "improve" unrelated prose in SKILL.md.** It is 71 KB; every changed line must
  trace to the portability fix.
- **Do not run `git add -A` or commit.**

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.
- Before commit while parallel lanes are active, run `git status` and confirm only intended paths are staged.

## Acceptance check

- The tracker serving and close-out blocks SHALL contain no unguarded command that is
  absent from stock Git Bash. Verify: `grep -nE "pkill|[^-]open \"" skills/mow/SKILL.md`
  returns only occurrences inside a `command -v` guard or a portable cascade.
- GIVEN a Windows Git Bash shell WHEN the operator runs the serving block for a repo
  whose port is already bound by a previous run's server, THEN the block either kills
  that server or reports the collision and stops — it SHALL NOT silently attach to a
  stale server serving another run's folder.
- GIVEN a shell with no `open`, no `start`, and no `xdg-open`, WHEN the serving block
  runs, THEN it still prints `tracker: http://localhost:<PORT>/tracker.html` so the
  operator can open it by hand.
- The same fixed block SHALL appear in both `skills/mow/SKILL.md` and
  `skills/mow/TRACKER.md`. Verify: the serving snippets in the two files are identical.
- The macOS path SHALL be unchanged in behavior — `pkill` and `open` still used when
  present.

## QA contract

- Extract each changed shell block to a scratch file and run `bash -n` on it — must parse
- Run the serving block on this Mac end-to-end: server starts, URL prints, page loads,
  then close-out stops it. `curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/tracker.html` → `200` before close-out, connection refused after
- `grep -c "http.server" skills/mow/SKILL.md skills/mow/TRACKER.md` — both files still document serving
- `git diff --stat skills/mow/` — only `SKILL.md` and `TRACKER.md` changed; `tracker.html` and `widget.py` untouched

## Toolkit

- none — this is a shell-portability edit with no matching skill in the repo's toolkit map

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: <none pointed — cite plan.md decisions instead>
