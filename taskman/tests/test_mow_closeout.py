"""Tests for the close-out gate — action report, tracker reconcile, and their composition.

Shape: `_stem()` builds a run that passes cleanly, and each test breaks exactly one
thing and asserts the gate fires (L33). A gate that has only ever been run against
a good fixture has not been tested; it has been admired.

The clean fixture is modelled on docs/plans/harness-boundary — the best real report
in the tree — because a gate that cannot pass the best existing artifact is
measuring the wrong thing, and that is checked directly in
test_real_harness_boundary_report_passes_structure.
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

from taskman.mow import check_action_report, check_ship_check, check_tracker, closeout

_TODAY = datetime.date.today().isoformat()

_REPORT = """# Action report — demo

**Date:** 2026-09-02
**Project slug:** `demo`
**Plan:** [`plan.md`](plan.md)
**Dispatch:** [`dispatch/INDEX.md`](dispatch/INDEX.md)

## Outcome

| Item | Result |
|---|---|
| The thing | **Shipped** |

## Wave results

Lane A shipped the thing.

## Decisions locked

- We went with the simple version.

## Open / deferred

*None — nothing left over*

## Verify

**P3 post-build protocol:** `n/a` — no flow to exercise.
**Board sync:** `n/a` — no taskman in this repo.
{ship_check}
"""

_TRACKER = {
    "schema": 1,
    "stem": "demo",
    "title": "Demo",
    "run_status": "shipped",
    "started": "2026-09-01T10:00:00Z",
    "updated": "2026-09-01T11:00:00Z",
    "waves": [
        {
            "wave": 1,
            "status": "done",
            "parallelism": "parallel",
            "started": "2026-09-01T10:01:00Z",
            "ended": "2026-09-01T10:50:00Z",
            "gate": {"status": "done", "detail": "clean"},
            "lanes": [
                {
                    "lane": "A",
                    "brief": "01-a.md",
                    "role": "code-edit",
                    "status": "done",
                    "todos": [{"id": "01", "title": "Do it", "status": "done"}],
                    "agents": [
                        {
                            "name": "tdd-builder",
                            "status": "done",
                            "started": "2026-09-01T10:01:00Z",
                            "ended": "2026-09-01T10:45:00Z",
                            "skills": [{"name": "tdd", "status": "done"}],
                        }
                    ],
                }
            ],
        }
    ],
}


def _stem(tmp_path: Path, *, report: str | None = None, tracker: dict | None = _TRACKER) -> Path:
    plans = tmp_path / "docs" / "plans"
    stem = plans / "demo"
    (stem / "dispatch").mkdir(parents=True)
    (stem / "plan.md").write_text("# Plan\n\nBuild the thing.\n", encoding="utf-8")
    (stem / "dispatch" / "INDEX.md").write_text(
        "# Dispatch index — demo\n\n"
        "**Action report:** [`../action-report.md`](../action-report.md)\n",
        encoding="utf-8",
    )
    if report is None:
        digest = check_ship_check.plan_digest(stem / "plan.md")
        report = _REPORT.format(
            ship_check=f"**Ship-check:** done {_TODAY} · plan sha256:{digest} · "
            "L1 0 critical · L2 0 critical · L3 0 critical"
        )
    if report != "":
        (stem / "action-report.md").write_text(report, encoding="utf-8")
    if tracker is not None:
        (stem / "dispatch" / "tracker.json").write_text(json.dumps(tracker), encoding="utf-8")
    plans.joinpath("INDEX.md").write_text(
        "# MOW runs\n\n"
        "| Stem | Title | Feature | Created | Updated | Status |\n"
        "|---|---|---|---|---|---|\n"
        "| demo | Demo run | - | 2026-09-01 | 2026-09-01 | running |\n",
        encoding="utf-8",
    )
    return stem


def _clean_report(stem: Path) -> str:
    return (stem / "action-report.md").read_text(encoding="utf-8")


# --- action report: the gate refuses ---------------------------------------


def test_baseline_fixture_is_clean(tmp_path):
    """If this ever fails, every break-one-thing test below is meaningless."""
    stem = _stem(tmp_path)
    assert closeout.run_closeout(stem) == ([], [])


def test_missing_report_fails(tmp_path):
    stem = _stem(tmp_path, report="")
    assert any("missing" in e and "action-report.md" in e for e in check_action_report.check_stem(stem))


def test_missing_report_is_reported_once_by_closeout(tmp_path):
    """check_ship_check also wants the file; the composer must not say it twice."""
    stem = _stem(tmp_path, report="")
    errors, _ = closeout.run_closeout(stem)
    assert sum("action-report.md" in e for e in errors) == 1


def test_missing_frontmatter_field_fails(tmp_path):
    stem = _stem(tmp_path)
    text = _clean_report(stem).replace("**Project slug:** `demo`\n", "")
    (stem / "action-report.md").write_text(text, encoding="utf-8")
    assert any("frontmatter missing **Project slug:**" in e for e in check_action_report.check_stem(stem))


def test_each_required_section_is_required(tmp_path):
    for heading in ("Outcome", "Wave results", "Decisions locked", "Open / deferred", "Verify"):
        stem = _stem(tmp_path / heading.replace(" ", "_").replace("/", "_"))
        text = _clean_report(stem).replace(f"## {heading}", "## Something else")
        (stem / "action-report.md").write_text(text, encoding="utf-8")
        errs = check_action_report.check_stem(stem)
        assert any(f"missing `## {heading}` section" in e for e in errs), heading


def test_empty_section_fails(tmp_path):
    stem = _stem(tmp_path)
    text = _clean_report(stem).replace("- We went with the simple version.\n", "")
    (stem / "action-report.md").write_text(text, encoding="utf-8")
    assert any("`## Decisions locked` is an empty heading" in e for e in check_action_report.check_stem(stem))


def test_none_with_reason_satisfies_an_empty_section(tmp_path):
    stem = _stem(tmp_path)
    text = _clean_report(stem).replace(
        "- We went with the simple version.", "*None — nothing worth locking*"
    )
    (stem / "action-report.md").write_text(text, encoding="utf-8")
    assert check_action_report.check_stem(stem) == []


def test_verify_without_board_sync_fails(tmp_path):
    stem = _stem(tmp_path)
    text = _clean_report(stem).replace("**Board sync:** `n/a` — no taskman in this repo.\n", "")
    (stem / "action-report.md").write_text(text, encoding="utf-8")
    assert any("**Board sync:**" in e for e in check_action_report.check_stem(stem))


def test_verify_without_p3_record_fails(tmp_path):
    stem = _stem(tmp_path)
    text = _clean_report(stem).replace("**P3 post-build protocol:** `n/a` — no flow to exercise.\n", "")
    (stem / "action-report.md").write_text(text, encoding="utf-8")
    assert any("P3 post-build record" in e for e in check_action_report.check_stem(stem))


def test_dispatch_index_without_action_report_link_fails(tmp_path):
    stem = _stem(tmp_path)
    (stem / "dispatch" / "INDEX.md").write_text("# Dispatch index — demo\n", encoding="utf-8")
    assert any("Action report:" in e for e in check_action_report.check_stem(stem))


def test_alternate_open_deferred_headings_accepted(tmp_path):
    for variant in ("Deferred", "Open and deferred", "Open follow-ups"):
        stem = _stem(tmp_path / variant.replace(" ", "_"))
        text = _clean_report(stem).replace("## Open / deferred", f"## {variant}")
        (stem / "action-report.md").write_text(text, encoding="utf-8")
        assert check_action_report.check_stem(stem) == [], variant


# --- tracker: the gate refuses ---------------------------------------------


def _broken(tmp_path: Path, mutate) -> Path:
    tracker = json.loads(json.dumps(_TRACKER))
    mutate(tracker)
    return _stem(tmp_path, tracker=tracker)


def test_no_tracker_is_a_no_op(tmp_path):
    stem = _stem(tmp_path, tracker=None)
    assert check_tracker.check_stem(stem) == []
    assert closeout.run_closeout(stem) == ([], [])


def test_run_status_still_running_fails(tmp_path):
    stem = _broken(tmp_path, lambda t: t.update(run_status="running"))
    assert any("not `shipped`" in e for e in check_tracker.check_stem(stem))


def test_lane_left_running_fails(tmp_path):
    stem = _broken(tmp_path, lambda t: t["waves"][0]["lanes"][0].update(status="running"))
    assert any("still `running` at close-out" in e for e in check_tracker.check_stem(stem))


def test_todo_left_pending_fails(tmp_path):
    stem = _broken(tmp_path, lambda t: t["waves"][0]["lanes"][0]["todos"][0].update(status="pending"))
    assert any("todo 01" in e and "still `pending`" in e for e in check_tracker.check_stem(stem))


def test_gate_never_ran_fails(tmp_path):
    stem = _broken(tmp_path, lambda t: t["waves"][0]["gate"].update(status="pending"))
    assert any("gate" in e and "still `pending`" in e for e in check_tracker.check_stem(stem))


def test_missing_gate_fails(tmp_path):
    stem = _broken(tmp_path, lambda t: t["waves"][0].pop("gate"))
    assert any("no `gate`" in e for e in check_tracker.check_stem(stem))


def test_issues_lane_without_findings_fails(tmp_path):
    stem = _broken(tmp_path, lambda t: t["waves"][0]["lanes"][0].update(status="issues"))
    assert any("no `findings[]`" in e for e in check_tracker.check_stem(stem))


def test_finding_without_task_id_fails(tmp_path):
    def mutate(t):
        t["waves"][0]["lanes"][0]["status"] = "issues"
        t["waves"][0]["lanes"][0]["findings"] = [{"severity": "warning", "title": "N+1"}]
    stem = _broken(tmp_path, mutate)
    assert any("has no `task` id" in e for e in check_tracker.check_stem(stem))


def test_status_outside_vocabulary_fails(tmp_path):
    stem = _broken(tmp_path, lambda t: t["waves"][0]["lanes"][0].update(status="finished"))
    assert any("outside the schema vocabulary" in e for e in check_tracker.check_stem(stem))


def test_unreadable_tracker_fails(tmp_path):
    stem = _stem(tmp_path)
    (stem / "dispatch" / "tracker.json").write_text("{not json", encoding="utf-8")
    assert any("unreadable" in e for e in check_tracker.check_stem(stem))


# --- tracker: reported, never blocking (the schema calls these optional) ----


def test_agent_missing_ended_warns_but_does_not_block(tmp_path):
    stem = _broken(tmp_path, lambda t: t["waves"][0]["lanes"][0]["agents"][0].pop("ended"))
    assert check_tracker.check_stem(stem) == []
    assert any("no `ended`" in w for w in check_tracker.collect_warnings(stem))


def test_wave_missing_started_warns(tmp_path):
    stem = _broken(tmp_path, lambda t: t["waves"][0].pop("started"))
    assert check_tracker.check_stem(stem) == []
    assert any("wave 1: no `started`" in w for w in check_tracker.collect_warnings(stem))


def test_unreconciled_skills_warn(tmp_path):
    stem = _broken(
        tmp_path,
        lambda t: t["waves"][0]["lanes"][0]["agents"][0].update(
            skills=[{"name": "test-coverage", "status": "pending"}]
        ),
    )
    assert check_tracker.check_stem(stem) == []
    assert any("skills never reconciled" in w for w in check_tracker.collect_warnings(stem))


# --- the cross-artifact check nothing else can make ------------------------


def test_tracker_findings_without_triage_record_fails(tmp_path):
    def mutate(t):
        t["waves"][0]["lanes"][0]["status"] = "issues"
        t["waves"][0]["lanes"][0]["findings"] = [
            {"task": "#3101", "severity": "warning", "title": "N+1 on timer list"}
        ]
    stem = _broken(tmp_path, mutate)
    errors, _ = closeout.run_closeout(stem)
    assert any("no finding-triage record" in e for e in errors)


def test_triage_section_satisfies_the_cross_check(tmp_path):
    def mutate(t):
        t["waves"][0]["lanes"][0]["status"] = "issues"
        t["waves"][0]["lanes"][0]["findings"] = [
            {"task": "#3101", "severity": "warning", "title": "N+1 on timer list"}
        ]
    stem = _broken(tmp_path, mutate)
    text = _clean_report(stem).replace(
        "## Verify", "## Finding triage\n\n- #3101 → **(c) one-off**, captured.\n\n## Verify"
    )
    (stem / "action-report.md").write_text(text, encoding="utf-8")
    errors, _ = closeout.run_closeout(stem)
    assert errors == []


# --- the chokepoint --------------------------------------------------------


def _run_flip(tmp_path: Path, status: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "taskman.mow.set_registry_status", "demo", status,
         "--index", str(tmp_path / "docs" / "plans" / "INDEX.md")],
        capture_output=True, text=True,
        cwd=str(Path(closeout.__file__).resolve().parents[2]),
    )


def test_flip_refused_when_tracker_still_running(tmp_path):
    _broken(tmp_path, lambda t: t.update(run_status="running"))
    proc = _run_flip(tmp_path, "shipped")
    assert proc.returncode == 3, proc.stderr
    assert "close-out gate FAILED" in proc.stderr
    assert "| running |" in (tmp_path / "docs" / "plans" / "INDEX.md").read_text()


def test_flip_refused_when_report_absent(tmp_path):
    _stem(tmp_path, report="")
    proc = _run_flip(tmp_path, "shipped")
    assert proc.returncode == 3, proc.stderr
    assert "| running |" in (tmp_path / "docs" / "plans" / "INDEX.md").read_text()


def test_flip_refused_when_only_the_ship_check_verdict_is_missing(tmp_path):
    """The narrow case: everything written, nobody compared plan to code."""
    stem = _stem(tmp_path)
    text = _clean_report(stem)
    (stem / "action-report.md").write_text(
        text[: text.index("**Ship-check:**")], encoding="utf-8"
    )
    proc = _run_flip(tmp_path, "shipped")
    assert proc.returncode == 3, proc.stderr
    assert "no **Ship-check:** line" in proc.stderr
    assert "| running |" in (tmp_path / "docs" / "plans" / "INDEX.md").read_text()


def test_flip_allowed_on_a_complete_run(tmp_path):
    _stem(tmp_path)
    proc = _run_flip(tmp_path, "shipped")
    assert proc.returncode == 0, proc.stderr
    assert "| shipped |" in (tmp_path / "docs" / "plans" / "INDEX.md").read_text()


def test_warnings_print_but_do_not_block_the_flip(tmp_path):
    _broken(tmp_path, lambda t: t["waves"][0]["lanes"][0]["agents"][0].pop("ended"))
    proc = _run_flip(tmp_path, "shipped")
    assert proc.returncode == 0, proc.stderr
    assert "no `ended`" in proc.stderr
    assert "| shipped |" in (tmp_path / "docs" / "plans" / "INDEX.md").read_text()


# --- the gate must pass the best artifact that already exists --------------


def test_real_harness_boundary_report_passes_structure():
    """Guards against a gate tuned to its own fixture (L46)."""
    real = Path(check_action_report.__file__).resolve().parents[3] / "docs" / "plans" / "harness-boundary"
    if not real.is_dir():
        return  # not this clone's tree
    assert check_action_report.check_stem(real) == []
    assert check_tracker.check_stem(real) == []
