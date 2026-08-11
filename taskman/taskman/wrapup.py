"""Wrap-up reconcile gate — evidence over recall.

Produces two worklists the agent must clear before /wrap-up continues:

* **unattributed** — paths changed since session start that no open ticket claims
* **stale** — every ``in_progress`` ticket requiring done / still-open / blocked
  with a citation

Exit 1 while either list remains after applying the session receipt.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select

from taskman.config import find_project
from taskman.db import Session
from taskman.models import Project, Task

MARKER_DIRNAME = ".session-markers"
RECEIPT_SUFFIX = ".receipt.json"
OPEN_STATUSES = frozenset({"backlog", "todo", "in_progress", "blocked"})
STALE_STATUS = "in_progress"
DONE_EXCLUDED = frozenset({"done", "disabled"})
DESIGN_TAG_MARKERS = frozenset(
    {
        "kind:design",
        "design",
        "spike",
        "kind:spike",
        "kind:decision",
    }
)
DESIGN_ROLES = frozenset({"explore", "ui-design"})
VERIFY_LINE_RE = re.compile(
    r"(?m)^\s*(?:[-*]\s*)?(?:`([^`]+)`|((?:\.venv/bin/)?(?:pytest|python\s+-m\s+pytest|make|ruff|mypy|npm\s+test)\b[^\n]*))"
)
IGNORE_PATH_PREFIXES = (
    ".session-markers/",
    "docs/session-reports/",
    "docs/chat-history/",
    "tmp/",
    ".git/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    "node_modules/",
    ".venv/",
)


@dataclass
class Marker:
    path: Path
    session_id: str
    start_sha: str
    worktree: Path
    branch: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class GateResult:
    unattributed: list[str]
    stale: list[dict[str, Any]]
    marker: Marker | None
    receipt_path: Path | None
    ok: bool


def find_repo_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        if (d / ".taskman.toml").is_file():
            return d
    raise FileNotFoundError("no .taskman.toml above cwd")


def _git(worktree: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(worktree), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout


def load_marker(
    *,
    worktree: Path | None = None,
    marker_path: Path | None = None,
    session_id: str | None = None,
    since: str | None = None,
) -> Marker:
    root = worktree or find_repo_root()
    if marker_path is None and os.environ.get("WRAPUP_SESSION_MARKER"):
        marker_path = Path(os.environ["WRAPUP_SESSION_MARKER"])
    if session_id is None:
        session_id = os.environ.get("WRAPUP_SESSION_ID")

    if marker_path is None and session_id:
        candidate = root / MARKER_DIRNAME / f"{session_id}.json"
        if candidate.is_file():
            marker_path = candidate

    if marker_path is None and since:
        return Marker(
            path=root / MARKER_DIRNAME / "_manual.json",
            session_id=session_id or "manual",
            start_sha=since,
            worktree=root,
            branch=_git(root, "branch", "--show-current").strip(),
            raw={"start_sha": since, "manual": True},
        )

    if marker_path is None:
        # Newest marker in this worktree (last resort — parallel sessions risk).
        marker_dir = root / MARKER_DIRNAME
        if marker_dir.is_dir():
            candidates = sorted(
                (p for p in marker_dir.glob("*.json") if not p.name.endswith(".receipt.json")),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                marker_path = candidates[0]

    if marker_path is None or not marker_path.is_file():
        raise FileNotFoundError(
            "no session marker — session-start hook did not run, "
            "or pass --since <sha> / --marker <path>"
        )

    data = json.loads(marker_path.read_text(encoding="utf-8"))
    return Marker(
        path=marker_path,
        session_id=str(data.get("session_id") or marker_path.stem),
        start_sha=str(data.get("start_sha") or ""),
        worktree=Path(str(data.get("worktree") or root)),
        branch=str(data.get("branch") or ""),
        raw=data if isinstance(data, dict) else {},
    )


def receipt_path_for(marker: Marker) -> Path:
    return marker.path.with_name(marker.path.stem + RECEIPT_SUFFIX)


def load_receipt(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {"schema": 1, "unattributed": {}, "stale": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema": 1, "unattributed": {}, "stale": {}}
    if not isinstance(data, dict):
        return {"schema": 1, "unattributed": {}, "stale": {}}
    data.setdefault("unattributed", {})
    data.setdefault("stale", {})
    return data


def save_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_path(raw: str) -> str | None:
    text = raw.strip().strip("`").strip()
    if not text or " " in text and not text.endswith("/"):
        # Prose with spaces is not a path claim (unless directory trailing slash).
        if " " in text:
            return None
    text = text.lstrip("./")
    if not text or text in {".", "*"}:
        return None
    return text


def path_ignored(path: str) -> bool:
    p = path.lstrip("./")
    return any(p == pref.rstrip("/") or p.startswith(pref) for pref in IGNORE_PATH_PREFIXES)


def path_claimed(path: str, claims: set[str]) -> bool:
    p = path.lstrip("./")
    for claim in claims:
        c = claim.lstrip("./").rstrip("/")
        if not c:
            continue
        if p == c or p.startswith(c + "/"):
            return True
        # Claimed file under a changed directory prefix is not enough to cover
        # sibling files — only exact / descendant matches count.
    return False


def changed_paths(worktree: Path, start_sha: str) -> list[str]:
    paths: set[str] = set()
    if start_sha and start_sha != "UNKNOWN":
        # Committed since session start.
        diff = _git(worktree, "diff", "--name-only", f"{start_sha}..HEAD")
        paths.update(line.strip() for line in diff.splitlines() if line.strip())
        # Unstaged + staged vs start (covers dirty tree relative to anchor).
        dirty = _git(worktree, "diff", "--name-only", start_sha)
        paths.update(line.strip() for line in dirty.splitlines() if line.strip())
    else:
        dirty = _git(worktree, "diff", "--name-only", "HEAD")
        paths.update(line.strip() for line in dirty.splitlines() if line.strip())

    untracked = _git(worktree, "ls-files", "--others", "--exclude-standard")
    paths.update(line.strip() for line in untracked.splitlines() if line.strip())

    out = sorted(p for p in paths if p and not path_ignored(p))
    return out


def claims_from_task(task: Task) -> set[str]:
    claims: set[str] = set()
    brief = task.brief if isinstance(task.brief, dict) else {}
    files = brief.get("files") if isinstance(brief.get("files"), list) else []
    for raw in files:
        norm = normalize_path(str(raw))
        if norm:
            claims.add(norm)
    return claims


def open_task_claims(project_id: int) -> dict[int, set[str]]:
    with Session() as session:
        rows = session.scalars(
            select(Task).where(
                Task.project_id == project_id,
                Task.status.in_(sorted(OPEN_STATUSES)),
            )
        ).all()
        return {t.id: claims_from_task(t) for t in rows}


def in_progress_tasks(project_id: int) -> list[Task]:
    with Session() as session:
        return list(
            session.scalars(
                select(Task)
                .where(Task.project_id == project_id, Task.status == STALE_STATUS)
                .order_by(Task.id)
            ).all()
        )


def extract_verify_command(task: Task) -> str | None:
    brief = task.brief if isinstance(task.brief, dict) else {}
    explicit = brief.get("verify")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    acceptance = brief.get("acceptance") or ""
    if not isinstance(acceptance, str):
        acceptance = str(acceptance)
    matches = VERIFY_LINE_RE.findall(acceptance)
    for a, b in matches:
        cmd = (a or b).strip()
        if cmd:
            return cmd
    return None


def is_design_ticket(task: Task) -> bool:
    tags = {str(t).lower() for t in (task.tags or [])}
    if tags & DESIGN_TAG_MARKERS:
        return True
    brief = task.brief if isinstance(task.brief, dict) else {}
    role = str(brief.get("role") or "").strip().lower()
    if role in DESIGN_ROLES and not extract_verify_command(task):
        return True
    return False


def _project_id() -> int:
    slug, _ = find_project()
    with Session() as session:
        proj = session.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise RuntimeError(f"project slug={slug!r} not registered — run taskman init-db")
        return proj.id


def unattributed_paths(worktree: Path, start_sha: str, project_id: int) -> list[str]:
    changed = [p for p in changed_paths(worktree, start_sha) if not path_ignored(p)]
    claims_by_task = open_task_claims(project_id)
    all_claims: set[str] = set()
    for claims in claims_by_task.values():
        all_claims |= claims
    return [p for p in changed if not path_claimed(p, all_claims)]


def _parse_marker_started_at(marker: Marker) -> dt.datetime | None:
    raw = marker.raw.get("started_at") if marker.raw else None
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        when = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when


def task_touched_this_session(
    task: Task,
    *,
    marker: Marker,
    changed: set[str],
    all_stale: bool = False,
) -> bool:
    """Scope stale candidates to session-touched work (not ancient board cruft).

    Full-board hygiene: pass ``all_stale=True``.
    """
    if all_stale:
        return True
    started = _parse_marker_started_at(marker)
    if task.claimed_at is not None and started is not None and task.claimed_at >= started:
        return True
    if task.updated_at is not None and started is not None and task.updated_at >= started:
        return True
    claims = claims_from_task(task)
    if claims and any(path_claimed(p, claims) for p in changed):
        return True
    return False


def stale_candidates(
    project_id: int,
    *,
    marker: Marker,
    changed: list[str] | None = None,
    all_stale: bool = False,
) -> list[dict[str, Any]]:
    changed_set = set(changed or [])
    out: list[dict[str, Any]] = []
    for task in in_progress_tasks(project_id):
        if not task_touched_this_session(
            task, marker=marker, changed=changed_set, all_stale=all_stale
        ):
            continue
        verify = extract_verify_command(task)
        design = is_design_ticket(task)
        out.append(
            {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "verify": verify,
                "needs_operator_ack": design and verify is None,
                "files": sorted(claims_from_task(task)),
            }
        )
    return out


def _receipt_clears_unattributed(path: str, receipt: dict[str, Any]) -> bool:
    entries = receipt.get("unattributed") or {}
    if not isinstance(entries, dict):
        return False
    entry = entries.get(path) or entries.get(path.lstrip("./"))
    if not isinstance(entry, dict):
        return False
    action = str(entry.get("action") or "").lower()
    task_id = entry.get("task_id")
    if action in {"attach", "attached", "opened", "open", "ignore"} and task_id:
        return True
    if action == "ignore" and entry.get("reason"):
        return True
    return False


def _receipt_clears_stale(task_id: int, item: dict[str, Any], receipt: dict[str, Any]) -> bool:
    entries = receipt.get("stale") or {}
    if not isinstance(entries, dict):
        return False
    entry = entries.get(str(task_id)) or entries.get(task_id)
    if not isinstance(entry, dict):
        return False
    verdict = str(entry.get("verdict") or "").lower().replace("_", "-")
    citation = str(entry.get("citation") or "").strip()
    if verdict not in {"done", "still-open", "stillopen", "blocked"}:
        return False
    if not citation:
        return False
    if verdict == "done":
        if item.get("needs_operator_ack") and not entry.get("operator_ack"):
            return False
        verify = item.get("verify")
        if verify and not entry.get("verify_ok"):
            return False
    return True


def apply_receipt(
    unattributed: list[str],
    stale: list[dict[str, Any]],
    receipt: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]]]:
    left_u = [p for p in unattributed if not _receipt_clears_unattributed(p, receipt)]
    left_s = [item for item in stale if not _receipt_clears_stale(item["id"], item, receipt)]
    return left_u, left_s


def run_gate(
    *,
    worktree: Path | None = None,
    marker_path: Path | None = None,
    session_id: str | None = None,
    since: str | None = None,
    receipt_path: Path | None = None,
    all_stale: bool = False,
) -> GateResult:
    root = worktree or find_repo_root()
    marker = load_marker(
        worktree=root,
        marker_path=marker_path,
        session_id=session_id,
        since=since,
    )
    if not marker.start_sha or marker.start_sha == "UNKNOWN":
        raise ValueError(f"marker {marker.path} has no usable start_sha")

    project_id = _project_id()
    changed = changed_paths(marker.worktree, marker.start_sha)
    raw_u = unattributed_paths(marker.worktree, marker.start_sha, project_id)
    raw_s = stale_candidates(
        project_id,
        marker=marker,
        changed=changed,
        all_stale=all_stale,
    )
    rpath = receipt_path or receipt_path_for(marker)
    receipt = load_receipt(rpath)
    left_u, left_s = apply_receipt(raw_u, raw_s, receipt)
    return GateResult(
        unattributed=left_u,
        stale=left_s,
        marker=marker,
        receipt_path=rpath,
        ok=not left_u and not left_s,
    )


def format_gate_report(result: GateResult) -> str:
    lines: list[str] = []
    marker = result.marker
    if marker:
        lines.append(
            f"marker: {marker.path}  session={marker.session_id}  "
            f"start_sha={marker.start_sha[:12]}  branch={marker.branch or '-'}"
        )
    if result.receipt_path:
        lines.append(f"receipt: {result.receipt_path}")
    lines.append("")
    lines.append(f"## Unattributed ({len(result.unattributed)})")
    if result.unattributed:
        for p in result.unattributed:
            lines.append(f"- {p}")
        lines.append(
            "Clear: taskman wrapup record --attach <path> --task <id> "
            "| --opened <path> --task <id> | --ignore <path> --reason '...'"
        )
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append(f"## Stale in_progress ({len(result.stale)})")
    if result.stale:
        for item in result.stale:
            flags = []
            if item.get("verify"):
                flags.append(f"verify={item['verify']!r}")
            if item.get("needs_operator_ack"):
                flags.append("needs_operator_ack")
            flag_s = f"  [{', '.join(flags)}]" if flags else ""
            lines.append(f"- #{item['id']} {item['title']}{flag_s}")
        lines.append(
            "Clear: taskman wrapup record --stale <id> --verdict done|still-open|blocked "
            "--citation '…' [--verify-ok] [--operator-ack]"
        )
    else:
        lines.append("- (none)")
    lines.append("")
    if result.ok:
        lines.append("wrapup gate: OK")
    else:
        lines.append("wrapup gate: BLOCKED — clear both lists, then re-run")
    return "\n".join(lines)
