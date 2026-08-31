#!/usr/bin/env python3
"""Regression tests for hooks/session-start-marker.py.

Plain `python3 hooks/tests/test_session_start_marker.py` — no pytest, matching
the other hook tests.

The bug these pin down: an earlier version of this hook returned early unless a
`.taskman.toml` existed, so in a board-less repo *no marker was ever written*
and hooks/peer-session-*.py silently found no peers. The board is beside the
point — one HEAD shared by two sessions is a hazard wherever it happens. The
`.taskman.toml` lookup may therefore decide the wrap-up *sentence* and nothing
else; `test_board_less_repo_still_writes_a_marker` is the assertion that fails
if that early return ever comes back.
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "..", "session-start-marker.py")

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAILURES.append(name)


def make_repo(board_at=None):
    """A git worktree, optionally with a `.taskman.toml` at `board_at`.

    realpath because macOS hands out /var/folders symlinks and the hook
    resolves its cwd before asking git for the toplevel.
    """
    parent = os.path.realpath(tempfile.mkdtemp())
    repo = os.path.join(parent, "repo")
    os.makedirs(repo)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    if board_at is not None:
        target = {"repo": repo, "parent": parent}[board_at]
        with open(os.path.join(target, ".taskman.toml"), "w", encoding="utf-8") as fh:
            fh.write("[project]\nslug = \"test\"\n")
    return parent, repo


def run_hook(cwd, event="SessionStart", session_id="s1"):
    """Run the hook the way a host does and hand back its parsed stdout."""
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_ENV_FILE"}
    payload = {"cwd": cwd, "hook_event_name": event, "session_id": session_id}
    proc = subprocess.run(
        [sys.executable, HOOK], input=json.dumps(payload),
        text=True, capture_output=True, check=False, env=env,
    )
    return proc


def context_of(proc):
    """The context string, whichever runtime shape the hook emitted.

    Silence rather than a traceback when stdout is not JSON, so a regression
    reads as a FAIL line in pre-push instead of a stack trace.
    """
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return ""
    specific = out.get("hookSpecificOutput") or {}
    return specific.get("additionalContext") or out.get("additional_context") or ""


def markers_in(repo):
    d = os.path.join(repo, ".session-markers")
    return sorted(f for f in os.listdir(d) if f.endswith(".json")) if os.path.isdir(d) else []


def test_board_less_repo_still_writes_a_marker():
    """The f6b25f9 guard: no board is not a reason to skip the marker."""
    _, repo = make_repo(board_at=None)
    proc = run_hook(repo)
    check("board-less: hook succeeded", proc.returncode == 0, proc.stderr[:300])
    check("board-less: marker written", markers_in(repo) == ["s1.json"],
          f"markers={markers_in(repo)} stdout={proc.stdout[:200]}")
    check("board-less: context announces the marker",
          "Session marker written" in context_of(proc), proc.stdout[:300])


def test_board_less_context_names_no_wrap_up_command():
    """A clone with nothing installed must not be told to run something."""
    _, repo = make_repo(board_at=None)
    ctx = context_of(run_hook(repo))
    for absent in ["wrapup", "wrap-up must run", "scripts/", ".venv"]:
        check(f"board-less: context omits {absent!r}", absent not in ctx, ctx)


def test_board_at_the_worktree_root_names_the_gate():
    _, repo = make_repo(board_at="repo")
    proc = run_hook(repo)
    ctx = context_of(proc)
    check("board: context names the gate", "taskman wrapup gate" in ctx, ctx)
    check("board: marker still written", markers_in(repo) == ["s1.json"],
          f"markers={markers_in(repo)}")


def test_board_is_found_by_walking_up():
    """The board is rarely in the directory the session happens to open in."""
    _, repo = make_repo(board_at="repo")
    subdir = os.path.join(repo, "a", "b")
    os.makedirs(subdir)
    check("walk-up: board at the worktree root found from a subdir",
          "taskman wrapup gate" in context_of(run_hook(subdir)), "")

    parent, repo2 = make_repo(board_at="parent")
    check("walk-up: board above the worktree found",
          "taskman wrapup gate" in context_of(run_hook(repo2)), "")


def test_cursor_runtime_still_emits_valid_json_and_env():
    _, repo = make_repo(board_at=None)
    proc = run_hook(repo, event="sessionStart")
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        check("cursor: valid JSON on stdout", False, proc.stdout[:200])
        return
    check("cursor: valid JSON on stdout", True)
    check("cursor: exports the marker env",
          set(out.get("env", {})) == {"WRAPUP_SESSION_ID", "WRAPUP_SESSION_MARKER",
                                      "WRAPUP_START_SHA", "WRAPUP_WORKTREE"},
          str(out.get("env")))
    check("cursor: board-less context stays quiet about wrap-up",
          "wrapup" not in context_of(proc), context_of(proc))


def test_outside_a_git_repo_nothing_is_written():
    """The one legitimate early return: no worktree to share, no dir to litter."""
    plain = os.path.realpath(tempfile.mkdtemp())
    proc = run_hook(plain)
    check("non-repo: exits clean", proc.returncode == 0, proc.stderr[:200])
    check("non-repo: no marker directory",
          not os.path.exists(os.path.join(plain, ".session-markers")))


if __name__ == "__main__":
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        print(fn.__name__)
        fn()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("all passed")
