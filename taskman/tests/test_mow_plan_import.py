"""Tests for scripts/mow_plan_import.py (dispatch resolve + import gate)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

_ROOT = Path(__file__).resolve().parents[2]
from taskman.mow import plan_import as _mod


def _write_minimal_dispatch(root: Path, *, with_brief: bool = True) -> Path:
    stem = root / "test-stem"
    dispatch = stem / "dispatch"
    dispatch.mkdir(parents=True)
    (dispatch / "INDEX.md").write_text(
        """# Dispatch — test-stem

Source plan: docs/plans/test-stem/plan.md

## Lanes
| Lane | Brief |
|---|---|
| A | 01-only.md |
""",
        encoding="utf-8",
    )
    if with_brief:
        (dispatch / "01-only.md").write_text(
            """# only: fixture brief

**Role:** code-edit   **Wave:** 1   **AFK:** yes   **Background:** yes

## Goal
Import fixture lands on the board.

## Context & decisions (only what this todo needs)
- Temp fixture for mow_plan_import tests.
- No production paths touched.

## Files in scope
- scripts/only.py

## Do NOT
- Do not edit production stems.

## Acceptance check
- The script SHALL exit 0 on this fixture.
- GIVEN valid dispatch WHEN import runs THEN feature ids print.
- Verify: `pytest taskman/tests/test_mow_plan_import.py -q`

## QA contract
- `pytest taskman/tests/test_mow_plan_import.py -q`
""",
            encoding="utf-8",
        )
    return stem


def test_resolve_dispatch_from_stem_dir(tmp_path: Path):
    stem = _write_minimal_dispatch(tmp_path)
    dispatch, index_path = _mod.resolve_dispatch(stem)
    assert dispatch == stem / "dispatch"
    assert index_path == dispatch / "INDEX.md"


def test_resolve_dispatch_accepts_dispatch_dir_directly(tmp_path: Path):
    stem = _write_minimal_dispatch(tmp_path)
    dispatch, index_path = _mod.resolve_dispatch(stem / "dispatch")
    assert dispatch == stem / "dispatch"
    assert index_path == dispatch / "INDEX.md"


def test_count_briefs(tmp_path: Path):
    stem = _write_minimal_dispatch(tmp_path)
    dispatch, _ = _mod.resolve_dispatch(stem)
    assert _mod.count_briefs(dispatch) == 1


def test_run_plan_import_exit_one_missing_dispatch(tmp_path: Path):
    stem = tmp_path / "no-dispatch"
    stem.mkdir()
    code, out = _mod.run_plan_import(stem, repo_root=tmp_path)
    assert code == 1
    assert "missing" in out.lower() or "dispatch" in out.lower()


def test_run_plan_import_exit_one_empty_briefs(tmp_path: Path):
    stem = _write_minimal_dispatch(tmp_path, with_brief=False)
    mock_run = MagicMock()
    code, out = _mod.run_plan_import(stem, repo_root=tmp_path, run_cmd=mock_run)
    assert code == 1
    assert "brief" in out.lower()
    mock_run.assert_not_called()


def test_run_plan_import_exit_one_subprocess_fails(tmp_path: Path):
    stem = _write_minimal_dispatch(tmp_path)

    def _fail(*_args, **_kwargs):
        proc = MagicMock()
        proc.returncode = 1
        proc.stdout = ""
        proc.stderr = "taskman plan from-decisions: no parseable briefs"
        return proc

    code, out = _mod.run_plan_import(stem, repo_root=tmp_path, run_cmd=_fail)
    assert code == 1
    assert "from-decisions" in out.lower() or "failed" in out.lower()


def test_run_plan_import_exit_zero_prints_feature_and_tasks(tmp_path: Path):
    stem = _write_minimal_dispatch(tmp_path)

    def _ok(*_args, **_kwargs):
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = (
            "taskman plan from-decisions: feature #42  Test stem  (slug=test-stem)  "
            "created=1 updated=0 total=1\n\n"
            "## Feature: Test stem [#42]\n"
            "  #99  Import fixture lands on the board.  backlog  med\n"
        )
        proc.stderr = ""
        return proc

    code, out = _mod.run_plan_import(stem, repo_root=tmp_path, run_cmd=_ok)
    assert code == 0
    assert "feature #42" in out.lower()
    assert "#99" in out


def test_cli_exit_one_when_stem_missing(tmp_path: Path):
    missing = tmp_path / "missing-stem"
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "taskman.mow.plan_import", str(missing)],
        capture_output=True,
        text=True,
        cwd=_ROOT,
    )
    assert result.returncode == 1


def test_empty_briefs_does_not_call_subprocess(tmp_path: Path):
    stem = _write_minimal_dispatch(tmp_path, with_brief=False)
    mock_run = MagicMock()
    _mod.run_plan_import(stem, repo_root=tmp_path, run_cmd=mock_run)
    mock_run.assert_not_called()
