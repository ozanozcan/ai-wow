"""Unit tests for taskman.metrics — jsonl parse + meta sidecar (no DB required)."""

from __future__ import annotations

import json
from pathlib import Path

from taskman.metrics import (
    build_meta,
    detect_source,
    iter_transcripts,
    meta_path_for,
    parse_jsonl,
    session_id_from_path,
    write_meta,
)


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def test_meta_path_for():
    p = Path("docs/chat-history/agent-sessions/source=claude/foo.jsonl")
    assert meta_path_for(p) == Path("docs/chat-history/agent-sessions/source=claude/foo.meta.json")


def test_session_id_from_path():
    assert (
        session_id_from_path(Path("20260703T162949Z-e09ce707-f510-4e50-9b4b-89e9a81037d1.jsonl"))
        == "e09ce707-f510-4e50-9b4b-89e9a81037d1"
    )


def test_detect_source_from_hive_path():
    assert detect_source(Path("x/source=claude/y.jsonl")) == "claude"
    assert detect_source(Path("x/source=cursor/y.jsonl")) == "cursor"


def test_parse_claude_usage_and_models(tmp_path: Path):
    path = _write_jsonl(
        tmp_path / "source=claude" / "20260101T000000Z-sess-1.jsonl",
        [
            {"type": "user", "sessionId": "sess-1", "message": {"role": "user", "content": "hi"}},
            {
                "type": "assistant",
                "sessionId": "sess-1",
                "message": {
                    "model": "claude-opus-4-8",
                    "content": [{"type": "thinking", "thinking": "abcd" * 10}],
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "cache_read_input_tokens": 50,
                        "cache_creation_input_tokens": 10,
                        "speed": "standard",
                        "server_tool_use": {"web_search_requests": 1, "web_fetch_requests": 0},
                    },
                },
            },
            {
                "type": "assistant",
                "sessionId": "sess-1",
                "message": {
                    "model": "claude-sonnet-5",
                    "content": [{"type": "text", "text": "ok"}],
                    "usage": {
                        "input_tokens": 30,
                        "output_tokens": 5,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                        "speed": "fast",
                    },
                },
            },
            {"type": "assistant", "sessionId": "sess-1", "message": {"model": "x"}},  # no usage
        ],
    )
    # corrupt line — must not raise
    path.write_text(path.read_text() + "not-json{{{\n", encoding="utf-8")

    parsed = parse_jsonl(path)
    assert parsed["tokens_status"] == "ok"
    assert parsed["session_id"] == "sess-1"
    assert parsed["source"] == "claude"
    assert parsed["totals"]["input_tokens"] == 130
    assert parsed["totals"]["output_tokens"] == 25
    assert parsed["totals"]["cache_read_tokens"] == 50
    assert parsed["totals"]["cache_creation_tokens"] == 10
    assert parsed["totals"]["api_calls"] == 2
    assert parsed["totals"]["server_tool_web_search"] == 1
    assert set(parsed["models"]) == {"claude-opus-4-8", "claude-sonnet-5"}
    assert parsed["models"]["claude-opus-4-8"]["api_calls"] == 1
    assert parsed["models"]["claude-sonnet-5"]["input_tokens"] == 30
    assert set(parsed["effort"]["speed_modes"]) == {"fast", "standard"}
    assert parsed["effort"]["thinking_turns"] == 1
    assert parsed["effort"]["thinking_token_estimate"] == 10  # 40 chars / 4

    meta = build_meta(path, project_slug="hlc", parsed=parsed)
    assert meta["project_slug"] == "hlc"
    assert "recorded_at" in meta
    dest = write_meta(path, meta)
    assert dest == meta_path_for(path)
    assert dest.is_file()
    loaded = json.loads(dest.read_text())
    assert loaded["totals"]["api_calls"] == 2


def test_parse_cursor_unknown(tmp_path: Path):
    path = _write_jsonl(
        tmp_path / "source=cursor" / "20260101T000000Z-cur-1.jsonl",
        [
            {"role": "user", "message": {"content": [{"type": "text", "text": "hi"}]}},
            {"role": "assistant", "message": {"content": [{"type": "text", "text": "yo"}]}},
        ],
    )
    parsed = parse_jsonl(path)
    assert parsed["tokens_status"] == "unknown"
    assert parsed["source"] == "cursor"
    assert parsed.get("tokens") == "unknown"
    assert parsed["totals"]["api_calls"] == 0

    meta = build_meta(path, project_slug="hlc", parsed=parsed)
    assert meta["tokens"] == "unknown"
    assert meta["tokens_status"] == "unknown"


def test_iter_transcripts_old_and_new_layouts(tmp_path: Path):
    root = tmp_path / "chat-history"
    old = root / "agent-sessions" / "source=claude" / "year=2026" / "a.jsonl"
    new = root / "agent-sessions" / "project=hlc" / "source=claude" / "year=2026" / "b.jsonl"
    _write_jsonl(old, [{"type": "user", "sessionId": "a"}])
    _write_jsonl(new, [{"type": "user", "sessionId": "b"}])
    found = {p.name for p in iter_transcripts(root)}
    assert found == {"a.jsonl", "b.jsonl"}
