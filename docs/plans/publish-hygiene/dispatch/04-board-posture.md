# 04-board-posture: board-less reads as a decision, not an omission

**Role:** code-edit   **Wave:** 2   **AFK:** no   **Background:** no

**Decisions / Specs (pointers):** `-` — board-less repo, no `d`/`req` ids. Context below is the full lock set.

**This is the run's final lane (`Z`).** It documents the posture the other three lanes leave the
repo in, so it runs after them and its wording must match what they actually shipped.

## Goal

A reader of the published repo learns that ai-wow ships the board **as a tool** while carrying no
board of its own, that this is a deliberate choice with a stated reason, and what to do if they
want one. `Board sync: n/a` in every session report becomes a legible consequence rather than a
gap someone forgot to close.

## Context & decisions (only what this todo needs)

- **The decision and its evidence (operator, 2026-09-01).** ai-wow stays board-less. Measured, not
  assumed: with a root `.taskman.toml` present and no reachable Postgres,
  `python -m taskman wrapup gate` exits **2**. `skills/wrap-up/SKILL.md`'s own exit table reads 2
  as *"No session marker — run `taskman wrapup open`"*, which is the wrong diagnosis and points at
  a command that fails identically. So a root board would break `/wrap-up` on any machine without
  Postgres — the work PC included — and contradict README's "the harness needs no database".
- **This is explicitly revisitable.** The sibling stem `taskman-no-db` may remove the Postgres
  dependency entirely, at which point the objection dissolves and a root board costs one file.
  Write the reason down so a future reader can tell it was a judgment about *today's* constraints,
  not a permanent rule.
- **What lane A will have shipped (grill Q1, 2026-09-01):** in a board-less repo the SessionStart
  hook says **nothing** about the wrap-up gate — it names the gate only when a `.taskman.toml`
  exists above the worktree. That is a visible consequence of the board-less decision and worth one
  sentence here, so a reader who notices the quiet hook understands why. Confirm what lane A
  actually shipped before describing it; do not assume this wording survived unchanged.
- **Where it goes:** `HOW-TO-USE.human.md` §6 ("The board"). §6 already gained a
  `### Standing one up` subsection on 2026-09-01 with the verified four-command bootstrap; the new
  material belongs alongside it, in the same voice. §5 ("Working without a board") already exists
  and covers the *workflow* — link to it rather than restating it.
- **`taskman/.taskman.toml` is tracked and stays**, with `slug = "taskman-tests"`. It scopes the
  package's own test suite and is not a board for the repo. Say so, so nobody reads it as a
  contradiction of the decision above.
- **Do not touch `README.md` or `HOW-TO-USE.agent.md`.** Both assert Postgres
  (`README.md:161`, invariant I10 at `HOW-TO-USE.agent.md:56`) and both are owned by the
  `taskman-no-db` stem. Editing them here is a cross-plan collision — the reason this stem was
  split out in the first place.
- **The scrub gate covers `docs/` and reads tracked files** (as of `1693827`). Any prose added
  here must be free of employer codenames and absolute `/Users/<name>` paths, or `githooks/pre-push`
  will refuse the push.

## Files in scope

- `HOW-TO-USE.human.md` — §6, alongside the existing `### Standing one up`

## Depends on

- `01-reference-honesty` — that lane makes the SessionStart hook conditional and repoints the
  wrap-up references; this lane's prose describes the board-less behavior it produces, so read that
  lane's shipped diff rather than quoting this brief.

## Do NOT

- **Do not add a root `.taskman.toml`.** The decision is to stay board-less; this lane documents
  that, it does not implement the opposite.
- **Do not edit `README.md` or `HOW-TO-USE.agent.md`** — owned by `taskman-no-db`.
- **Do not remove or rewrite `### Standing one up`** — it was verified end to end on 2026-09-01
  (`uv sync` → `init-db` → board renders, 135/135 tests). Add beside it.
- **Do not restate §5's content.** Link to it.
- Do not add a Contents entry for a `###` heading — the Contents list in this file tracks
  top-level sections only.
- Do not introduce employer codenames or absolute home paths; the push gate now scans `docs/` and
  the published guides.

## Acceptance check

- **SHALL:** `HOW-TO-USE.human.md` SHALL state that ai-wow deliberately carries no root
  `.taskman.toml`, give the reason, and name the condition under which that would change.
- **GIVEN** a reader who has just run `ai-sync` and wants a board, **WHEN** they read §6,
  **THEN** they can tell that the four-command bootstrap applies to *their own* project repo and
  not to the ai-wow clone itself.
- **GIVEN** a reader who notices `taskman/.taskman.toml` in the tree, **WHEN** they read §6,
  **THEN** they learn it scopes the package's test suite rather than contradicting the decision.
- Verify: `python3 bin/tests/test_repo_shape.py` → 0 failures (inventory claims and scrub both
  still hold after the prose change).
- Verify: `grep -n "taskman.toml" HOW-TO-USE.human.md` → the new text is present and the existing
  Appendix C troubleshooting row is untouched.

## QA contract

- `python3 bin/tests/test_repo_shape.py` → exit 0
- `sh githooks/pre-push` → `pre-push: clean` (the full gate, since this lane edits a published surface)
- Anchor check: every in-page link this lane adds resolves to a heading that exists in the file

## Toolkit

- `Invoke: skill:docs` — this is prose a human reads in a published guide, which is that skill's
  remit. Match the existing §6 voice; do not restructure the section around the addition.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- Prefer **`git commit -- HOW-TO-USE.human.md`** over `git add` + `git commit`.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.
- A peer session is live in this checkout planning `taskman-no-db`. Before any commit, run
  `git status` and confirm only your own path is staged.

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: none pointed (board-less repo — see header)
