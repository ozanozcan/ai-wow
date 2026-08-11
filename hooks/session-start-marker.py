#!/usr/bin/env python3
"""Session-open hook: write a worktree-scoped start marker for /wrap-up.

Works for Claude Code (SessionStart) and Cursor (sessionStart). Reads optional
JSON on stdin; never blocks session creation.

Marker path: <worktree>/.session-markers/<session_id>.json
Env exported for the rest of the session:
  WRAPUP_SESSION_ID, WRAPUP_SESSION_MARKER, WRAPUP_START_SHA, WRAPUP_WORKTREE
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
MARKER_DIRNAME = ".session-markers"


def _git(cwd: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _worktree_root(cwd: Path) -> Path:
    top = _git(cwd, "rev-parse", "--show-toplevel")
    return Path(top) if top else cwd.resolve()


def _read_stdin_json() -> dict:
    try:
        raw = sys.stdin.read()
    except OSError:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _session_id(payload: dict, worktree: Path) -> str:
    for key in ("session_id", "conversation_id", "sessionId", "conversationId"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    # Stable-enough fallback when the host omits an id (rare).
    digest = hashlib.sha1(  # noqa: S324 — non-crypto id only
        f"{worktree}:{os.getpid()}:{datetime.now(timezone.utc).isoformat()}".encode()
    ).hexdigest()[:12]
    return f"local-{digest}"


def _runtime(payload: dict) -> str:
    name = str(payload.get("hook_event_name") or payload.get("hookEventName") or "")
    if name == "SessionStart":
        return "claude"
    if name == "sessionStart":
        return "cursor"
    if os.environ.get("CLAUDE_ENV_FILE"):
        return "claude"
    return "cursor"


def write_marker(
    *,
    worktree: Path,
    session_id: str,
    runtime: str,
    source: str | None = None,
) -> Path:
    """Write marker. Preserve start_sha on resume for the same session_id."""
    marker_dir = worktree / MARKER_DIRNAME
    marker_dir.mkdir(parents=True, exist_ok=True)
    # Keep directory local-only even if .gitignore is missing.
    (marker_dir / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")

    path = marker_dir / f"{session_id}.json"
    start_sha = _git(worktree, "rev-parse", "HEAD") or "UNKNOWN"
    branch = _git(worktree, "branch", "--show-current") or ""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if path.is_file() and source in {"resume", "compact"}:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if isinstance(existing, dict) and existing.get("start_sha"):
            start_sha = str(existing["start_sha"])
            # Keep original started_at when resuming.
            started_at = str(existing.get("started_at") or now)
        else:
            started_at = now
    else:
        started_at = now

    payload = {
        "schema": SCHEMA,
        "session_id": session_id,
        "started_at": started_at,
        "updated_at": now,
        "start_sha": start_sha,
        "branch": branch,
        "worktree": str(worktree),
        "runtime": runtime,
        "source": source,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _export_env(marker_path: Path, session_id: str, start_sha: str, worktree: Path) -> dict[str, str]:
    return {
        "WRAPUP_SESSION_ID": session_id,
        "WRAPUP_SESSION_MARKER": str(marker_path),
        "WRAPUP_START_SHA": start_sha,
        "WRAPUP_WORKTREE": str(worktree),
    }


def _write_claude_env(env: dict[str, str]) -> None:
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if not env_file:
        return
    try:
        with open(env_file, "a", encoding="utf-8") as fh:
            for key, val in env.items():
                fh.write(f"export {key}={json.dumps(val)}\n")
    except OSError:
        pass


def main() -> int:
    payload = _read_stdin_json()
    cwd = Path(str(payload.get("cwd") or os.getcwd())).resolve()
    roots = payload.get("workspace_roots")
    if isinstance(roots, list) and roots:
        cwd = Path(str(roots[0])).resolve()

    worktree = _worktree_root(cwd)
    # Only mark taskman-backed projects (web-app / demo / others with .taskman.toml).
    if not (worktree / ".taskman.toml").is_file():
        return 0

    session_id = _session_id(payload, worktree)
    runtime = _runtime(payload)
    source = payload.get("source")
    source_s = str(source) if source else None

    marker_path = write_marker(
        worktree=worktree,
        session_id=session_id,
        runtime=runtime,
        source=source_s,
    )
    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
        start_sha = str(data.get("start_sha") or "")
    except (OSError, json.JSONDecodeError):
        start_sha = ""

    env = _export_env(marker_path, session_id, start_sha, worktree)
    _write_claude_env(env)

    ctx = (
        f"Session marker written at {marker_path} "
        f"(start_sha={start_sha[:12] or 'unknown'}). "
        f"/wrap-up must run: python scripts/wrapup_reconcile.py"
    )

    if runtime == "claude":
        # Claude SessionStart: stdout context + optional hookSpecificOutput.
        out = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": ctx,
            }
        }
        print(json.dumps(out))
    else:
        # Cursor sessionStart: env is the reliable channel; context is best-effort.
        print(json.dumps({"env": env, "additional_context": ctx}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
