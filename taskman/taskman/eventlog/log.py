"""Append-only event log: one JSON object per line in board/events.jsonl.

One lock file, board.lock, serializes every mutation — the log append *and*
the id counters — so there is no lock ordering to get wrong. O_APPEND is not
atomic on Windows, which is exactly why appends go through the lock too.

Ids come from a counter file, never from the log's length: a counter only
grows, so an id can never be reissued even if an add event was lost to a
crash — the same gap semantics as the Postgres sequence this replaces.
Counters are per entity (plan d-p4): one JSON file `next_ids`, keyed by
entity name, written whole via tmp + os.replace.
"""

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterable, Iterator

from . import schema
from .locking import exclusive

LOG_NAME = "events.jsonl"
LOCK_NAME = "board.lock"
COUNTER_NAME = "next_ids"


def _lock_path(board_dir: Path) -> Path:
    return board_dir / LOCK_NAME


@contextmanager
def transaction(board_dir: Path) -> Iterator[Callable[[dict], None]]:
    """Hold the board lock; yield an `append(event)` callable.

    The public seam for every read-check-append critical section — nothing
    outside this module touches the lock or the locked append directly.
    Acquisition also sweeps stale-lock debris (one listdir), so a leftover
    `board.lock.stale.*` never outlives the next write.
    """
    with exclusive(_lock_path(board_dir)):
        sweep_stale_debris(board_dir)
        yield lambda event: _append_locked(board_dir, event)


def append(board_dir: Path, event: dict) -> None:
    with transaction(board_dir) as append_locked:
        append_locked(event)


def _append_locked(board_dir: Path, event: dict) -> None:
    """Write one event. Caller holds the board lock."""
    line = json.dumps(event, separators=(",", ":"), sort_keys=True) + "\n"
    with open(board_dir / LOG_NAME, "a", encoding="utf-8") as fh:
        fh.write(line)  # closed (hence flushed) before the lock is released


def replay(board_dir: Path) -> dict[str, dict[int, dict]]:
    """Rebuild entity -> id -> current fields by folding the log from the top.

    Lockless by design: writers emit whole lines, so the only torn state a
    reader can observe is a final line without its newline — from a writer
    killed mid-write — and that tail is provably incomplete, so it is
    dropped. A malformed line *with* a newline is real corruption, and an
    envelope this reader does not recognise (plan d-p1: unknown entity or
    verb, missing `v`, `v` above SUPPORTED_VERSION) is a newer board than
    this code: both raise, naming the line, before any state is returned.
    """
    state: dict[str, dict[int, dict]] = {entity: {} for entity in schema.ENTITIES}
    try:
        raw = (board_dir / LOG_NAME).read_bytes()
    except FileNotFoundError:
        return state
    for lineno, line in enumerate(raw.split(b"\n")[:-1], start=1):
        try:
            event = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"corrupt event log: {LOG_NAME} line {lineno}: {exc}") from exc
        try:
            schema.validate_event(event)
            _apply(state, event)
        except (ValueError, KeyError, TypeError) as exc:
            # KeyError/TypeError belt-and-braces: any payload gap validate_event
            # misses must still surface as the named-line refusal, never bare.
            raise ValueError(f"corrupt event log: {LOG_NAME} line {lineno}: {exc}") from exc
    return state


def next_id(board_dir: Path, entity: str) -> int:
    with exclusive(_lock_path(board_dir)):
        return _next_id_locked(board_dir, entity)


def _next_id_locked(board_dir: Path, entity: str) -> int:
    """Allocate the next id for `entity`. Caller holds the board lock.

    The file stores the *next* id per entity (so the migration exporter seeds
    `max(id) + 1` — plan d-p4), never the last one issued.
    """
    counter = board_dir / COUNTER_NAME
    try:
        counts = json.loads(counter.read_text(encoding="utf-8"))
    except FileNotFoundError:
        counts = {}
    allocated = counts.get(entity)
    if allocated is None:
        # Lost counter (or first use of this entity), surviving log:
        # re-derive from replay so an id is never reissued.
        allocated = max(replay(board_dir)[entity], default=0) + 1
    counts[entity] = allocated + 1
    tmp = counter.with_name(counter.name + ".tmp")
    tmp.write_text(json.dumps(counts, sort_keys=True), encoding="utf-8")
    os.replace(tmp, counter)  # atomic on POSIX and Windows
    return allocated


def sweep_stale_debris(board_dir: Path) -> int:
    """Remove `board.lock.stale.*` files a failed unlink left behind.

    `_break_if_stale`'s rename-then-unlink can lose its unlink (Windows
    delete-pending, or a crash between the two) — noise on a committed
    board. Returns how many debris files were removed.
    """
    removed = 0
    prefix = LOCK_NAME + ".stale."
    try:
        names = os.listdir(board_dir)
    except OSError:
        return 0
    for name in names:
        if name.startswith(prefix):
            try:
                os.unlink(board_dir / name)
                removed += 1
            except OSError:
                pass  # delete-pending or already gone — the next sweep gets it
    return removed


def bootstrap(board_dir: Path, events: Iterable[dict], next_ids: dict[str, int]) -> None:
    """Migration-only: write a complete events.jsonl + next_ids into an EMPTY
    board dir. All-or-nothing: every event is validated (and folded, so
    relation shapes are checked too) before anything is written; an existing
    events.jsonl is a refusal, never an overwrite.
    """
    log_path = board_dir / LOG_NAME
    if log_path.exists():
        raise ValueError(f"refusing bootstrap: {log_path} already exists")
    for entity in next_ids:
        if entity not in schema.ENTITIES:
            raise ValueError(f"unknown entity {entity!r} in next_ids")
    state: dict[str, dict[int, dict]] = {entity: {} for entity in schema.ENTITIES}
    lines = []
    for n, event in enumerate(events, start=1):
        try:
            schema.validate_event(event)
            _apply(state, event)
        except (ValueError, KeyError, TypeError) as exc:
            # same belt-and-braces as replay: no payload gap escapes unnamed
            raise ValueError(f"invalid bootstrap event {n}: {exc}") from exc
        lines.append(json.dumps(event, separators=(",", ":"), sort_keys=True))
    # Counters must land past the stream's max ids (d-p4: never reissue), as
    # real integers (bool is an int — refused), and for EVERY entity, so no
    # first add of an entity pays a full replay under the lock.
    seeded = {}
    for entity in schema.ENTITIES:
        floor = max(state[entity], default=0)
        value = next_ids.get(entity)
        if value is None:
            seeded[entity] = floor + 1
        elif not isinstance(value, int) or isinstance(value, bool) or value <= floor:
            raise ValueError(
                f"next_ids[{entity!r}] must be an integer above the stream's"
                f" max id {floor}: {value!r}")
        else:
            seeded[entity] = value
    with transaction(board_dir) as append_locked:
        if log_path.exists():
            raise ValueError(f"refusing bootstrap: {log_path} already exists")
        tmp = log_path.with_name(log_path.name + ".tmp")
        tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        os.replace(tmp, log_path)  # the log appears whole or not at all
        counter = board_dir / COUNTER_NAME
        ctmp = counter.with_name(counter.name + ".tmp")
        ctmp.write_text(json.dumps(seeded, sort_keys=True), encoding="utf-8")
        os.replace(ctmp, counter)


def _apply(state: dict[str, dict[int, dict]], event: dict) -> None:
    """Fold one (already validated) event into state."""
    entity, verb = event["type"].split(".", 1)
    eid = event["id"]
    table = state[entity]
    if verb == schema.CREATE_VERBS[entity]:
        if eid in table:
            # The counter invariant (d-p4) makes this unreachable on a healthy
            # log — a duplicate create is corruption, never a legal overwrite.
            raise ValueError(f"duplicate create for {entity} id {eid}")
        obj = {"id": eid}
        if entity == "task":
            obj["claimed_by"] = None
            obj["blocked_by"] = []
        obj.update(event.get("fields", {}))
        table[eid] = obj
    elif verb == "set":
        obj = table.get(eid)
        if obj is not None:
            obj.update(event.get("fields", {}))
    elif verb in ("link", "unlink"):
        relation, target = event["relation"], event["target"]
        shape = schema.RELATIONS.get(entity, {}).get(relation)
        if shape is None:
            raise ValueError(f"unknown relation {relation!r} for entity {entity!r}")
        obj = table.get(eid)
        if obj is None:
            return
        if shape == "many":
            targets = obj.setdefault(relation, [])
            if verb == "link" and target not in targets:
                targets.append(target)
            elif verb == "unlink" and target in targets:
                targets.remove(target)
        else:  # "one"
            if verb == "link":
                obj[relation] = target
            elif obj.get(relation) == target:
                obj[relation] = None
    elif verb == "claim":
        obj = table.get(eid)
        if obj is not None and obj["claimed_by"] is None:
            obj["claimed_by"] = event["agent"]  # first claim wins — the CAS
    elif verb == "release":
        obj = table.get(eid)
        if obj is not None:
            obj["claimed_by"] = None
    else:  # unreachable once validate_event has passed — belt and braces
        raise ValueError(f"unknown event type {event['type']!r}")
