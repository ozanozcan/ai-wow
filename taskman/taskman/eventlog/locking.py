"""O_EXCL lockfile — the one concurrency primitive of the eventlog store.

Never fcntl: flock is POSIX-only and does not exist on Windows CPython (Git
Bash included). `os.open(..., O_CREAT | O_EXCL)` is atomic on both families,
so existence of the lock file *is* the lock.

Crashed holders leave the file behind, so a lock is judged stale purely by
age (mtime): liveness probing via `os.kill(pid, 0)` is off the table because
on Windows that call *terminates* the process. Hold times here are one JSON
line's worth of I/O, so `STALE_AFTER` has orders-of-magnitude headroom, and
it is kept below the acquire timeout so a crashed holder is recovered from
within a single default `exclusive()` call rather than wedging the board.

The holder keeps the fd open for the whole hold. POSIX ignores that, but on
Windows it makes a live holder's lock unbreakable (rename fails while a
handle is open), which turns the stale-break race into a POSIX-only concern.
"""

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_POLL = 0.005          # seconds between acquire attempts
STALE_AFTER = 5.0      # a lock older than this belongs to a crashed holder
TIMEOUT = 10.0         # default acquire deadline; must exceed STALE_AFTER


class LockTimeout(Exception):
    pass


@contextmanager
def exclusive(lock_path: Path, *, timeout: float = TIMEOUT,
              stale_after: float = STALE_AFTER) -> Iterator[None]:
    """Hold `lock_path` exclusively. Raises LockTimeout. Releases on exception."""
    deadline = time.monotonic() + timeout
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    while True:
        try:
            fd = os.open(lock_path, flags)
            break
        except FileExistsError:
            _break_if_stale(lock_path, stale_after)
            if time.monotonic() >= deadline:
                raise LockTimeout(f"could not acquire {lock_path} within {timeout}s")
            time.sleep(_POLL)
    try:
        os.write(fd, f"pid={os.getpid()} t={time.time()}\n".encode())  # forensics only
        yield
    finally:
        os.close(fd)
        try:
            os.unlink(lock_path)
        except OSError:
            pass  # a breaker judged us stale and already removed it


def _break_if_stale(lock_path: Path, stale_after: float) -> None:
    """Remove a lock left behind by a crashed holder.

    Rename-to-unique first: exactly one contender's rename can succeed, so two
    waiters can never each unlink a lock and let two acquirers through.
    """
    try:
        age = time.time() - os.stat(lock_path).st_mtime
    except OSError:
        return  # gone already — the normal case
    if age < stale_after:
        return
    doomed = lock_path.with_name(f"{lock_path.name}.stale.{os.getpid()}.{time.monotonic_ns()}")
    try:
        # Re-check right before the rename: a *fresh* lock has a fresh mtime,
        # so this can only doom a file that has sat untouched past the window.
        # debt: stat->rename is a microsecond non-atomic window; close it with
        # shape B (SQLite) if a doomed-fresh-lock incident is ever observed.
        if time.time() - os.stat(lock_path).st_mtime < stale_after:
            return
        os.rename(lock_path, doomed)
    except OSError:
        return  # lost the break race, or (Windows) the holder is alive with an open handle
    try:
        os.unlink(doomed)
    except OSError:
        pass
