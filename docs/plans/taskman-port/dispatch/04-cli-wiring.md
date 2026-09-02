# cli-wiring: move every subcommand from SQLAlchemy onto the event-log store

**Role:** code-edit   **Wave:** 2   **AFK:** yes   **Background:** yes   **Model:** fable

**Decisions / Specs (pointers):** `-` — board-less repo; working decisions d-p2/d-p6/d-p7/
d-p8 in `docs/plans/taskman-port/plan.md` §Decisions locked, restated below where they bind
this lane.

## Goal

`taskman ...` runs entirely on `eventlog` — all 42 subcommands, with `db.py`, `models.py`,
and the alembic tree deleted, `config.py` stripped of database URL + dotenv machinery,
`wrapup.py`'s three `Session()` sites rewired, and the 17-file pytest suite in
`taskman/tests/` converted from throwaway-Postgres fixtures to tmp-board fixtures — then
added to the CI matrix so the port is proven on `windows-latest` the way the spike was.

## Context & decisions (only what this todo needs)

- **Scale, measured:** `cli.py` (2,980 lines) has 38 `Session()` sites and imports
  `case/func/select/update` + `selectinload` directly; `wrapup.py` has 3 sites
  (`open_task_claims`, `in_progress_tasks`, `_project_id`). `plan.py` and `matching.py`
  are already DB-free but `plan.py:15` imports `LANES, PRIORITIES, STATUSES, SURFACES`
  from `taskman.models` — repoint to `eventlog.schema` (lane A moved them there).
- **The store API is the seam:** read via one `store.state(board_dir)` per command
  invocation; mutate via `add`/`update`/`link`/`unlink`/`claim`/`release`. Filtering,
  sorting, and rendering that SQL did (status filters, priority ordering via
  `PRIORITY_ORDER`, tag matching, `recommend next`'s blocker logic) become plain Python
  over the replayed dicts. Do not add query helpers to the store; the CLI owns semantics
  (that boundary is stated in `eventlog/store.py`'s docstring).
- **Board discovery:** `board_dir = <dir containing nearest .taskman.toml> / "board"` —
  resolved in `cli.py` next to `find_project()` (which stays: slug identity still comes
  from the marker, plan d-p6). The store keeps taking `board_dir` as a parameter.
- **Command surface changes, the full list** (anything else is a straight rewire):
  - `taskman db upgrade` — delete the subcommand; the concept has no referent.
  - `taskman init-db` — becomes `taskman init`: creates `board/` (with `.gitkeep` or the
    first event — your call, say which in Verification) and prints where.
  - `taskman task claim` — same CAS semantics via `store.claim`; the loser's message still
    names the existing claimant (fetch state after a lost claim to report who holds it —
    the spike store's `False` return carries no claimant; `state()` after does).
  - `session record` / `backfill` / `list` — DB row becomes a `session.record` event
    (plan d-p8); the meta.json sidecar behavior is unchanged. Backfill's "skip if
    meta.json exists" rule is unchanged; its dedup against existing rows keys on
    (session_id, transcript_path) like the old unique constraint, over replayed state.
  - Everything Project/Tag-table-shaped disappears (plan d-p6): no project registration
    row on `init`, feature/pbi tags are string-array fields.
- **`warn_if_behind` (d#859) dies with alembic** — no replacement warning; replay's
  version refusal (lane A) is the new schema-drift guard.
- **`config.py`:** keep `find_project` + `find_toolkit` exactly as they are; delete
  `database_url`, `load_dotenv_from_cwd`, the dotenv import, and `DEFAULT_DATABASE_URL`.
- **`pyproject.toml` (plan d-p7):** dependencies become `["pydantic>=2.7"]`; add
  `[project.optional-dependencies] pgexport = ["psycopg[binary]>=3.2"]` (lane C's lazy
  import names this extra). Drop alembic/sqlalchemy/python-dotenv. Keep scripts and dev
  group as-is.
- **Deletions:** `taskman/taskman/db.py`, `taskman/taskman/models.py`,
  `taskman/taskman/alembic.ini`, `taskman/taskman/alembic/` (env.py, guard.py, 9
  versions). `taskman/tests/test_db_upgrade.py` and `test_schema_cli_footguns.py` lose
  their subject — convert what still has meaning (CLI footguns) and delete what doesn't
  (say which, per file, in Verification).
- **Test conversion:** `taskman/conftest.py`'s throwaway-Postgres guard (d#867) becomes a
  tmp-board fixture: chdir into a tmp project dir carrying a `.taskman.toml` + empty
  `board/`. The 17 files' assertions are the port's safety net — port assertions
  faithfully; where a test asserted SQL-specific mechanics (e.g. alembic revision
  stamping), delete with a one-line reason in Verification.
- **CI:** `.github/workflows/ci.yml`'s scan deliberately excludes `taskman/tests` (the
  comment at ~line 59 says why — conftest needed Postgres). That reason dies in this lane:
  add a separate step to both matrix legs that installs the package (`pip install -e
  taskman` + `pytest`, or uv if the runner setup is cleaner) and runs `pytest
  taskman/tests`. Keep the existing plain-script scan exactly as is; do not fold pytest
  into it.
- Store constants: `PRIORITY_ORDER` lives in `models.py` today — recreate it in
  `eventlog/schema.py`? No: lane A owns that file and has already copied the tuples.
  Derive `PRIORITY_ORDER` locally in `cli.py` from `schema.PRIORITIES` if lane A didn't
  export it (check first; don't edit lane A's files).

## Files in scope

- `taskman/taskman/cli.py`
- `taskman/taskman/wrapup.py`
- `taskman/taskman/config.py`
- `taskman/taskman/plan.py` (import line + any models references only)
- `taskman/taskman/matching.py` (only if it references models — verify, likely untouched)
- `taskman/taskman/db.py`, `taskman/taskman/models.py`, `taskman/taskman/alembic.ini`, `taskman/taskman/alembic/` — **deletions**
- `taskman/taskman/README.md` (package doc: dbless usage, deps, init)
- `taskman/conftest.py`
- `taskman/tests/**` — all existing 17 test files + fixtures as needed (lane C owns only tests/test_pgexport.py — leave that file alone)
- `taskman/pyproject.toml`
- `.github/workflows/ci.yml` (the added pytest step only)

## Depends on

- 01-store-entities (the whole store API)
- (02 only via handoff notes — read lane B's Verification for `transcript_path` consumers
  it flagged in `cli.py`/`wrapup.py`, and honor them)

## Do NOT

- Do not edit anything under `taskman/taskman/eventlog/` — lane A owns it; if the store
  API can't express a command's semantics, stop and report the gap in Verification rather
  than patching the store.
- Do not touch `taskman/taskman/pgexport.py` or `taskman/tests/test_pgexport.py` (lane C,
  same wave).
- Do not keep a compatibility shim, dead `Session` import, or optional-Postgres code path.
  The port is a cutover, not a dual backend.
- Do not weaken test assertions to get green — converting a fixture is fine, blunting an
  assertion is not; every deleted test/assertion gets a named reason.
- Do not amend `README.md` (repo root), `HOW-TO-USE.agent.md`, or any shipped-guarantee
  text — lane Z owns the guarantee amendment (I10, Requirements). The package-level
  `taskman/taskman/README.md` is yours; the repo-level story is not.
- Do not run `alembic` anything, and do not drop/alter any live database — the old data
  outlives the port as archive by decision d-p3.
- Do not restructure the existing plain-script scan in `ci.yml` or touch `WINDOWS_SKIP`.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- Prefer **`git commit -- <paths>`** over `git add` + `git commit`; new files must be
  `git add`-ed by name first, then still commit with `-- <paths>`. Deletions: `git rm`
  the exact paths, and confirm with `git diff --cached --name-status` that only your
  paths are staged before any bare commit.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.

## Acceptance check

- Every subcommand SHALL work with no database: GIVEN a tmp project (`.taskman.toml` +
  empty `board/`), no `TASKMAN_DATABASE_URL`, no reachable Postgres WHEN the converted
  pytest suite runs THEN all files pass — `cd taskman && uv run pytest` exits 0.
- The claim CAS SHALL survive the rewire end-to-end: GIVEN one unclaimed task WHEN two
  `taskman task claim` **processes** race (subprocess-level test, not function-level) THEN
  exactly one exits 0 and the loser's stderr names the winner.
- `grep -rn "sqlalchemy\|alembic\|psycopg\|dotenv" taskman/taskman --include="*.py"` SHALL
  return only `pgexport.py`'s lazy psycopg import and comments/docstrings — no live import
  elsewhere (anchored check, L15: prove by import, not by absence in a filtered list).
- `taskman init && taskman task add "x" && taskman board` SHALL round-trip in a tmp dir
  with only the wheel's own deps installed (pydantic, nothing else).
- CI SHALL run the converted suite on both runners: the added step appears in both matrix
  legs and `pytest taskman/tests` is its command (verified locally by running the step's
  exact command; the real matrix run lands in wave Z's push).
- Verify: `cd taskman && uv run pytest` · `python3 taskman/taskman/eventlog/tests/test_store.py` ·
  `python3 taskman/taskman/eventlog/tests/test_concurrency.py` — all exit 0.

## QA contract

- Full converted pytest suite green, dbless (command above).
- Eventlog plain-script suites still green (you didn't touch them; prove it anyway).
- Per-file conversion ledger in Verification: 17 rows — converted / deleted-with-reason.
- tdd for the two genuinely new behaviors (`init`, claim-loser message): red first.
- If >1 unrelated test fails mid-conversion: invoke `skill:parallel-debug` rather than
  serially guessing.

## Toolkit

- Invoke: `skill:tdd` for new behaviors; `skill:parallel-debug` on multi-failure states.
- The built-in `/code-review` runs at the wave gate on the combined diff — expect it; keep
  the diff reviewable (no drive-by reformatting of untouched handlers).

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: <d-p2/d-p6/d-p7/d-p8: how, file:line — or "none pointed">
