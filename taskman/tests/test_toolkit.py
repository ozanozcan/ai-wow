"""Toolkit recommendations: tag → skills/agents derivation + [toolkit] config parsing."""

from __future__ import annotations

from taskman.cli import toolkit_for_tags
from taskman.config import find_toolkit

MAP = {
    "bug": ["skill:tdd", "skill:diagnose", "skill:parallel-debug"],
    "perf": ["skill:complexity-audit"],
    "backend": ["agent:django-reviewer"],
    "migration": ["agent:django-reviewer"],
}


def test_mapped_tag_yields_entries_in_map_order():
    assert toolkit_for_tags(["bug"], MAP) == [
        "skill:tdd",
        "skill:diagnose",
        "skill:parallel-debug",
    ]


def test_unmapped_tags_yield_nothing():
    assert toolkit_for_tags(["docs"], MAP) == []
    assert toolkit_for_tags([], MAP) == []


def test_union_across_tags_stable_order():
    assert toolkit_for_tags(["perf", "bug"], MAP) == [
        "skill:complexity-audit",
        "skill:tdd",
        "skill:diagnose",
        "skill:parallel-debug",
    ]


def test_union_dedupes_shared_recommendations():
    # backend and migration both recommend django-reviewer — once only.
    assert toolkit_for_tags(["backend", "migration"], MAP) == ["agent:django-reviewer"]


def test_explicit_skill_and_agent_tags_pass_through():
    assert toolkit_for_tags(["skill:imprint", "agent:ui-designer"], MAP) == [
        "skill:imprint",
        "agent:ui-designer",
    ]


def test_explicit_tag_dedupes_against_mapped_entry():
    # `bug` already recommends skill:tdd; an explicit skill:tdd tag adds no dup.
    assert toolkit_for_tags(["bug", "skill:tdd"], MAP) == [
        "skill:tdd",
        "skill:diagnose",
        "skill:parallel-debug",
    ]


def test_role_and_plan_tags_are_not_recommendations():
    assert toolkit_for_tags(["role:code-edit", "plan:harness-automation"], MAP) == []


def test_find_toolkit_reads_nearest_marker(tmp_path, monkeypatch):
    (tmp_path / ".taskman.toml").write_text(
        '[project]\nslug = "scratch"\n\n[toolkit]\nbug = ["skill:tdd"]\n'
    )
    monkeypatch.chdir(tmp_path)
    assert find_toolkit() == {"bug": ["skill:tdd"]}


def test_find_toolkit_missing_table_is_empty(tmp_path, monkeypatch):
    (tmp_path / ".taskman.toml").write_text('[project]\nslug = "scratch"\n')
    monkeypatch.chdir(tmp_path)
    assert find_toolkit() == {}


def test_repo_toolkit_map_drives_bug_recommendations(monkeypatch, tmp_path):
    # A project .taskman.toml [toolkit] stanza is the machine projection of
    # protocols.md P1. The package no longer lives inside a host repo, so the
    # test carries its own stanza instead of chdir-ing to demo/web-app.
    (tmp_path / ".taskman.toml").write_text(
        '[project]\nslug = "toolkit-test"\n\n[toolkit]\nbug = ["skill:tdd", "skill:diagnose"]\n'
    )
    monkeypatch.chdir(tmp_path)
    mapping = find_toolkit()
    assert "bug" in mapping
    assert toolkit_for_tags(["bug"], mapping) == mapping["bug"]
