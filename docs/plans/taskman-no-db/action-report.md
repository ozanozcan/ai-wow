---
Date: 2026-09-01
Project slug: taskman-no-db
Plan: [`plan.md`](plan.md)
Dispatch: [`dispatch/INDEX.md`](dispatch/INDEX.md)
Spike result: [`spike-result.md`](spike-result.md)
CI run: https://github.com/ozanozcan/ai-wow/actions/runs/33479579913
Commit: `b0fe9ad`
---

# Action report — taskman-no-db (the C3 event-log spike)

## Outcome

| Item | Status |
|---|---|
| CI matrix on Linux + Windows, discovering tests by directory scan | **shipped** |
| Dbless append-only `Task` store (`O_EXCL` id allocation + claim) | **shipped** |
| Contested-concurrency suite green on Windows | **shipped** — all 3 scenarios green on `windows-latest`, 4 consecutive runs, nothing skipped |
| The spike's verdict, in writing | **settled** — `spike-result.md`: **C3 is viable on Windows, build the port** (green ×4 after the `PermissionError` fix) |
| `test_repo_shape.py` cp1252 fix | **shipped** (operator-approved scope widening) |
| Windows job green overall | **not achieved** — red on two pre-existing harness bugs, deliberately not quarantined |
| CLI wiring, other entities, board migration | **not started** — the port, explicitly out of scope |

## Wave results

**Wave 1 (parallel, isolated worktrees)**

- **Lane A — `ci-matrix`.** `.github/workflows/ci.yml` built from zero: `ubuntu-latest` + `windows-latest`,
  `fail-fast: false`, triggered on push and PR to `master`. Discovers tests by scanning
  `hooks/tests`, `bin/tests`, `skills/*/tests`, `taskman/taskman/eventlog/tests`. Two deviations
  announced, not buried: `sys.executable` instead of literal `python3` (not guaranteed on Windows),
  and an empty-scan guard so a moved directory cannot read as green. Proved by killing three mutants
  of its own driver rather than by inspection.
- **Lane B — `eventlog-store`.** `locking.py` / `log.py` / `store.py` plus two test files.
  Stale locks break by mtime age, never by `os.kill(pid, 0)` — that call *terminates* the target on
  Windows. Holder keeps its fd open, so a live lock is unbreakable there. Ids come from a counter
  file via atomic `os.replace`, never from log length, so an id survives a lost add event.

**Wave 1 gate.** No stack reviewer spawned (INDEX `Review flags: -` — no roster agent covers plain
Python). Orchestrator verified independently rather than trusting the reports: removed `os.O_EXCL`
from the shipped `locking.py` and the suite went red 50/50; restored, 3 clean runs. Independent AST
sweep found zero third-party imports. Injected a failure into `test_store.py` to prove it exits
non-zero under lane A's driver — the silent-false-pass risk lane A had flagged.

**Wave 2 (foreground)**

- **Lane Z — `windows-proof`.** Committed and pushed with operator consent (private repo; pre-push
  redaction gate clean). CI ran both runners. Linux green in 22s. Windows ran all 11 discovered test
  files; the eventlog suites passed; two unrelated tests failed.

## Decisions locked

- ~~**C3 is viable. Shape B stays retired.**~~ **Overturned by CI run 33484818579** (see
  `spike-result.md` amendment). `claim` is trustworthy on Windows across two runs; **id
  allocation crashed a worker in run 2**. No id collision was ever observed — the failure is a
  crash, not a double-allocation. **Shape B stays live as the fallback.**
- **Nothing was weakened to get green.** `WINDOWS_SKIP` is empty by choice. The Windows job is red
  on master, on two real pre-existing bugs, and that is the honest state.
- **The cross-lane seam worked unprompted.** Lane A's discover-don't-enumerate decision picked up
  lane B's two new tests *and* a peer stem's new test — 11 files where the repo had 8 — with no
  workflow edit.

## Open / deferred

**Windows bugs the matrix surfaced (both pre-existing, neither this stem's):**
- `skills/mow/tests/test_tracker_port.py` — `PermissionError [WinError 32]`: `TemporaryDirectory`
  cleanup while a server subprocess holds a file.
- `bin/tests/test_ai_sync_commit.py` — `porcelain lines classify correctly`: got
  `[' M global/CLAUDE.md']`, want `[]`. Path classification differs on Windows.

**Latent, not yet failing:**
- `bin/ai-sync` has 11 bare `read_text()` calls, including line 618 which reads arbitrary source
  files during a sync — the same cp1252 defect just fixed in `test_repo_shape.py`.
- `hooks/peer-session-guard.py`, `hooks/peer-session-notice.py` read JSON markers with bare
  `read_text()`.

**Ship-check findings (all Minor, all port inputs):**
- `store.py:38,42` reaches into `log.py`'s private API (`_lock_path`, `_append_locked`). Correct —
  `claim` needs one critical section — but the seam should become a public `log.transaction()`
  before the port grows more callers.
- `claim` does a full log replay under a global lock on every call. A deliberate corner per the
  brief, but it carries no `# debt:` marker, unlike `locking.py:76`.
- Stale-lock debris (`board.lock.stale.*`) can survive a failed unlink — noise on a board committed
  to git. Wants a sweep-on-startup in the port.
- `plan.md`'s phrase "`Task` entity only, behind the existing CLI" is ambiguous against the brief's
  "do not touch `cli.py`". Tighten in the port's plan.

**Port work named in `spike-result.md`:** event-record shape and version tolerance, compaction
policy, migration of the two live Postgres boards, CLI wiring, relativizing
`AgentSession.transcript_path` (`taskman/taskman/metrics.py:250`), and amending I10 + `README.md:161`
in the change that lands the port.


## Amendment — 2026-09-01, after CI run 2

This report was written after a single Windows CI run. A second run on a later commit
([33484818579](https://github.com/ozanozcan/ai-wow/actions/runs/33484818579)) changed the outcome,
and the change is recorded here rather than by rewriting history:

- **Both Windows fixes from this session worked.** `test_ai_sync_commit.py` and
  `test_tracker_port.py` both left the FAILED list, confirming the `as_posix()` and `sandbox()`
  fixes on the platform they were written for.
- **`taskman/taskman/eventlog/tests/test_concurrency.py` failed** — a `concurrent creates` worker
  crashed, 50 of 100 ids allocated. The contested-claim half passed, as it did in run 1.
- **The cause is not yet known**, because the test truncated the worker's stderr from the head
  (`err[:300]`), discarding the exception line. Fixed to report the tail; the next run will name it.
- **Consequence:** the spike's question is *not* settled. `claim` looks sound; id allocation is
  unresolved on Windows. The port should not start on this evidence.

## Verify

| Step | Result |
|---|---|
| Full harness suite, locally (11 files) | pass |
| CI — `ubuntu-latest` | pass, 22s |
| CI — `windows-latest` | eventlog suites pass (18 + 23 checks); job red on 2 pre-existing tests |
| Kill-power check (orchestrator removed `O_EXCL`) | suite went red 50/50, restored clean ×3 |
| Third-party import sweep (independent AST) | zero |
| Injected-failure check under CI driver | exit 1 — tests fail loudly |
| cp1252 fix proven | bare `read_text()` raises; explicit utf-8 reads 29,618 chars; green on Windows |
| `ship-check` | Layer 1: 1 · Layer 2: 2 · Layer 3: 1 — all Minor, no Critical spec miss |
| `test-coverage` | n/a — module built test-first, 42 checks, kill-power proven by mutation |
| `adversarial-tester` | run by lane B on `locking.py` (manual procedure; hypothesis/mutmut would violate the stdlib-only rule) — 4 mutants killed, 1 equivalent, 0 product bugs |
| Board sync (`taskman plan mark-shipped`) | n/a — repo is deliberately board-less, no `.taskman.toml` |

**Finding triage.** No taskman board exists in this repo, so findings carry no ids. Classified per
mow go §3: the cp1252 defect was **(a) mechanizable** and fixed in-run with the matrix that catches
it; the two Windows harness bugs and the ship-check Minors are **(c) one-off**, recorded here and in
`spike-result.md` since there is no board to file them on.

## Amendment 2 — 2026-09-01, verdict settled

The withdrawn verdict is restored, on evidence rather than on a single run.

`exclusive()` caught only `FileExistsError`. On Windows, opening a lock whose name is delete-pending
raises `PermissionError` instead, so routine contention escaped the retry loop and killed the
caller. Treating both as "held, retry" fixed it: **green ×4 consecutively** on `windows-latest`,
where the unfixed store failed 2 of 3 runs.

Sequence worth keeping, because each step only became visible once the previous one cleared:
the CI matrix exposed three Windows bugs → fixing two of them unmasked the third, which was the
spike's own core test → its stderr truncation (`err[:300]`, the head of a traceback) hid the
exception → fixing the reporting named `PermissionError` → the fix was two lines.

Nothing was ever quarantined. `WINDOWS_SKIP` is still empty.
