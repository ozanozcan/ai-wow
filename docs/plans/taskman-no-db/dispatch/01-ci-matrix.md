# ci-matrix: CI on both platforms, discovering the harness tests

**Role:** code-edit   **Wave:** 1   **AFK:** yes   **Background:** yes

**Decisions / Specs (pointers):** `-` — this repo is deliberately board-less, so no decision or
requirement ids exist. The binding decisions live in `docs/plans/taskman-no-db/plan.md`
-> `## Decisions locked` ("Concurrency: `O_EXCL` lockfile, proven by a cross-platform CI matrix").

## Goal

`.github/workflows/ci.yml` exists and runs this repo's database-free tests on both a Linux and a
Windows runner on every push and pull request to `master`. A fresh clone is covered by CI without
anyone typing `git config core.hooksPath githooks`.

## Context & decisions (only what this todo needs)

- **There is no CI in this repo at all** — no `.github/`, no config of any kind. `origin` is a
  GitHub remote, so Actions is available and unbuilt. You are creating this from zero.
- **The 8 existing harness tests are plain scripts, not pytest**, and all are database-free:
  `hooks/tests/test_stamp_tracker.py`, `test_redact_private.py`, `test_peer_session_notice.py`,
  `bin/tests/test_ai_sync_status.py`, `test_ai_sync_commit.py`, `test_repo_shape.py`,
  `skills/mow/tests/test_board_table.py`, `test_tracker_port.py`. `githooks/pre-push` runs them
  as `python3 <path>`. Match that convention.
- **Do not run `taskman/tests/`.** `taskman/conftest.py` calls `psycopg.connect()` at conftest
  import time, unconditionally, so that suite hard-requires a reachable Postgres. It cannot run
  on either runner and is not this stem's problem.
- **Discover, do not enumerate.** Scan a named list of directories for `test_*.py` rather than
  hardcoding the 8 filenames. Two other work streams are adding test files right now — a peer
  session is writing `hooks/tests/test_session_start_marker.py`, and lane Z adds tests under
  `taskman/taskman/eventlog/tests/`. A hardcoded list goes stale within the week and silently
  under-tests. Directories to scan: `hooks/tests`, `bin/tests`, `skills/*/tests`,
  `taskman/taskman/eventlog/tests`.
- **A missing scan directory is not a failure.** `taskman/taskman/eventlog/tests` does not exist
  until lane B lands. Skip absent directories quietly; fail only on a test that actually fails.

## Files in scope

- `.github/workflows/ci.yml` (new)

## Depends on

- none

## Do NOT

- **Do not add a Postgres service container**, and do not try to make `taskman/tests/` run. That
  suite is out of scope for this stem entirely.
- **Do not edit `githooks/pre-push`.** It works; duplicating its list into CI is the point, and
  changing it is a different decision.
- **Do not edit any test file.** If a test fails on the Windows runner, that is a finding, not
  your bug to fix — see the quarantine rule below.
- **Do not touch** `hooks/`, `bin/`, `skills/`, `README.md`, `HOW-TO-USE.*`, or `.gitignore`. A
  parallel stem (`publish-hygiene`) owns all of them and is running right now.
- Do not add linting, coverage, release automation, or a dependency cache. A matrix that runs the
  existing tests is the whole job.

## Quarantine rule (scope guard)

Some harness tests may not pass on Windows today — `bin/tests/test_ai_sync_status.py` and
`test_ai_sync_commit.py` exercise `bin/ai-sync`, a `sh` script. If a test fails on the Windows
runner, **do not fix it and do not delete it.** Add it to an explicit, commented `WINDOWS_SKIP`
list in the workflow naming the failure, and record it in your `## Verification` block as a
follow-up. Finding this is valuable; chasing it turns a one-file lane into a rabbit hole.

## Acceptance check

- **SHALL:** CI SHALL run the repository's database-free tests on both a Linux and a Windows
  runner for every push and pull request targeting `master`.
- **SHALL:** The workflow SHALL discover tests by scanning directories, so that a test file added
  later is picked up with no edit to the workflow.
- *Scenario:* `new test is picked up` | GIVEN the workflow is committed | WHEN a new
  `test_*.py` is added under any scanned directory | THEN the next CI run executes it without
  the workflow being edited.
- *Scenario:* `absent directory` | GIVEN `taskman/taskman/eventlog/tests` does not exist yet |
  WHEN CI runs | THEN the job succeeds and skips that directory silently.
- *Scenario:* `a real failure still fails` | GIVEN a scanned test exits non-zero | WHEN CI runs |
  THEN the job fails and names that test.
- Verify locally before reporting done, from the repo root:
  `python3 -c "import pathlib,glob; print([p for d in ['hooks/tests','bin/tests','taskman/taskman/eventlog/tests'] for p in glob.glob(d+'/test_*.py')] + glob.glob('skills/*/tests/test_*.py'))"`
  — confirm it lists the 8 existing tests and does not raise on the absent directory.

## QA contract

- Validate the workflow YAML parses: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"`.
  If PyYAML is unavailable, say so in Verification rather than skipping silently.
- Run the discovery expression above and paste its output.
- Run the 8 discovered tests locally with `python3 <path>` and report pass/fail for each.
- You cannot observe a real CI run — this lane never pushes. Report the workflow as *written and
  locally validated*, never as *green*. Lane Z owns proving it actually runs.

## Toolkit

- `skill:tdd` is a poor fit for a YAML workflow; use the discovery expression above as the
  executable check instead. Note the substitution in Verification.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- Prefer `git commit -- <paths>`; `.github/workflows/ci.yml` is new, so `git add` that exact path
  first, then confirm `git diff --cached --name-only` holds only it.
- **Forbidden** during this run: `git stash`, `git reset --hard`, `git clean -fd`. A peer session
  is live in this checkout.
- **Never push.** Pushing is an outward-facing action on a public repo and belongs to lane Z with
  the operator watching.

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item -> met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: <none pointed — this repo is board-less; cite plan.md decisions instead>
