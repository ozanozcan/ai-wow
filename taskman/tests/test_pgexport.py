"""pgexport: Postgres rows -> event-log board, plus the --verify zero-loss gate (d-p10).

Runs with `uv run pytest --noconftest tests/test_pgexport.py` — the legacy
conftest probes Postgres at import time, and this lane never touches a real
database: every test feeds the builder fake row dicts. The thin psycopg fetch
layer stays untested by design (lane Z exercises it against reality).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from taskman import pgexport
from taskman.eventlog import store

UTC = dt.timezone.utc


def _ts(hour: int) -> dt.datetime:
    return dt.datetime(2026, 1, 2, hour, 30, 0, tzinfo=UTC)


def _task(tid: int, hour: int, **over) -> dict:
    row = {
        "id": tid, "pbi_id": None, "title": f"task {tid}", "status": "todo",
        "priority": "med", "tags": [], "lane": "", "surface": "", "afk": "",
        "notes": "", "source_ref": None, "brief": None, "claimed_by": None,
        "claimed_at": None, "created_at": _ts(hour), "updated_at": _ts(hour),
    }
    row.update(over)
    return row


def _feature(fid: int, hour: int, **over) -> dict:
    row = {
        "id": fid, "title": f"feature {fid}", "description": "", "status": "backlog",
        "lane": "", "surface": "", "created_at": _ts(hour), "updated_at": _ts(hour),
    }
    row.update(over)
    return row


def _raw(**over) -> dict:
    raw = {
        "task": [_task(3, 9), _task(17, 10)],
        "feature": [_feature(2, 8)],
        "pbi": [], "requirement": [], "decision": [], "capture": [], "session": [],
        "task_dep": [], "feature_tag": [], "pbi_tag": [],
    }
    raw.update(over)
    return raw


def test_ids_preserved_and_counters_seeded(tmp_path):
    """d-p4: task #17 stays #17; next_ids reads max+1 per entity, 1 when empty."""
    counts = pgexport.export_board(_raw(), tmp_path)
    state = store.state(tmp_path)
    assert set(state["task"]) == {3, 17}
    assert set(state["feature"]) == {2}
    assert state["task"][17]["title"] == "task 17"
    assert state["feature"][2]["title"] == "feature 2"
    assert counts == {"task": 2, "feature": 1, "pbi": 0, "requirement": 0,
                      "decision": 0, "capture": 0, "session": 0}
    # a fresh add continues past the migrated max, per entity
    assert store.add(tmp_path, "task", {"title": "next"}) == 18
    assert store.add(tmp_path, "feature", {"title": "next"}) == 3
    assert store.add(tmp_path, "pbi", {"title": "first"}) == 1


def test_relations_flattened(tmp_path):
    """d-p6: dep rows become blocked_by id lists; tag M2Ms become name arrays."""
    raw = _raw(task_dep=[(17, 3)], feature_tag=[(2, "port"), (2, "infra")])
    pgexport.export_board(raw, tmp_path)
    state = store.state(tmp_path)
    assert state["task"][17]["blocked_by"] == [3]
    assert state["task"][3]["blocked_by"] == []
    assert state["feature"][2]["tags"] == ["infra", "port"]


def test_session_transcript_path_relativized(tmp_path):
    """d-p9: absolute-under-home transcript paths land as ~/... on the board."""
    home_abs = str(Path.home() / ".claude" / "s.jsonl")
    session = {
        "id": 5, "session_id": "abc", "source": "claude",
        "transcript_path": home_abs, "tokens_status": "ok",
        "input_tokens": 1, "output_tokens": 2, "cache_read_tokens": 0,
        "cache_creation_tokens": 0, "api_calls": 3, "models": {}, "effort": {},
        "recorded_at": _ts(11), "created_at": _ts(11),
    }
    pgexport.export_board(_raw(session=[session]), tmp_path)
    stored = store.state(tmp_path)["session"][5]
    assert stored["transcript_path"] == "~/.claude/s.jsonl"
    assert stored["created_at"] == "2026-01-02T11:30:00+00:00"


def _cli(monkeypatch, raw, *args):
    """Run the CLI with the psycopg fetch layer replaced by fake rows."""
    monkeypatch.setattr(pgexport, "_fetch_raw", lambda dsn, slug: raw)
    return pgexport.main(["--slug", "demo", *args])


def test_cli_refuses_non_empty_board_dir(tmp_path, monkeypatch, capsys):
    """No --force: a board dir already holding events.jsonl is a clean error,
    exit non-zero, dir untouched."""
    board = tmp_path / "board"
    board.mkdir(exist_ok=True)  # the suite-wide board_dir fixture may have made it
    existing = board / "events.jsonl"
    existing.write_text("", encoding="utf-8")
    code = _cli(monkeypatch, _raw(), "--board-dir", str(board))
    assert code != 0
    assert capsys.readouterr().err.strip() != ""
    assert existing.read_text(encoding="utf-8") == ""
    assert sorted(p.name for p in board.iterdir()) == ["events.jsonl"]


def test_cli_reports_counts_matching_written_events(tmp_path, monkeypatch, capsys):
    import json

    board = tmp_path / "board"
    assert _cli(monkeypatch, _raw(), "--board-dir", str(board)) == 0
    out = capsys.readouterr().out
    written: dict[str, int] = {}
    with open(board / "events.jsonl", encoding="utf-8") as fh:
        for line in fh:
            entity = json.loads(line)["type"].split(".", 1)[0]
            written[entity] = written.get(entity, 0) + 1
    for entity, count in {"task": 2, "feature": 1}.items():
        assert written[entity] == count
        assert f"{entity}: {count} events" in out
    assert "pbi: 0 events" in out  # empty entities still reported


def _rich_raw() -> dict:
    raw = _raw(task_dep=[(17, 3)], feature_tag=[(2, "port")])
    raw["task"][1]["claimed_by"] = "alpha"
    raw["task"][1]["claimed_at"] = _ts(10)
    return raw


def test_verify_exits_zero_with_totals_on_untouched_source(tmp_path, monkeypatch, capsys):
    """d-p10 green half: same rows, same board -> per-entity totals, exit 0."""
    board = tmp_path / "board"
    assert _cli(monkeypatch, _rich_raw(), "--board-dir", str(board)) == 0
    capsys.readouterr()
    code = _cli(monkeypatch, _rich_raw(), "--board-dir", str(board), "--verify")
    out = capsys.readouterr().out
    assert code == 0
    assert "task: 2 rows" in out
    assert "feature: 1 rows" in out


def test_verify_names_entity_id_field_on_any_mutation(tmp_path, monkeypatch, capsys):
    """d-p10 red half: one mutated source field -> non-zero exit, diff line
    naming entity, id, and field."""
    board = tmp_path / "board"
    assert _cli(monkeypatch, _rich_raw(), "--board-dir", str(board)) == 0

    renamed = _rich_raw()
    renamed["feature_tag"] = [(2, "prot")]  # a tag renamed
    cleared = _rich_raw()
    cleared["task"][1]["claimed_by"] = None  # a claimed_by cleared
    dropped = _rich_raw()
    dropped["task_dep"] = []  # a blocked_by id dropped

    for mutated, entity, eid, field in (
        (renamed, "feature", 2, "tags"),
        (cleared, "task", 17, "claimed_by"),
        (dropped, "task", 17, "blocked_by"),
    ):
        capsys.readouterr()
        code = _cli(monkeypatch, mutated, "--board-dir", str(board), "--verify")
        out = capsys.readouterr().out
        assert code != 0
        diff_lines = [l for l in out.splitlines()
                      if entity in l and f"#{eid}" in l and field in l]
        assert diff_lines, f"no diff line naming {entity} #{eid} {field}: {out!r}"


def test_export_and_verify_share_one_row_transform(tmp_path, monkeypatch):
    """d-p10 structurally: both paths must flow through pgexport.row_fields.
    If verify ever grows its own divergent copy, its half of this test fails."""
    calls: list[str] = []
    original = pgexport.row_fields

    def recording(entity, row):
        calls.append("call")
        return original(entity, row)

    monkeypatch.setattr(pgexport, "row_fields", recording)
    board = tmp_path / "board"
    board.mkdir(exist_ok=True)  # the suite-wide board_dir fixture may have made it
    pgexport.export_board(_rich_raw(), board)
    export_calls = len(calls)
    assert export_calls > 0, "export did not go through row_fields"
    pgexport.verify_board(_rich_raw(), board)
    assert len(calls) > export_calls, "verify did not go through row_fields"


def test_orphaned_tag_rows_are_elided_not_diffed(tmp_path, monkeypatch, capsys):
    """d-p6: a tag name attached to no feature/PBI produces no events and no
    verify diffs — the operator accepted this elision at grill Q2. (The fetch
    layer never even selects orphans; extra raw keys must stay inert.)"""
    raw = _rich_raw()
    raw["tag"] = [{"id": 9, "name": "orphan"}]  # never selected in reality
    board = tmp_path / "board"
    assert _cli(monkeypatch, raw, "--board-dir", str(board)) == 0
    assert "orphan" not in (board / "events.jsonl").read_text(encoding="utf-8")
    capsys.readouterr()
    assert _cli(monkeypatch, raw, "--board-dir", str(board), "--verify") == 0
    assert "orphan" not in capsys.readouterr().out


def test_all_entities_round_trip_through_export_and_verify(tmp_path, monkeypatch, capsys):
    """JSONB passes through as-is; decision/capture task_id ride as plain
    fields; every entity survives export -> replay -> verify with zero diffs."""
    scenarios = [{"name": "s", "given": "g", "when": "w", "then": "t"}]
    raw = _rich_raw()
    raw["pbi"] = [{"id": 4, "feature_id": 2, "title": "the pbi",
                   "acceptance_criteria": "done when", "status": "todo",
                   "priority": "high", "created_at": _ts(7), "updated_at": _ts(7)}]
    raw["requirement"] = [{"id": 6, "feature_id": 2, "title": "req",
                           "statement": "SHALL", "scenarios": scenarios,
                           "status": "active", "source_pbi_id": 4,
                           "created_at": _ts(7), "updated_at": _ts(7)}]
    raw["decision"] = [{"id": 9, "task_id": 17, "title": "dec", "why": "",
                        "alternatives": "", "implications": "", "tags": ["area"],
                        "source_ref": None, "created_at": _ts(8)}]
    raw["capture"] = [{"id": 11, "task_id": None, "kind": "qa", "summary": "",
                       "body": "b", "tags": [], "source_ref": None,
                       "created_at": _ts(9)}]
    raw["pbi_tag"] = [(4, "port")]
    board = tmp_path / "board"
    assert _cli(monkeypatch, raw, "--board-dir", str(board)) == 0
    state = store.state(board)
    assert state["requirement"][6]["scenarios"] == scenarios
    assert state["decision"][9]["task_id"] == 17
    assert state["capture"][11]["task_id"] is None
    assert state["pbi"][4]["tags"] == ["port"]
    capsys.readouterr()
    assert _cli(monkeypatch, raw, "--board-dir", str(board), "--verify") == 0


def test_verify_reports_missing_and_extra_rows(tmp_path, monkeypatch, capsys):
    board = tmp_path / "board"
    assert _cli(monkeypatch, _raw(), "--board-dir", str(board)) == 0
    grown = _raw()
    grown["task"].append(_task(99, 11))  # in Postgres, not on the board
    capsys.readouterr()
    assert _cli(monkeypatch, grown, "--board-dir", str(board), "--verify") != 0
    assert "task #99: missing from the board" in capsys.readouterr().out
    shrunk = _raw()
    del shrunk["task"][0]  # task 3 on the board, gone from Postgres
    assert _cli(monkeypatch, shrunk, "--board-dir", str(board), "--verify") != 0
    assert "task #3: on the board but not in Postgres" in capsys.readouterr().out


def test_import_works_without_psycopg(tmp_path):
    """d-p3: psycopg is the optional pgexport extra — importing the module (and
    running the pure pipeline) must not touch it. Proven in a subprocess whose
    meta_path refuses psycopg outright."""
    import subprocess
    import sys

    probe = (
        "import sys\n"
        "class Refuse:\n"
        "    def find_spec(self, name, *a, **k):\n"
        "        if name.split('.')[0] == 'psycopg':\n"
        "            raise ImportError('psycopg forbidden in this probe')\n"
        "sys.meta_path.insert(0, Refuse())\n"
        "import taskman.pgexport\n"
        "print('imported ok')\n"
    )
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                          text=True, cwd=Path(__file__).resolve().parents[1])
    assert done.returncode == 0, done.stderr
    assert "imported ok" in done.stdout
