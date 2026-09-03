#!/usr/bin/env python3
"""PreToolUse(Bash) hook: keep two sessions from colliding in one checkout.

A git checkout has ONE HEAD and ONE index. When two sessions share one, a
branch switch or a bare `git add` in either reaches into the other's work —
silently, and after the fact. This hook does two things on every Bash call:

  1. Heartbeats this session's own marker, so "is a peer live?" is answerable.
     The marker writer sets `updated_at` once at startup and never again, which
     makes a nine-hour-dead session look identical to a live one.
  2. Asks before the commands that mutate *global* checkout state, but only
     while another session is actually live in this same worktree.

Scoped deliberately narrow: file edits, tests, and path-limited git are never
gated. Only the operations whose blast radius is the whole checkout.

Fails open — a crash here must never block a session.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PEER_LIVE_SECONDS = 15 * 60      # a marker older than this is treated as dead
HEARTBEAT_SECONDS = 60           # throttle marker writes

# Commands whose effect is the whole checkout, not one path.
GLOBAL_STATE = [
    (r"\bgit\s+(checkout|switch)\b", "switches the branch for every session in this checkout"),
    (r"\bgit\s+reset\b", "moves HEAD and can unstage another session's staged work"),
    (r"\bgit\s+stash\b", "stashes the whole tree, including files another session is editing"),
    (r"\bgit\s+clean\b", "deletes untracked files, including another session's new files"),
    (r"\bgit\s+(rebase|merge)\b", "rewrites or moves HEAD under the other session"),
    (r"\bgit\s+branch\s+(-f|-D|--force|--delete)", "moves or deletes a branch ref another session may be on"),
    (r"\bgit\s+add\s+(-A\b|--all\b|\.(\s|$))", "stages everything, including another session's changes"),
    # `-a` also hides inside short-flag clusters (`-am`, `-va`); `--amend` must not
    # match, hence the single-dash requirement.
    (r"\bgit\s+commit\b[^|;&]*?(\s-[a-zA-Z]*a[a-zA-Z]*|\s--all\b)",
     "commits every modified file, including another session's"),
    # ai-sync's manual mode commits every dirty *managed* path (agents, commands,
    # global/CLAUDE.md, hooks, rules, skills) — which is exactly what a peer
    # editing this harness is dirtying. Anchored to a command segment so that
    # reading the file (`grep ... bin/ai-sync`) is not gated; --from-hook never
    # commits, and status/check-managed are read-only, so neither is gated.
    (r"(?:^|[;&|]|&&|\|\|)\s*(?:[\w./~-]*python3?\s+)?[\w./~-]*\bai-sync\b"
     r"(?![^|;&]*(?:--from-hook|--commit-anyway|\bstatus\b|\bcheck-managed\b))",
     "commits every dirty managed path, including another session's in-progress work"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _heartbeat(marker: Path) -> None:
    """Touch our own marker so peers can tell we are alive."""
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        last = _parse(data.get("updated_at"))
        if last and (_now() - last).total_seconds() < HEARTBEAT_SECONDS:
            return
        data["updated_at"] = _now().strftime("%Y-%m-%dT%H:%M:%SZ")
        marker.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def live_peers(marker: Path, worktree: str) -> list[dict]:
    """Other sessions whose marker names this worktree and is still warm."""
    peers = []
    for path in marker.parent.glob("*.json"):
        if path == marker:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("worktree") != worktree:
            continue
        seen = _parse(data.get("updated_at")) or _parse(data.get("started_at"))
        if seen and (_now() - seen).total_seconds() <= PEER_LIVE_SECONDS:
            peers.append(data)
    return peers


def _derive(payload: dict) -> tuple[str | None, str | None]:
    """Recompute what session-start-marker.py exports, from our own payload.

    That hook exports WRAPUP_* by appending to CLAUDE_ENV_FILE, and those never
    reach this hook's environment — so the env lookup below returned None on
    every call and this guard silently did nothing at all: no heartbeat, so every
    marker aged out at 15 minutes, and no gating, so the commands it exists to
    catch went through unasked. peer-session-notice.py already derives its own;
    this mirrors it. Keep the two in step.
    """
    cwd = str(payload.get("cwd") or os.getcwd())
    try:
        top = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True,
                             encoding="utf-8", timeout=5).stdout.strip()
    except Exception:
        return None, None
    if not top:
        return None, None
    sid = ""
    for key in ("session_id", "conversation_id", "sessionId", "conversationId"):
        if payload.get(key):
            sid = str(payload[key])
            break
    if not sid:
        return None, None
    return str(Path(top) / ".session-markers" / f"{sid}.json"), top


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        return 0

    marker_path = os.environ.get("WRAPUP_SESSION_MARKER")
    worktree = os.environ.get("WRAPUP_WORKTREE")
    if not marker_path or not worktree:
        marker_path, worktree = _derive(payload)
    if not marker_path or not worktree:
        return 0
    marker = Path(marker_path)

    _heartbeat(marker)

    reason = next((why for pattern, why in GLOBAL_STATE
                   if re.search(pattern, command)), None)
    if not reason:
        return 0

    peers = live_peers(marker, worktree)
    if not peers:
        return 0

    branches = sorted({p.get("branch") or "?" for p in peers})
    # Age, not presence: a marker records the last command a session ran, so an idle
    # window and a closed one are indistinguishable from one reading (L28).
    freshest = min(
        (_now() - (_parse(p.get("updated_at")) or _parse(p.get("started_at")))).total_seconds()
        for p in peers
    ) / 60
    note = (
        f"{len(peers)} other session(s) touched this checkout recently "
        f"({worktree}), on {', '.join(branches)}; most recent activity "
        f"{freshest:.0f}m ago — that may mean idle or closed, not present.\n"
        f"This command {reason}.\n"
        "A checkout has one HEAD and one index — this reaches into their work.\n"
        "Prefer: `git commit -- <paths>` (ignores the index entirely), explicit "
        "paths for `git add`, or `git worktree add` to get your own checkout."
    )
    # stdout + exit 0 is the reply channel this repo has verified live for
    # PreToolUse (see guard-destructive.sh and hooks.def.json's copilot caveat).
    # stderr + exit 2 is the *block* channel: it would deny the command outright
    # and surface this JSON to the model as raw text, which is neither the "ask"
    # this asks for nor readable. Never exercised before now — these hooks were
    # registered nowhere until 2026-08-29.
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": note,
        },
        "systemMessage": note,
    }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail open, always
