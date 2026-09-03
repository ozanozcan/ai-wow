"""decision/requirement/capture show — readable for mow go hydrate."""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

from taskman.cli import main

MARKER = "decision-show-test"


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
