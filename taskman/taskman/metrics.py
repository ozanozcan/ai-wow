"""Parse Claude Code / Cursor transcripts → meta.json + session metrics."""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger("taskman.metrics")

# Rough chars→tokens proxy for thinking blocks (exact effort knob not in transcript).
_THINKING_CHARS_PER_TOKEN = 4


def meta_path_for(transcript: Path) -> Path:
    """Sidecar next to the transcript: foo.jsonl → foo.meta.json."""
    if transcript.suffix == ".jsonl":
        return transcript.with_suffix(".meta.json")
    return transcript.with_name(transcript.name + ".meta.json")


def detect_source(transcript: Path, first_rows: list[dict] | None = None) -> str:
    parts = transcript.as_posix()
    m = re.search(r"source=([a-zA-Z0-9_-]+)", parts)
    if m:
        return m.group(1)
    if ".cursor" in parts:
        return "cursor"
    if ".claude" in parts:
        return "claude"
    if first_rows:
        sample = first_rows[0]
        if "aiTitle" in sample or (
            sample.get("role") in ("user", "assistant")
            and "sessionId" not in sample
            and "type" not in sample
        ):
            return "cursor"
        if sample.get("type") in ("assistant", "user", "system") and sample.get("sessionId"):
            return "claude"
    return "unknown"


def detect_project_slug(transcript: Path, default: str | None = None) -> str | None:
    m = re.search(r"project=([a-zA-Z0-9_-]+)", transcript.as_posix())
    if m:
        return m.group(1)
    return default


def session_id_from_path(transcript: Path) -> str | None:
    """Filenames look like 20260703T162949Z-<uuid>.jsonl."""
    stem = transcript.name
    if stem.endswith(".jsonl"):
        stem = stem[: -len(".jsonl")]
    # strip leading UTC timestamp if present
    m = re.match(r"^\d{8}T\d{6}Z-(.+)$", stem)
    if m:
        return m.group(1)
    return stem or None


def _empty_bucket() -> dict[str, int]:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "api_calls": 0,
        "server_tool_web_search": 0,
        "server_tool_web_fetch": 0,
    }


def _add_usage(bucket: dict[str, int], usage: dict[str, Any]) -> None:
    bucket["input_tokens"] += int(usage.get("input_tokens") or 0)
    bucket["output_tokens"] += int(usage.get("output_tokens") or 0)
    bucket["cache_read_tokens"] += int(
        usage.get("cache_read_input_tokens") or usage.get("cache_read_tokens") or 0
    )
    bucket["cache_creation_tokens"] += int(
        usage.get("cache_creation_input_tokens") or usage.get("cache_creation_tokens") or 0
    )
    bucket["api_calls"] += 1
    stu = usage.get("server_tool_use") or {}
    if isinstance(stu, dict):
        bucket["server_tool_web_search"] += int(stu.get("web_search_requests") or 0)
        bucket["server_tool_web_fetch"] += int(stu.get("web_fetch_requests") or 0)


def _thinking_stats(content: Any) -> tuple[int, int]:
    """Return (thinking_block_count, char_len) for one assistant message."""
    if not isinstance(content, list):
        return 0, 0
    blocks = 0
    chars = 0
    for part in content:
        if isinstance(part, dict) and part.get("type") == "thinking":
            blocks += 1
            chars += len(part.get("thinking") or "")
    return blocks, chars


def parse_jsonl(path: Path) -> dict[str, Any]:
    """Parse a transcript into a metrics dict (not yet a full meta.json).

    Corrupt lines are logged and skipped. Returns tokens_status ok|unknown.
    """
    models: dict[str, dict[str, int]] = {}
    totals = _empty_bucket()
    speed_modes: set[str] = set()
    thinking_turns = 0
    thinking_chars = 0
    session_id: str | None = None
    wall_ms = 0
    saw_claude_usage = False
    rows_preview: list[dict] = []

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        log.warning("cannot read %s: %s", path, e)
        return _unknown_result(path, session_id_from_path(path), "unknown")

    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            log.warning("%s:%d: corrupt jsonl line (%s) — skipping", path, lineno, e)
            continue
        if not isinstance(row, dict):
            continue
        if len(rows_preview) < 5:
            rows_preview.append(row)

        sid = row.get("sessionId") or row.get("session_id")
        if isinstance(sid, str) and sid:
            session_id = session_id or sid

        # wall-clock from system turn_duration entries (when present)
        if row.get("type") == "system":
            subtype = row.get("subtype") or row.get("content")
            if subtype == "turn_duration" or row.get("turn_duration") is not None:
                dur = row.get("duration_ms") or row.get("turn_duration") or 0
                try:
                    wall_ms += int(dur)
                except (TypeError, ValueError):
                    pass

        if row.get("type") != "assistant":
            continue

        msg = row.get("message") or {}
        if not isinstance(msg, dict):
            continue
        usage = msg.get("usage")
        model = msg.get("model") or "unknown"

        blocks, chars = _thinking_stats(msg.get("content"))
        if blocks:
            thinking_turns += 1
            thinking_chars += chars

        if not isinstance(usage, dict):
            continue

        saw_claude_usage = True
        speed = usage.get("speed")
        if isinstance(speed, str) and speed:
            speed_modes.add(speed)

        if model not in models:
            models[model] = _empty_bucket()
        _add_usage(models[model], usage)
        _add_usage(totals, usage)

    source = detect_source(path, rows_preview)
    if session_id is None:
        session_id = session_id_from_path(path) or "unknown"
    if source == "unknown" and saw_claude_usage:
        source = "claude"

    if source == "cursor" or (not saw_claude_usage and source not in ("claude",)):
        return _unknown_result(path, session_id, source if source != "unknown" else "unknown")

    return {
        "session_id": session_id,
        "source": source,
        "tokens_status": "ok",
        "models": models,
        "totals": {
            "input_tokens": totals["input_tokens"],
            "output_tokens": totals["output_tokens"],
            "cache_read_tokens": totals["cache_read_tokens"],
            "cache_creation_tokens": totals["cache_creation_tokens"],
            "api_calls": totals["api_calls"],
            "server_tool_web_search": totals["server_tool_web_search"],
            "server_tool_web_fetch": totals["server_tool_web_fetch"],
        },
        "effort": {
            "speed_modes": sorted(speed_modes) or (["standard"] if saw_claude_usage else []),
            "thinking_turns": thinking_turns,
            "thinking_token_estimate": thinking_chars // _THINKING_CHARS_PER_TOKEN,
            "wall_clock_ms": wall_ms,
        },
    }


def _unknown_result(path: Path, session_id: str | None, source: str) -> dict[str, Any]:
    return {
        "session_id": session_id or session_id_from_path(path) or "unknown",
        "source": source,
        "tokens_status": "unknown",
        "models": {},
        "totals": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "api_calls": 0,
        },
        "effort": {
            "speed_modes": [],
            "thinking_turns": 0,
            "thinking_token_estimate": 0,
        },
        "tokens": "unknown",
    }


def build_meta(
    transcript: Path,
    *,
    project_slug: str,
    parsed: dict[str, Any] | None = None,
    recorded_at: dt.datetime | None = None,
) -> dict[str, Any]:
    parsed = parsed or parse_jsonl(transcript)
    recorded_at = recorded_at or dt.datetime.now(dt.timezone.utc)
    meta: dict[str, Any] = {
        "session_id": parsed["session_id"],
        "source": parsed["source"],
        "project_slug": project_slug,
        "transcript_path": str(transcript),
        "recorded_at": recorded_at.isoformat(),
        "tokens_status": parsed["tokens_status"],
        "models": parsed.get("models") or {},
        "totals": parsed.get("totals") or {},
        "effort": parsed.get("effort") or {},
    }
    if parsed.get("tokens") == "unknown":
        meta["tokens"] = "unknown"
    return meta


def write_meta(transcript: Path, meta: dict[str, Any]) -> Path:
    dest = meta_path_for(transcript)
    dest.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dest


def iter_transcripts(chat_history_root: Path) -> list[Path]:
    """All .jsonl under docs/chat-history (old flat + project= layouts)."""
    if not chat_history_root.is_dir():
        return []
    return sorted(p for p in chat_history_root.rglob("*.jsonl") if p.is_file())
