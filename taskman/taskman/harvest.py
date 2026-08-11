"""Mine archived transcripts into Task / Decision / Capture candidates.

Model: env ``TASKMAN_HARVEST_MODEL`` (default ``openai:gpt-4o-mini``).
Set ``TASKMAN_HARVEST_MOCK=1`` for a deterministic stub (no API key).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session as SASession

from taskman.models import CAPTURE_KINDS, Capture, Decision, Feature, Project, Requirement, Task

# Cheap/fast default; override with TASKMAN_HARVEST_MODEL (e.g. anthropic:claude-haiku-4-5).
DEFAULT_HARVEST_MODEL = "openai:gpt-4o-mini"
CHUNK_MESSAGES = 40
AGENT_SESSIONS = Path("docs/chat-history/agent-sessions")

CandidateKind = Literal["task", "decision", "capture", "requirement"]


class ExtractedScenario(BaseModel):
    name: str = ""
    given: str = ""
    when: str = ""
    then: str = ""


class ExtractedRequirement(BaseModel):
    title: str
    statement: str = ""
    scenarios: list[ExtractedScenario] = Field(default_factory=list)
    feature_title: str = ""
    line_number: int = 1


class ExtractedTask(BaseModel):
    title: str
    body: str = ""
    tags: list[str] = Field(default_factory=list)
    line_number: int = 1


class ExtractedDecision(BaseModel):
    title: str
    why: str = ""
    alternatives: str = ""
    implications: str = ""
    tags: list[str] = Field(default_factory=list)
    line_number: int = 1


class ExtractedCapture(BaseModel):
    kind: str = "plan"  # qa|grill|plan
    summary: str = ""
    body: str = ""
    tags: list[str] = Field(default_factory=list)
    line_number: int = 1


class ExtractionResult(BaseModel):
    tasks: list[ExtractedTask] = Field(default_factory=list)
    decisions: list[ExtractedDecision] = Field(default_factory=list)
    captures: list[ExtractedCapture] = Field(default_factory=list)
    requirements: list[ExtractedRequirement] = Field(default_factory=list)


@dataclass
class Candidate:
    kind: CandidateKind
    title: str
    body: str
    source_ref: str
    tags: list[str] = field(default_factory=list)
    # decision extras
    why: str = ""
    alternatives: str = ""
    implications: str = ""
    # capture extras
    capture_kind: str = "plan"
    # requirement extras
    statement: str = ""
    scenarios: list[dict[str, str]] = field(default_factory=list)
    feature_title: str = ""


ExtractFn = Callable[[str, str], ExtractionResult]


def harvest_model_name() -> str:
    return os.environ.get("TASKMAN_HARVEST_MODEL", DEFAULT_HARVEST_MODEL)


def use_mock_extractor() -> bool:
    return os.environ.get("TASKMAN_HARVEST_MOCK", "").strip() in ("1", "true", "yes")


def has_llm_api_key() -> bool:
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "AZURE_OPENAI_API_KEY",
    ):
        if os.environ.get(key):
            return True
    return False


def project_root_from_cwd() -> Path:
    """Nearest directory containing .taskman.toml (same walk as config.find_project)."""
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / ".taskman.toml").exists():
            return d
    return here


def relative_transcript_path(transcript: Path, root: Path | None = None) -> str:
    root = root or project_root_from_cwd()
    try:
        return transcript.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return transcript.as_posix()


def source_ref_for(transcript: Path, line_number: int, root: Path | None = None) -> str:
    rel = relative_transcript_path(transcript, root)
    return f"{rel}#L{max(1, int(line_number))}"


def _message_text(row: dict[str, Any]) -> str | None:
    """Return a short role:text line for harvest condensation, or None to skip."""
    # Cursor-style
    if row.get("role") in ("user", "assistant"):
        msg = row.get("message") or {}
        content = msg.get("content") if isinstance(msg, dict) else None
        if content is None:
            content = row.get("message")
        text = _flatten_content(content)
        if text:
            return f"{row['role']}: {text}"
    # Claude Code style
    typ = row.get("type")
    if typ in ("user", "assistant"):
        msg = row.get("message") or {}
        if not isinstance(msg, dict):
            return None
        role = msg.get("role") or typ
        text = _flatten_content(msg.get("content"))
        if text:
            return f"{role}: {text}"
    return None


def _flatten_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                if part.get("type") == "text" and part.get("text"):
                    parts.append(str(part["text"]))
                elif part.get("type") == "tool_use":
                    name = part.get("name") or "tool"
                    parts.append(f"[tool:{name}]")
                elif part.get("type") == "tool_result":
                    parts.append("[tool_result]")
        return " ".join(p.strip() for p in parts if p and p.strip())
    return str(content).strip()


def condense_transcript(transcript: Path) -> list[tuple[int, str]]:
    """Return (line_number, condensed_line) for user/assistant messages."""
    out: list[tuple[int, str]] = []
    try:
        text = transcript.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        msg = _message_text(row)
        if msg:
            # Cap very long lines for the LLM prompt.
            if len(msg) > 2000:
                msg = msg[:2000] + "…"
            out.append((lineno, msg))
    return out


def iter_harvest_transcripts(
    *,
    project_slug: str,
    root: Path | None = None,
    since: dt.datetime | None = None,
) -> list[Path]:
    """Glob agent-sessions JSONL for this project (hive + legacy flat)."""
    root = root or project_root_from_cwd()
    base = root / AGENT_SESSIONS
    if not base.is_dir():
        return []

    preferred = base / f"project={project_slug}"
    candidates: list[Path] = []
    if preferred.is_dir():
        candidates.extend(p for p in preferred.rglob("*.jsonl") if p.is_file())
    # Legacy flat (no project=) — still harvestable for this project.
    for p in base.rglob("*.jsonl"):
        if not p.is_file():
            continue
        if "project=" in p.as_posix() and f"project={project_slug}" not in p.as_posix():
            continue
        if p not in candidates:
            # Only add legacy (no project=) or already-preferred.
            if "project=" not in p.as_posix() or f"project={project_slug}" in p.as_posix():
                candidates.append(p)

    # Skip sidecars (*.meta.json already excluded by *.jsonl glob).
    out: list[Path] = []
    for p in sorted(set(candidates)):
        if p.name.endswith(".meta.json"):
            continue
        mtime = dt.datetime.fromtimestamp(p.stat().st_mtime, tz=dt.timezone.utc)
        if since is not None and mtime <= since:
            continue
        out.append(p)
    return out


_EXTRACTION_INSTRUCTIONS = """\
You extract actionable work items from agent chat transcripts for a project task board.

Return ONLY structured data with four lists:
- tasks: concrete work to do (title, optional body, tags, line_number from the transcript)
- decisions: choices that were made (title, why, alternatives, implications, line_number)
- captures: notes of kind qa|grill|plan (kind, summary, body, line_number)
- requirements: durable system behaviors stated as living spec (title, statement with
  SHALL/MUST/SHOULD/MAY, scenarios with name/given/when/then, optional feature_title hint,
  line_number). Only include requirements when the transcript establishes lasting product
  behavior — not one-off tasks.

Rules:
- Prefer high-signal items; skip chitchat and tool noise.
- line_number must refer to a line shown in the transcript excerpt (the [L#] prefix).
- tags are short lowercase labels when obvious; else empty.
- requirement statement must be one observable behavior with a normative keyword.
- If nothing worth capturing, return empty lists.
"""


def build_pydantic_ai_agent(model: str | None = None):
    """Create a pydantic-ai Agent for structured extraction."""
    from pydantic_ai import Agent

    return Agent(
        model or harvest_model_name(),
        output_type=ExtractionResult,
        instructions=_EXTRACTION_INSTRUCTIONS,
    )


def llm_extract(condensed: str, transcript_label: str, *, agent=None) -> ExtractionResult:
    if agent is None:
        agent = build_pydantic_ai_agent()
    prompt = (
        f"Transcript: {transcript_label}\n\n"
        f"Excerpt (each line prefixed with [L<line_number>]):\n{condensed}\n"
    )
    result = agent.run_sync(prompt)
    out = result.output
    if isinstance(out, ExtractionResult):
        return out
    return ExtractionResult.model_validate(out)


def mock_extract(condensed: str, transcript_label: str) -> ExtractionResult:
    """Deterministic stub for tests / AFK without API keys (TASKMAN_HARVEST_MOCK=1)."""
    tasks: list[ExtractedTask] = []
    decisions: list[ExtractedDecision] = []
    captures: list[ExtractedCapture] = []
    first_line = 1
    for line in condensed.splitlines():
        m = re.match(r"\[L(\d+)\]", line)
        if m:
            first_line = int(m.group(1))
            break
    # Always emit one capture so dry-run / tests have a candidate.
    label = Path(transcript_label).name
    captures.append(
        ExtractedCapture(
            kind="plan",
            summary=f"Harvest stub: {label}",
            body="Deterministic mock extraction (TASKMAN_HARVEST_MOCK=1).",
            tags=["harvest-mock"],
            line_number=first_line,
        )
    )
    # Heuristic: decision-ish language → decision candidate.
    lower = condensed.lower()
    if "decid" in lower or "we will" in lower or "locked" in lower:
        decisions.append(
            ExtractedDecision(
                title=f"Decision from {label}",
                why="Mentioned in transcript (mock heuristic).",
                line_number=first_line,
            )
        )
    if "todo" in lower or "implement" in lower or "add " in lower or "fix " in lower:
        tasks.append(
            ExtractedTask(
                title=f"Follow-up from {label}",
                body="Mock task from transcript keywords.",
                tags=["harvest-mock"],
                line_number=first_line,
            )
        )
    if "shall" in lower or "must " in lower or "given " in lower:
        requirements: list[ExtractedRequirement] = []
        requirements.append(
            ExtractedRequirement(
                title=f"Behavior from {label}",
                statement="The system SHALL behave as discussed in the transcript (mock).",
                scenarios=[
                    ExtractedScenario(
                        name="Happy path",
                        given="the discussed preconditions",
                        when="the trigger occurs",
                        then="the expected outcome holds",
                    )
                ],
                feature_title="",
                line_number=first_line,
            )
        )
        return ExtractionResult(
            tasks=tasks, decisions=decisions, captures=captures, requirements=requirements
        )
    return ExtractionResult(tasks=tasks, decisions=decisions, captures=captures)


def _chunk_messages(
    messages: list[tuple[int, str]], size: int = CHUNK_MESSAGES
) -> list[list[tuple[int, str]]]:
    if not messages:
        return []
    return [messages[i : i + size] for i in range(0, len(messages), size)]


def _format_chunk(chunk: list[tuple[int, str]]) -> str:
    return "\n".join(f"[L{lineno}] {text}" for lineno, text in chunk)


def _merge_extractions(parts: list[ExtractionResult]) -> ExtractionResult:
    tasks: list[ExtractedTask] = []
    decisions: list[ExtractedDecision] = []
    captures: list[ExtractedCapture] = []
    requirements: list[ExtractedRequirement] = []
    seen_t: set[str] = set()
    seen_d: set[str] = set()
    seen_c: set[str] = set()
    seen_r: set[str] = set()
    for part in parts:
        for t in part.tasks:
            key = t.title.strip().lower()
            if key and key not in seen_t:
                seen_t.add(key)
                tasks.append(t)
        for d in part.decisions:
            key = d.title.strip().lower()
            if key and key not in seen_d:
                seen_d.add(key)
                decisions.append(d)
        for c in part.captures:
            key = (c.kind, (c.summary or c.body)[:80].strip().lower())
            if key[1] and key not in seen_c:
                seen_c.add(key)
                captures.append(c)
        for r in part.requirements:
            key = (r.title.strip().lower(), r.statement.strip().lower()[:120])
            if key[0] and key not in seen_r:
                seen_r.add(key)
                requirements.append(r)
    return ExtractionResult(
        tasks=tasks,
        decisions=decisions,
        captures=captures,
        requirements=requirements,
    )


def extract_from_transcript(
    transcript: Path,
    *,
    root: Path | None = None,
    extract_fn: ExtractFn | None = None,
    agent=None,
) -> list[Candidate]:
    root = root or project_root_from_cwd()
    messages = condense_transcript(transcript)
    if not messages:
        return []

    if extract_fn is None:
        if use_mock_extractor():
            extract_fn = mock_extract
        else:

            def extract_fn(condensed: str, label: str) -> ExtractionResult:
                return llm_extract(condensed, label, agent=agent)

    label = relative_transcript_path(transcript, root)
    parts: list[ExtractionResult] = []
    for chunk in _chunk_messages(messages):
        parts.append(extract_fn(_format_chunk(chunk), label))
    merged = _merge_extractions(parts)

    cands: list[Candidate] = []
    for t in merged.tasks:
        cands.append(
            Candidate(
                kind="task",
                title=t.title.strip(),
                body=t.body or "",
                tags=list(t.tags or []),
                source_ref=source_ref_for(transcript, t.line_number, root),
            )
        )
    for d in merged.decisions:
        cands.append(
            Candidate(
                kind="decision",
                title=d.title.strip(),
                body=d.why or "",
                why=d.why or "",
                alternatives=d.alternatives or "",
                implications=d.implications or "",
                tags=list(d.tags or []),
                source_ref=source_ref_for(transcript, d.line_number, root),
            )
        )
    for c in merged.captures:
        kind = c.kind if c.kind in CAPTURE_KINDS else "plan"
        summary = (c.summary or c.body or "capture").strip()
        cands.append(
            Candidate(
                kind="capture",
                title=summary,
                body=c.body or "",
                capture_kind=kind,
                tags=list(c.tags or []),
                source_ref=source_ref_for(transcript, c.line_number, root),
            )
        )
    for r in merged.requirements:
        statement = (r.statement or "").strip()
        if not statement:
            continue
        scenarios = [
            {
                "name": sc.name,
                "given": sc.given,
                "when": sc.when,
                "then": sc.then,
            }
            for sc in (r.scenarios or [])
        ]
        cands.append(
            Candidate(
                kind="requirement",
                title=r.title.strip(),
                body=statement,
                statement=statement,
                scenarios=scenarios,
                feature_title=(r.feature_title or "").strip(),
                source_ref=source_ref_for(transcript, r.line_number, root),
            )
        )
    return [c for c in cands if c.title]


def _norm_title(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _resolve_feature_id(
    session: SASession,
    project: Project,
    *,
    feature_title: str = "",
    default_feature_id: int | None = None,
) -> int | None:
    """Match feature by title hint, else fall back to CLI --feature default."""
    hint = feature_title.strip()
    if hint:
        feat = session.scalar(
            select(Feature).where(
                Feature.project_id == project.id,
                Feature.title.ilike(hint),
            )
        )
        if feat is not None:
            return feat.id
        feat = session.scalar(
            select(Feature).where(
                Feature.project_id == project.id,
                Feature.title.ilike(f"%{hint}%"),
            )
        )
        if feat is not None:
            return feat.id
    if default_feature_id is not None:
        feat = session.get(Feature, default_feature_id)
        if feat is not None and feat.project_id == project.id:
            return feat.id
    return None


def dedupe_candidates(
    session: SASession,
    project: Project,
    candidates: list[Candidate],
    *,
    default_feature_id: int | None = None,
) -> list[Candidate]:
    """Drop candidates that already exist (source_ref exact or fuzzy title+source path)."""
    if not candidates:
        return []

    refs = {c.source_ref for c in candidates if c.source_ref}
    existing_refs: set[str] = set()
    if refs:
        for model in (Task, Decision, Capture):
            rows = session.scalars(
                select(model.source_ref).where(
                    model.project_id == project.id,
                    model.source_ref.in_(refs),
                )
            ).all()
            existing_refs.update(r for r in rows if r)

    # Fuzzy: same title (norm) and same transcript path prefix of source_ref.
    existing_fuzzy: set[tuple[str, str]] = set()
    existing_req_fuzzy: set[tuple[int, str]] = set()
    titles = {_norm_title(c.title) for c in candidates}
    if titles:
        task_rows = session.scalars(
            select(Task).where(
                Task.project_id == project.id,
                or_(Task.source_ref.is_not(None), Task.title.is_not(None)),
            )
        ).all()
        for t in task_rows:
            if _norm_title(t.title) in titles:
                path = (t.source_ref or "").split("#", 1)[0]
                existing_fuzzy.add((_norm_title(t.title), path))
        dec_rows = session.scalars(
            select(Decision).where(Decision.project_id == project.id)
        ).all()
        for d in dec_rows:
            if _norm_title(d.title) in titles:
                path = (d.source_ref or "").split("#", 1)[0]
                existing_fuzzy.add((_norm_title(d.title), path))
        cap_rows = session.scalars(
            select(Capture).where(Capture.project_id == project.id)
        ).all()
        for c in cap_rows:
            key = _norm_title(c.summary or "")
            if key in titles:
                path = (c.source_ref or "").split("#", 1)[0]
                existing_fuzzy.add((key, path))
        req_rows = session.scalars(
            select(Requirement).where(
                Requirement.project_id == project.id,
                Requirement.status == "active",
            )
        ).all()
        for r in req_rows:
            existing_req_fuzzy.add((r.feature_id, _norm_title(r.title)))

    kept: list[Candidate] = []
    seen_local: set[str] = set()
    for c in candidates:
        if c.source_ref in existing_refs:
            continue
        path = c.source_ref.split("#", 1)[0]
        if (_norm_title(c.title), path) in existing_fuzzy:
            continue
        if c.kind == "requirement":
            feat_id = _resolve_feature_id(
                session,
                project,
                feature_title=c.feature_title,
                default_feature_id=default_feature_id,
            )
            if feat_id is not None and (feat_id, _norm_title(c.title)) in existing_req_fuzzy:
                continue
        local_key = f"{c.kind}:{c.source_ref}:{_norm_title(c.title)}"
        if local_key in seen_local:
            continue
        seen_local.add(local_key)
        kept.append(c)
    return kept


def commit_candidates(
    session: SASession,
    project: Project,
    approved: list[Candidate],
    *,
    default_feature_id: int | None = None,
) -> dict[str, int]:
    counts = {"task": 0, "decision": 0, "capture": 0, "requirement": 0}
    for c in approved:
        if c.kind == "task":
            session.add(
                Task(
                    project_id=project.id,
                    title=c.title,
                    tags=c.tags or [],
                    source_ref=c.source_ref,
                    status="backlog",
                )
            )
            counts["task"] += 1
        elif c.kind == "decision":
            session.add(
                Decision(
                    project_id=project.id,
                    title=c.title,
                    why=c.why or c.body or "",
                    alternatives=c.alternatives or "",
                    implications=c.implications or "",
                    source_ref=c.source_ref,
                )
            )
            counts["decision"] += 1
        elif c.kind == "capture":
            session.add(
                Capture(
                    project_id=project.id,
                    kind=c.capture_kind if c.capture_kind in CAPTURE_KINDS else "plan",
                    summary=c.title,
                    body=c.body or "",
                    source_ref=c.source_ref,
                )
            )
            counts["capture"] += 1
        elif c.kind == "requirement":
            feat_id = _resolve_feature_id(
                session,
                project,
                feature_title=c.feature_title,
                default_feature_id=default_feature_id,
            )
            if feat_id is None:
                print(
                    f"taskman harvest: skipping requirement {c.title!r} — "
                    "no matching feature (pass --feature or feature_title hint)"
                )
                continue
            if not (c.statement or c.body or "").strip():
                print(
                    f"taskman harvest: skipping requirement {c.title!r} — empty statement"
                )
                continue
            existing = session.scalars(
                select(Requirement).where(
                    Requirement.project_id == project.id,
                    Requirement.feature_id == feat_id,
                    Requirement.status == "active",
                )
            ).all()
            if any(_norm_title(r.title) == _norm_title(c.title) for r in existing):
                print(
                    f"taskman harvest: skipping requirement {c.title!r} — "
                    f"already active on feature #{feat_id}"
                )
                continue
            session.add(
                Requirement(
                    project_id=project.id,
                    feature_id=feat_id,
                    title=c.title,
                    statement=(c.statement or c.body or "").strip(),
                    scenarios=list(c.scenarios or []),
                    status="active",
                )
            )
            counts["requirement"] += 1
    return counts


def format_candidate(i: int, c: Candidate) -> str:
    extra = ""
    if c.kind == "capture":
        extra = f" kind={c.capture_kind}"
    elif c.kind == "decision" and c.why:
        extra = f" why={c.why[:60]}"
    elif c.kind == "requirement":
        stmt = (c.statement or c.body or "")[:60]
        feat = f" feature={c.feature_title}" if c.feature_title else ""
        extra = f" statement={stmt}{feat}"
    tags = f" tags={','.join(c.tags)}" if c.tags else ""
    return f"  [{i}] {c.kind}{extra}: {c.title}{tags}\n      source_ref={c.source_ref}"


def parse_approval(raw: str, n: int) -> list[int]:
    """Parse 'all', 'none', or comma/space-separated 1-based indices."""
    raw = raw.strip().lower()
    if not raw or raw in ("none", "n", "skip"):
        return []
    if raw in ("all", "a", "*"):
        return list(range(1, n + 1))
    idxs: list[int] = []
    for part in re.split(r"[\s,]+", raw):
        if not part:
            continue
        if not part.isdigit():
            raise ValueError(f"invalid selection: {part!r}")
        i = int(part)
        if i < 1 or i > n:
            raise ValueError(f"index out of range: {i}")
        idxs.append(i)
    return idxs


def run_harvest(
    session: SASession,
    project: Project,
    *,
    dry_run: bool = False,
    auto_approve: bool = False,
    since: dt.date | None = None,
    root: Path | None = None,
    extract_fn: ExtractFn | None = None,
    agent=None,
    approve_fn: Callable[[list[Candidate]], list[Candidate]] | None = None,
    default_feature_id: int | None = None,
) -> dict[str, Any]:
    """Full harvest pipeline. Returns a summary dict for the CLI."""
    root = root or project_root_from_cwd()

    cursor = project.last_harvest_at
    since_dt: dt.datetime | None = None
    if since is not None:
        since_dt = dt.datetime.combine(since, dt.time.min, tzinfo=dt.timezone.utc)
    elif cursor is not None:
        since_dt = cursor if cursor.tzinfo else cursor.replace(tzinfo=dt.timezone.utc)

    files = iter_harvest_transcripts(
        project_slug=project.slug, root=root, since=since_dt
    )
    summary: dict[str, Any] = {
        "scanned": len(files),
        "candidates": 0,
        "approved": 0,
        "committed": {"task": 0, "decision": 0, "capture": 0, "requirement": 0},
        "cursor_advanced": False,
        "skipped_reason": None,
    }

    if not files:
        print(f"taskman harvest: no new transcripts since cursor ({since_dt or 'beginning'}).")
        return summary

    print(f"taskman harvest: scanned {len(files)} transcript(s).")

    # Resolve extractor when not injected.
    if extract_fn is None and agent is None:
        if use_mock_extractor():
            extract_fn = mock_extract
            print("taskman harvest: using TASKMAN_HARVEST_MOCK stub extractor.")
        elif not has_llm_api_key():
            print(
                "taskman harvest: no API key; set OPENAI_API_KEY / ANTHROPIC_API_KEY "
                "(or TASKMAN_HARVEST_MOCK=1 for stub). Scanned files only — no extraction."
            )
            summary["skipped_reason"] = "no_api_key"
            return summary

    all_cands: list[Candidate] = []
    for path in files:
        try:
            all_cands.extend(
                extract_from_transcript(
                    path, root=root, extract_fn=extract_fn, agent=agent
                )
            )
        except Exception as e:  # noqa: BLE001 — continue other files
            print(f"taskman harvest: warning: extract failed for {path}: {e}")

    all_cands = dedupe_candidates(
        session, project, all_cands, default_feature_id=default_feature_id
    )
    summary["candidates"] = len(all_cands)

    if not all_cands:
        print("taskman harvest: no new candidates after dedupe.")
        if not dry_run:
            project.last_harvest_at = dt.datetime.now(dt.timezone.utc)
            summary["cursor_advanced"] = True
        return summary

    print(f"\n# candidates ({len(all_cands)})")
    for i, c in enumerate(all_cands, start=1):
        print(format_candidate(i, c))

    if dry_run:
        print("\ntaskman harvest: dry-run — nothing written; cursor unchanged.")
        return summary

    if approve_fn is not None:
        approved = approve_fn(all_cands)
    elif auto_approve:
        approved = list(all_cands)
    else:
        try:
            raw = input(
                "\nApprove which? (all / none / 1,2,3): "
            )
        except EOFError:
            raw = "none"
        try:
            idxs = parse_approval(raw, len(all_cands))
        except ValueError as e:
            raise SystemExit(f"taskman harvest: {e}") from e
        approved = [all_cands[i - 1] for i in idxs]

    summary["approved"] = len(approved)
    if approved:
        counts = commit_candidates(
            session, project, approved, default_feature_id=default_feature_id
        )
        summary["committed"] = counts
        print(
            f"taskman harvest: committed "
            f"tasks={counts['task']} decisions={counts['decision']} "
            f"captures={counts['capture']} requirements={counts['requirement']}"
        )
    else:
        print("taskman harvest: nothing approved.")

    project.last_harvest_at = dt.datetime.now(dt.timezone.utc)
    summary["cursor_advanced"] = True
    return summary
