#!/usr/bin/env python3
"""Single-process behavior of the eventlog store.

Plain `python3 taskman/taskman/eventlog/tests/test_store.py` — no pytest,
because taskman/conftest.py requires a reachable Postgres at import time and
this store's whole point is to need no database.

Covers the store's public surface (add/update/link/unlink/claim/release/state),
the versioned envelope's fail-closed replay, per-entity id counters, replay
edge cases including a torn tail from a killed writer, lock acquisition
failure modes, and the acceptance rule that the package imports nothing
outside the standard library (checked by AST, not by inspection).
"""

import ast
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from taskman.eventlog import locking, log, schema, store  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    mark = "ok" if cond else "FAIL"
    print(f"  {mark}  {name}" + ("" if cond else f"  [{detail}]"))
    if not cond:
        FAILURES.append(name)


def test_add_state_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        tid = store.add(board, "task", {"title": "write the port", "lane": "B", "wave": 1})
        check("first task id is 1", tid == 1, f"got {tid}")
        task = store.state(board)["task"][tid]
        check("title round-trips", task["title"] == "write the port", f"{task}")
        check("extra fields round-trip", task["lane"] == "B" and task["wave"] == 1, f"{task}")
        check("a fresh task is unclaimed", task["claimed_by"] is None, f"{task}")
        second = store.add(board, "task", {"title": "another"})
        check("task ids increment", second == 2, f"got {second}")
        fid = store.add(board, "feature", {"title": "the feature"})
        check("feature ids count independently of task ids", fid == 1, f"got {fid}")
        state = store.state(board)
        check("feature round-trips under its own entity",
              state["feature"][fid]["title"] == "the feature", f"{state['feature']}")
        check("missing id is absent from state", 99 not in state["task"])
        check("unknown entity is refused at add", _raises(
            lambda: store.add(board, "widget", {"title": "no"})))


def test_session_creation_verb_is_record():
    """d-p8: `session record` emits one session.record event — the creation
    verb for the session entity is `record`, and the log carries it by name."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        sid = store.add(board, "session", {"summary": "did the thing"})
        check("session id allocates from its own counter", sid == 1, f"got {sid}")
        events = [json.loads(l) for l in
                  (board / log.LOG_NAME).read_text(encoding="utf-8").splitlines()]
        check("the log line is session.record, not session.add",
              events[0]["type"] == "session.record", f"{events[0]}")
        check("session replays into state",
              store.state(board)["session"][sid]["summary"] == "did the thing")


def _raises(fn, exc=ValueError):
    try:
        fn()
        return False
    except exc:
        return True


def _line_of(fn):
    """Run fn, return the ValueError message (or None if it did not raise)."""
    try:
        fn()
        return None
    except ValueError as e:
        return str(e)


def test_envelope_refusal():
    """d-p1: fail closed. An event replay does not recognise stops the world,
    naming the line — never a silent skip."""
    cases = [
        ("v above SUPPORTED_VERSION",
         {"v": 2, "type": "task.add", "id": 1, "ts": "t", "fields": {"title": "x"}}),
        ("missing v",
         {"type": "task.add", "id": 1, "ts": "t", "fields": {"title": "x"}}),
        ("unknown entity",
         {"v": 1, "type": "widget.add", "id": 1, "ts": "t", "fields": {}}),
        ("unknown verb",
         {"v": 1, "type": "task.explode", "id": 1, "ts": "t"}),
        ("verb valid on another entity only",
         {"v": 1, "type": "feature.claim", "id": 1, "ts": "t", "agent": "a"}),
        ("non-integer id",
         {"v": 1, "type": "task.add", "id": "7", "ts": "t", "fields": {"title": "x"}}),
    ]
    for name, bad in cases:
        with tempfile.TemporaryDirectory() as tmp:
            board = Path(tmp)
            store.add(board, "task", {"title": "good line first"})
            with open(board / log.LOG_NAME, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(bad) + "\n")
            msg = _line_of(lambda: log.replay(board))
            check(f"replay refuses: {name}", msg is not None)
            check(f"refusal names the line: {name}",
                  msg is not None and "line 2" in msg, f"msg={msg!r}")


def test_set_refuses_protected_fields():
    """`set` must not bypass the claim CAS or rewrite an id: claimed_by moves
    only via claim/release, and ids are never reassigned (d-p4). Refused at
    the store layer, and fail-closed (d-p1) for a hand-written set event."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        tid = store.add(board, "task", {"title": "guarded"})
        check("store.update refuses claimed_by", _raises(
            lambda: store.update(board, "task", tid, {"claimed_by": "sneak"})))
        check("store.update refuses id", _raises(
            lambda: store.update(board, "task", tid, {"id": 99})))
        task = store.state(board)["task"][tid]
        check("refused updates wrote nothing",
              task["claimed_by"] is None and task["id"] == tid, f"{task}")
        for field, value in (("claimed_by", "sneak"), ("id", 99)):
            with open(board / log.LOG_NAME, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"v": 1, "type": "task.set", "id": tid,
                                     "ts": "t", "fields": {field: value}}) + "\n")
            msg = _line_of(lambda: log.replay(board))
            check(f"replay refuses a hand-written set carrying {field}",
                  msg is not None and "line 2" in msg, f"msg={msg!r}")
            (board / log.LOG_NAME).write_text(
                json.dumps({"v": 1, "type": "task.add", "id": tid, "ts": "t",
                            "fields": {"title": "guarded"}}) + "\n", encoding="utf-8")


def test_create_refuses_id_in_fields():
    """A create's fields must not smuggle an `id`: the id lives in the
    envelope, and a fields id desyncs the table key from the object's
    reported id (claim targets the wrong task). Refused at the store layer,
    and fail-closed (d-p1) for a hand-written add line."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        check("store.add refuses id inside fields", _raises(
            lambda: store.add(board, "task", {"title": "x", "id": 99})))
        check("refused add wrote no event", store.state(board)["task"] == {})
        tid = store.add(board, "task", {"title": "clean"})
        with open(board / log.LOG_NAME, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"v": 1, "type": "task.add", "id": 2, "ts": "t",
                                 "fields": {"title": "smuggler", "id": 99}}) + "\n")
        msg = _line_of(lambda: log.replay(board))
        check("replay refuses a hand-written add smuggling id",
              msg is not None and "line 2" in msg, f"msg={msg!r}")


def _replay_refusal(board, bad_event):
    """Append `bad_event` as line 2, replay, and return None when replay
    fail-closed correctly (ValueError naming line 2) — else what went wrong."""
    with open(board / log.LOG_NAME, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(bad_event) + "\n")
    try:
        log.replay(board)
        return "did not raise"
    except ValueError as e:
        return None if "line 2" in str(e) else f"does not name line 2: {e}"
    except Exception as e:  # a bare KeyError/TypeError is the bug under test
        return f"escaped as {type(e).__name__}: {e}"


def test_malformed_payloads_fail_closed():
    """d-p1: a link/unlink/claim event with a missing or mistyped payload key
    must be a ValueError naming the line — never a bare KeyError."""
    cases = [
        ("link missing relation",
         {"v": 1, "type": "task.link", "id": 1, "ts": "t", "target": 2}),
        ("link missing target",
         {"v": 1, "type": "task.link", "id": 1, "ts": "t", "relation": "blocked_by"}),
        ("unlink missing target",
         {"v": 1, "type": "task.unlink", "id": 1, "ts": "t", "relation": "blocked_by"}),
        ("link with non-string relation",
         {"v": 1, "type": "task.link", "id": 1, "ts": "t", "relation": 5, "target": 2}),
        ("link with non-integer target",
         {"v": 1, "type": "task.link", "id": 1, "ts": "t", "relation": "blocked_by",
          "target": "2"}),
        ("claim missing agent",
         {"v": 1, "type": "task.claim", "id": 1, "ts": "t"}),
        ("claim with non-string agent",
         {"v": 1, "type": "task.claim", "id": 1, "ts": "t", "agent": 5}),
    ]
    for name, bad in cases:
        with tempfile.TemporaryDirectory() as tmp:
            board = Path(tmp)
            store.add(board, "task", {"title": "good line first"})
            problem = _replay_refusal(board, bad)
            check(f"replay refuses, naming the line: {name}", problem is None, problem)


def test_relation_fields_guarded():
    """A relation field in a `set` (or a mis-shaped one in an `add`) would
    brick every future replay with a TypeError. Relations change only via
    link/unlink; an add's initial relation fields must match their shape."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        tid = store.add(board, "task", {"title": "linked"})
        check("store.update refuses a relation field", _raises(
            lambda: store.update(board, "task", tid, {"blocked_by": 5})))
        check("store.update refuses a relation field even when well-shaped", _raises(
            lambda: store.update(board, "task", tid, {"blocked_by": [5]})))
        check("refused relation set wrote nothing",
              store.state(board)["task"][tid]["blocked_by"] == [])
        problem = _replay_refusal(board, {"v": 1, "type": "task.set", "id": tid,
                                          "ts": "t", "fields": {"blocked_by": 5}})
        check("replay refuses a hand-written set carrying a relation", problem is None, problem)

    cases = [
        ("scalar blocked_by in an add",
         {"v": 1, "type": "task.add", "id": 2, "ts": "t",
          "fields": {"title": "x", "blocked_by": 3}}),
        ("non-integer member in blocked_by",
         {"v": 1, "type": "task.add", "id": 2, "ts": "t",
          "fields": {"title": "x", "blocked_by": ["3"]}}),
        ("non-integer scalar in a one-relation add",
         {"v": 1, "type": "decision.add", "id": 1, "ts": "t",
          "fields": {"title": "d", "task_id": "1"}}),
    ]
    for name, bad in cases:
        with tempfile.TemporaryDirectory() as tmp:
            board = Path(tmp)
            store.add(board, "task", {"title": "good line first"})
            problem = _replay_refusal(board, bad)
            check(f"replay refuses: {name}", problem is None, problem)

    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        store.add(board, "task", {"title": "target"})
        tid = store.add(board, "task", {"title": "migrated", "blocked_by": [1]})
        check("an add may still carry a well-shaped list relation",
              store.state(board)["task"][tid]["blocked_by"] == [1])


def test_duplicate_create_id_fails_closed():
    """The counter invariant (d-p4) means a second create with the same id can
    only be a corrupted or hand-edited log — replay refuses it (d-p1) rather
    than silently overwriting the first object."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        tid = store.add(board, "task", {"title": "original"})
        problem = _replay_refusal(board, {"v": 1, "type": "task.add", "id": tid,
                                          "ts": "t", "fields": {"title": "usurper"}})
        check("replay refuses a duplicate create id, naming the line",
              problem is None, problem)


def test_booleans_are_not_integers():
    """bool is an int subclass: `true` would pass an isinstance(int) check and
    id=true hashes to 1 — silently mutating task #1. Refused everywhere an
    integer is expected."""
    cases = [
        ("v is true",
         {"v": True, "type": "task.add", "id": 2, "ts": "t", "fields": {"title": "x"}}),
        ("id is true",
         {"v": 1, "type": "task.set", "id": True, "ts": "t", "fields": {"title": "x"}}),
        ("target is true",
         {"v": 1, "type": "task.link", "id": 1, "ts": "t", "relation": "blocked_by",
          "target": True}),
        ("boolean member in blocked_by",
         {"v": 1, "type": "task.add", "id": 2, "ts": "t",
          "fields": {"title": "x", "blocked_by": [True]}}),
    ]
    for name, bad in cases:
        with tempfile.TemporaryDirectory() as tmp:
            board = Path(tmp)
            store.add(board, "task", {"title": "good line first"})
            problem = _replay_refusal(board, bad)
            check(f"replay refuses: {name}", problem is None, problem)


def test_update():
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        tid = store.add(board, "task", {"title": "before", "status": "todo"})
        check("update of an existing id returns True",
              store.update(board, "task", tid, {"status": "in_progress"}) is True)
        task = store.state(board)["task"][tid]
        check("updated field shows the new value", task["status"] == "in_progress", f"{task}")
        check("untouched fields survive an update", task["title"] == "before", f"{task}")
        check("update of a missing id returns False and writes nothing",
              store.update(board, "task", 99, {"status": "done"}) is False)
        check("missing id still absent after failed update",
              99 not in store.state(board)["task"])


def test_link_unlink():
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        a = store.add(board, "task", {"title": "a"})
        b = store.add(board, "task", {"title": "b"})
        c = store.add(board, "task", {"title": "c"})
        check("link grows blocked_by", store.link(board, "task", a, "blocked_by", b) is True)
        store.link(board, "task", a, "blocked_by", c)
        check("blocked_by lists both targets",
              store.state(board)["task"][a]["blocked_by"] == [b, c])
        check("re-link is idempotent",
              store.link(board, "task", a, "blocked_by", b) is True and
              store.state(board)["task"][a]["blocked_by"] == [b, c])
        check("unlink shrinks blocked_by",
              store.unlink(board, "task", a, "blocked_by", b) is True and
              store.state(board)["task"][a]["blocked_by"] == [c])
        check("link on a missing id returns False",
              store.link(board, "task", 99, "blocked_by", b) is False)
        check("link on an unknown relation raises", _raises(
            lambda: store.link(board, "task", a, "tags", b)))

        cid = store.add(board, "capture", {"body": "an insight"})
        store.link(board, "capture", cid, "task_id", a)
        check("capture.task_id is a scalar link",
              store.state(board)["capture"][cid]["task_id"] == a)
        store.unlink(board, "capture", cid, "task_id", a)
        check("capture.task_id unlinks back to None",
              store.state(board)["capture"][cid]["task_id"] is None)

        did = store.add(board, "decision", {"title": "d", "task_id": b})
        check("an add may carry an initial relation field",
              store.state(board)["decision"][did]["task_id"] == b)


def test_replay_edges():
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        empty = log.replay(board)
        check("empty board replays to empty per-entity maps",
              all(empty[e] == {} for e in schema.ENTITIES), f"{empty}")

        store.add(board, "task", {"title": "survivor"})
        events = board / log.LOG_NAME
        with open(events, "a", encoding="utf-8") as fh:
            fh.write('{"v":1,"type":"task.add","id":2,"fields":{"title":"torn')  # killed writer
        state = log.replay(board)
        check("torn tail is dropped, not fatal", set(state["task"]) == {1},
              f"{sorted(state['task'])}")

        with open(events, "a", encoding="utf-8") as fh:
            fh.write('this is not json\n')  # newline-terminated garbage: real corruption
        check("a corrupt full line raises ValueError", _raises(lambda: log.replay(board)))


def test_claim_release():
    """Mirrors cli.py cmd_task_claim: win only while claimed_by is NULL."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        tid = store.add(board, "task", {"title": "contested thing"})
        check("claim of an unclaimed task wins", store.claim(board, tid, "alpha") is True)
        check("second claim loses", store.claim(board, tid, "beta") is False)
        check("re-claim by the holder also loses", store.claim(board, tid, "alpha") is False)
        check("claimed_by shows the winner",
              store.state(board)["task"][tid]["claimed_by"] == "alpha")
        check("claim of a missing id loses", store.claim(board, 99, "alpha") is False)
        store.release(board, tid)
        check("released task is unclaimed",
              store.state(board)["task"][tid]["claimed_by"] is None)
        check("released task can be claimed again", store.claim(board, tid, "beta") is True)
        check("claimed_by shows the new winner",
              store.state(board)["task"][tid]["claimed_by"] == "beta")


def test_replay_cas_first_claim_wins():
    """Two claim events in the raw log (a bootstrap stream can carry claim
    history): replay honors the first, exactly like the live CAS."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        tid = store.add(board, "task", {"title": "raced"})
        with open(board / log.LOG_NAME, "a", encoding="utf-8") as fh:
            for agent in ("alpha", "beta"):
                fh.write(json.dumps({"v": 1, "type": "task.claim", "id": tid,
                                     "ts": "t", "agent": agent}) + "\n")
        check("replay keeps the first claim, not the last",
              store.state(board)["task"][tid]["claimed_by"] == "alpha")


def test_lost_counter_never_reissues():
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        store.add(board, "task", {"title": "one"})
        store.add(board, "task", {"title": "two"})
        store.add(board, "feature", {"title": "f-one"})
        (board / log.COUNTER_NAME).unlink()  # counter lost, log survives
        tid = store.add(board, "task", {"title": "three"})
        check("task id is re-derived past the log's max, never reissued",
              tid == 3, f"got {tid}")
        fid = store.add(board, "feature", {"title": "f-two"})
        check("feature id re-derives from its own entity's max, not the task's",
              fid == 2, f"got {fid}")


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


def test_stale_debris_swept_by_writes():
    """_break_if_stale's rename can leave board.lock.stale.* behind on a
    failed unlink — noise on a committed board. Any write transaction sweeps
    it, so debris never outlives the next write."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        debris = board / "board.lock.stale.1234.99"
        debris.write_text("leftover\n", encoding="utf-8")
        check("sweep_stale_debris reports what it removed",
              log.sweep_stale_debris(board) == 1)
        check("debris is gone after an explicit sweep", not debris.exists())

        debris.write_text("leftover again\n", encoding="utf-8")
        (board / "board.lock.stale.5678.11").write_text("more\n", encoding="utf-8")
        store.add(board, "task", {"title": "any write"})
        leftovers = [p.name for p in board.glob("board.lock.stale.*")]
        check("any write transaction sweeps all debris", not leftovers, f"{leftovers}")
        check("the write itself still landed",
              store.state(board)["task"][1]["title"] == "any write")


def test_stdlib_only_by_ast():
    """Acceptance rule: no third-party imports — proven by parse, not inspection."""
    pkg = Path(__file__).resolve().parents[1]
    offenders = []
    for name in ("__init__.py", "locking.py", "log.py", "schema.py", "store.py"):
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


def test_no_underscore_reach_outside_log():
    """The spike ship-check finding: store.py reached into log._lock_path /
    log._append_locked. The public transaction() seam replaces that; nothing
    outside log.py touches an underscore name of a sibling module again."""
    pkg = Path(__file__).resolve().parents[1]
    offenders = []
    for name in ("__init__.py", "schema.py", "store.py"):
        tree = ast.parse((pkg / name).read_text(encoding="utf-8"), filename=name)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and node.attr.startswith("_")
                    and isinstance(node.value, ast.Name)
                    and node.value.id in ("log", "locking", "schema")):
                offenders.append(f"{name}: {node.value.id}.{node.attr}")
    check("no module but log.py touches a sibling's underscore name",
          not offenders, f"{offenders}")


def main():
    test_add_state_roundtrip()
    test_session_creation_verb_is_record()
    test_set_refuses_protected_fields()
    test_create_refuses_id_in_fields()
    test_malformed_payloads_fail_closed()
    test_relation_fields_guarded()
    test_duplicate_create_id_fails_closed()
    test_booleans_are_not_integers()
    test_update()
    test_link_unlink()
    test_envelope_refusal()
    test_replay_edges()
    test_claim_release()
    test_replay_cas_first_claim_wins()
    test_lost_counter_never_reissues()
    test_locking_failure_modes()
    test_stale_debris_swept_by_writes()
    test_stdlib_only_by_ast()
    test_no_underscore_reach_outside_log()
    print(f"\n{len(FAILURES)} failure(s)" + (": " + ", ".join(FAILURES) if FAILURES else ""))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
