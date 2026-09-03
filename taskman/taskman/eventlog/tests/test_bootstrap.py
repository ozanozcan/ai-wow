#!/usr/bin/env python3
"""bootstrap() — the migration exporter's entry into an empty board dir.

Plain `python3 taskman/taskman/eventlog/tests/test_bootstrap.py` — no pytest,
because taskman/conftest.py requires a reachable Postgres at import time and
this store's whole point is to need no database.

Pins down: a full stream lands whole (events + per-entity counters, original
ids preserved — plan d-p4), a stream with one invalid event writes NOTHING
(all-or-nothing), and an existing events.jsonl is a refusal, never an
overwrite.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from taskman.eventlog import log, schema, store  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    mark = "ok" if cond else "FAIL"
    print(f"  {mark}  {name}" + ("" if cond else f"  [{detail}]"))
    if not cond:
        FAILURES.append(name)


def _event(kind, eid, **payload):
    return {"v": 1, "type": kind, "id": eid, "ts": "2026-01-01T00:00:00+00:00", **payload}


GOOD_STREAM = [
    _event("task.add", 868, fields={"title": "the famous task"}),
    _event("feature.add", 3, fields={"title": "a feature", "tags": ["port"]}),
    _event("session.record", 12, fields={"summary": "migrated session"}),
    _event("task.claim", 868, agent="alpha"),
]
GOOD_COUNTERS = {"task": 869, "feature": 4, "session": 13}


def test_happy_path():
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        log.bootstrap(board, list(GOOD_STREAM), dict(GOOD_COUNTERS))
        state = store.state(board)
        check("original ids are preserved (d-p4): task #868 stays #868",
              state["task"][868]["title"] == "the famous task")
        check("claim in the stream replays", state["task"][868]["claimed_by"] == "alpha")
        check("session.record replays", state["session"][12]["summary"] == "migrated session")
        tid = store.add(board, "task", {"title": "first post-migration task"})
        check("next task id continues from the seeded counter", tid == 869, f"got {tid}")
        fid = store.add(board, "feature", {"title": "next feature"})
        check("next feature id continues from its own seeded counter", fid == 4, f"got {fid}")


def test_all_or_nothing():
    bad_streams = {
        "an event with no v": [GOOD_STREAM[0], {"type": "task.add", "id": 2, "fields": {}}],
        "an unknown entity": [GOOD_STREAM[0], _event("widget.add", 1, fields={})],
        "a future version": [GOOD_STREAM[0], _event("task.add", 2, fields={}) | {"v": 2}],
        "an unknown relation": [GOOD_STREAM[0],
                                _event("task.link", 868, relation="tags", target=1)],
        "a scalar relation field in an add": [
            _event("task.add", 868, fields={"title": "t", "blocked_by": 3})],
        "a set carrying a relation field": [
            GOOD_STREAM[0], _event("task.set", 868, fields={"blocked_by": [3]})],
        "a set carrying claimed_by": [
            GOOD_STREAM[0], _event("task.set", 868, fields={"claimed_by": "x"})],
        "a link with no target": [GOOD_STREAM[0],
                                  _event("task.link", 868, relation="blocked_by")],
    }
    for name, stream in bad_streams.items():
        with tempfile.TemporaryDirectory() as tmp:
            board = Path(tmp)
            try:
                log.bootstrap(board, stream, {"task": 869})
                raised = False
            except ValueError:
                raised = True
            check(f"bootstrap raises on {name}", raised)
            check(f"no events.jsonl was written for {name}",
                  not (board / log.LOG_NAME).exists())
            check(f"no counter file was written for {name}",
                  not (board / log.COUNTER_NAME).exists())

    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        try:
            log.bootstrap(board, GOOD_STREAM, {"widget": 1})
            raised = False
        except ValueError:
            raised = True
        check("bootstrap raises on an unknown entity in next_ids", raised)
        check("nothing written when next_ids is bad", not (board / log.LOG_NAME).exists())


def test_next_ids_validated_and_seeded():
    """d-p4: a seeded counter at or below the stream's max id would reissue an
    id. Every value must be a real integer past the folded max, and every
    entity gets a counter so no first add pays a full replay under the lock."""
    bad_counters = {
        "a non-integer value": {"task": "869"},
        "a boolean value": {"task": 869, "session": True},
        "a value equal to the folded max": {"task": 868},
        "a value below the folded max": {"task": 3},
    }
    for name, counters in bad_counters.items():
        with tempfile.TemporaryDirectory() as tmp:
            board = Path(tmp)
            try:
                log.bootstrap(board, [GOOD_STREAM[0]], counters)
                raised = False
            except ValueError:
                raised = True
            check(f"bootstrap raises on {name} in next_ids", raised)
            check(f"nothing written for {name}",
                  not (board / log.LOG_NAME).exists()
                  and not (board / log.COUNTER_NAME).exists())

    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        stream = [GOOD_STREAM[0], _event("capture.add", 7, fields={"body": "kept"})]
        log.bootstrap(board, stream, {"task": 869})
        counters = json.loads((board / log.COUNTER_NAME).read_text(encoding="utf-8"))
        check("every entity is seeded in the counter file",
              set(counters) == set(schema.ENTITIES), f"{sorted(counters)}")
        cid = store.add(board, "capture", {"body": "next"})
        check("an unseeded entity with events continues past its folded max",
              cid == 8, f"got {cid}")
        pid = store.add(board, "pbi", {"title": "first pbi"})
        check("an entity with no events starts at 1", pid == 1, f"got {pid}")


def test_duplicate_create_id_refused():
    """Two creates with one id would silently overwrite the first (d-p4: ids
    are never reissued, so a duplicate is always exporter corruption)."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        stream = [_event("task.add", 1, fields={"title": "first"}),
                  _event("task.add", 1, fields={"title": "usurper"})]
        try:
            log.bootstrap(board, stream, {"task": 2})
            msg = None
        except ValueError as e:
            msg = str(e)
        check("bootstrap raises on a duplicate create id", msg is not None)
        check("the refusal names the event position",
              msg is not None and "event 2" in msg, f"msg={msg!r}")
        check("nothing written on a duplicate create id",
              not (board / log.LOG_NAME).exists()
              and not (board / log.COUNTER_NAME).exists())


def test_refuses_existing_log():
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        store.add(board, "task", {"title": "already here"})
        try:
            log.bootstrap(board, list(GOOD_STREAM), dict(GOOD_COUNTERS))
            raised = False
        except ValueError:
            raised = True
        check("bootstrap refuses a board with an existing events.jsonl", raised)
        check("the existing board is untouched",
              store.state(board)["task"][1]["title"] == "already here")


def main():
    test_happy_path()
    test_all_or_nothing()
    test_next_ids_validated_and_seeded()
    test_duplicate_create_id_refused()
    test_refuses_existing_log()
    print(f"\n{len(FAILURES)} failure(s)" + (": " + ", ".join(FAILURES) if FAILURES else ""))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
