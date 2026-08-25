"""Unit tests for mow_hydrate_specs pointer parsing (no DB)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from taskman.models import Capture, Decision, Requirement
from taskman.mow import hydrate_specs as _mod


def test_parse_pointer_cell_catalog_style():
    cell = "d `#384` `#387` `#388` `#394` `#395` · req `#195`"
    assert _mod.parse_pointer_cell(cell) == [
        ("d", 384),
        ("d", 387),
        ("d", 388),
        ("d", 394),
        ("d", 395),
        ("req", 195),
    ]


def test_parse_pointer_cell_dash():
    assert _mod.parse_pointer_cell("-") == []
    assert _mod.parse_pointer_cell("`-`") == []


def test_resolve_entries_accepts_decision_in_workflow_project():
    """d#856: machinery decisions under slug workflow resolve from any cwd project."""
    demo = SimpleNamespace(id=1, slug="demo-api")
    workflow = SimpleNamespace(id=99, slug="workflow")
    dec = SimpleNamespace(
        id=856,
        project_id=workflow.id,
        title="Cross-project visibility",
        implications="Visible from demo cwd",
        why="",
    )
    session = MagicMock()

    def _get(model, oid):
        if model is Decision and oid == 856:
            return dec
        if model is Project and oid == workflow.id:
            return workflow
        return None

    session.get.side_effect = _get
    session.scalar.return_value = workflow

    lines, errors = _mod.resolve_entries(session, demo, [("d", 856)])
    assert errors == []
    assert len(lines) == 1
    assert "d #856" in lines[0]
    assert "Cross-project visibility" in lines[0]


def test_resolve_entries_rejects_decision_in_unrelated_project():
    demo = SimpleNamespace(id=1, slug="demo-api")
    other = SimpleNamespace(id=50, slug="other-app")
    dec = SimpleNamespace(
        id=1,
        project_id=other.id,
        title="Foreign",
        implications="",
        why="",
    )
    session = MagicMock()

    def _get(model, oid):
        if model is Decision and oid == 1:
            return dec
        if model is Project and oid == other.id:
            return other
        return None

    session.get.side_effect = _get
    session.scalar.return_value = None  # no workflow project

    lines, errors = _mod.resolve_entries(session, demo, [("d", 1)])
    assert lines == []
    assert errors == ["decision #1 not found"]


def test_resolve_entries_keeps_requirements_project_scoped():
    demo = SimpleNamespace(id=1, slug="demo-api")
    workflow = SimpleNamespace(id=99, slug="workflow")
    req = SimpleNamespace(
        id=430,
        project_id=workflow.id,
        title="Should stay scoped",
        statement="The system SHALL not leak reqs across projects",
    )
    session = MagicMock()

    def _get(model, oid):
        if model is Requirement and oid == 430:
            return req
        return None

    session.get.side_effect = _get
    session.scalar.return_value = workflow

    lines, errors = _mod.resolve_entries(session, demo, [("req", 430)])
    assert lines == []
    assert errors == ["requirement #430 not found"]


def test_parse_waived_extracts_id_and_reason():
    cell = "d `#852` · waived: d#99 (already handled by sibling lane)"
    assert _mod.parse_waived(cell) == [(99, "already handled by sibling lane")]


def test_parse_pointer_cell_excludes_waived_ids():
    cell = "d `#852` · d `#853` · waived: d#99 (rot)"
    assert _mod.parse_pointer_cell(cell) == [("d", 852), ("d", 853)]


def test_unclaimed_ids_treats_waived_as_claimed():
    # Bare #100 must sit outside a kind's repeated-id chunk (middot after d#N
    # would claim it as another d — that's the #3329 grammar, not unclaimed).
    cell = "#100 · d `#852` · waived: d#99 (reason)"
    pointers = _mod.parse_pointer_cell(cell)
    assert pointers == [("d", 852)]
    assert _mod.unclaimed_ids(cell, pointers) == [100]


def test_waived_reason_does_not_inject_pointers_or_unclaimed_ids():
    """Wave 4 review Critical: reason text must not become citation-gated ids."""
    cell = "waived: d#99 (superseded by d#100; see task #3329)"
    assert _mod.parse_waived(cell) == [
        (99, "superseded by d#100; see task #3329")
    ]
    assert _mod.parse_pointer_cell(cell) == []
    assert _mod.unclaimed_ids(cell, []) == []


def test_waived_reason_may_contain_a_function_call():
    """A reason ending in `foo()` must not truncate at the inner paren (2026-08-26)."""
    cell = "d `#852` · waived: d#1129 (this lane owns instantiate_day() only; the rest is lane Z)"
    assert _mod.parse_waived(cell) == [
        (1129, "this lane owns instantiate_day() only; the rest is lane Z")
    ]
    assert _mod.parse_pointer_cell(cell) == [("d", 852)]
    assert _mod.unclaimed_ids(cell, [("d", 852)]) == []


def test_waived_marker_with_unclosed_paren_is_not_a_marker():
    """No matching close paren -> not parsed, and left in the cell for the lint."""
    cell = "waived: d#99 (never closed"
    assert _mod.parse_waived(cell) == []
    assert _mod._cell_without_waived(cell) == cell


def test_resolve_entries_accepts_capture_in_workflow_project():
    demo = SimpleNamespace(id=1, slug="demo-api")
    workflow = SimpleNamespace(id=99, slug="workflow")
    cap = SimpleNamespace(
        id=848,
        project_id=workflow.id,
        kind="grill",
        summary="Machinery capture",
    )
    session = MagicMock()

    def _get(model, oid):
        if model is Capture and oid == 848:
            return cap
        return None

    session.get.side_effect = _get
    session.scalar.return_value = workflow

    lines, errors = _mod.resolve_entries(session, demo, [("cap", 848)])
    assert errors == []
    assert "cap #848" in lines[0]
