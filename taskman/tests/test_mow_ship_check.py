"""Tests for the ship-check gate (taskman.mow.check_ship_check) + its chokepoint.

Every case here breaks something the gate exists to protect and asserts it fails
(L33) — a gate read but never fired is not a gate. The round-trip test is the one
that keeps the two halves honest: `--emit` writes the marker, `check_stem` reads
it, and a format drift in either would show up as a green-to-red here rather than
as a run that ships unreviewed.
"""

from __future__ import annotations

import datetime
import subprocess
import sys
from pathlib import Path

from taskman.mow import check_ship_check as _mod

_TODAY = datetime.date.today().isoformat()


def _stem(tmp_path: Path, *, plan: str = "# Plan\n\nBuild the thing.\n", report: str | None = None) -> Path:
    """A minimal docs/plans/<stem> tree; `report=None` means no action report."""
    plans = tmp_path / "docs" / "plans"
    stem = plans / "demo"
    (stem / "dispatch").mkdir(parents=True)
    (stem / "plan.md").write_text(plan, encoding="utf-8")
    if report is not None:
        (stem / "action-report.md").write_text(report, encoding="utf-8")
    plans.joinpath("INDEX.md").write_text(
        "# MOW runs\n\n"
        "| Stem | Title | Feature | Created | Updated | Status |\n"
        "|---|---|---|---|---|---|\n"
        "| demo | Demo run | - | 2026-09-01 | 2026-09-01 | running |\n",
        encoding="utf-8",
    )
    return stem


def _marker(stem: Path, *, l1: int = 0, l2: int = 0, l3: int = 0, digest: str | None = None) -> str:
    d = digest or _mod.plan_digest(stem / "plan.md")
    return (
        f"**Ship-check:** done {_TODAY} · plan sha256:{d} · "
        f"L1 {l1} critical · L2 {l2} critical · L3 {l3} critical"
    )


# --- the gate refuses ------------------------------------------------------


def test_missing_action_report_fails(tmp_path):
    stem = _stem(tmp_path)
    errs = _mod.check_stem(stem)
    assert any("action-report.md" in e for e in errs)


def test_missing_plan_fails(tmp_path):
    stem = _stem(tmp_path, report="# Report\n")
    (stem / "plan.md").unlink()
    errs = _mod.check_stem(stem)
    assert any("plan.md" in e and "benchmark" in e for e in errs)


def test_report_without_marker_fails(tmp_path):
    stem = _stem(tmp_path, report="# Report\n\nWe shipped everything. Looks good.\n")
    errs = _mod.check_stem(stem)
    assert any("no **Ship-check:** line" in e for e in errs)


def test_pending_marker_fails(tmp_path):
    stem = _stem(tmp_path, report="**Ship-check:** pending\n")
    errs = _mod.check_stem(stem)
    assert any("still pending" in e for e in errs)


def test_prose_only_marker_fails(tmp_path):
    """The shape found in the wild before this gate existed."""
    stem = _stem(
        tmp_path,
        report="**Ship-check:** run — see the Ship-check gate section above. No Criticals.\n",
    )
    errs = _mod.check_stem(stem)
    assert any("done YYYY-MM-DD" in e for e in errs)
    assert any("plan sha256" in e for e in errs)


def test_stale_plan_digest_fails(tmp_path):
    """Ship-check ran, then plan.md changed — the verdict no longer describes it."""
    stem = _stem(tmp_path, report="placeholder")
    (stem / "action-report.md").write_text(_marker(stem) + "\n", encoding="utf-8")
    (stem / "plan.md").write_text("# Plan\n\nBuild the thing, and also a CSV export.\n", encoding="utf-8")
    errs = _mod.check_stem(stem)
    assert any("the plan changed after the review" in e for e in errs)


def test_missing_layer_count_fails(tmp_path):
    stem = _stem(tmp_path, report="x")
    d = _mod.plan_digest(stem / "plan.md")
    (stem / "action-report.md").write_text(
        f"**Ship-check:** done {_TODAY} · plan sha256:{d} · L1 0 critical\n", encoding="utf-8"
    )
    errs = _mod.check_stem(stem)
    assert any("missing Layer 2, 3" in e for e in errs)


def test_layer1_critical_without_waiver_fails(tmp_path):
    stem = _stem(tmp_path, report="x")
    (stem / "action-report.md").write_text(_marker(stem, l1=2) + "\n", encoding="utf-8")
    errs = _mod.check_stem(stem)
    assert any("accounts for 0" in e for e in errs)


def test_waiver_without_reason_fails(tmp_path):
    stem = _stem(tmp_path, report="x")
    (stem / "action-report.md").write_text(
        _marker(stem, l1=1) + "\n**Ship-check waivers:** L1 CSV export — n/a\n",
        encoding="utf-8",
    )
    errs = _mod.check_stem(stem)
    assert any("has no reason" in e for e in errs)


# --- the gate passes -------------------------------------------------------


def test_clean_record_passes(tmp_path):
    stem = _stem(tmp_path, report="x")
    (stem / "action-report.md").write_text(
        "# Action report — demo\n\n## Verify\n\n" + _marker(stem, l2=1) + "\n",
        encoding="utf-8",
    )
    assert _mod.check_stem(stem) == []


def test_deferred_critical_with_reason_passes(tmp_path):
    stem = _stem(tmp_path, report="x")
    (stem / "action-report.md").write_text(
        _marker(stem, l1=2) + "\n"
        "**Ship-check waivers:** L1 CSV export missing — deferred to stem `exports`, "
        "operator approved; L1 no audit log — fixed in-run, re-verified clean\n",
        encoding="utf-8",
    )
    assert _mod.check_stem(stem) == []


def test_dispatch_dir_argument_resolves_to_stem(tmp_path):
    stem = _stem(tmp_path, report="x")
    (stem / "action-report.md").write_text(_marker(stem) + "\n", encoding="utf-8")
    assert _mod.check_stem(stem / "dispatch") == []


def test_emit_round_trips_through_the_checker(tmp_path):
    """--emit's output must be something check_stem accepts, or the pair rots apart."""
    stem = _stem(tmp_path, report="x")
    line = _mod.emit_marker(stem, 0, 1, 0, _TODAY)
    (stem / "action-report.md").write_text(line + "\n", encoding="utf-8")
    assert _mod.check_stem(stem) == []


def test_emit_refuses_to_invent_a_verdict(tmp_path):
    stem = _stem(tmp_path, report="x")
    assert _mod.main([str(stem), "--emit"]) == 2


# --- reaching the chokepoint -----------------------------------------------
#
# The registry flip now runs the composed close-out gate, so the end-to-end
# subprocess tests live in test_mow_closeout.py alongside the other two checks.
# What belongs here is narrower: a ship-check failure must survive composition
# rather than being swallowed by a report that is otherwise complete.


def test_ship_check_errors_reach_the_composed_gate(tmp_path):
    from tests.test_mow_closeout import _stem as _complete_stem
    from taskman.mow import closeout

    stem = _complete_stem(tmp_path)
    text = (stem / "action-report.md").read_text(encoding="utf-8")
    (stem / "action-report.md").write_text(
        text.replace("**Ship-check:** done", "**Ship-check:** pending —"), encoding="utf-8"
    )
    errors, _ = closeout.run_closeout(stem)
    assert any("still pending" in e for e in errors)
