#!/usr/bin/env python3
"""Regression tests for hooks/stamp-tracker.py span stamping.

Plain `python3 hooks/tests/test_stamp_tracker.py` — no pytest, because the
interpreter these hooks actually run under has no third-party packages.

The bug these pin down: a *backgrounded* subagent's PostToolUse fires when the
launch returns, not when the agent finishes. Stamping `ended` there reported
every AFK lane as finishing seconds after it started, which froze the board's
clock and made a live run look dead.
"""

import datetime
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


SWEEP_SENTINEL = ".last-sweep"


def write_marker(marker_dir, sid, age_hours):
    """A session marker aged `age_hours` into the past."""
    stamp = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(hours=age_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    path = os.path.join(marker_dir, f"{sid}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"schema": 1, "session_id": sid, "started_at": stamp,
                   "updated_at": stamp, "start_sha": "0" * 40, "branch": "master",
                   "worktree": os.path.dirname(marker_dir), "runtime": "claude",
                   "source": None}, fh)
    return path


def run_hook_with_marker(cwd, marker):
    """PostToolUse, with the session marker exported the way the real hook sees it."""
    env = dict(os.environ)
    env["WRAPUP_SESSION_MARKER"] = marker
    payload = {"cwd": cwd, "tool_name": "Edit", "hook_event_name": "PostToolUse",
               "tool_input": {}, "tool_response": {}}
    subprocess.run([sys.executable, HOOK], input=json.dumps(payload), text=True,
                   capture_output=True, check=False, env=env)


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


ACTIVITY = ".activity"


def write_board(tmp, stem, run_status):
    """A dispatch dir holding a board in `run_status`. Returns the dispatch dir."""
    dispatch = os.path.join(tmp, "docs", "plans", stem, "dispatch")
    os.makedirs(dispatch, exist_ok=True)
    data = board()
    data["stem"] = stem
    data["run_status"] = run_status
    with open(os.path.join(dispatch, "tracker.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return dispatch


def seed_trail(dispatch, age_seconds=600):
    """An existing trail, backdated past the sample window."""
    trail = os.path.join(dispatch, ACTIVITY)
    with open(trail, "w", encoding="utf-8") as fh:
        fh.write("1700000000\n")
    old = datetime.datetime.now(datetime.timezone.utc).timestamp() - age_seconds
    os.utime(trail, (old, old))


def samples(dispatch):
    trail = os.path.join(dispatch, ACTIVITY)
    if not os.path.exists(trail):
        return 0
    with open(trail, encoding="utf-8") as fh:
        return len([ln for ln in fh.read().splitlines() if ln.strip()])


def age_gate(tmp, seconds):
    """Backdate the shared sample gate so the next call is past its window."""
    for name in (".activity-gate",):
        gate = os.path.join(tmp, "docs", "plans", name)
        if os.path.exists(gate):
            old = datetime.datetime.now(datetime.timezone.utc).timestamp() - seconds
            os.utime(gate, (old, old))


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


    # 5. Marker retention: a long-lived session must collect its own litter,
    #    because session-start-marker only sweeps when a NEW session opens.
    print("marker retention sweep")
    with tempfile.TemporaryDirectory() as tmp:
        markers = os.path.join(tmp, ".session-markers")
        os.makedirs(markers)
        mine = write_marker(markers, "mine", 0)
        stale = write_marker(markers, "stale", 72)
        fresh = write_marker(markers, "fresh", 1)
        sentinel = os.path.join(markers, SWEEP_SENTINEL)

        run_hook_with_marker(tmp, mine)
        check("sweep: stale marker dropped", not os.path.exists(stale))
        check("sweep: fresh marker kept", os.path.exists(fresh))
        check("sweep: own marker kept", os.path.exists(mine))
        check("sweep: sentinel written", os.path.exists(sentinel))

        stale2 = write_marker(markers, "stale2", 72)
        run_hook_with_marker(tmp, mine)
        check("sweep: rate-limited inside the window", os.path.exists(stale2),
              "a second call in the same window must not re-glob")

        old = datetime.datetime.now(datetime.timezone.utc).timestamp() - 7200
        if os.path.exists(sentinel):
            os.utime(sentinel, (old, old))
        run_hook_with_marker(tmp, mine)
        check("sweep: runs again once the window passes", not os.path.exists(stale2))

    # 6. Activity trail attribution. Two defects of one shape: the key did not
    #    cover what the surrounding rules permit (L34). mow expressly allows two
    #    runs live in one repo when their files are disjoint, but
    #    `max(hits, key=mtime)` gave the whole repo a single winner — so
    #    concurrent runs stole each other's samples, flip-flopping to whoever
    #    wrote tracker.json last, and each run's board under-reported active
    #    time. Separately the run_status check sat only on the missing-trail
    #    path, so a shipped run whose trail still existed kept accruing samples
    #    forever.
    print("activity trail")
    with tempfile.TemporaryDirectory() as tmp:
        live_a = write_board(tmp, "alpha", "running")
        live_b = write_board(tmp, "beta", "running")
        done = write_board(tmp, "gamma", "shipped")
        seed_trail(done)

        run_hook(tmp, "PostToolUse", {}, tool_name="Edit")
        check("both live runs sampled", samples(live_a) == 1 and samples(live_b) == 1,
              f"alpha={samples(live_a)} beta={samples(live_b)} — one winner is the bug")
        check("shipped run's trail stops growing", samples(done) == 1,
              f"gamma={samples(done)} — run_status must gate every append, not just the first")

        run_hook(tmp, "PostToolUse", {}, tool_name="Edit")
        check("rate-limited inside the window",
              samples(live_a) == 1 and samples(live_b) == 1,
              f"alpha={samples(live_a)} beta={samples(live_b)}")

        age_gate(tmp, 600)
        seed_trail(live_a, 600)
        seed_trail(live_b, 600)
        run_hook(tmp, "PostToolUse", {}, tool_name="Edit")
        check("samples again once the window passes",
              samples(live_a) == 2 and samples(live_b) == 2,
              f"alpha={samples(live_a)} beta={samples(live_b)}")

    print(f"\n{len(FAILURES)} failure(s)" + (": " + ", ".join(FAILURES) if FAILURES else ""))
    return 1 if FAILURES else 0


sys.exit(main())
