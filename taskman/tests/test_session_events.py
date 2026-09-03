"""`session record/backfill/list` — sessions are board events too (plan d-p8).

One `session.record` event per transcript; dedup keys on
(session_id, transcript_path) with the path in portable form (plan d-p9),
matched over replayed state — re-recording updates the row, never duplicates it.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from taskman.cli import main
from taskman.eventlog import store
from taskman.metrics import meta_path_for, portable_transcript_path

MARKER = "session-events-test"


def _run(argv: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(argv)
    return buf.getvalue()


def _write_transcript(path: Path, *, session_id: str, in_tokens: int = 10) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "type": "assistant",
        "sessionId": session_id,
        "message": {
            "model": "claude-x",
            "usage": {"input_tokens": in_tokens, "output_tokens": 5},
        },
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return path


def test_record_emits_session_record_event_and_meta_sidecar(board_dir: Path, tmp_path: Path):
    transcript = _write_transcript(tmp_path / "logs" / "a.jsonl", session_id=f"{MARKER}-1")

    out = _run(["session", "record", "--file", str(transcript)])
    assert "recorded" in out

    # meta.json sidecar behavior is unchanged
    assert meta_path_for(transcript).is_file()

    sessions = list(store.state(board_dir)["session"].values())
    assert len(sessions) == 1
    row = sessions[0]
    assert row["session_id"] == f"{MARKER}-1"
    assert row["input_tokens"] == 10
    assert row["transcript_path"] == portable_transcript_path(transcript)

    # d-p8: the creation verb on the log is session.record, not session.add
    first_event = json.loads(
        (board_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert first_event["type"] == "session.record"


def test_record_twice_updates_in_place_never_duplicates(board_dir: Path, tmp_path: Path):
    transcript = _write_transcript(tmp_path / "logs" / "a.jsonl", session_id=f"{MARKER}-1")
    _run(["session", "record", "--file", str(transcript)])
    _write_transcript(tmp_path / "logs" / "a.jsonl", session_id=f"{MARKER}-1", in_tokens=99)

    _run(["session", "record", "--file", str(transcript)])

    sessions = list(store.state(board_dir)["session"].values())
    assert len(sessions) == 1
    assert sessions[0]["input_tokens"] == 99  # updated, not duplicated


def test_same_session_id_different_transcript_is_a_second_row(board_dir: Path, tmp_path: Path):
    a = _write_transcript(tmp_path / "logs" / "a.jsonl", session_id=f"{MARKER}-1")
    b = _write_transcript(tmp_path / "logs" / "b.jsonl", session_id=f"{MARKER}-1")

    _run(["session", "record", "--file", str(a)])
    _run(["session", "record", "--file", str(b)])

    # dedup key is (session_id, transcript_path) — like the old unique constraint
    assert len(store.state(board_dir)["session"]) == 2


def test_backfill_skips_transcripts_with_existing_meta(board_dir: Path, tmp_path: Path):
    root = tmp_path / "chat-history"
    done = _write_transcript(root / "done.jsonl", session_id=f"{MARKER}-done")
    _write_transcript(root / "fresh.jsonl", session_id=f"{MARKER}-fresh")
    _run(["session", "record", "--file", str(done)])  # writes done's meta.json

    out = _run(["session", "backfill", "--root", str(root)])

    assert "recorded=1" in out
    assert "skipped=1" in out
    assert "errors=0" in out
    assert len(store.state(board_dir)["session"]) == 2


def test_session_list_totals_and_since_filter(board_dir: Path, tmp_path: Path):
    a = _write_transcript(tmp_path / "logs" / "a.jsonl", session_id=f"{MARKER}-1", in_tokens=7)
    b = _write_transcript(tmp_path / "logs" / "b.jsonl", session_id=f"{MARKER}-2", in_tokens=3)
    _run(["session", "record", "--file", str(a)])
    _run(["session", "record", "--file", str(b)])

    out = _run(["session", "list"])
    assert f"{MARKER}-1" in out
    assert f"{MARKER}-2" in out
    assert "input=10" in out  # 7 + 3

    out = _run(["session", "list", "--since", "2099-01-01"])
    assert "(none)" in out
