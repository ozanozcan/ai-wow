#!/usr/bin/env python3
"""Regression tests for hooks/stamp-tracker.py span stamping.

Plain `python3 hooks/tests/test_stamp_tracker.py` — no pytest, because the
interpreter these hooks actually run under has no third-party packages.

The bug these pin down: a *backgrounded* subagent's PostToolUse fires when the
launch returns, not when the agent finishes. Stamping `ended` there reported
every AFK lane as finishing seconds after it started, which froze the board's
clock and made a live run look dead.
"""

import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stamp-tracker.py")

BRIEF = "01-thing.md"
FAILURES = []


def board(agent_name="tdd-builder"):
    return {
        "schema": 1, "stem": "teststem", "run_status": "running",
        "updated": "2026-01-01T00:00:00Z",
        "waves": [{
            "wave": 1, "status": "running",
            "lanes": [{
                "lane": "A", "brief": BRIEF, "status": "running",
                "agents": [{"name": agent_name, "status": "running"}],
            }],
        }],
    }


def run_hook(cwd, event, tool_input, tool_name="Agent"):
    payload = {
        "cwd": cwd, "tool_name": tool_name, "hook_event_name": event,
        "tool_input": tool_input, "tool_response": {},
    }
    subprocess.run(
        [sys.executable, HOOK], input=json.dumps(payload),
        text=True, capture_output=True, check=False,
    )


def spawn_and_return(tmp, tool_input, tool_name="Agent"):
    """Drive one full Pre → Post cycle and hand back the agent entry."""
    dispatch = os.path.join(tmp, "docs", "plans", "teststem", "dispatch")
    os.makedirs(dispatch, exist_ok=True)
    path = os.path.join(dispatch, "tracker.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(board(), fh)
    run_hook(tmp, "PreToolUse", tool_input, tool_name)
    run_hook(tmp, "PostToolUse", tool_input, tool_name)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data["waves"][0]["lanes"][0]["agents"][0]


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f" — {detail}" if not cond and detail else ""))
    if not cond:
        FAILURES.append(name)


def main():
    prompt = f"Read your brief docs/plans/teststem/dispatch/{BRIEF} and go."
    print("stamp-tracker span stamping")

    # 1. Explicitly backgrounded: the Post event is the *launch* returning.
    with tempfile.TemporaryDirectory() as tmp:
        agent = spawn_and_return(tmp, {
            "subagent_type": "tdd-builder", "description": "lane A",
            "prompt": prompt, "run_in_background": True,
        })
        check("backgrounded agent gets started", bool(agent.get("started")))
        check("backgrounded agent does NOT get ended", not agent.get("ended"),
              f"ended={agent.get('ended')!r} — launch return mistaken for completion")

    # 2. The Agent tool backgrounds by DEFAULT, so an absent key is still async.
    with tempfile.TemporaryDirectory() as tmp:
        agent = spawn_and_return(tmp, {
            "subagent_type": "tdd-builder", "description": "lane A", "prompt": prompt,
        })
        check("Agent with no run_in_background key gets started", bool(agent.get("started")))
        check("Agent with no run_in_background key does NOT get ended", not agent.get("ended"),
              f"ended={agent.get('ended')!r} — background is the Agent tool's default")

    # 3. Explicitly synchronous: the Post event really is completion — stamp both.
    with tempfile.TemporaryDirectory() as tmp:
        agent = spawn_and_return(tmp, {
            "subagent_type": "tdd-builder", "description": "lane A",
            "prompt": prompt, "run_in_background": False,
        })
        check("synchronous agent gets started", bool(agent.get("started")))
        check("synchronous agent gets ended", bool(agent.get("ended")),
              "a foreground agent's return IS its completion")

    # 4. Cursor's `Task` has no background default — absent key means synchronous.
    with tempfile.TemporaryDirectory() as tmp:
        agent = spawn_and_return(tmp, {
            "subagent_type": "tdd-builder", "description": "lane A", "prompt": prompt,
        }, tool_name="Task")
        check("Task with no key gets ended", bool(agent.get("ended")),
              "Task is synchronous unless it opts into background")

    print(f"\n{len(FAILURES)} failure(s)" + (": " + ", ".join(FAILURES) if FAILURES else ""))
    return 1 if FAILURES else 0


sys.exit(main())
