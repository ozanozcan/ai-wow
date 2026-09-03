"""Tests for the per-wave verification gate (taskman.mow.check_verification).

Every failing case breaks one thing the gate exists to catch (L33). The
round-trip is a record the close-out fixture would accept, so a format drift
in either half shows up here rather than as a run that ships unverified.
"""

from __future__ import annotations

from pathlib import Path

from taskman.mow import check_verification as _mod
from taskman.mow import closeout

from tests.test_mow_closeout import _stem


def _lane_stem(tmp_path: Path, *, decisions: str = "-", qa: str = "- `true`") -> Path:
    stem = _stem(tmp_path)
    index = stem / "dispatch" / "INDEX.md"
    index.write_text(
        index.read_text(encoding="utf-8")
        + """
## Waves
- **Wave 1 (parallel, AFK):** A | B
- **Wave 2 (after wave 1):** Z

## Lanes
| Lane | Todos (in order) | Brief | Decisions / Specs |
|---|---|---|---|
| A | 01 | 01-a.md | """
        + decisions
        + """ |
| B | 02 | 02-b.md | - |
| Z | 04 | 04-z.md | - |
""",
        encoding="utf-8",
    )
    for name, goal in (("01-a.md", "Do A"), ("02-b.md", "Do B"), ("04-z.md", "Do Z")):
        (stem / "dispatch" / name).write_text(
            f"# {name}: {goal}\n\n**Role:** code-edit   **Wave:** 1\n\n"
            f"## Goal\n{goal} for the fixture.\n\n"
            f"## QA contract\n{qa}\n",
            encoding="utf-8",
        )
    return stem


def _record(
    *,
    commands: str = "`true` — pass",
    contract: str = "all met",
    artifacts: str = "none",
    honored: str = "none pointed",
) -> str:
    return (
        "## Verification\n"
        f"- Commands run: {commands}\n"
        f"- Contract items: {contract}\n"
        f"- Artifacts: {artifacts}\n"
        f"- Decisions honored: {honored}\n"
    )


def _write_all(stem: Path, body: str | None = None) -> None:
    (stem / "dispatch" / "verification").mkdir(exist_ok=True)
    text = body if body is not None else _record()
    for name in ("01-a.md", "02-b.md", "04-z.md"):
        (stem / "dispatch" / "verification" / name).write_text(text, encoding="utf-8")


def test_no_lanes_is_a_noop(tmp_path):
    stem = _stem(tmp_path)
    assert _mod.check_stem(stem) == []


def test_missing_record_fails(tmp_path):
    stem = _lane_stem(tmp_path)
    errs = _mod.check_stem(stem)
    assert any("missing" in e and "01-a.md" in e for e in errs)
    assert any("chat is not a record" in e for e in errs)


def test_missing_label_fails(tmp_path):
    stem = _lane_stem(tmp_path)
    _write_all(
        stem,
        "## Verification\n- Commands run: ok\n- Contract items: all met\n- Artifacts: none\n",
    )
    assert any("Decisions honored" in e for e in _mod.check_stem(stem))


def test_tbd_commands_fail(tmp_path):
    stem = _lane_stem(tmp_path)
    _write_all(stem, _record(commands="tbd"))
    assert any("Commands run" in e and "empty" in e for e in _mod.check_stem(stem))


def test_pointer_not_honored_fails(tmp_path):
    stem = _lane_stem(tmp_path, decisions="d `#12` · req `#3`")
    _write_all(stem, _record(honored="none pointed"))
    errs = _mod.check_stem(stem)
    assert any("d#12" in e for e in errs)
    assert any("req#3" in e for e in errs)


def test_pointers_honored_pass(tmp_path):
    stem = _lane_stem(tmp_path, decisions="d `#12`")
    (stem / "dispatch" / "verification").mkdir()
    (stem / "dispatch" / "verification" / "01-a.md").write_text(
        _record(honored="d#12: added the check, closeout.py:68"), encoding="utf-8"
    )
    (stem / "dispatch" / "verification" / "02-b.md").write_text(_record(), encoding="utf-8")
    (stem / "dispatch" / "verification" / "04-z.md").write_text(_record(), encoding="utf-8")
    assert _mod.check_stem(stem) == []


def test_dash_cell_requires_none_pointed(tmp_path):
    stem = _lane_stem(tmp_path)
    _write_all(stem, _record(honored="looks fine"))
    assert any("none pointed" in e for e in _mod.check_stem(stem))


def test_qa_unaccounted_fails(tmp_path):
    stem = _lane_stem(tmp_path, qa="- pytest the new module\n- grep for the old name")
    _write_all(stem, _record(contract="n/a"))
    assert any("QA contract" in e for e in _mod.check_stem(stem))


def test_all_met_covers_qa(tmp_path):
    stem = _lane_stem(tmp_path, qa="- pytest the new module")
    _write_all(stem)
    assert _mod.check_stem(stem) == []


def test_wave_filter_ignores_other_waves(tmp_path):
    stem = _lane_stem(tmp_path)
    (stem / "dispatch" / "verification").mkdir()
    (stem / "dispatch" / "verification" / "01-a.md").write_text(_record(), encoding="utf-8")
    (stem / "dispatch" / "verification" / "02-b.md").write_text(_record(), encoding="utf-8")
    # Z (wave 2) has no record — wave 1 must still pass
    assert _mod.check_stem(stem, wave="1") == []
    assert any("04-z.md" in e for e in _mod.check_stem(stem, wave="2"))


def test_wave_parse_reads_letters_after_colon():
    text = "- **Wave 1 (parallel, AFK):** A | B\n- **Wave 2 (after wave 1):** Z\n"
    assert _mod.parse_wave_lane_letters("## Waves\n" + text) == {
        "1": ["A", "B"],
        "2": ["Z"],
    }


def test_closeout_refuses_without_verification(tmp_path):
    stem = _lane_stem(tmp_path)
    errors, _ = closeout.run_closeout(stem)
    assert any("verification" in e.lower() or "chat is not a record" in e for e in errors)


def test_closeout_passes_when_records_exist(tmp_path):
    stem = _lane_stem(tmp_path)
    _write_all(stem)
    # Suite autouse plants a .taskman.toml; this fixture has no board rows, so
    # drop the marker — a docs-only stem is the close-out shape without import.
    (tmp_path / ".taskman.toml").unlink()
    errors, _ = closeout.run_closeout(stem)
    assert errors == []
