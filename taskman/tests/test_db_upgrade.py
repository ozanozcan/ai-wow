"""`taskman db upgrade` + behind-head warning (workflow-parity d#859).

Explicit, deliberate migrations: `db upgrade` is the only thing that moves the
schema; every other invocation warns on stderr when the DB is behind the package
head — and never blocks, not even when the DB is unreachable.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

from alembic import command

from taskman import db
from taskman.cli import main


def _run(argv: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(argv)
    return buf.getvalue()


def test_db_upgrade_at_head_is_noop():
    db.upgrade_head()
    out = _run(["db", "upgrade"])
    assert "already at head" in out
    assert db.current_revision() == db.head_revision()


def test_db_upgrade_applies_when_behind():
    db.upgrade_head()
    command.downgrade(db.alembic_config(), "-1")
    assert db.current_revision() != db.head_revision()
    out = _run(["db", "upgrade"])
    assert db.current_revision() == db.head_revision()
    assert "upgraded" in out


def test_warn_when_behind_writes_stderr_and_does_not_block(capsys):
    db.upgrade_head()
    command.downgrade(db.alembic_config(), "-1")
    try:
        db.warn_if_behind()
        err = capsys.readouterr().err
        assert "behind" in err
        assert db.head_revision() in err
    finally:
        db.upgrade_head()


def test_warn_at_head_is_silent(capsys):
    db.upgrade_head()
    db.warn_if_behind()
    assert capsys.readouterr().err == ""


def test_warn_never_raises_on_unreachable_db(monkeypatch, capsys):
    import sqlalchemy

    bad = sqlalchemy.create_engine(
        "postgresql+psycopg://nobody:wrong@localhost:59999/nowhere", future=True
    )
    monkeypatch.setattr(db, "engine", bad)
    db.warn_if_behind()  # must not raise (d#859: warn, never block)
    assert capsys.readouterr().err == ""
