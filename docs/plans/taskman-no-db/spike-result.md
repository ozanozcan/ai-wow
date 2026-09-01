# taskman-no-db — spike result

**Date:** 2026-09-01
**Stem:** `taskman-no-db`
**Plan:** [`plan.md`](plan.md) · **Dispatch:** [`dispatch/INDEX.md`](dispatch/INDEX.md)
**CI run:** https://github.com/ozanozcan/ai-wow/actions/runs/33479579913 (commit `b0fe9ad`)

## Verdict — C3 is viable. Build the port.

A dbless, append-only event log **can** be trusted under two concurrent processes on Windows.
`O_EXCL` makes both id allocation and `claim` safe without a transaction, and the contested suite
is green on the platform this effort exists for. **Shape B (SQLite) is not needed and stays
retired as the documented fallback.**

This is the answer the spike was commissioned to get, and it was not assumed — the guarantee was
seen to fail before it passed, twice.

## The evidence

| Claim | How it was proven |
|---|---|
| The guarantee is real, not incidental | Against a deliberately lockless store, two OS processes double-won **all 50** contested rounds and produced 50 distinct ids where 100 were required |
| The test has kill power | Orchestrator removed `os.O_EXCL` from the shipped `locking.py`: suite went red, 50/50 double wins. Restored: 3 consecutive clean runs |
| It holds on Windows | CI run above, `windows-latest`: `test_concurrency.py` **18 checks, 0 failures**; `test_store.py` **23 checks, 0 failures** |
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
