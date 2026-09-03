"""Board operations over the event log — every entity, one generic surface.

`board_dir` is always a parameter, never resolved from config. The board is
meant to be committed to git, so callers must store *relative* paths in
fields — this store keeps no paths of its own.
"""

from datetime import datetime, timezone
from pathlib import Path

from . import log, schema


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _check_entity(entity: str) -> None:
    if entity not in schema.ENTITIES:
        raise ValueError(f"unknown entity {entity!r}")


def _event(entity: str, verb: str, eid: int, **payload) -> dict:
    event = {"v": schema.SUPPORTED_VERSION, "type": f"{entity}.{verb}", "id": eid,
             "ts": _now(), **payload}
    # The store never writes an event replay would refuse (d-p1): validate
    # here, before append, so a bad payload raises instead of bricking replay.
    schema.validate_event(event)
    return event


def add(board_dir: Path, entity: str, fields: dict) -> int:
    _check_entity(entity)
    eid = log.next_id(board_dir, entity)
    log.append(board_dir, _event(entity, schema.CREATE_VERBS[entity], eid,
                                 fields=dict(fields)))
    return eid


def update(board_dir: Path, entity: str, entity_id: int, fields: dict) -> bool:
    """False: no such id. Check and append are one critical section."""
    _check_entity(entity)
    with log.transaction(board_dir) as append:
        if entity_id not in log.replay(board_dir)[entity]:
            return False
        append(_event(entity, "set", entity_id, fields=dict(fields)))
        return True


def _relink(board_dir: Path, entity: str, entity_id: int, relation: str,
            target: int, verb: str) -> bool:
    _check_entity(entity)
    if relation not in schema.RELATIONS.get(entity, {}):
        raise ValueError(f"unknown relation {relation!r} for entity {entity!r}")
    with log.transaction(board_dir) as append:
        if entity_id not in log.replay(board_dir)[entity]:
            return False
        append(_event(entity, verb, entity_id, relation=relation, target=target))
        return True


def link(board_dir: Path, entity: str, entity_id: int, relation: str, target: int) -> bool:
    return _relink(board_dir, entity, entity_id, relation, target, "link")


def unlink(board_dir: Path, entity: str, entity_id: int, relation: str, target: int) -> bool:
    return _relink(board_dir, entity, entity_id, relation, target, "unlink")


def state(board_dir: Path) -> dict[str, dict[int, dict]]:
    """entity -> id -> current fields. One replay; callers read, never mutate."""
    return log.replay(board_dir)


def claim(board_dir: Path, task_id: int, agent: str) -> bool:
    """True if this caller won. False if already claimed (or no such task) —
    mirrors cli.py cmd_task_claim's UPDATE ... WHERE claimed_by IS NULL.

    The test-and-set must be one critical section: replay, check, and append
    all happen under the board lock, or two callers both see NULL and both win.
    """
    # debt: full replay under the board lock per claim, revisit above ~50k events or ~5MB log
    with log.transaction(board_dir) as append:
        task = log.replay(board_dir)["task"].get(task_id)
        if task is None or task["claimed_by"] is not None:
            return False
        append(_event("task", "claim", task_id, agent=agent))
        return True


def release(board_dir: Path, task_id: int) -> None:
    log.append(board_dir, _event("task", "release", task_id))
