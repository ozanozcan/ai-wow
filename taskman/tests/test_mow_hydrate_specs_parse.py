"""Unit tests for mow_hydrate_specs pointer parsing + board-state resolution (no CLI)."""

from __future__ import annotations

from taskman.mow import hydrate_specs as _mod


def _state(**entities) -> dict:
    """Replayed-board shape: entity -> id -> fields dict."""
    base: dict = {
        e: {} for e in ("task", "feature", "pbi", "requirement", "decision", "capture", "session")
    }
    for entity, rows in entities.items():
        base[entity] = {row["id"]: row for row in rows}
    return base


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


def test_resolve_entries_decision_from_board_state():
    state = _state(
        decision=[
            {
                "id": 856,
                "title": "Cross-project visibility",
                "implications": "Visible from demo cwd",
                "why": "",
            }
        ]
    )
    lines, errors = _mod.resolve_entries(state, [("d", 856)])
    assert errors == []
    assert len(lines) == 1
    assert "d #856" in lines[0]
    assert "Cross-project visibility" in lines[0]


def test_resolve_entries_reports_missing_ids():
    lines, errors = _mod.resolve_entries(_state(), [("d", 1), ("req", 430)])
    assert lines == []
    assert errors == ["decision #1 not found", "requirement #430 not found"]


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


def test_resolve_entries_capture_from_board_state():
    state = _state(
        capture=[
            {
                "id": 848,
                "kind": "grill",
                "summary": "Machinery capture",
            }
        ]
    )
    lines, errors = _mod.resolve_entries(state, [("cap", 848)])
    assert errors == []
    assert "cap #848" in lines[0]
