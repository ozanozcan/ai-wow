#!/usr/bin/env python3
"""SessionStart hook: say so, up front, when another session shares this checkout.

Runs after session-start-marker.py has written this session's marker. Prints
plain text, which Claude Code appends as session context. Silent when this is
the only session here — no noise in the common case.

Emits an actionable offer, not just a warning: the agent is told to ask the
user whether to relocate, and given the exact call. Offer, never act — moving
a session's working directory without being asked is its own surprise.

Fails open: a crash must never block session creation.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PEER_LIVE_SECONDS = 15 * 60

# Claude Code replaces an over-long hook output with a short stub, silently, while
# the hook still reports success — so an oversized notice is worse than a trimmed
# one. The ceiling is undocumented; one measurement puts it near 10,000 chars
# (thedotmack/claude-mem#3802). Budget under that and leave headroom.
CONTEXT_BUDGET = 8000

# Peers are unbounded, and their branches are interpolated into the notice three
# times. Cap the list at the build step rather than truncating the finished text.
BRANCH_CAP = 5


def _fmt_branches(branches: list[str]) -> str:
    if len(branches) <= BRANCH_CAP:
        return ", ".join(branches)
    return ", ".join(branches[:BRANCH_CAP]) + f", +{len(branches) - BRANCH_CAP} more"


def _fit(blocks: list[tuple[int, str]], budget: int) -> str:
    """Join blocks, dropping the most-droppable first until the text fits.

    Blocks are (drop_rank, text); rank 0 never drops. Selection, not truncation:
    a cut notice still ends on a whole sentence.
    """
    keep = list(blocks)
    while True:
        text = "\n".join(t for _, t in keep)
        if len(text) <= budget:
            return text
        worst = max((r for r, _ in keep), default=0)
        if worst == 0:
            return text          # only required blocks left; send them oversized
        keep = [(r, t) for r, t in keep if r != worst]


def _parse(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _suggested_name(worktree: str, branch: str | None) -> str:
    """A worktree name that says which session it belongs to."""
    base = (branch or "session").split("/")[-1]
    base = re.sub(r"[^A-Za-z0-9._-]", "-", base).strip("-") or "session"
    return f"peer-{base}"[:64]


def _derive() -> tuple[str | None, str | None]:
    """Recompute what session-start-marker.py exports, from our own stdin payload.

    That hook exports WRAPUP_* by appending to CLAUDE_ENV_FILE, which the runtime
    does not source until the SessionStart event is over — so a sibling hook in
    the *same* event sees none of it, and this one would silently no-op forever.
    Mirrors session-start-marker.py's conventions: worktree = git toplevel of cwd,
    marker = <worktree>/.session-markers/<session_id>.json, session id taken from
    the first of its four accepted payload keys. Keep the two in step.
    """
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}
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
    marker_path = os.environ.get("WRAPUP_SESSION_MARKER")
    worktree = os.environ.get("WRAPUP_WORKTREE")
    if not marker_path or not worktree:
        marker_path, worktree = _derive()
    if not marker_path or not worktree:
        return 0
    marker = Path(marker_path)
    now = datetime.now(timezone.utc)

    mine = {}
    try:
        mine = json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        pass

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
        if seen and (now - seen).total_seconds() <= PEER_LIVE_SECONDS:
            peers.append(data)

    if not peers:
        return 0

    branches = sorted({p.get("branch") or "?" for p in peers})
    branch_str = _fmt_branches(branches)
    name = _suggested_name(worktree, mine.get("branch"))

    freshest = min(
        (now - (_parse(p.get("updated_at")) or _parse(p.get("started_at")))).total_seconds()
        for p in peers
    ) / 60
    # Ranked for the budget pass: 0 never drops, higher ranks go first.
    blocks: list[tuple[int, str]] = [
        (0,
         f"PEER SESSION: {len(peers)} other session(s) touched this checkout recently\n"
         f"({worktree}), on {branch_str}; most recent activity {freshest:.0f}m ago.\n"
         "A marker records the last command a session ran, so this may mean idle or closed\n"
         "rather than present — if it matters, sample it twice and see whether it advances."),
        (0,
         "\nA git checkout has one HEAD and one index, so branch switches and staging are\n"
         "global. Concurrent work here is not safe, only careful."),
        (0,
         "\nACTION REQUIRED — before doing any git work, offer the user a worktree of your\n"
         "own, and wait for their answer. Do not relocate unasked."),
        (2,
         "Suggested wording:\n"
         "\n"
         f"  \"Another session has been working in this checkout (on {branch_str}),\n"
         "   last active a few minutes ago. Want me to\n"
         "   work in my own worktree instead? It's isolated — separate HEAD and index — so\n"
         "   neither of us can disturb the other.\""),
        (0,
         "\nIf they accept, this project authorises the worktree tool for exactly this case\n"
         "(see ~/.claude/CLAUDE.md, 'Shared checkouts'):\n"
         f"  EnterWorktree(name: \"{name}\")"),
        (1,
         "Note its base ref comes from the `worktree.baseRef` setting — `fresh` (the default)\n"
         "branches from origin/<default-branch>, `head` from current local HEAD. If your work\n"
         "builds on uncommitted or unpushed state, say so rather than silently starting from\n"
         "a different base."),
        (0,
         "\nIf they decline and you stay in the shared checkout:\n"
         "  - `git commit -- <paths>` — never touches the index, so it cannot pick up their\n"
         "    staged work. Prefer it over `git add` + `git commit`.\n"
         "  - always give `git add` explicit paths; never `-A` or `.`\n"
         "  - never switch branches; if you must, switch back\n"
         "  - never `git stash` / `reset --hard` / `clean -fd` — they hit the whole tree\n"
         "A PreToolUse hook will ask before those commands while the peer stays live."),
    ]
    print(_fit(blocks, CONTEXT_BUDGET))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
