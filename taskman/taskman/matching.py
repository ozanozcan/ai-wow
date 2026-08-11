"""Decision/Capture scope-tag matching (d#852).

Conventions (schema is a plain ``tags`` ARRAY; meaning lives here):

- plain tag → area match against lane/task tags
- ``path:<glob>`` → ``fnmatch`` against file paths
- ``feature:N`` → literal feature linkage (same as a plain tag for matching)
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable, Sequence
from typing import Protocol, TypeVar


class HasTags(Protocol):
    tags: Sequence[str] | None


T = TypeVar("T", bound=HasTags)

PATH_PREFIX = "path:"
FEATURE_PREFIX = "feature:"


def path_tag_matches(tag: str, path: str) -> bool:
    """True when ``tag`` is ``path:<glob>`` and ``path`` matches the glob."""
    if not tag.startswith(PATH_PREFIX):
        return False
    pattern = tag[len(PATH_PREFIX) :]
    if not pattern:
        return False
    return fnmatch.fnmatch(path, pattern)


def is_area_tag(tag: str) -> bool:
    """Area tags are plain names (not ``path:`` / ``feature:`` prefixes)."""
    return not tag.startswith(PATH_PREFIX) and not tag.startswith(FEATURE_PREFIX)


def tag_matches_scope(
    tag: str,
    *,
    paths: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
) -> bool:
    """Whether one decision/capture tag matches the given paths and/or area tags."""
    paths = paths or ()
    tags = tags or ()
    if tag.startswith(PATH_PREFIX):
        return any(path_tag_matches(tag, p) for p in paths)
    # feature:N and plain area tags: exact membership in the provided tag set
    return tag in tags


def decision_matches(
    decision_tags: Sequence[str] | None,
    *,
    paths: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
) -> bool:
    """True when any of ``decision_tags`` matches paths or area/feature tags."""
    if not decision_tags:
        return False
    return any(tag_matches_scope(t, paths=paths, tags=tags) for t in decision_tags)


def decisions_touching(
    decisions: Iterable[T],
    paths: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
) -> list[T]:
    """Filter decisions whose tags touch the given paths and/or area tags."""
    return [
        d
        for d in decisions
        if decision_matches(d.tags, paths=paths, tags=tags)
    ]


def captures_touching(
    captures: Iterable[T],
    paths: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
) -> list[T]:
    """Same matching rules as :func:`decisions_touching` for Capture rows."""
    return decisions_touching(captures, paths=paths, tags=tags)
