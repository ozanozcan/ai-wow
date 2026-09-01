# eventlog-store: a dbless Task store — append-only log, state by replay

**Role:** code-edit   **Wave:** 1   **AFK:** yes   **Background:** yes

**Decisions / Specs (pointers):** `-` — board-less repo, no decision ids exist. Binding decisions
are in `docs/plans/taskman-no-db/plan.md` -> `## Decisions locked`: "Dbless — shape C3",
"Concurrency: `O_EXCL` lockfile", "Absolute paths must be relativized at write time".

## Goal

A `Task` board that works with no database and no third-party package: events appended to
`board/events.jsonl`, state rebuilt by replay, with `O_EXCL` guarding both id allocation and
`claim` so two concurrent processes can never both win. Green on this machine. Lane Z proves it
on Windows.

## Context & decisions (only what this todo needs)

- **What `claim` depends on today is a compare-and-swap.** `taskman/taskman/cli.py:740` runs
  `UPDATE ... WHERE id = ? AND claimed_by IS NULL` and treats `rowcount == 0` as "already
  claimed". That is a test-and-set in one statement, and its atomicity is entirely the
  database's. Invariant I3 — same-wave mow lanes own disjoint file sets — leans on claim being
  trustworthy. Rebuilding this without a transaction is the whole point of the spike.
- **`fcntl.flock` is rejected and must not be used.** It is POSIX-only; it does not exist on
  Windows Python, and Git Bash does not change that (still native Windows CPython). The origin
  brainstorm named it first, which is exactly why this is called out.
- **`O_APPEND` is not atomic on Windows** the way it is on POSIX under `PIPE_BUF`. Do not assume
  "just append, the log is the total order". Serialize writes through the same `O_EXCL` lock.
- **There is no lock or atomic-write helper anywhere in this repo** — not in `hooks/`, `bin/`,
  `skills/`, or `taskman/`. You are writing this from scratch; there is no house pattern to copy.
- **Relativize every path you store.** `AgentSession.transcript_path` stores `str(transcript)`
  verbatim (`taskman/taskman/metrics.py:250`), unlike `source_ref`, whose relative format is
  locked at `taskman/taskman/models.py:36`. The board is committed to git, so an absolute path is
  wrong on every machine but the one that wrote it. This is a portability defect before it is a
  privacy one.
- **Your tests must not live under `taskman/tests/`.** `taskman/conftest.py` calls
  `psycopg.connect()` at conftest import time, so anything collected there hard-requires a
  reachable Postgres and cannot run in CI. Put tests in `taskman/taskman/eventlog/tests/` as
  plain scripts runnable by `python3 <path>`, matching the 8 existing harness tests.

## Files in scope

- `taskman/taskman/eventlog/__init__.py` (new)
- `taskman/taskman/eventlog/locking.py` (new) — the `O_EXCL` primitive
- `taskman/taskman/eventlog/log.py` (new) — append + replay
- `taskman/taskman/eventlog/store.py` (new) — Task operations and `claim`
- `taskman/taskman/eventlog/tests/__init__.py` (new)
- `taskman/taskman/eventlog/tests/test_store.py` (new)
- `taskman/taskman/eventlog/tests/test_concurrency.py` (new)

Nothing outside this list.

## Signatures

Lane Z calls these; settle them here so that lane does not guess. Bodies omitted.

```python
# locking.py
class LockTimeout(Exception): ...
@contextmanager
def exclusive(lock_path: Path, *, timeout: float = 10.0) -> Iterator[None]:
    """O_EXCL lockfile. Raises LockTimeout. Releases on exception. Never fcntl."""

# log.py
def append(board_dir: Path, event: dict) -> None:      # serialized via exclusive()
def replay(board_dir: Path) -> dict[int, dict]:        # id -> current Task state
def next_id(board_dir: Path) -> int:                   # allocated under exclusive()

# store.py
def add_task(board_dir: Path, title: str, **fields) -> int:
def get_task(board_dir: Path, task_id: int) -> dict | None:
def claim(board_dir: Path, task_id: int, agent: str) -> bool:
    """True if this caller won. False if already claimed. Mirrors cli.py:740 semantics."""
def release(board_dir: Path, task_id: int) -> None:
```

`board_dir` is a parameter, never resolved from config — tests pass a temp directory.

## Depends on

- none (lane A is independent; Z depends on both)

## Do NOT

- **Do not modify `cli.py`, `models.py`, `db.py`, or anything under `alembic/`.** Wiring the CLI
  onto this store is the *port*, and the port is explicitly not this run. The spike proves the
  hard part in isolation; if it fails, nothing has to be unwound.
- **Do not import any third-party package** — no `sqlalchemy`, no `psycopg`, no `pydantic`, no
  `portalocker`. Standard library only. This is an acceptance criterion, not a preference.
- **Do not use `fcntl`** (see Context).
- **Do not migrate the two existing Postgres boards**, and do not write anything that reads them.
- **Do not add a `board/` directory to this repo, and do not edit `.gitignore`** — a parallel stem
  owns that file. The store takes `board_dir` as an argument; tests use temp directories.
- Do not build compaction, an index, or a cache. Replay of a few thousand events is milliseconds,
  and shape F was recorded as an escape hatch precisely so it is not built speculatively.

## Acceptance check

- **SHALL:** The store SHALL grant a claim to at most one agent, with no database present.
- **SHALL:** The store SHALL never issue the same task id twice.
- **SHALL:** The store SHALL import no third-party package.
- *Scenario:* `contested claim` | GIVEN task #N exists and is unclaimed | WHEN two processes call
  `claim` on it concurrently | THEN exactly one receives `True` and the other `False`, and a
  replay shows exactly one `claimed_by`.
- *Scenario:* `concurrent creates` | GIVEN an empty board directory | WHEN two processes each add
  50 tasks concurrently | THEN 100 distinct ids exist and `replay()` parses the log without error.
- *Scenario:* `crash mid-write` | GIVEN a writer is killed while holding the lock | WHEN the next
  process runs | THEN it acquires the lock (stale lock is not fatal) and the log still replays.
  This is the case you would be upset to see broken — a wedged board halts every lane.
- Verify: `python3 taskman/taskman/eventlog/tests/test_store.py` and
  `python3 taskman/taskman/eventlog/tests/test_concurrency.py`, both exit 0.

## QA contract

- Write the failing concurrency test **before** the store — invoke `skill:tdd` and record the red
  evidence (the assertion text and exit code) in Verification. A concurrency guarantee that was
  never seen to fail is not a proven guarantee.
- Use real concurrency — `multiprocessing` or `subprocess`, two OS processes. Threads share a GIL
  and will pass against a broken implementation.
- Run the contested test at least 50 iterations; a race that fails 1-in-20 passes a single run.
- Assert the no-third-party rule with a committed test, not by inspection: parse each module with
  `ast` and assert every import resolves to the standard library.
- State plainly in Verification that results are POSIX-only and Windows is unproven.

## Toolkit

- `skill:tdd` before production code (required by the QA contract above).
- `skill:adversarial-tester` on `locking.py` — pure logic with a hostile concurrency surface, the
  case that skill exists for.
- `skill:parallel-debug` if more than one unrelated test fails.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- All files here are new, so `git add` each path by name, confirm `git diff --cached --name-only`
  holds only your paths, then `git commit -- <paths>`.
- **Forbidden** during this run: `git stash`, `git reset --hard`, `git clean -fd`. A peer session
  is live in this checkout.
- **Never push.**

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail, including the red-test evidence>
- Contract items: <each item -> met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: <none pointed — board-less repo; cite plan.md decisions instead>
