"""decision/requirement/capture show — readable for mow go hydrate."""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest
from sqlalchemy import select, text

from taskman.cli import main
from taskman.db import Session, upgrade_head
from taskman.config import find_project
from taskman.models import Decision, Project

MARKER = "decision-show-test"


@pytest.fixture(scope="module", autouse=True)
def _schema_ready():
    upgrade_head()


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    with Session() as session:
        slug, _ = find_project()
        proj = session.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            return
        session.execute(
            text(
                "DELETE FROM taskman_decision WHERE project_id = :pid AND title LIKE :m"
            ),
            {"pid": proj.id, "m": f"%{MARKER}%"},
        )
        session.commit()


def _run(argv: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(argv)
    return buf.getvalue()


def test_decision_show_prints_why_and_implications():
    out = _run(
        [
            "decision",
            "add",
            f"Hydrate {MARKER}",
            "--why",
            "so go can resolve pointers",
            "--implications",
            "lanes get one-liners",
            "--source",
            "tests",
        ]
    )
    dec_id = int(out.split("#")[1].split()[0])

    shown = _run(["decision", "show", str(dec_id)])
    assert f"#{dec_id}" in shown
    assert f"Hydrate {MARKER}" in shown
    assert "so go can resolve pointers" in shown
    assert "lanes get one-liners" in shown

    listed = _run(["decision", "list", "--id", str(dec_id)])
    assert f"#{dec_id}" in listed
    assert f"Hydrate {MARKER}" in listed


def test_decision_show_missing_exits():
    with pytest.raises(SystemExit):
        _run(["decision", "show", "999999999"])
