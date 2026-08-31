#!/usr/bin/env python3
"""PostToolUse hook — keep a mow tracker.json's timing fields honest.

Two jobs, both mechanical, both previously left to the orchestrator's memory:

1. `updated` — TRACKER.md's contract says every write to `dispatch/tracker.json`
   also bumps it. A live run was observed rewriting the file every few
   seconds while the field sat 19 minutes stale, which made the board's
   staleness indicator call a healthy run behind.

2. Per-agent `started` / `ended` — the board draws `duration · tokens` beside
   every subagent name, but a whole run shipped with 8 of 8 agents unstamped, so
   the column was blank everywhere. A *foreground* subagent's wall-clock bounds
   are exactly the bounds of its tool call, so take them from the tool call.

Job 2 runs in two halves because a spawn and its return are two separate hook
events. PreToolUse records the start in a disposable ledger beside the board
(`dispatch/.agent-times.json`); PostToolUse pairs the return with it and merges
the span into the matching agent. A span that has no agent entry to land on yet
— the orchestrator appends agents on its own schedule — stays in the ledger and
is retried on every later tracker write, so the merge does not depend on the two
happening in any particular order.

**A backgrounded subagent only ever gets `started` from this hook.** Its
PostToolUse fires when the *launch* returns, not when the agent finishes, so the
return carries no information about completion. Stamping `ended` there reported
every AFK lane as finishing seconds after it started: the board froze that lane's
clock at ~20s and a live multi-minute run read as dead. The real `ended` comes
from the orchestrator when the lane's report lands, which TRACKER.md already
requires of it. Background is the `Agent` tool's *default*, so an absent
`run_in_background` key is async there; Cursor's `Task` is synchronous unless it
opts in.

Matching a Task call to a board entry is the one heuristic part, and unlike the
`updated` stamp it can be wrong: it prefers the lane whose `brief` path appears
in the Task prompt, and falls back to the first unstamped agent whose name
starts with the `subagent_type`. It only ever fills a field that is empty, so a
value the orchestrator wrote by hand always wins.

Deliberately narrow throughout: only a file literally named tracker.json, inside
a `dispatch/` directory, whose JSON is an object carrying `waves`. Never raises
and never blocks the tool — a tracker is disposable run state and must never
fail a run.
"""

import datetime
import glob
import hashlib
import json
import os
import sys

LEDGER = ".agent-times.json"
ACTIVITY = ".activity"
SAMPLE_EVERY = 30           # seconds between activity samples — cheap, still dense

# The subagent tool is `Agent` here and `Task` in other runtimes/versions. Guarding
# on one name meant the span stamping never fired at all; accept both.
AGENT_TOOLS = ("Agent", "Task")


def _now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None                 # mid-write, malformed or absent — leave it be


def _write_json(path, data) -> None:
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
    except Exception:
        return


def _is_board(data) -> bool:
    return isinstance(data, dict) and "waves" in data


def _agents(data):
    """Every agent dict on the board, in wave → lane → call order."""
    for wave in data.get("waves") or []:
        for lane in (wave or {}).get("lanes") or []:
            for agent in (lane or {}).get("agents") or []:
                if isinstance(agent, dict):
                    yield lane, agent


# ---------------------------------------------------------------- job 1: updated

def stamp_updated(path, data) -> bool:
    stamp = _now()
    if data.get("updated") == stamp:
        return False                # already current to the second
    data["updated"] = stamp
    return True


# ------------------------------------------------------------- job 2: agent spans

def _task_key(tool_input) -> str:
    """Pairs a PreToolUse with its PostToolUse: same call, same tool_input."""
    raw = "\x1f".join(
        str(tool_input.get(k) or "") for k in ("subagent_type", "description", "prompt")
    )
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:16]


def _returns_at_launch(tool_name, tool_input) -> bool:
    """True when this spawn's PostToolUse is the launch, not the completion.

    `Agent` backgrounds by default — an omitted key is still async — while
    Cursor's `Task` runs in the foreground unless it opts in. Either way an
    explicit value wins.
    """
    flag = tool_input.get("run_in_background")
    if flag is None:
        return str(tool_name or "") == "Agent"
    return bool(flag)


def _find_board(cwd, prompt):
    """The running mow board this Task most likely belongs to, or None.

    No tracker in flight is the common case — the hook stays inert for every
    Task call outside a `/mow go`.
    """
    roots = []
    for pattern in ("docs/plans/*/dispatch/tracker.json", "dispatch/tracker.json"):
        roots.extend(glob.glob(os.path.join(cwd or ".", pattern)))
    live = []
    for path in roots:
        data = _read_json(path)
        if _is_board(data) and data.get("run_status") == "running":
            try:
                live.append((os.path.getmtime(path), path))
            except OSError:
                continue
    if not live:
        return None
    live.sort()

    # More than one run can be `running` at once — mow allows parallel go on
    # disjoint files, and separate chats each have their own board. "Most
    # recently written" then attributes a spawn to whichever board some *other*
    # session happened to touch last: a kill-calls-review-queue run collected an
    # llm-sec-review span it never spawned (flag-football-usable's), and lost
    # three backend-reviewers of its own. A misattributed span is worse than no
    # span, because it is indistinguishable from a real one.
    #
    # So the prompt has to name the run. A mow lane prompt carries its brief
    # path, and TRACKER.md has the orchestrator name the stem in gate prompts —
    # both contain the stem. No name, no stamp.
    if len(live) > 1:
        named = [path for _mtime, path in live if _prompt_names_run(path, prompt)]
        if not named:
            return None             # cannot attribute — better blank than wrong
        return named[-1]
    only = live[-1][1]
    return only if _prompt_names_run(only, prompt) else None


def _stem_of(board_path) -> str:
    """`docs/plans/<stem>/dispatch/tracker.json` -> `<stem>`."""
    dispatch = os.path.dirname(board_path)
    return os.path.basename(os.path.dirname(dispatch))


def _prompt_names_run(board_path, prompt) -> bool:
    """Does this spawn's prompt actually reference the run that owns the board?

    Two signals, either sufficient: the dispatch directory itself (a lane prompt
    points at its brief and hydrated-specs), or the stem name (a gate or P3
    prompt names the run it is gating). Both are cheap substring checks.
    """
    if not prompt:
        return False
    dispatch = os.path.dirname(board_path).replace("\\", "/")
    tail = "/".join(dispatch.split("/")[-3:])   # docs/plans/<stem>/dispatch
    stem = _stem_of(board_path)
    return bool(stem) and (tail in prompt.replace("\\", "/") or stem in prompt)


def _lane_hint(data, prompt):
    """The lane whose brief this Task prompt names — the strong match."""
    if not prompt:
        return None
    for lane, _agent in _agents(data):
        brief = str((lane or {}).get("brief") or "")
        if brief and brief in prompt:
            return str(lane.get("lane") or "")
    return None


def _name_matches(name, want) -> bool:
    name, want = str(name or "").strip().lower(), str(want or "").strip().lower()
    return bool(want) and (name == want or name.startswith(want))


def apply_span(data, span) -> bool:
    """Fill one recorded span into the first agent entry that still wants it."""
    want, lane_hint = span.get("agent"), span.get("lane")
    for pass_lane_hint in (True, False):
        if pass_lane_hint and not lane_hint:
            continue
        for lane, agent in _agents(data):
            if pass_lane_hint and str((lane or {}).get("lane") or "") != lane_hint:
                continue
            if not _name_matches(agent.get("name"), want):
                continue
            if agent.get("started") and agent.get("ended"):
                continue            # already stamped — never overwrite
            filled = False
            for field in ("started", "ended"):
                if span.get(field) and not agent.get(field):
                    agent[field] = span[field]
                    filled = True
            if filled:
                return True
    return False


def drain(board_path, data) -> bool:
    """Merge every span the ledger is still holding. Returns True if the board moved."""
    ledger_path = os.path.join(os.path.dirname(board_path), LEDGER)
    ledger = _read_json(ledger_path)
    if not isinstance(ledger, dict):
        return False
    spans = [s for s in ledger.get("spans") or [] if isinstance(s, dict)]
    if not spans:
        return False
    left = [span for span in spans if not apply_span(data, span)]
    if len(left) != len(spans):
        ledger["spans"] = left
        _write_json(ledger_path, ledger)
        return True
    return False


def on_task(payload, event) -> None:
    tool_input = payload.get("tool_input") or {}
    subagent = str(tool_input.get("subagent_type") or "").strip()
    if not subagent:
        return                      # not a subagent spawn we can name

    prompt = str(tool_input.get("prompt") or "")
    board_path = _find_board(payload.get("cwd") or os.getcwd(), prompt)
    if not board_path:
        return                      # no live board this spawn can be tied to

    ledger_path = os.path.join(os.path.dirname(board_path), LEDGER)
    ledger = _read_json(ledger_path)
    if not isinstance(ledger, dict):
        ledger = {}
    open_calls = ledger.get("open") if isinstance(ledger.get("open"), dict) else {}
    spans = [s for s in ledger.get("spans") or [] if isinstance(s, dict)]
    key = _task_key(tool_input)

    if event == "PreToolUse":
        open_calls[key] = _now()
        ledger["open"], ledger["spans"] = open_calls, spans
        _write_json(ledger_path, ledger)
        # Retry spans the board could not accept yet. The orchestrator appends
        # its agent entries *after* spawning, so a span recorded at launch has
        # nowhere to land at that moment; and a board written by a shell
        # heredoc rather than Write/Edit never fires the file-write drain at
        # all. Draining on each new spawn is the one hook event guaranteed to
        # recur while a wave is in flight.
        board = _read_json(board_path)
        if _is_board(board) and drain(board_path, board):
            stamp_updated(board_path, board)
            _write_json(board_path, board)
        return

    data = _read_json(board_path)
    if not _is_board(data):
        return
    # A backgrounded spawn returns at launch, so this event says nothing about
    # when the agent finished — record the start and leave `ended` to the
    # orchestrator, which writes it when the lane's report lands.
    spans.append({
        "agent": subagent,
        "lane": _lane_hint(data, prompt),
        "started": open_calls.pop(key, None),
        "ended": None if _returns_at_launch(payload.get("tool_name"), tool_input) else _now(),
    })
    ledger["open"], ledger["spans"] = open_calls, spans
    _write_json(ledger_path, ledger)

    if drain(board_path, data):
        stamp_updated(board_path, data)
        _write_json(board_path, data)


# ------------------------------------------------------------------------ routing

def on_file_write(payload) -> None:
    tool_input = payload.get("tool_input") or {}
    tool_response = payload.get("tool_response") or {}
    path = (
        tool_response.get("filePath")            # Claude PostToolUse
        or tool_input.get("file_path")
        or payload.get("file_path")              # Cursor afterFileEdit
        or ""
    )
    if not path or os.path.basename(path) != "tracker.json":
        return
    if "dispatch" not in path.replace("\\", "/").split("/"):
        return

    data = _read_json(path)
    if not _is_board(data):
        return                      # not a mow board

    moved = drain(path, data)
    if stamp_updated(path, data) or moved:
        _write_json(path, data)


# ---------------------------------------------------------------- activity trail
#
# A Task's wall clock is not work: a background agent left open while the operator
# sleeps reports twelve hours, which is the number active time set out to kill. The
# only honest evidence of work is tool calls, and a subagent's tool calls fire this
# same hook under the parent's session id (verified) — so sampling every call gives
# a trail that is dense exactly while something is running and empty while nobody
# is. The page intersects agent spans with it, so an overnight gap inside one span
# stops counting.
#
# Kept cheap because this now runs on every tool call in every session: a glob, and
# for 29 seconds out of 30 a single stat that returns immediately.

def _live_dispatch(cwd):
    """Newest dispatch dir holding a board, or None. Glob only — no reads."""
    hits = glob.glob(os.path.join(cwd or ".", "docs/plans/*/dispatch/tracker.json"))
    hits += glob.glob(os.path.join(cwd or ".", "dispatch/tracker.json"))
    if not hits:
        return None
    try:
        return os.path.dirname(max(hits, key=os.path.getmtime))
    except OSError:
        return None


def note_activity(cwd) -> None:
    dispatch = _live_dispatch(cwd)
    if not dispatch:
        return
    trail = os.path.join(dispatch, ACTIVITY)
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    try:
        if now - os.path.getmtime(trail) < SAMPLE_EVERY:
            return              # already sampled this window — the cheap path
    except OSError:
        board = _read_json(os.path.join(dispatch, "tracker.json"))
        if not _is_board(board) or board.get("run_status") != "running":
            return              # no trail for a finished run's leftover folder
    try:
        with open(trail, "a", encoding="utf-8") as fh:
            fh.write(f"{int(now)}\n")
    except Exception:
        return


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    note_activity(payload.get("cwd") or os.getcwd())
    if payload.get("tool_name") in AGENT_TOOLS:
        on_task(payload, payload.get("hook_event_name") or "PostToolUse")
    else:
        on_file_write(payload)


main()
