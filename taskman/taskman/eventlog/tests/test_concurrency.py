#!/usr/bin/env python3
"""Concurrency proof for the eventlog store — real OS processes, never threads.

Plain `python3 taskman/taskman/eventlog/tests/test_concurrency.py` — no pytest,
because taskman/conftest.py requires a reachable Postgres at import time and
this store's whole point is to need no database.

What these pin down:
  * contested claim   — two subprocesses race `claim` on the same task, 50
    rounds, rendezvousing on a shared wall-clock deadline each round: exactly
    one wins every round, the log carries exactly one claim event per task,
    and replay agrees with the winners. Threads share a GIL and would pass
    against a broken store; these are separate interpreters.
  * concurrent creates — two subprocesses each add 50 tasks flat out: 100
    distinct ids, and the log still replays.
  * crash mid-write    — a writer is SIGKILLed while holding the lock: the
    next comer breaks the stale lock and proceeds, first at the locking layer
    with a short staleness window, then through `add_task` with stock
    defaults. A wedged board would halt every lane.

Results here are POSIX-only; Windows is lane Z's to prove.
"""

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

ROUNDS = 50   # QA contract: at least 50 contested iterations
GAP = 0.05    # seconds between per-round rendezvous deadlines

FAILURES = []


def check(name, cond, detail=""):
    mark = "ok" if cond else "FAIL"
    print(f"  {mark}  {name}" + ("" if cond else f"  [{detail}]"))
    if not cond:
        FAILURES.append(name)


def spawn(mode, *args):
    return subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), mode] + [str(a) for a in args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


def read_events(board):
    events = []
    for line in (board / "events.jsonl").read_text(encoding="utf-8").splitlines():
        events.append(json.loads(line))
    return events


# ---------------------------------------------------------------- workers ---

def worker_claim(board, agent, start, rounds):
    """Rendezvous with the sibling process on wall-clock deadlines, then race."""
    from taskman.eventlog import store

    while time.time() < start:
        pass
    for tid in range(1, rounds + 1):
        while time.time() < start + tid * GAP:
            pass
        won = store.claim(board, tid, agent)
        print(("WON" if won else "LOST"), tid, flush=True)
    return 0


def worker_add(board, prefix, start, count):
    from taskman.eventlog import store

    while time.time() < start:
        pass
    for i in range(count):
        print(store.add_task(board, f"{prefix} {i}"), flush=True)
    return 0


def worker_hold(lock_path):
    """Acquire the lock, announce it, then hang until SIGKILLed — a crash."""
    from taskman.eventlog import locking

    cm = locking.exclusive(Path(lock_path), timeout=5.0)
    cm.__enter__()  # deliberately never exited: the parent kills us here
    print("HOLDING", flush=True)
    time.sleep(60)
    return 0


def worker_main(argv):
    mode = argv[0]
    if mode == "worker-claim":
        return worker_claim(Path(argv[1]), argv[2], float(argv[3]), int(argv[4]))
    if mode == "worker-add":
        return worker_add(Path(argv[1]), argv[2], float(argv[3]), int(argv[4]))
    if mode == "worker-hold":
        return worker_hold(argv[1])
    raise SystemExit(f"unknown worker mode {mode!r}")


# -------------------------------------------------------------- scenarios ---

def contested_claim():
    print(f"contested claim — 2 processes x {ROUNDS} rounds")
    from taskman.eventlog import log, store

    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        for i in range(ROUNDS):
            store.add_task(board, f"task {i + 1}")

        start = time.time() + 0.5
        procs = {a: spawn("worker-claim", board, a, start, ROUNDS) for a in ("alpha", "beta")}
        wins, exits = {}, {}
        for agent, p in procs.items():
            out, err = p.communicate(timeout=120)
            exits[agent] = (p.returncode, err.strip())
            wins[agent] = {int(l.split()[1]) for l in out.splitlines() if l.startswith("WON")}

        for agent, (code, err) in exits.items():
            check(f"claim worker {agent} exited 0", code == 0, f"exit={code} stderr={err[:300]}")
        every = set(range(1, ROUNDS + 1))
        both = wins["alpha"] & wins["beta"]
        check("no round won by both processes", not both, f"double wins: {sorted(both)}")
        check("every round won by exactly one process",
              (wins["alpha"] | wins["beta"]) == every,
              f"unwon: {sorted(every - wins['alpha'] - wins['beta'])}")

        claim_events = [e for e in read_events(board) if e["type"] == "task.claim"]
        per_id = {tid: [e for e in claim_events if e["id"] == tid] for tid in every}
        dupes = {t: len(evs) for t, evs in per_id.items() if len(evs) != 1}
        check("log holds exactly one claim event per task", not dupes, f"{dupes}")

        state = log.replay(board)
        agree = all(
            state[tid]["claimed_by"] == ("alpha" if tid in wins["alpha"] else "beta")
            for tid in every
        )
        check("replay claimed_by matches the reported winner of every round", agree)


def concurrent_creates():
    print("concurrent creates — 2 processes x 50 add_task")
    from taskman.eventlog import log

    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        start = time.time() + 0.5
        procs = {a: spawn("worker-add", board, a, start, 50) for a in ("alpha", "beta")}
        ids, exits = {}, {}
        for agent, p in procs.items():
            out, err = p.communicate(timeout=120)
            exits[agent] = (p.returncode, err.strip())
            ids[agent] = [int(l) for l in out.splitlines()]

        for agent, (code, err) in exits.items():
            check(f"add worker {agent} exited 0", code == 0, f"exit={code} stderr={err[:300]}")
        allocated = ids["alpha"] + ids["beta"]
        check("100 ids allocated", len(allocated) == 100, f"got {len(allocated)}")
        check("all 100 ids distinct", len(set(allocated)) == 100,
              f"only {len(set(allocated))} distinct")
        state = log.replay(board)  # raises if the log does not parse
        check("replay sees all 100 tasks", set(state) == set(allocated),
              f"replay has {len(state)}")


def crash_while_holding():
    print("crash mid-write — writer SIGKILLed while holding the lock")
    from taskman.eventlog import locking, log, store

    # Locking layer: a short staleness window, so the recovery itself is fast.
    with tempfile.TemporaryDirectory() as tmp:
        lock = Path(tmp) / "board.lock"
        holder = spawn("worker-hold", lock)
        line = holder.stdout.readline()
        check("holder announced HOLDING", line.strip() == "HOLDING", repr(line))
        holder.kill()
        holder.wait(timeout=30)
        check("stale lock file survives the kill", lock.exists())
        try:
            with locking.exclusive(lock, timeout=5.0, stale_after=0.5):
                acquired = True
        except locking.LockTimeout:
            acquired = False
        check("next comer breaks the stale lock and acquires", acquired)
        check("broken lock is released again afterwards", not lock.exists())

    # Store layer, stock defaults: the acceptance scenario verbatim.
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        store.add_task(board, "before the crash")
        holder = spawn("worker-hold", board / log.LOCK_NAME)
        holder.stdout.readline()
        holder.kill()
        holder.wait(timeout=30)
        t0 = time.monotonic()
        tid = store.add_task(board, "after the crash")  # defaults must recover
        waited = time.monotonic() - t0
        check("add_task recovers past a crashed holder with stock defaults",
              tid == 2, f"tid={tid}")
        check("recovery happened inside the default timeout", waited < 10.0,
              f"waited {waited:.1f}s")
        state = log.replay(board)
        check("log still replays after the crash", set(state) == {1, 2},
              f"state ids {sorted(state)}")


def main():
    contested_claim()
    concurrent_creates()
    crash_while_holding()
    print(f"\n{len(FAILURES)} failure(s)" + (": " + ", ".join(FAILURES) if FAILURES else ""))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("worker-"):
        sys.exit(worker_main(sys.argv[1:]))
    sys.exit(main())
