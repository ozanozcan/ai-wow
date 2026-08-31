# 01-reference-honesty: every shipped instruction names something that exists

**Role:** code-edit   **Wave:** 1   **AFK:** yes   **Background:** yes

**Decisions / Specs (pointers):** `-` — this repo is board-less by decision (see `plan.md` → Decisions locked), so there are no `d`/`req` ids. Context below is the full lock set.

## Goal

Four shipped files instruct an agent to use something this repo does not contain. After this
lane, every such reference either names a real path/agent or is phrased conditionally. A fresh
clone's first session receives no instruction it cannot follow.

## Context & decisions (only what this todo needs)

- **`scripts/wrapup_reconcile.py` does not exist in ai-wow, and neither does a repo-root
  `.venv/`.** Both are leftovers from the layout taskman was extracted from, where it lived at
  `demo/taskman` beside a `scripts/` directory. The real entry point is
  **`python -m taskman wrapup gate`** — but read the next bullet before naming it anywhere:
  it is not unconditionally runnable. `taskman/pyproject.toml` also installs a
  `wrapup-reconcile` console script into `taskman/.venv/bin/`.
- **The gate command only exists inside `taskman/.venv`.** Verified 2026-09-01:
  `python3 -m taskman wrapup gate` on system Python fails with
  `No module named taskman.__main__`. The package is installed by `uv sync` into
  `taskman/.venv`, so **naming any form of this command unconditionally would ship the same
  defect this lane exists to remove** — just with a different error on a fresh clone.
- **Locked (grill Q1, 2026-09-01): the hook names the gate only when a board exists.** Walk up
  from the resolved worktree/cwd looking for a `.taskman.toml`. Found → name the gate. Not found
  → print the marker line and nothing about wrap-up. The skill docs (`wrap-up`, `mow`) may name
  the command unconditionally, because by the time a human reads those they have a repo in front
  of them; the *hook* is what greets a clone with nothing installed.
- **When a board IS present, the command is correct**: from a directory with a `.taskman.toml`
  and a working venv, `python -m taskman wrapup gate` exits 0 board-less-style or reports real
  worklists. Do not "improve" the board-less exit-0 behavior; it is what makes ai-wow work
  without a database.
- **`django-reviewer` is deliberately absent** and stays absent (operator, 2026-09-01 — Django is
  not widely used at the operator's company). `skills/mow/SKILL.md:526` currently asserts it
  exists in both runtime columns. The neighbouring line at `:200` already gets this right
  ("Stack-specific review (**if project has the agent**)") — match that hedge rather than
  inventing new wording, and leave `:200` itself alone.
- **`skills/checkpoint/SKILL.md:110`** lists `django-reviewer` inside a bracketed `[e.g. ...]`
  example of suggested skills. It is an illustration, not a routing claim — swap the example for
  an agent this repo ships rather than rewriting the line's structure.
- The skills in this repo are also the operator's live runtime via `ai-sync`, so a wording change
  here reaches a running harness. Keep edits minimal and in the surrounding voice.

## Files in scope

- `hooks/session-start-marker.py` — the `ctx` string around line 187
- `skills/wrap-up/SKILL.md` — the evidence-gate command block around line 37
- `skills/mow/SKILL.md` — the go-mode close-out step around line 805, and the runtime-resolution
  table row around line 526
- `skills/checkpoint/SKILL.md` — the suggested-skills example around line 110
- `hooks/tests/test_session_start_marker.py` — **new**, this lane creates it (grill Q3)
- `githooks/pre-push` — register the new suite alongside the existing `hooks/tests/` line

## Depends on

- none

## Do NOT

- **Do not create a `scripts/` directory or a shim file.** The fix is to point at the entry point
  that already exists, not to manufacture the missing path. A shim would make the false reference
  true by adding code nobody asked for.
- **Do not touch `taskman/**`.** The sibling stem `taskman-no-db` owns that tree; edits there
  are a cross-plan collision.
- **Do not add `agents/django-reviewer.md`.** Keeping it out is the locked decision; this lane
  makes the references honest, it does not change the roster.
- **Do not change `skills/mow/SKILL.md:200`**, which is already correctly hedged.
- **Do not let the `.taskman.toml` check gate anything except the message text.** An earlier
  version of this hook returned early unless a `.taskman.toml` existed, so in a board-less repo
  **no marker was ever written** and the peer-session hooks silently found nothing. That was
  fixed in `f6b25f9` by gating on "is this a git worktree" instead. The marker must still be
  written unconditionally; only the wrap-up sentence is conditional. Re-introducing that early
  return is the single worst outcome of this lane.
- **Do not "fix" the board-less exit-0 behavior** of `taskman wrapup gate` — that is intended.
- Do not reformat, reflow, or re-voice surrounding prose in any of the four files.

## Acceptance check

- **SHALL:** No file under `hooks/` or `skills/` SHALL reference `scripts/wrapup_reconcile.py`
  or a repo-root `.venv/` path.
  - Verify: `grep -rn "scripts/wrapup_reconcile\|\.venv/bin/python scripts/" hooks/ skills/`
    → **no matches** (exit 1).
- **SHALL:** The runtime-resolution table SHALL NOT assert that an agent absent from `agents/`
  exists in this repo.
  - Verify: for every agent name in `skills/mow/SKILL.md`'s runtime-resolution table, a matching
    `agents/<name>.md` exists, or the row is explicitly conditional.
- **SHALL:** The SessionStart hook SHALL name the evidence gate only when a `.taskman.toml`
  exists at or above the resolved worktree.
- **GIVEN** a repo with no `.taskman.toml` above it, **WHEN** the hook runs, **THEN** its context
  string contains no wrap-up command at all — and a session marker **is still written**.
- **GIVEN** a repo that does have a `.taskman.toml`, **WHEN** the hook runs, **THEN** its context
  string names the gate.
  - Verify both by feeding the hook a payload with `cwd` set to each case and asserting on the
    emitted JSON: board-less → no `wrapup` substring **and** a marker file created; board present
    → `wrapup` named. The marker assertion is the one that catches the `f6b25f9` regression.
- **GIVEN** the edited hook, **WHEN** it runs, **THEN** it still emits valid JSON on stdout.
  - Verify: `python3 -m py_compile hooks/session-start-marker.py` → exit 0.

## QA contract

- `python3 -m py_compile hooks/session-start-marker.py` → exit 0
- `python3 hooks/tests/test_session_start_marker.py` → passes, **with the pre-fix red run quoted**
  (break the board-less branch deliberately and confirm the marker assertion fails)
- `python3 hooks/tests/test_stamp_tracker.py` → 7/7 (proves no collateral hook damage)
- `python3 bin/tests/test_repo_shape.py` → 0 failures (the scrub/inventory gate)
- `sh githooks/pre-push` → `pre-push: clean`, **and its output names the new suite** — proving the
  registration took, not just that the file exists
- The two `grep` verifications above, reported with their exit codes

## Toolkit

- `Invoke: skill:tdd` — **required**, changed by grill Q1. This lane is no longer string-only:
  it adds a `.taskman.toml` finder to the hook and must prove the board-less branch still writes
  a marker. Write that assertion first and watch it fail against a deliberately-broken early
  return, so the `f6b25f9` regression is caught by a test rather than by review.
- The rest of the lane (the three reference edits) stays grep-shaped and needs no test.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- Prefer **`git commit -- <paths>`** over `git add` + `git commit`.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.
- A peer session is live in this checkout planning `taskman-no-db`. Before any commit, run
  `git status` and confirm only your own paths are staged.

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: none pointed (board-less repo — see header)
