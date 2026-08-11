"""Isolated-DB guard for the canonical taskman package suite (workflow-parity d#867).

The vendored suites once ran against the live shared board DB and leaked 134 junk
Feature rows through an incomplete cleanup fixture. Structural fix: tests default to
a throwaway database; touching the live board requires an explicit opt-in.

Order matters: TASKMAN_DATABASE_URL must be set before any test imports taskman.db,
because taskman.db builds its engine at import time. A pytest fixture would be too
late — this runs at conftest import, which pytest guarantees precedes test modules.
"""

from __future__ import annotations

import os
import sys

_LIVE_OPT_IN = "TASKMAN_TESTS_ALLOW_LIVE"
# Point TASKMAN_TEST_DATABASE_URL at any reachable Postgres whose role may CREATE
# DATABASE; the throwaway test database is created from it on first run.
_TEST_DB_URL = os.environ.get(
    "TASKMAN_TEST_DATABASE_URL",
    "postgresql+psycopg://taskman:taskman@localhost:5432/taskman_test",
)


def _ensure_test_database(url: str) -> None:
    import psycopg

    base, dbname = url.rsplit("/", 1)
    admin = base.replace("+psycopg", "", 1) + "/postgres"
    with psycopg.connect(admin, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{dbname}"')


if os.environ.get(_LIVE_OPT_IN) != "1":
    os.environ["TASKMAN_DATABASE_URL"] = _TEST_DB_URL
    _ensure_test_database(_TEST_DB_URL)

if "taskman.db" in sys.modules:  # engine already bound before the guard could act
    raise RuntimeError(
        "taskman.db imported before conftest set TASKMAN_DATABASE_URL — "
        "the suite would run against the live board DB. Fix the import order."
    )


def pytest_configure(config):
    from taskman.config import database_url
    from taskman.db import upgrade_head

    url = database_url()
    if os.environ.get(_LIVE_OPT_IN) != "1":
        # Must be the designated throwaway database — not merely *a* database.
        if url != _TEST_DB_URL:
            raise RuntimeError(
                f"refusing to run tests against {url!r} without {_LIVE_OPT_IN}=1 "
                f"(expected the throwaway DB {_TEST_DB_URL!r})"
            )
        upgrade_head()
    else:
        # Live opt-in: d#859 says schema moves only via explicit `taskman db upgrade`.
        # Fail fast if the live DB is behind head (don't auto-migrate).
        from taskman.db import current_revision, head_revision
        cur = current_revision()
        head = head_revision()
        if cur != head:
            raise RuntimeError(
                f"live DB {url!r} is at {cur}, package expects {head} "
                "— run `taskman db upgrade` first (tests do not migrate; d#859)"
            )
