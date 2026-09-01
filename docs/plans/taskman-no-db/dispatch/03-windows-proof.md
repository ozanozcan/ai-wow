# windows-proof: take the contested suite green on Windows, and answer the spike

**Role:** code-edit   **Wave:** 2   **AFK:** no   **Background:** no

**Decisions / Specs (pointers):** `-` — board-less repo. Binding decisions in
`docs/plans/taskman-no-db/plan.md` -> `## Decisions locked`: "Concurrency: `O_EXCL` lockfile,
proven by a cross-platform CI matrix" and "This run is the spike, not the port".

## Goal

The contested-concurrency suite runs green on a **Windows** runner in CI, and the spike's
question is answered in writing: is a dbless store trustworthy under two concurrent agents, or
does the fallback to shape B stand?

## Why this lane is foreground (AFK: no)

Proving CI green requires **pushing to a public GitHub repository** — an outward-facing action
that publishes whatever is in the commit. It needs the operator watching and consenting to each
push. Do not background this lane, and do not push without asking.

## Context & decisions (only what this todo needs)

- **This is the lane the spike exists for.** Lane B proves the store on POSIX. Everything
  genuinely at risk — `O_EXCL` semantics, `O_APPEND` non-atomicity, path separators, stale-lock
  cleanup, process spawn differences — only shows up on the target platform.
- **A POSIX-only green means nothing here**, and this repo has already paid for that lesson: a
  `HOME=` sandbox did nothing on Windows, where `Path.home()` reads `USERPROFILE`. A guard is
  proven by firing it in the environment it exists for.
- **Lane A's workflow discovers tests by directory**, so a file you add under
  `taskman/taskman/eventlog/tests/` is picked up with no workflow edit. If you find yourself
  editing `.github/workflows/ci.yml`, stop and re-read lane A's discovery list first.
- **You may edit lane B's modules.** Fixing what Windows breaks is this lane's job. Wave 1 is
  finished, so there is no same-wave conflict.
- **The answer may be "no".** Shape B (portable SQL) is the recorded fallback if ids or `claim`
  cannot be made trustworthy without a transaction. Reporting that honestly is a successful
  outcome for this lane, not a failure. Do not force a green.

## Files in scope

- `taskman/taskman/eventlog/**` (fixes to lane B's modules and tests)
- `taskman/taskman/eventlog/tests/test_purity.py` (new — the no-third-party AST probe, if lane B
  did not already commit it)
- `docs/plans/taskman-no-db/spike-result.md` (new — the written answer)

## Depends on

- `01-ci-matrix` (the workflow must exist and run)
- `02-eventlog-store` (the store and its suite must exist)

## Do NOT

- **Do not push without the operator's explicit consent, every time.** Public repository.
- **Do not weaken a test to get green.** Lowering the iteration count, dropping to threads,
  skipping the contested case, or marking it `xfail` on Windows converts the spike's entire
  purpose into a green tick. If it cannot pass honestly, say so and recommend the B fallback.
- **Do not start the port.** No `cli.py`, no `models.py`, no `db.py`, no `alembic/`, no other
  entity, no migration of the two live boards.
- **Do not amend `README.md` or `HOW-TO-USE.agent.md`** — invariant I10 stays until the port
  lands, and a parallel stem is touching neighbouring files right now.
- **Do not edit `.gitignore`, `bin/`, `hooks/`, or `skills/`** — the `publish-hygiene` stem owns
  them and is running concurrently.

## Acceptance check

- **SHALL:** The contested-concurrency suite SHALL execute on a Windows runner in CI, and a
  failure on either runner SHALL fail the build.
- **SHALL:** The spike's verdict SHALL be recorded in writing, whichever way it goes.
- *Scenario:* `matrix proves both` | GIVEN the workflow and store are committed | WHEN CI runs on
  a push to `master` | THEN the contested-claim and id-collision tests execute on both the Linux
  and the Windows runner, and both report pass.
- *Scenario:* `windows-only breakage is caught, not hidden` | GIVEN a change that is correct on
  POSIX but races on Windows | WHEN CI runs | THEN the Windows job fails and names the test.
- *Scenario:* `honest no` | GIVEN the contested test cannot be made to pass on Windows | WHEN this
  lane reports | THEN `spike-result.md` records the failure mode and recommends the shape B
  fallback, and no test was weakened to avoid it.
- Verify: a CI run URL for a commit on `master` showing both jobs, with the concurrency tests
  named in the log output. Paste the run URL in Verification.

## QA contract

- Run the full suite locally first: `python3 taskman/taskman/eventlog/tests/test_store.py`,
  `test_concurrency.py`, `test_purity.py`.
- Confirm the Windows job actually *ran the tests* rather than skipping them — quote the lines
  from the CI log naming each test. A green job that collected nothing is the failure mode here.
- Confirm lane A's `WINDOWS_SKIP` quarantine list, if any, does not contain a concurrency test.
- `spike-result.md` states: the verdict, the evidence (CI run URL), what broke on Windows and how
  it was fixed, and what the port would now need.

## Toolkit

- `skill:parallel-debug` when more than one unrelated test fails across the two runners — that is
  precisely the two-independent-problems case.
- `skill:diagnose` if a Windows-only race resists explanation. Do not guess at concurrency bugs.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- Prefer `git commit -- <paths>`; `git add` new paths by name first, then confirm
  `git diff --cached --name-only` holds only them.
- **Forbidden** during this run: `git stash`, `git reset --hard`, `git clean -fd`. A peer session
  is live in this checkout.
- **Ask before every push.** This is the only lane permitted to push, and only with the operator
  watching.

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail, plus the CI run URL>
- Contract items: <each item -> met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: <none pointed — board-less repo; cite plan.md decisions instead>
