"""Tag matching helpers for Decision/Capture scope (d#852)."""

from __future__ import annotations

from dataclasses import dataclass, field

from taskman.matching import (
    captures_touching,
    decision_matches,
    decisions_touching,
    is_area_tag,
    path_tag_matches,
    tag_matches_scope,
)


@dataclass
class _Tagged:
    id: int
    tags: list[str] = field(default_factory=list)


def test_path_tag_matches_glob_include():
    assert path_tag_matches("path:app/domain/formation*.py", "app/domain/formation_setup.py")


def test_path_tag_matches_glob_exclude():
    assert not path_tag_matches("path:app/domain/formation*.py", "web/x.tsx")


def test_plain_area_tag_matches_lane_tags():
    assert tag_matches_scope("backend", paths=[], tags=["backend", "ui"])
    assert not tag_matches_scope("backend", paths=[], tags=["ui"])


def test_feature_tag_is_literal_not_path():
    assert not path_tag_matches("feature:42", "feature/42.py")
    assert tag_matches_scope("feature:42", paths=[], tags=["feature:42"])


def test_decision_matches_any_path_or_area():
    tags = ["path:app/domain/formation*.py", "backend"]
    assert decision_matches(tags, paths=["app/domain/formation_setup.py"], tags=[])
    assert decision_matches(tags, paths=["web/x.tsx"], tags=["backend"])
    assert not decision_matches(tags, paths=["web/x.tsx"], tags=["ui"])


def test_decisions_touching_filters_collection():
    rows = [
        _Tagged(1, ["path:app/domain/formation*.py"]),
        _Tagged(2, ["path:web/**/*.tsx"]),
        _Tagged(3, ["backend"]),
    ]
    hits = decisions_touching(
        rows, paths=["app/domain/formation_setup.py"], tags=["backend"]
    )
    assert [r.id for r in hits] == [1, 3]


def test_captures_touching_same_rules():
    rows = [_Tagged(10, ["path:docs/**/*.md"]), _Tagged(11, ["ops"])]
    hits = captures_touching(rows, paths=["docs/plans/x.md"], tags=[])
    assert [r.id for r in hits] == [10]


def test_empty_path_prefix_never_matches():
    assert not path_tag_matches("path:", "anything.py")
    assert not path_tag_matches("backend", "backend/x.py")


def test_decision_matches_empty_tags_is_false():
    assert not decision_matches([], paths=["a.py"], tags=["backend"])
    assert not decision_matches(None, paths=["a.py"], tags=["backend"])


def test_is_area_tag_excludes_path_and_feature_prefixes():
    assert is_area_tag("backend")
    assert not is_area_tag("path:app/**")
    assert not is_area_tag("feature:9")
