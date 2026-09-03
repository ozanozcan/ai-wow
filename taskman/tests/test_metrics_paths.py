"""Portable transcript paths: build_meta must never emit machine-absolute paths (d-p9)."""

from __future__ import annotations

from pathlib import Path

from taskman.metrics import build_meta, expand_transcript_path, portable_transcript_path

_PARSED = {
    "session_id": "abc-123",
    "source": "claude",
    "tokens_status": "ok",
    "models": {},
    "totals": {},
    "effort": {},
}


def test_build_meta_emits_home_relative_transcript_path():
    transcript = Path.home() / ".claude" / "projects" / "demo" / "20260703T162949Z-abc.jsonl"
    meta = build_meta(transcript, project_slug="demo", parsed=dict(_PARSED))
    assert meta["transcript_path"].startswith("~/")
    assert "/Users/" not in meta["transcript_path"]
    assert ":" not in meta["transcript_path"]  # no Windows drive letter


def test_round_trip_restores_absolute_path():
    original = Path.home() / ".claude" / "projects" / "demo" / "s.jsonl"
    assert expand_transcript_path(portable_transcript_path(original)) == original


def test_expand_accepts_legacy_absolute_string():
    # old meta.json sidecars on disk still carry absolute paths — keep them readable
    legacy = "/Users/someone/.claude/projects/demo/s.jsonl"
    assert expand_transcript_path(legacy) == Path(legacy)


def test_symlinked_home_path_still_relativizes(tmp_path):
    # A transcript reached through a symlink to home (macOS /var → /private/var
    # style) is still under home — it must not leak absolute into the board.
    homelink = tmp_path / "homelink"
    homelink.symlink_to(Path.home())
    transcript = homelink / ".claude" / "projects" / "demo" / "s.jsonl"
    assert portable_transcript_path(transcript) == "~/.claude/projects/demo/s.jsonl"


def test_path_outside_home_kept_verbatim():
    outside = Path("/opt/transcripts/s.jsonl")
    assert portable_transcript_path(outside) == "/opt/transcripts/s.jsonl"
    assert expand_transcript_path("/opt/transcripts/s.jsonl") == outside
