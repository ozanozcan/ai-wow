# 05-invocation-truth: one way to invoke taskman, true in every repo

**Role:** code-edit   **Wave:** 3   **AFK:** no   **Background:** no

**Decisions / Specs (pointers):** `-` — board-less repo, no `d`/`req` ids. Context below is the full lock set.

**Lane letter:** `Z2`. The A→Z rule gave `Z` to the wave-2 documentation lane, which had shipped
before the ship-check gate added this wave. Renaming a shipped lane would falsify the record, so the
run reads A · B · C · Z · Z2 and this note explains why.

**AFK is `no`:** this lane edits the operator's live runtime (`ai-sync` symlinks `skills/` into
`~/.claude`) and rewrites a bootstrap whose last version was verified against the wrong case. It
wants a human watching.

## Goal

There is exactly one documented way to invoke `taskman`, it works from any repo, and the bootstrap
that sets it up targets the reader's project rather than taskman's own test project. A durable check
refuses any future shipped file that names a path this repo does not have.

## Context & decisions (only what this todo needs)

- **The Critical the ship-check gate found.** The plan promised no repo-root `.venv/` path would
  survive in a shipped file. **29 did** — `skills/wrap-up/SKILL.md` (20),
  `skills/grill-with-docs/SKILL.md` (7), `skills/bs/SKILL.md` (2). ai-wow has no root `.venv/`, so
  those lines name something a clone cannot run. The lane-A grep that "verified" this searched
  `\.venv/bin/python scripts/` — the `scripts/` is required immediately after, so it could only ever
  match the combination, never a bare `.venv/bin/python`. It passed while the criterion failed.
- **A second defect, in already-pushed work (`1693827`).** `HOW-TO-USE.human.md` §6
  `### Standing one up` says: put a `.taskman.toml` at *your* repo root (steps 1–2), then
  `cd taskman && uv run python -m taskman init-db` (steps 3–4). Those steps run in **ai-wow's**
  taskman directory. `config.py:find_project()` walks up from **cwd**, so it registers
  `taskman-tests`, not the reader's project. Proven:
  `resolved from my-service dir -> ('my-service', 'My Service')` vs
  `resolved from ai-wow/taskman -> ('taskman-tests', 'taskman package test project')`.
- **The single fix for both: the console script on PATH.** `taskman/pyproject.toml` declares
  `[project.scripts] taskman = "taskman.cli:main"`, so `uv sync` installs
  `taskman/.venv/bin/taskman`. Verified working from an unrelated directory. On PATH, every skill
  line becomes a bare `taskman …`.
- **Why PATH beats a relative venv prefix, and this is the load-bearing reason.** `find_project()`
  resolves the project by walking up from cwd, so the CLI **must** be run from the reader's project
  directory. A relative `.venv/bin/python` points into whatever repo you happen to be standing in,
  which fights that. An absolute install on PATH does not care where you stand.
- **`uv run` is not a substitute.** `uv run` resolves the project venv relative to cwd too, so it
  reintroduces the same coupling the PATH line removes.
- The skills in this repo are the operator's live runtime via `ai-sync`. A wording change here
  reaches a running harness; keep edits minimal and in the surrounding voice.

## Files in scope

- `HOW-TO-USE.human.md` — §6 `### Standing one up` (rewrite the invocation steps only)
- `skills/wrap-up/SKILL.md` — 20 command prefixes
- `skills/grill-with-docs/SKILL.md` — 7 command prefixes
- `skills/bs/SKILL.md` — 2 command prefixes
- `bin/tests/test_repo_shape.py` — add the durable check

All five are inside this stem's declared ownership; the sibling `taskman-no-db` INDEX attributes
`skills/*/SKILL.md`, `bin/tests/` and `HOW-TO-USE.human.md` to this stem and reserves only
`.github/workflows/` and `taskman/taskman/eventlog/` for itself.

## Depends on

- `04-board-posture` (shipped) — this lane edits the same §6 section it wrote. Read the committed
  version; do not restore anything it deliberately changed.

## Do NOT

- **Do not delete the `### This repo has no board, deliberately` subsection** that wave 2 added.
  This lane changes the *invocation* steps beside it, not the board-posture prose.
- **Do not touch `README.md` or `HOW-TO-USE.agent.md`** — reserved for `taskman-no-db`.
- **Do not touch `taskman/**`** — that whole tree is the sibling stem's.
- **Do not replace `.venv/bin/python` with `uv run`** — see Context; it has the same cwd coupling.
- **Do not add a `scripts/` directory or any shim.**
- **Do not rewrite prefixes inside `docs/`** — plan folders and session reports record the defect on
  purpose, and the scrub gate now scans `docs/`.
- Do not reformat or re-voice surrounding prose in any of the five files.

## Acceptance check

- **SHALL:** No file under `hooks/` or `skills/` SHALL reference a repo-root `.venv/` path or
  `scripts/wrapup_reconcile.py`.
  - Verify: `grep -rn "\.venv/bin\|scripts/wrapup_reconcile" hooks/ skills/` → **no matches**
    (exit 1). Note this pattern is deliberately broader than the one that missed last time.
- **SHALL:** `bin/tests/test_repo_shape.py` SHALL fail if either pattern reappears in a shipped file.
  - **Prove it by making it fire:** reintroduce one `.venv/bin/python` line, confirm the suite
    fails, remove it, confirm it passes. A check that has never failed is not a check.
- **GIVEN** a reader with their own repo and a `.taskman.toml` at its root, **WHEN** they follow
  §6's bootstrap verbatim, **THEN** the project registered is theirs, not `taskman-tests`.
  - Verify by reading the rewritten steps back: the command that touches the board must run from
    the reader's project directory, not from `ai-wow/taskman`.
- **GIVEN** the rewritten bootstrap, **WHEN** a reader asks "where does the CLI live", **THEN** §6
  answers it exactly once, at the PATH step.
- Verify: `python3 bin/tests/test_repo_shape.py` → 0 failures.
- Verify: `sh githooks/pre-push` → `pre-push: clean`.

## QA contract

- `python3 bin/tests/test_repo_shape.py` → exit 0, with the deliberate-break run quoted
- `sh githooks/pre-push` → `pre-push: clean`
- The broad grep above, reported with its exit code
- `python3 -m py_compile bin/tests/test_repo_shape.py` → exit 0
- Count check: `grep -rc "taskman" skills/wrap-up/SKILL.md` before and after, showing the commands
  survived the rewrite rather than being deleted

## Toolkit

- `Invoke: skill:tdd` — the durable check in `test_repo_shape.py` is real logic guarding a defect
  that already shipped once. Write it, watch it fail against today's tree (29 hits), then fix.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- Prefer **`git commit -- <paths>`** over `git add` + `git commit`.
- **Forbidden:** `git stash`, `git reset --hard`, `git clean -fd`.
- A peer session is running its own mow lanes in this checkout. Before any commit, run
  `git status` and confirm only your own paths are staged.

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail, including the deliberate-break run>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: none pointed (board-less repo — see header)
