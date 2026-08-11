"""Tests for scripts/mow_preflight.py (parse/validation helpers + fixture gate)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
from taskman.mow import preflight as _mod

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "mow_preflight"


def test_paths_overlap_same_and_prefix():
    assert _mod.paths_overlap("foo/bar.py", "foo/bar.py")
    assert _mod.paths_overlap("foo/", "foo/bar.py")
    assert _mod.paths_overlap("foo/bar.py", "foo/")
    assert not _mod.paths_overlap("foo/a.py", "foo/b.py")
    assert not _mod.paths_overlap("scripts/x.py", "taskman/tests/y.py")


def test_parse_files_owned_backtick_list():
    cell = "`scripts/mow_preflight.py`, `taskman/tests/test_mow_preflight.py`"
    assert _mod.parse_files_owned(cell) == [
        "scripts/mow_preflight.py",
        "taskman/tests/test_mow_preflight.py",
    ]


def test_same_wave_overlap_detects_shared_prefix():
    index_text = """
## Waves
- **Wave 1 (parallel):** A (a) ‖ B (b)

## Lanes
| Lane | Files owned | Brief |
|---|---|---|
| A | `scripts/foo.py` | 01-a.md |
| B | `scripts/` | 02-b.md |
"""
    errs = _mod.check_same_wave_overlap(index_text)
    assert any("same-wave" in e.lower() or "overlap" in e.lower() for e in errs)


def test_brief_index_drift_detects_mismatch():
    index_text = """
## Lanes
| Lane | Files owned | Brief |
|---|---|---|
| A | `scripts/foo.py` | 01-a.md |
"""
    brief = """# a

## Files in scope
- scripts/bar.py

## Goal
Concrete goal here.

## Context & decisions (only what this todo needs)
- bullet one
- bullet two

## Do NOT
- do not edit bar

## Acceptance check
- SHALL do thing
- GIVEN x WHEN y THEN z
- Verify: `true`

## QA contract
- `true`
"""
    errs = _mod.check_brief_index_drift(index_text, {"01-a.md": brief})
    assert any("drift" in e.lower() or "01-a.md" in e for e in errs)


def test_thin_brief_rejects_missing_sections(tmp_path: Path):
    brief = """# thin

## Goal
Only goal.
"""
    errs = _mod.check_thin_brief("01-thin.md", brief)
    assert len(errs) >= 3


def test_registry_status_from_index():
    registry = """
| Stem | Title | Feature | Created | Updated | Status |
|---|---|---|---|---|---|
| foo | Foo | - | 2026-01-01 | 2026-01-01 | running |
| bar | Bar | - | 2026-01-01 | 2026-01-01 | shipped |
"""
    assert _mod.registry_status(registry, "foo") == "running"
    assert _mod.registry_status(registry, "bar") == "shipped"
    assert _mod.registry_status(registry, "missing") is None


def test_all_decisions_specs_dash():
    lanes = [("A", "-", "01-a.md"), ("B", "`-`", "02-b.md")]
    assert _mod.all_decisions_specs_dash(lanes) is True
    lanes_with_ptr = [("A", "d `#1`", "01-a.md")]
    assert _mod.all_decisions_specs_dash(lanes_with_ptr) is False


def _write_minimal_fixture(root: Path) -> Path:
    """Minimal dispatch that should pass all preflight checks."""
    stem = root / "test-stem"
    dispatch = stem / "dispatch"
    dispatch.mkdir(parents=True)
    (stem / "plan.md").write_text(
        "## Decisions locked\nGrill write-back evidence.\n",
        encoding="utf-8",
    )
    (dispatch / "INDEX.md").write_text(
        """# Dispatch — test-stem

## Waves
- **Wave 1 (parallel):** A (only-lane)

## Lanes
| Lane | Files owned | Brief |
|---|---|---|
| A | `scripts/only.py` | 01-only.md |

**Grill checkpoint:** done 2026-07-29
**Grill write-back:** no changes — plan held 2026-07-29
""",
        encoding="utf-8",
    )
    (dispatch / "01-only.md").write_text(
        """# only-lane: single lane fixture

## Goal
Ship one file with tests passing.

## Context & decisions (only what this todo needs)
- Fixture stem for preflight exit-0 tests.
- No cross-plan overlap in isolated tmp registry.

## Files in scope
- scripts/only.py

## Do NOT
- Do not touch production stems.

## Acceptance check
- The script SHALL exit 0 on this fixture.
- GIVEN valid dispatch WHEN preflight runs THEN exit 0.
- Verify: `pytest taskman/tests/test_mow_preflight.py -q`

## QA contract
- `pytest taskman/tests/test_mow_preflight.py -q`
""",
        encoding="utf-8",
    )
    plans = root / "docs" / "plans"
    plans.mkdir(parents=True)
    (plans / "INDEX.md").write_text(
        """# MOW runs

| Stem | Title | Feature | Created | Updated | Status |
|---|---|---|---|---|---|
| test-stem | Test stem | - | 2026-07-29 | 2026-07-29 | planned |
""",
        encoding="utf-8",
    )
    return stem


def test_run_preflight_exit_zero_on_minimal_fixture(tmp_path: Path):
    stem = _write_minimal_fixture(tmp_path)
    code, errors = _mod.run_preflight(
        stem,
        repo_root=tmp_path,
        skip_hydrate=True,
        decisions=[],  # isolate from live board
    )
    assert errors == []
    assert code == 0


def test_run_preflight_exit_one_missing_dispatch(tmp_path: Path):
    stem = tmp_path / "no-dispatch"
    stem.mkdir()
    code, errors = _mod.run_preflight(
        stem, repo_root=tmp_path, skip_hydrate=True, decisions=[]
    )
    assert code == 1
    assert errors


def test_run_preflight_exit_one_grill_pending(tmp_path: Path):
    stem = _write_minimal_fixture(tmp_path)
    index = stem / "dispatch" / "INDEX.md"
    index.write_text(
        index.read_text(encoding="utf-8").replace(
            "**Grill checkpoint:** done 2026-07-29",
            "**Grill checkpoint:** pending",
        ),
        encoding="utf-8",
    )
    code, errors = _mod.run_preflight(
        stem, repo_root=tmp_path, skip_hydrate=True, decisions=[]
    )
    assert code == 1
    assert any("grill" in e.lower() for e in errors)


def test_run_preflight_skips_grill_when_shipped(tmp_path: Path):
    stem = _write_minimal_fixture(tmp_path)
    index = stem / "dispatch" / "INDEX.md"
    index.write_text(
        index.read_text(encoding="utf-8").replace(
            "**Grill checkpoint:** done 2026-07-29",
            "**Grill checkpoint:** pending",
        ),
        encoding="utf-8",
    )
    registry = tmp_path / "docs" / "plans" / "INDEX.md"
    registry.write_text(
        registry.read_text(encoding="utf-8").replace("planned", "shipped"),
        encoding="utf-8",
    )
    code, errors = _mod.run_preflight(
        stem, repo_root=tmp_path, skip_hydrate=True, decisions=[]
    )
    assert code == 0
    assert errors == []


def test_cli_json_output(tmp_path: Path):
    stem = _write_minimal_fixture(tmp_path)
    env = {"PYTHONPATH": str(_ROOT)}
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m", "taskman.mow.preflight",
            str(stem),
            "--json",
            "--skip-hydrate",
            "--skip-candidates",
            "--repo-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=_ROOT,
        env={**dict(**{}), **__import__("os").environ, **env},
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["stem"] == str(stem.resolve())


# --- Living-spec scenarios: citation / candidate / waived / dead-glob (d#852, d#853) ---


def _brief_with_sections(
    *,
    files: str = "scripts/only.py",
    acceptance_extra: str = "",
    do_not_extra: str = "",
) -> str:
    return f"""# fixture-lane

## Goal
Ship one file with tests passing.

## Context & decisions (only what this todo needs)
- Fixture stem for citation/candidate gates.
- Isolated from production stems.

## Files in scope
- {files}

## Do NOT
- Do not touch production stems.
{do_not_extra}

## Acceptance check
- The script SHALL exit 0 on this fixture.
- GIVEN valid dispatch WHEN preflight runs THEN exit 0.
- Verify: `pytest -q`
{acceptance_extra}

## QA contract
- `pytest -q`
"""


def test_uncited_pointer_blocks_go():
    """Living-spec: uncited-pointer-blocks-go (req#430 / d#853)."""
    cell = "d `#812`"
    brief = _brief_with_sections()  # no d#812 citation
    errs = _mod.check_pointer_citations("A", "01-a.md", cell, brief)
    assert errs
    assert any("uncited" in e.lower() and "812" in e and "lane A" in e for e in errs)


def test_mow_enforcement_fixture_folder_uncited_blocks():
    """Acceptance evidence: fixtures/mow_enforcement must not self-cite."""
    fixture = Path(__file__).resolve().parent / "fixtures" / "mow_enforcement" / "dispatch"
    brief = (fixture / "01-uncited.md").read_text(encoding="utf-8")
    cell = "d `#1`"
    errs = _mod.check_pointer_citations("A", "01-uncited.md", cell, brief)
    assert any("uncited" in e.lower() and "1" in e for e in errs)
    # Fixture must not accidentally cite the pointer in Acceptance/Do NOT.
    assert ("d", 1) not in _mod.cited_pointers_in_brief(brief)


def test_cited_in_acceptance_or_do_not_passes():
    cell = "d `#812` · req `#430`"
    brief = _brief_with_sections(
        acceptance_extra="- Cite d#812 for the gate shape.",
        do_not_extra="- Do not weaken req#430.",
    )
    assert _mod.check_pointer_citations("A", "01-a.md", cell, brief) == []


def test_short_parse_cell_errors_not_silent():
    """Silent short-parses must error (#3329 lesson)."""
    cell = "d `#1` · #2"  # #2 unclaimed
    brief = _brief_with_sections(acceptance_extra="- d#1 cited.")
    errs = _mod.check_pointer_citations("B", "02-b.md", cell, brief)
    assert any("not claimed" in e.lower() or "unclaimed" in e.lower() or "#2" in e for e in errs)


def test_waived_decision_skipped_by_citation_and_hydrate_parse():
    from taskman.mow import hydrate_specs as hydrate_mod

    cell = "d `#852` · waived: d#99 (covered elsewhere)"
    assert hydrate_mod.parse_pointer_cell(cell) == [("d", 852)]
    brief = _brief_with_sections(acceptance_extra="- Honor d#852.")
    assert _mod.check_pointer_citations("G", "07-g.md", cell, brief) == []


def test_candidate_neither_accepted_nor_waived_exits():
    """Living-spec: candidate must be accepted or waved off (d#852)."""
    from dataclasses import dataclass, field

    @dataclass
    class Dec:
        id: int
        tags: list[str] = field(default_factory=list)
        title: str = ""

    cell = "-"  # nothing accepted/waived
    decisions = [Dec(42, ["path:scripts/*.py"], title="Touches scripts")]
    errs, warns = _mod.check_decision_candidates(
        lane="A",
        cell=cell,
        files_in_scope=["scripts/only.py"],
        lane_tags=[],
        decisions=decisions,
        repo_root=None,
    )
    assert errs
    assert any("42" in e and ("candidate" in e.lower() or "waiv" in e.lower()) for e in errs)
    assert warns == []  # no dead-glob scan without repo_root



def test_candidate_waived_passes_without_hydrate():
    from dataclasses import dataclass, field

    @dataclass
    class Dec:
        id: int
        tags: list[str] = field(default_factory=list)
        title: str = ""

    cell = "waived: d#42 (not this lane)"
    decisions = [Dec(42, ["path:scripts/*.py"])]
    errs, _warns = _mod.check_decision_candidates(
        lane="A",
        cell=cell,
        files_in_scope=["scripts/only.py"],
        lane_tags=[],
        decisions=decisions,
        repo_root=None,
    )
    assert errs == []


def test_dead_glob_warns_non_blocking(tmp_path: Path):
    from dataclasses import dataclass, field

    @dataclass
    class Dec:
        id: int
        tags: list[str] = field(default_factory=list)
        title: str = "Rotten glob"

    # Repo has no matching files for this glob
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "only.py").write_text("x\n", encoding="utf-8")
    cell = "d `#7`"
    decisions = [Dec(7, ["path:does/not/exist/**/*.py"])]
    errs, warns = _mod.check_decision_candidates(
        lane="A",
        cell=cell,
        files_in_scope=["scripts/only.py"],
        lane_tags=[],
        decisions=decisions,
        repo_root=tmp_path,
    )
    # accepted in cell → no candidate error; dead glob → warning only
    assert errs == []
    assert any("7" in w and ("dead" in w.lower() or "glob" in w.lower()) for w in warns)


def test_fixture_dispatch_uncited_candidate_waived_dead_glob(tmp_path: Path):
    """Fixture folder exercising uncited / candidate / waived / dead-glob together."""
    from dataclasses import dataclass, field

    @dataclass
    class Dec:
        id: int
        tags: list[str] = field(default_factory=list)
        title: str = ""

    stem = tmp_path / "gate-demo"
    dispatch = stem / "dispatch"
    dispatch.mkdir(parents=True)
    (stem / "plan.md").write_text("## Decisions locked\nFixture.\n", encoding="utf-8")
    (dispatch / "INDEX.md").write_text(
        """# Dispatch — gate-demo

## Waves
- **Wave 1 (parallel):** A (uncited) ‖ B (candidate) ‖ C (waived)

## Lanes
| Lane | Files owned | Decisions / Specs | Brief |
|---|---|---|---|
| A | `scripts/a.py` | d `#1` | 01-uncited.md |
| B | `scripts/b.py` | - | 02-candidate.md |
| C | `scripts/c.py` | waived: d#3 (other lane) | 03-waived.md |

**Grill checkpoint:** done 2026-08-10
**Grill write-back:** no changes — plan held 2026-08-10
""",
        encoding="utf-8",
    )
    (dispatch / "01-uncited.md").write_text(
        _brief_with_sections(files="scripts/a.py"), encoding="utf-8"
    )
    (dispatch / "02-candidate.md").write_text(
        _brief_with_sections(files="scripts/b.py"), encoding="utf-8"
    )
    (dispatch / "03-waived.md").write_text(
        _brief_with_sections(files="scripts/c.py"), encoding="utf-8"
    )
    plans = tmp_path / "docs" / "plans"
    plans.mkdir(parents=True)
    (plans / "INDEX.md").write_text(
        """# MOW runs
| Stem | Title | Feature | Created | Updated | Status |
|---|---|---|---|---|---|
| gate-demo | Gate demo | - | 2026-08-10 | 2026-08-10 | planned |
""",
        encoding="utf-8",
    )

    index_text = (dispatch / "INDEX.md").read_text(encoding="utf-8")
    briefs = {
        p.name: p.read_text(encoding="utf-8")
        for p in dispatch.glob("[0-9][0-9]-*.md")
    }
    from taskman.mow import hydrate_specs as hydrate_mod

    cite_errs: list[str] = []
    for lane, cell, brief_name in hydrate_mod._split_index_lanes(index_text):
        cite_errs.extend(
            _mod.check_pointer_citations(lane, brief_name, cell, briefs[brief_name])
        )
    assert any("uncited" in e.lower() and "1" in e for e in cite_errs)

    decisions = [
        Dec(2, ["path:scripts/b.py"], title="candidate"),
        Dec(3, ["path:scripts/c.py"], title="waived"),
        Dec(4, ["path:zzz/nope/**"], title="dead"),
    ]
    # Lane B: candidate 2 not accepted → error
    e_b, _ = _mod.check_decision_candidates(
        lane="B",
        cell="-",
        files_in_scope=["scripts/b.py"],
        lane_tags=[],
        decisions=decisions,
        repo_root=tmp_path,
    )
    assert any("2" in e for e in e_b)

    # Lane C: waived 3 → no error
    e_c, _ = _mod.check_decision_candidates(
        lane="C",
        cell="waived: d#3 (other lane)",
        files_in_scope=["scripts/c.py"],
        lane_tags=[],
        decisions=decisions,
        repo_root=tmp_path,
    )
    assert e_c == []

    # Dead glob on accepted pointer
    _e, w = _mod.check_decision_candidates(
        lane="A",
        cell="d `#4`",
        files_in_scope=["scripts/a.py"],
        lane_tags=[],
        decisions=decisions,
        repo_root=tmp_path,
    )
    assert any("4" in x and ("dead" in x.lower() or "glob" in x.lower()) for x in w)


def test_candidate_area_tag_match():
    from dataclasses import dataclass, field

    @dataclass
    class Dec:
        id: int
        tags: list[str] = field(default_factory=list)
        title: str = ""

    decisions = [Dec(55, ["backend"], title="Area match")]
    errs, _ = _mod.check_decision_candidates(
        lane="A",
        cell="-",
        files_in_scope=["scripts/x.py"],
        lane_tags=["backend"],
        decisions=decisions,
        repo_root=None,
    )
    assert any("55" in e for e in errs)


def test_run_preflight_citation_gate_integrated(tmp_path: Path):
    stem = _write_minimal_fixture(tmp_path)
    index = stem / "dispatch" / "INDEX.md"
    text = index.read_text(encoding="utf-8")
    text = text.replace(
        "| Lane | Files owned | Brief |\n|---|---|---|\n| A | `scripts/only.py` | 01-only.md |",
        "| Lane | Files owned | Decisions / Specs | Brief |\n|---|---|---|---|\n"
        "| A | `scripts/only.py` | d `#99` | 01-only.md |",
    )
    index.write_text(text, encoding="utf-8")
    code, errors = _mod.run_preflight(
        stem, repo_root=tmp_path, skip_hydrate=True, decisions=[]
    )
    assert code == 1
    assert any("uncited" in e.lower() and "99" in e for e in errors)


# --- INDEX Decisions/Specs pointer-only grammar (d#946 / plan Decision 6) ---


def test_prose_dump_in_decisions_cell_fails():
    """GIVEN prose after a pointer WHEN lint runs THEN pointers-only error."""
    cell = (
        "d `#12` · The renderer MUST auto-fit the bbox and also flip hashes when…"
    )
    errs = _mod.check_index_decisions_pointer_only("A", cell)
    assert errs
    assert any("pointers only" in e.lower() for e in errs)
    assert any("lane A" in e for e in errs)


def test_stray_annotation_in_decisions_cell_fails():
    """Residual annotation after a pointer is still residual text (d#946)."""
    cell = "d `#12` (renderer bbox)"
    errs = _mod.check_index_decisions_pointer_only("B", cell)
    assert errs
    assert any("lane B" in e and ("pointers only" in e.lower() or "residual" in e.lower()) for e in errs)


def test_pointer_only_cells_pass_prose_lint():
    """Valid pointer grammar (including plan Decision tokens) must pass."""
    assert _mod.check_index_decisions_pointer_only("A", "d `#12` · req `#3`") == []
    assert (
        _mod.check_index_decisions_pointer_only(
            "A", "plan Decisions 1, 2, 7 · task `#8609`"
        )
        == []
    )
    assert _mod.check_index_decisions_pointer_only("A", "-") == []
    assert (
        _mod.check_index_decisions_pointer_only(
            "A", "d `#852` · waived: d#99 (covered elsewhere)"
        )
        == []
    )
