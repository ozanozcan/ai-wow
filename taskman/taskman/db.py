from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from taskman.config import database_url

engine = create_engine(database_url(), future=True)
Session = sessionmaker(bind=engine, expire_on_commit=False)

_TASKMAN_DIR = Path(__file__).resolve().parent
_ALEMBIC_INI = _TASKMAN_DIR / "alembic.ini"
_ALEMBIC_SCRIPT = _TASKMAN_DIR / "alembic"


def alembic_config() -> Config:
    """Alembic Config pointed at taskman/alembic.ini (URL set in env.py)."""
    cfg = Config(str(_ALEMBIC_INI))
    # Absolute script_location so init-db works regardless of cwd.
    cfg.set_main_option("script_location", str(_ALEMBIC_SCRIPT))
    # In-process run: leave the caller's logging config alone (see taskman/alembic/env.py).
    cfg.attributes["configure_logger"] = False
    return cfg


def upgrade_head() -> None:
    """Apply taskman_* migrations to head."""
    command.upgrade(alembic_config(), "head")


def head_revision() -> str:
    """Head revision id of the package's migration tree."""
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def current_revision() -> str | None:
    """Revision currently stamped in the database (None when unstamped)."""
    from alembic.runtime.migration import MigrationContext

    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def warn_if_behind() -> None:
    """stderr warning when the DB is behind the package head. Never raises, never blocks.

    d#859: schema moves only via an explicit `taskman db upgrade`; everything else
    just gets loud. An unreachable DB stays silent — the actual command will surface
    its own connection error with better context than this hint could.
    """
    try:
        cur = current_revision()
        head = head_revision()
    except Exception:
        return
    if cur != head:
        print(
            f"taskman: database revision {cur or '(empty)'} is behind package head "
            f"{head} — run `taskman db upgrade`",
            file=sys.stderr,
        )
