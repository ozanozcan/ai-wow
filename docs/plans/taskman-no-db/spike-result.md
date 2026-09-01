# taskman-no-db — spike result

**Date:** 2026-09-01
**Stem:** `taskman-no-db`
**Plan:** [`plan.md`](plan.md) · **Dispatch:** [`dispatch/INDEX.md`](dispatch/INDEX.md)
**CI runs:** [33479579913](https://github.com/ozanozcan/ai-wow/actions/runs/33479579913) (`b0fe9ad`, run 1) · [33484818579](https://github.com/ozanozcan/ai-wow/actions/runs/33484818579) (`57b310c`, run 2 — the one that overturned the verdict)

## Verdict — C3 is viable on Windows. Build the port.

**Settled 2026-09-01 by CI run [33506642639](https://github.com/ozanozcan/ai-wow/actions/runs/33506642639),
green on `windows-latest` four consecutive times** after the `PermissionError` fix below. Shape B
(SQLite) is retired as the fallback.

The verdict took three swings, and the history is kept because it is the evidence:

| # | State | Windows result |
|---|---|---|
| 1 | Original store | Green once — and called "proven" on that single run. **That was wrong** |
| 2 | Same store, second run | `concurrent creates` red: a worker crashed, 50 of 100 ids. Verdict withdrawn to NOT PROVEN |
| 3 | `PermissionError` treated as contention | Green ×4 consecutive, `WINDOWS_SKIP` empty, all 11 files run |

**The bug was real and is now understood, not merely absent.** `os.open(..., O_CREAT | O_EXCL)`
raises `PermissionError` on Windows — not `FileExistsError` — when the lock's name is *delete-pending*
(a previous holder unlinked it, but a handle has not finished closing). `exclusive()` caught only
`FileExistsError`, so ordinary contention escaped the retry loop and killed the caller. POSIX frees
the name on unlink and cannot reach that state, which is why 150 contested rounds on macOS never saw
it and the second Windows run did.

**No id collision was observed at any point, before or after the fix.** The store never handed the
same id to two callers; a process crashed. The *safety* property held throughout — only *liveness*
broke. That is why the fix is two lines rather than a redesign.

### What the old verdict said

### Superseded — the withdrawn verdict

(kept for the record)

#### NOT PROVEN. Promising, but do not start the port yet.

> **Amended 2026-09-01, after a second CI run.** An earlier version of this file read
> "C3 is viable. Build the port." That verdict rested on a single Windows run. A second run
> ([33484818579](https://github.com/ozanozcan/ai-wow/actions/runs/33484818579)) contradicted it.
> The original wording is corrected here rather than quietly edited away.

Split the question in two, because the two halves now have different answers:

- **`claim` — holds.** The contested-claim scenario passed on Windows in **both** runs, all six
  checks each time: no round won twice, exactly one winner per round, one claim event per task in
  the log, and replay agreeing with every reported winner. This is the half the spike most doubted,
  and it is the half that survived.
- **Id allocation — intermittent failure on Windows.** In run 2, `concurrent creates` failed: one
  of the two worker processes **crashed** (exit 1) partway through, so 50 ids were allocated
  instead of 100. Run 1 had passed the same scenario.

**The distinction that matters: no id collision has ever been observed.** The failure is a crash,
not two processes receiving the same id — the *safety* property held, the *liveness* property did
not. That is a materially better position than "ids collide", and still not good enough to bet a
port on.

**Shape B (SQLite) therefore stays live as the fallback, not retired.**

### Why the cause is not named here

The test truncated the crashed worker's stderr with `err[:300]` — the head of a traceback, which is
the harness, not the exception. The exception type was on the line that got cut. That reporting bug
is fixed (`_tail()`), so the next Windows run will name it.

**Leading hypothesis, unconfirmed and deliberately not acted on yet:** `add_task` takes the board
lock *twice* — once in `next_id`, once in `append` — so 100 creates churn the same lock filename
through 200 rapid create/delete cycles. On Windows, deletion is not always synchronous, and a
subsequent `os.open(..., O_CREAT | O_EXCL)` on a name whose handle is still closing raises
**`PermissionError`, not `FileExistsError`** — and `exclusive()` catches only `FileExistsError`, so
it would propagate and kill the worker exactly as observed. If that is confirmed, the fix is small
(catch `PermissionError` in the acquire loop, and give `add_task` one critical section instead of
two). It is not being written before the evidence arrives.

## The evidence

| Claim | How it was proven |
|---|---|
| The guarantee is real, not incidental | Against a deliberately lockless store, two OS processes double-won **all 50** contested rounds and produced 50 distinct ids where 100 were required |
| The test has kill power | Orchestrator removed `os.O_EXCL` from the shipped `locking.py`: suite went red, 50/50 double wins. Restored: 3 consecutive clean runs |
| `claim` holds on Windows | **Two** runs, `windows-latest`: contested claim green both times (6 checks each) |
| Id allocation on Windows | **Run 1 green, run 2 red** — a worker crashed, 50 of 100 ids allocated. Intermittent; no collision ever seen |
| `test_store.py` on Windows | 23 checks, 0 failures, both runs |
| The tests actually ran, not skipped | Windows log names each file under `=== <path>` and prints each check; `WINDOWS_SKIP` is empty, so nothing was quarantined |
| No hidden dependency | Independent AST sweep over all four modules: every import resolves to `sys.stdlib_module_names`. No `fcntl` outside a docstring explaining the ban |

## What Windows broke, and what it did not

**It did not break the store.** Three portability decisions taken in advance are why:

- **`fcntl.flock` was never used.** It does not exist on Windows CPython, and Git Bash does not
  change that. The plan rejected it before a line was written.
- **Stale locks break by mtime age, not by liveness probe.** `os.kill(pid, 0)` — the obvious
  POSIX idiom — *terminates the target process* on Windows. Age is portable; the probe is a
  cross-platform trap.
- **The holder keeps its fd open for the whole hold.** On Windows an open handle blocks rename,
  which makes a live holder's lock unbreakable rather than merely unlikely to be broken.

**It did break two pre-existing harness tests**, both unrelated to this stem, and both found only
because the matrix now exists:

| Test | Failure | Status |
|---|---|---|
| `bin/tests/test_repo_shape.py` | `UnicodeDecodeError` — bare `read_text()` decoding UTF-8 docs as cp1252 | **Fixed in this run.** Explicit `encoding="utf-8"` at 6 call sites; green on Windows in the run above |
| `skills/mow/tests/test_tracker_port.py` | `PermissionError [WinError 32]` — `TemporaryDirectory` cleanup while a server subprocess still holds a file | **Open.** Windows refuses to unlink an open file; POSIX does not |
| `bin/tests/test_ai_sync_commit.py` | `porcelain lines classify correctly` — got `[' M global/CLAUDE.md']`, want `[]` | **Open.** Path classification differs on Windows |

The Windows job is therefore **red on master**, on two bugs that predate this stem and are real.
Nothing was weakened or quarantined to hide that — `WINDOWS_SKIP` is empty by choice.

## Latent, not yet failing

- **`bin/ai-sync` has 11 bare `read_text()` calls**, including line 618, which reads *arbitrary
  source files* during a sync. The same cp1252 defect just fixed in `test_repo_shape.py`. It has
  not fired yet only because no synced file has carried a non-ASCII byte on a Windows run.
- **`hooks/peer-session-guard.py` and `peer-session-notice.py`** read JSON markers with bare
  `read_text()`. Safe while markers stay ASCII; not guaranteed.

## What the port now needs

The spike deliberately proved one entity behind no CLI. The port has to answer what it did not:

1. **Event record shape and version tolerance** — what replay does with an event version it does
   not recognise. Sharp enough to book; unbookable here because the repo has no board.
2. **Compaction policy** — never, on demand, or at a size threshold. Replay of a few thousand
   events is milliseconds, so this is not urgent, but it is unanswered.
3. **Migration of the two live Postgres boards** — and whether it is one-way.
4. **Wiring `cli.py` onto the store** — untouched here on purpose. If the spike had failed,
   nothing would have needed unwinding.
5. **Relativizing `AgentSession.transcript_path`** (`taskman/taskman/metrics.py:250`), which
   stores `str(transcript)` verbatim. A committed board carrying absolute paths is wrong on every
   machine but the one that wrote it.
6. **Amending invariant I10 and `README.md:161`** — in the change that *lands* the port, not this
   one. The spike amends no shipped guarantee.

## Known debt carried by the store

`locking.py:76` documents a microsecond non-atomic window between the `stat` and the `rename` in
`_break_if_stale`, with its trigger written next to it: close it with shape B if a doomed-fresh-lock
incident is ever observed. It is unclosable with plain files and was not hidden.
