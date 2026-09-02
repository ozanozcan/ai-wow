# store-entities: grow the event-log store from one entity to the full board

**Role:** code-edit   **Wave:** 1   **AFK:** yes   **Background:** yes

**Decisions / Specs (pointers):** `-` — this repo is board-less; the working decisions are
d-p1/d-p2/d-p4/d-p6/d-p8 in `docs/plans/taskman-port/plan.md` §Decisions locked, restated
below in full where they bind this lane.

## Goal

`taskman/taskman/eventlog/` handles every board entity — task, feature, pbi, requirement,
decision, capture, session — behind a small generic API (`add`/`update`/`link`/`unlink`/
`state`, plus the existing task-only `claim`/`release`), with a versioned envelope that
replay refuses when it doesn't recognise, per-entity id counters, a public
`log.transaction()` seam, a stale-lock-debris sweep, and a bootstrap entry the migration
exporter can hand a full event stream to. All proven by plain-script tests in
`eventlog/tests/` (auto-discovered by the CI matrix on Linux + Windows).

## Context & decisions (only what this todo needs)

- **Envelope (plan d-p1):** every event is one JSON line
  `{"v": 1, "type": "<entity>.<verb>", "id": N, "ts": "<utc iso>", ...payload}`. Replay
  raises `ValueError` naming the line for: malformed JSON with a newline (existing rule),
  unknown entity, unknown verb, missing `v`, or `v > SUPPORTED_VERSION`. Fail-closed on
  purpose: board and code share a git tree, so an old reader on a new board must stop, not
  silently drop events. The spike's un-versioned `task.add` format has **no live logs** —
  change it freely, no back-compat shim.
- **Per-entity counters (plan d-p4):** replace the single `next_id` file with one JSON file
  `next_ids` (`{"task": N, "feature": N, ...}`), written via the existing tmp +
  `os.replace` pattern. Lost-counter recovery re-derives per entity from replay, exactly as
  `_next_id_locked` does today.
- **Entity set (plan d-p6, d-p8):** `task`, `feature`, `pbi`, `requirement`, `decision`,
  `capture`, `session`. **No `project`, no `tag` entities** — the board dir is the project;
  tags are plain string arrays in fields. Session events exist so `session record`/`list`
  can go dbless (d-p8).
- **Relations as events:** `task` has `blocked_by` (list of task ids, grown/shrunk by
  `task.link`/`task.unlink`), `capture` and `decision` have a `task_id` settable via
  `*.link`/`*.unlink`. An `*.add` may carry initial relation fields.
- **Public transaction seam:** the spike's ship-check flagged `store.py:38,42` reaching into
  `log._lock_path` / `log._append_locked`. Give `log.py` a public
  `transaction(board_dir)` context manager and rewrite `claim` on it; nothing outside
  `log.py` touches an underscore name afterwards.
- **Debt markers (plan d-p2):** `claim`'s full-replay-under-global-lock corner gets
  `# debt: full replay under the board lock per claim, revisit above ~50k events or ~5MB log`.
  Compaction is **not** implemented.
- **Stale-lock debris:** `_break_if_stale`'s rename can leave `board.lock.stale.*` behind on
  a failed unlink — noise on a committed board. Add `sweep_stale_debris(board_dir)`;
  call it from `transaction()` acquisition (cheap: one listdir), so debris never outlives
  the next write.
- **Windows rules are settled — do not relitigate:** `O_EXCL` with `PermissionError`
  treated as contention, mtime-age staleness (never `os.kill(pid, 0)` — it terminates the
  target on Windows), holder keeps its fd open, `O_APPEND` never trusted for atomicity.
  These are in `locking.py`/`log.py` already; extend, don't rewrite.
- Existing style: `eventlog/tests/*.py` are **plain scripts, not pytest** (taskman's
  conftest needs Postgres at import — the exact dependency this package exists to not
  have). Keep that: new tests as plain scripts in the same dir, so the CI matrix's
  directory scan (`.github/workflows/ci.yml` scans `taskman/taskman/eventlog/tests`) picks
  them up on both runners with zero workflow edits.

## Files in scope

- `taskman/taskman/eventlog/log.py`
- `taskman/taskman/eventlog/store.py`
- `taskman/taskman/eventlog/locking.py` (only if the sweep needs a helper here)
- `taskman/taskman/eventlog/schema.py` (new — envelope constants + the entity/verb table +
  the status/priority/lane/surface/kind constant tuples copied from `models.py`, which lane
  D will delete)
- `taskman/taskman/eventlog/__init__.py`
- `taskman/taskman/eventlog/tests/` (new plain-script test files; extend the existing two
  as needed)

## Signatures (the seam lanes C and D build against)

```python
# eventlog/schema.py
SUPPORTED_VERSION = 1
ENTITIES: tuple[str, ...]          # task, feature, pbi, requirement, decision, capture, session
VERBS: dict[str, tuple[str, ...]]  # entity -> allowed verbs (add/set/link/unlink; +claim/release on task; record on session)
STATUSES, PRIORITIES, LANES, SURFACES, CAPTURE_KINDS, REQUIREMENT_STATUSES  # moved verbatim from models.py

# eventlog/store.py
def add(board_dir: Path, entity: str, fields: dict) -> int
def update(board_dir: Path, entity: str, entity_id: int, fields: dict) -> bool   # False: no such id
def link(board_dir: Path, entity: str, entity_id: int, relation: str, target: int) -> bool
def unlink(board_dir: Path, entity: str, entity_id: int, relation: str, target: int) -> bool
def claim(board_dir: Path, task_id: int, agent: str) -> bool                      # CAS, unchanged semantics
def release(board_dir: Path, task_id: int) -> None
def state(board_dir: Path) -> dict[str, dict[int, dict]]                          # entity -> id -> current fields

# eventlog/log.py
def transaction(board_dir: Path)            # context manager: board lock held; yields append(event) callable
def bootstrap(board_dir: Path, events: Iterable[dict], next_ids: dict[str, int]) -> None
    # migration-only: writes a complete events.jsonl + next_ids into an EMPTY board dir;
    # raises if events.jsonl already exists. Validates every event against schema before writing any.
def sweep_stale_debris(board_dir: Path) -> int
```

Adjacent-lane assumptions: lane D calls `state()` once per command and the mutators above;
lane C builds event dicts matching `schema.py` and calls `bootstrap`. Neither touches
underscore names.

## Depends on

- none (wave 1)

## Do NOT

- Do not touch `cli.py`, `models.py`, `db.py`, `wrapup.py`, `metrics.py`, `plan.py`, or
  `pyproject.toml` — lanes B/C/D own those. `schema.py` *copies* the constant tuples from
  `models.py`; it does not import them (models.py dies in wave 2).
- Do not import anything outside the Python standard library anywhere under `eventlog/` —
  the committed AST test (`eventlog/tests/test_store.py:138`) enforces it; extend that test
  to cover `schema.py` rather than exempting it.
- Do not implement compaction, snapshotting, or any read-path cache — d-p2 says never, with
  a debt marker.
- Do not add pytest-style tests here (conftest poisons them with a Postgres requirement) and
  do not edit `.github/workflows/ci.yml` — the scan already covers this test dir.
- Do not weaken or skip the existing concurrency suite; it is the spike's proof and must
  stay green byte-for-byte in behaviour.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- Prefer **`git commit -- <paths>`** over `git add` + `git commit`; new files must be
  `git add`-ed by name first, then still commit with `-- <paths>`.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.
- Before commit while parallel lanes are active, run `git status` and confirm only intended
  paths are staged.

## Acceptance check

- The store SHALL refuse an event it does not recognise: GIVEN a log line with `"v": 2`, an
  unknown type, or no `"v"` key WHEN `replay`/`state` runs THEN it raises `ValueError`
  naming the line number, and no partial state is returned.
- Ids SHALL be per-entity and collision-free: GIVEN an empty board WHEN two processes each
  add 25 tasks and 25 features concurrently THEN 50 distinct task ids and 50 distinct
  feature ids exist and the log parses cleanly (extend `test_concurrency.py`'s worker
  pattern — same contested harness, per-entity counters).
- `claim` SHALL keep its CAS guarantee through the new `transaction()` seam: the existing
  contested-claim scenario in `test_concurrency.py` passes unmodified in what it asserts.
- `bootstrap` SHALL be all-or-nothing: GIVEN a stream containing one invalid event WHEN
  `bootstrap` runs THEN it raises and the board dir contains no `events.jsonl`.
- GIVEN `board.lock.stale.xyz` debris in a board dir WHEN any write transaction runs THEN
  the debris is gone afterwards.
- Verify: `python3 taskman/taskman/eventlog/tests/test_store.py && python3 taskman/taskman/eventlog/tests/test_concurrency.py` plus each new test file, all exit 0.

## QA contract

- All plain-script tests under `eventlog/tests/` exit 0, run individually.
- The AST stdlib-only check covers every `eventlog/*.py` module including new ones.
- tdd skill before production code (red evidence in Verification) — this is new logic on a
  concurrency-critical module.

## Toolkit

- Invoke: `skill:tdd` before each new store capability (envelope refusal, per-entity
  counters, bootstrap).
- Invoke: `skill:adversarial-tester`-style manual mutation pass on `schema.py` validation
  (hypothesis/mutmut are banned here by the stdlib-only rule — follow lane B's spike
  precedent: hand-injected mutants, documented in Verification).

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: <d-p1/d-p2/d-p4/d-p6/d-p8: how, file:line — or "none pointed">
