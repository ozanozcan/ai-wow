"""Task operations over the event log.

`board_dir` is always a parameter, never resolved from config. The board is
meant to be committed to git, so callers must store *relative* paths in task
fields — this store keeps no paths of its own.
"""

from datetime import datetime, timezone
from pathlib import Path

from . import log
from .locking import exclusive


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_task(board_dir: Path, title: str, **fields) -> int:
    tid = log.next_id(board_dir)
    log.append(board_dir, {
        "type": "task.add", "id": tid, "title": title, "fields": fields, "ts": _now(),
    })
    return tid


def get_task(board_dir: Path, task_id: int) -> dict | None:
    return log.replay(board_dir).get(task_id)


def claim(board_dir: Path, task_id: int, agent: str) -> bool:
    """True if this caller won. False if already claimed (or no such task) —
    mirrors cli.py cmd_task_claim's UPDATE ... WHERE claimed_by IS NULL.

    The test-and-set must be one critical section: replay, check, and append
    all happen under the board lock, or two callers both see NULL and both win.
    """
    with exclusive(log._lock_path(board_dir)):
        task = log.replay(board_dir).get(task_id)
        if task is None or task["claimed_by"] is not None:
            return False
        log._append_locked(board_dir, {
            "type": "task.claim", "id": task_id, "agent": agent, "ts": _now(),
        })
        return True


def release(board_dir: Path, task_id: int) -> None:
    log.append(board_dir, {"type": "task.release", "id": task_id, "ts": _now()})
