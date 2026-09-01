#!/usr/bin/env python3
"""Single-process behavior of the eventlog store.

Plain `python3 taskman/taskman/eventlog/tests/test_store.py` — no pytest,
because taskman/conftest.py requires a reachable Postgres at import time and
this store's whole point is to need no database.

Covers the store's public surface (add/get/claim/release), replay edge cases
including a torn tail from a killed writer, lock acquisition failure modes,
and the acceptance rule that the package imports nothing outside the standard
library (checked by AST, not by inspection).
"""

import ast
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from taskman.eventlog import locking, log, store  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    mark = "ok" if cond else "FAIL"
    print(f"  {mark}  {name}" + ("" if cond else f"  [{detail}]"))
    if not cond:
        FAILURES.append(name)


def test_add_get_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        tid = store.add_task(board, "write the spike", lane="B", wave=1)
        check("first id is 1", tid == 1, f"got {tid}")
        task = store.get_task(board, tid)
        check("title round-trips", task["title"] == "write the spike", f"{task}")
        check("extra fields round-trip", task["lane"] == "B" and task["wave"] == 1, f"{task}")
        check("a fresh task is unclaimed", task["claimed_by"] is None, f"{task}")
        second = store.add_task(board, "another")
        check("ids increment", second == 2, f"got {second}")
        check("missing id returns None", store.get_task(board, 99) is None)


def test_claim_release():
    """Mirrors cli.py cmd_task_claim: win only while claimed_by is NULL."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        tid = store.add_task(board, "contested thing")
        check("claim of an unclaimed task wins", store.claim(board, tid, "alpha") is True)
        check("second claim loses", store.claim(board, tid, "beta") is False)
        check("re-claim by the holder also loses", store.claim(board, tid, "alpha") is False)
        check("claimed_by shows the winner",
              store.get_task(board, tid)["claimed_by"] == "alpha")
        check("claim of a missing id loses", store.claim(board, 99, "alpha") is False)
        store.release(board, tid)
        check("released task is unclaimed", store.get_task(board, tid)["claimed_by"] is None)
        check("released task can be claimed again", store.claim(board, tid, "beta") is True)
        check("claimed_by shows the new winner",
              store.get_task(board, tid)["claimed_by"] == "beta")


def test_replay_edges():
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        check("empty board replays to {}", log.replay(board) == {})

        store.add_task(board, "survivor")
        events = board / "events.jsonl"
        with open(events, "a", encoding="utf-8") as fh:
            fh.write('{"type":"task.add","id":2,"title":"torn')  # no newline: killed writer
        state = log.replay(board)
        check("torn tail is dropped, not fatal", set(state) == {1}, f"{sorted(state)}")

        with open(events, "a", encoding="utf-8") as fh:
            fh.write('this is not json\n')  # newline-terminated garbage: real corruption
        try:
            log.replay(board)
            corrupt_raised = False
        except ValueError:
            corrupt_raised = True
        check("a corrupt full line raises ValueError", corrupt_raised)


def test_lost_counter_never_reissues():
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        store.add_task(board, "one")
        store.add_task(board, "two")
        (board / log.COUNTER_NAME).unlink()  # counter lost, log survives
        tid = store.add_task(board, "three")
        check("id is re-derived past the log's max, never reissued", tid == 3, f"got {tid}")


def test_locking_failure_modes():
    with tempfile.TemporaryDirectory() as tmp:
        lock = Path(tmp) / "board.lock"

        lock.write_text("held by a live process\n", encoding="utf-8")  # fresh mtime
        try:
            with locking.exclusive(lock, timeout=0.3, stale_after=60.0):
                timed_out = False
        except locking.LockTimeout:
            timed_out = True
        check("a fresh held lock times out, not gets stolen", timed_out)
        check("the held lock file was left in place", lock.exists())
        lock.unlink()

        try:
            with locking.exclusive(lock, timeout=1.0):
                raise RuntimeError("boom inside the critical section")
        except RuntimeError:
            pass
        check("lock is released when the body raises", not lock.exists())

        with locking.exclusive(lock, timeout=0.0):  # free lock: no waiting needed
            acquired_at_zero = True
        check("timeout=0 still acquires a free lock", acquired_at_zero)


def test_stdlib_only_by_ast():
    """Acceptance rule: no third-party imports — proven by parse, not inspection."""
    pkg = Path(__file__).resolve().parents[1]
    offenders = []
    for name in ("__init__.py", "locking.py", "log.py", "store.py"):
        tree = ast.parse((pkg / name).read_text(encoding="utf-8"), filename=name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                tops = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    continue  # relative import — this package itself
                tops = [node.module.split(".")[0]]
            else:
                continue
            offenders += [f"{name}:{t}" for t in tops if t not in sys.stdlib_module_names]
    check("every import resolves to the standard library", not offenders, f"{offenders}")


def main():
    test_add_get_roundtrip()
    test_claim_release()
    test_replay_edges()
    test_lost_counter_never_reissues()
    test_locking_failure_modes()
    test_stdlib_only_by_ast()
    print(f"\n{len(FAILURES)} failure(s)" + (": " + ", ".join(FAILURES) if FAILURES else ""))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
