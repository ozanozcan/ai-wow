"""Append-only event log: one JSON object per line in board/events.jsonl.

One lock file, board.lock, serializes every mutation — the log append *and*
the id counter — so there is no lock ordering to get wrong. O_APPEND is not
atomic on Windows, which is exactly why appends go through the lock too.

Ids come from a counter file, never from the log's length: a counter only
grows, so an id can never be reissued even if an add event was lost to a
crash — the same gap semantics as the Postgres sequence this replaces.
"""

import json
import os
from pathlib import Path

from .locking import exclusive

LOG_NAME = "events.jsonl"
LOCK_NAME = "board.lock"
COUNTER_NAME = "next_id"


def _lock_path(board_dir: Path) -> Path:
    return board_dir / LOCK_NAME


def append(board_dir: Path, event: dict) -> None:
    with exclusive(_lock_path(board_dir)):
        _append_locked(board_dir, event)


def _append_locked(board_dir: Path, event: dict) -> None:
    """Write one event. Caller holds the board lock."""
    line = json.dumps(event, separators=(",", ":"), sort_keys=True) + "\n"
    with open(board_dir / LOG_NAME, "a", encoding="utf-8") as fh:
        fh.write(line)  # closed (hence flushed) before the lock is released


def replay(board_dir: Path) -> dict[int, dict]:
    """Rebuild id -> current task state by folding the log from the top.

    Lockless by design: writers emit whole lines, so the only torn state a
    reader can observe is a final line without its newline — from a writer
    killed mid-write — and that tail is provably incomplete, so it is
    dropped. A malformed line *with* a newline is real corruption: raise.
    """
    state: dict[int, dict] = {}
    try:
        raw = (board_dir / LOG_NAME).read_bytes()
    except FileNotFoundError:
        return state
    for lineno, line in enumerate(raw.split(b"\n")[:-1], start=1):
        try:
            event = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"corrupt event log: {LOG_NAME} line {lineno}: {exc}") from exc
        _apply(state, event)
    return state


def next_id(board_dir: Path) -> int:
    with exclusive(_lock_path(board_dir)):
        return _next_id_locked(board_dir)


def _next_id_locked(board_dir: Path) -> int:
    """Allocate the next id. Caller holds the board lock."""
    counter = board_dir / COUNTER_NAME
    try:
        current = int(counter.read_text(encoding="utf-8"))
    except FileNotFoundError:
        # Lost counter, surviving log: re-derive so an id is never reissued.
        state = replay(board_dir)
        current = max(state, default=0)
    allocated = current + 1
    tmp = counter.with_name(counter.name + ".tmp")
    tmp.write_text(str(allocated), encoding="utf-8")
    os.replace(tmp, counter)  # atomic on POSIX and Windows
    return allocated


def _apply(state: dict[int, dict], event: dict) -> None:
    kind, tid = event["type"], event["id"]
    if kind == "task.add":
        task = {"id": tid, "title": event["title"], "claimed_by": None}
        task.update(event.get("fields", {}))
        state[tid] = task
    elif kind == "task.claim":
        task = state.get(tid)
        if task is not None and task["claimed_by"] is None:
            task["claimed_by"] = event["agent"]  # first claim wins — the CAS
    elif kind == "task.release":
        task = state.get(tid)
        if task is not None:
            task["claimed_by"] = None
    else:
        raise ValueError(f"unknown event type {kind!r}")
