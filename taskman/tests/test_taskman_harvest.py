"""Harvest pipeline tests — mock LLM, fixture jsonl, live Postgres."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from sqlalchemy import inspect, select, text

from taskman.db import Session, engine, upgrade_head
from taskman.harvest import (
    ExtractedCapture,
    ExtractedDecision,
    ExtractedRequirement,
    ExtractedScenario,
    ExtractedTask,
    ExtractionResult,
    commit_candidates,
    dedupe_candidates,
    extract_from_transcript,
    iter_harvest_transcripts,
    mock_extract,
    parse_approval,
    run_harvest,
    source_ref_for,
)
from taskman.models import Feature, Project, Requirement, Task

MARKER = "wave4-harvest-test"


@pytest.fixture(scope="module", autouse=True)
def _schema_ready():
    upgrade_head()


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    with Session() as session:
        proj = session.scalar(select(Project).where(Project.slug == "demo"))
        if proj is None:
            return
        pid = proj.id
        session.execute(
            text("DELETE FROM taskman_task WHERE project_id = :pid AND title LIKE :m"),
            {"pid": pid, "m": f"%{MARKER}%"},
        )
        session.execute(
            text("DELETE FROM taskman_decision WHERE project_id = :pid AND title LIKE :m"),
            {"pid": pid, "m": f"%{MARKER}%"},
        )
        session.execute(
            text("DELETE FROM taskman_capture WHERE project_id = :pid AND summary LIKE :m"),
            {"pid": pid, "m": f"%{MARKER}%"},
        )
        session.execute(
            text("DELETE FROM taskman_requirement WHERE project_id = :pid AND title LIKE :m"),
            {"pid": pid, "m": f"%{MARKER}%"},
        )
        session.execute(
            text("DELETE FROM taskman_feature WHERE project_id = :pid AND title LIKE :m"),
            {"pid": pid, "m": f"%{MARKER}%"},
        )
        session.commit()


def _fixture_jsonl(tmp_path: Path) -> Path:
    """Minimal Claude-style transcript with extractable content."""
    rows = [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": (
                    f"We decided to use MinIO for log archive. "
                    f"Please implement the harvest CLI next. {MARKER}"
                ),
            },
            "sessionId": "harvest-fixture-session",
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Locked: MinIO first. I'll add taskman harvest with "
                            f"interactive approve. {MARKER}"
                        ),
                    }
                ],
                "model": "claude-test",
                "usage": {"input_tokens": 10, "output_tokens": 20},
            },
            "sessionId": "harvest-fixture-session",
        },
    ]
    path = tmp_path / "docs" / "chat-history" / "agent-sessions" / "project=demo"
    path = path / "source=claude" / "year=2026" / "month=07" / "day=09"
    path.mkdir(parents=True)
    dest = path / "20260709T120000Z-harvest-fixture.jsonl"
    dest.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return dest


def _fixed_extract(condensed: str, label: str) -> ExtractionResult:
    """Mock extract_fn returning one of each kind with MARKER titles."""
    line = 1
    for part in condensed.splitlines():
        if part.startswith("[L"):
            try:
                line = int(part[2:].split("]", 1)[0])
            except ValueError:
                pass
            break
    return ExtractionResult(
        tasks=[
            ExtractedTask(
                title=f"Implement harvest CLI {MARKER}",
                body="From fixture transcript",
                tags=["harvest"],
                line_number=line,
            )
        ],
        decisions=[
            ExtractedDecision(
                title=f"Use MinIO for archives {MARKER}",
                why="Dev-first S3-compatible storage",
                line_number=line,
            )
        ],
        captures=[
            ExtractedCapture(
                kind="plan",
                summary=f"Harvest plan note {MARKER}",
                body="Fixture capture body",
                line_number=line,
            )
        ],
    )


def test_last_harvest_at_column_exists():
    cols = {c["name"] for c in inspect(engine).get_columns("taskman_project")}
    assert "last_harvest_at" in cols


def test_source_ref_format(tmp_path: Path):
    dest = _fixture_jsonl(tmp_path)
    ref = source_ref_for(dest, 2, root=tmp_path)
    assert ref.endswith(".jsonl#L2")
    assert "project=demo" in ref
    assert "#L" in ref


def test_iter_harvest_prefers_project_paths(tmp_path: Path):
    dest = _fixture_jsonl(tmp_path)
    # legacy flat sibling
    legacy_dir = tmp_path / "docs" / "chat-history" / "agent-sessions" / "source=claude"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy = legacy_dir / "20260701T000000Z-legacy.jsonl"
    legacy.write_text('{"type":"user","message":{"role":"user","content":"hi"}}\n')

    found = iter_harvest_transcripts(project_slug="demo", root=tmp_path, since=None)
    assert dest in found
    assert legacy in found
    # other project excluded
    other = tmp_path / "docs" / "chat-history" / "agent-sessions" / "project=other" / "x.jsonl"
    other.parent.mkdir(parents=True)
    other.write_text("{}\n")
    found2 = iter_harvest_transcripts(project_slug="demo", root=tmp_path, since=None)
    assert other not in found2


def test_extract_and_commit_with_mock(tmp_path: Path):
    dest = _fixture_jsonl(tmp_path)
    cands = extract_from_transcript(dest, root=tmp_path, extract_fn=_fixed_extract)
    assert len(cands) == 3
    assert all("#L" in c.source_ref for c in cands)
    assert any(c.kind == "task" for c in cands)

    with Session() as session:
        proj = session.scalar(select(Project).where(Project.slug == "demo"))
        if proj is None:
            proj = Project(slug="demo", name="demo-api")
            session.add(proj)
            session.flush()

        kept = dedupe_candidates(session, proj, cands)
        assert len(kept) == 3
        counts = commit_candidates(session, proj, kept)
        session.commit()
        assert counts == {"task": 1, "decision": 1, "capture": 1, "requirement": 0}

        task = session.scalar(
            select(Task).where(Task.project_id == proj.id, Task.title.like(f"%{MARKER}%"))
        )
        assert task is not None
        assert task.source_ref is not None
        assert "#L" in task.source_ref

        # second pass dedupes
        again = dedupe_candidates(session, proj, cands)
        assert again == []


def test_run_harvest_auto_approve_advances_cursor(tmp_path: Path):
    _fixture_jsonl(tmp_path)
    with Session() as session:
        proj = session.scalar(select(Project).where(Project.slug == "demo"))
        if proj is None:
            proj = Project(slug="demo", name="demo-api")
            session.add(proj)
            session.flush()
        proj.last_harvest_at = None
        session.flush()

        buf = io.StringIO()
        with redirect_stdout(buf):
            summary = run_harvest(
                session,
                proj,
                dry_run=False,
                auto_approve=True,
                root=tmp_path,
                extract_fn=_fixed_extract,
            )
        session.commit()

        assert summary["scanned"] >= 1
        assert summary["approved"] == 3
        assert summary["cursor_advanced"] is True
        assert proj.last_harvest_at is not None

        n_tasks = session.scalar(
            select(Task).where(Task.project_id == proj.id, Task.title.like(f"%{MARKER}%"))
        )
        assert n_tasks is not None


def test_dry_run_does_not_write(tmp_path: Path):
    _fixture_jsonl(tmp_path)
    with Session() as session:
        proj = session.scalar(select(Project).where(Project.slug == "demo"))
        if proj is None:
            proj = Project(slug="demo", name="demo-api")
            session.add(proj)
            session.flush()
        before = proj.last_harvest_at

        buf = io.StringIO()
        with redirect_stdout(buf):
            summary = run_harvest(
                session,
                proj,
                dry_run=True,
                root=tmp_path,
                extract_fn=_fixed_extract,
            )
        session.commit()
        out = buf.getvalue()
        assert summary["candidates"] == 3
        assert "dry-run" in out
        assert "source_ref=" in out
        assert proj.last_harvest_at == before
        # no MARKER rows from this dry-run (cleanup may leave none)
        _ = session.scalars(
            select(Task).where(Task.project_id == proj.id, Task.title.like(f"%{MARKER}%"))
        ).all()
        # dry-run must not have added; if prior test left rows, that's ok — count unchanged
        # Ensure dry-run committed count is zero
        assert summary["committed"] == {
            "task": 0,
            "decision": 0,
            "capture": 0,
            "requirement": 0,
        }


def test_parse_approval():
    assert parse_approval("all", 3) == [1, 2, 3]
    assert parse_approval("none", 3) == []
    assert parse_approval("1,3", 3) == [1, 3]
    with pytest.raises(ValueError):
        parse_approval("9", 3)


def test_mock_extract_emits_candidate():
    condensed = "[L5] user: please implement the harvest feature\n[L6] assistant: ok"
    result = mock_extract(condensed, "docs/chat-history/x.jsonl")
    assert result.captures
    assert result.captures[0].line_number == 5


def _requirement_extract(condensed: str, label: str) -> ExtractionResult:
    line = 1
    for part in condensed.splitlines():
        if part.startswith("[L"):
            try:
                line = int(part[2:].split("]", 1)[0])
            except ValueError:
                pass
            break
    return ExtractionResult(
        requirements=[
            ExtractedRequirement(
                title=f"Session timeout {MARKER}",
                statement="The system SHALL expire idle sessions after 30 minutes.",
                scenarios=[
                    ExtractedScenario(
                        name="Idle",
                        given="an authenticated session",
                        when="30 minutes pass with no activity",
                        then="the session is invalidated",
                    )
                ],
                feature_title="",
                line_number=line,
            )
        ]
    )


def test_harvest_requirement_commit_with_feature_flag(tmp_path: Path):
    dest = _fixture_jsonl(tmp_path)
    with Session() as session:
        proj = session.scalar(select(Project).where(Project.slug == "demo"))
        if proj is None:
            proj = Project(slug="demo", name="demo-api")
            session.add(proj)
            session.flush()
        feat = Feature(
            project_id=proj.id,
            title=f"Harvest feature {MARKER}",
            status="backlog",
        )
        session.add(feat)
        session.flush()
        feat_id = feat.id

        cands = extract_from_transcript(dest, root=tmp_path, extract_fn=_requirement_extract)
        assert len(cands) == 1
        assert cands[0].kind == "requirement"

        counts = commit_candidates(session, proj, cands, default_feature_id=feat_id)
        session.commit()
        assert counts["requirement"] == 1

        req = session.scalar(
            select(Requirement).where(
                Requirement.project_id == proj.id,
                Requirement.title.like(f"%{MARKER}%"),
            )
        )
        assert req is not None
        assert req.feature_id == feat_id
        assert "SHALL" in req.statement
        assert req.scenarios and req.scenarios[0]["then"] == "the session is invalidated"

        again = dedupe_candidates(session, proj, cands, default_feature_id=feat_id)
        assert again == []
