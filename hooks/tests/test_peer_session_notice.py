#!/usr/bin/env python3
"""Regression tests for hooks/peer-session-notice.py context budgeting.

Plain `python3 hooks/tests/test_peer_session_notice.py` — no pytest, matching
the other hook tests.

What these pin down: Claude Code silently swaps an over-long hook output for a
stub while still reporting success, so this notice must fit a budget by
dropping whole optional blocks — never by truncating mid-sentence, and never at
the cost of the ACTION REQUIRED lines that are the whole point of the hook.
"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "..", "peer-session-notice.py")

spec = importlib.util.spec_from_loader(
    "notice", importlib.machinery.SourceFileLoader("notice", HOOK))
notice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notice)

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAILURES.append(name)


def make_tree(branches):
    """A worktree with one marker for us and one live peer per branch."""
    d = tempfile.mkdtemp()
    md = os.path.join(d, ".session-markers")
    os.makedirs(md)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    mine = os.path.join(md, "mine.json")
    with open(mine, "w") as f:
        json.dump({"session_id": "mine", "worktree": d, "branch": "master",
                   "updated_at": now}, f)
    for i, b in enumerate(branches):
        with open(os.path.join(md, f"peer{i}.json"), "w") as f:
            json.dump({"session_id": f"peer{i}", "worktree": d, "branch": b,
                       "updated_at": now}, f)
    return d, mine


def run(worktree, marker):
    env = dict(os.environ, WRAPUP_SESSION_MARKER=marker, WRAPUP_WORKTREE=worktree)
    p = subprocess.run([sys.executable, HOOK], input="{}", capture_output=True,
                       text=True, env=env)
    return p.stdout


def test_normal_notice_is_complete():
    d, m = make_tree(["feature-x"])
    out = run(d, m)
    for frag in ["PEER SESSION: 1 other session(s)",
                 "one HEAD and one index",
                 "ACTION REQUIRED",
                 "Suggested wording:",
                 "EnterWorktree(name:",
                 "worktree.baseRef",
                 "never `git stash`"]:
        check(f"normal: contains {frag!r}", frag in out, out[:200])
    check("normal: under budget", len(out) <= notice.CONTEXT_BUDGET, f"len={len(out)}")


def test_branch_list_is_capped():
    branches = [f"very-long-feature-branch-name-number-{i:02d}" for i in range(20)]
    d, m = make_tree(branches)
    out = run(d, m)
    check("cap: says how many were elided", "+15 more" in out, out[:300])
    check("cap: only 5 names listed",
          sum(out.count(b) for b in branches) <= 5 * 3,  # up to 3 interpolations
          out[:300])
    check("cap: still under budget", len(out) <= notice.CONTEXT_BUDGET, f"len={len(out)}")


def test_fit_drops_optional_blocks_in_rank_order():
    blocks = [(0, "REQUIRED-A"), (2, "DROP-FIRST"), (1, "DROP-SECOND"), (0, "REQUIRED-B")]
    full = notice._fit(blocks, 10_000)
    check("fit: nothing dropped when it fits",
          all(x in full for x in ["REQUIRED-A", "DROP-FIRST", "DROP-SECOND", "REQUIRED-B"]))

    tight = notice._fit(blocks, 35)
    check("fit: highest rank dropped first", "DROP-FIRST" not in tight, tight)
    check("fit: lower rank survives one pass", "DROP-SECOND" in tight, tight)

    tighter = notice._fit(blocks, 22)
    check("fit: both optional dropped", "DROP-SECOND" not in tighter and "DROP-FIRST" not in tighter, tighter)
    check("fit: required always kept",
          "REQUIRED-A" in tighter and "REQUIRED-B" in tighter, tighter)


def test_fit_never_truncates_mid_block():
    """Selection, not truncation: whatever survives is whole."""
    blocks = [(0, "A" * 50), (1, "B" * 50)]
    out = notice._fit(blocks, 60)
    check("fit: survivor is intact", out == "A" * 50, out[:80])


def test_required_blocks_survive_an_impossible_budget():
    d, m = make_tree(["feature-x"])
    saved = notice.CONTEXT_BUDGET
    try:
        notice.CONTEXT_BUDGET = 10
        blocks_out = notice._fit([(0, "ACTION REQUIRED — do the thing"), (1, "optional")], 10)
    finally:
        notice.CONTEXT_BUDGET = saved
    check("impossible budget: action text still emitted",
          "ACTION REQUIRED" in blocks_out, blocks_out)
    check("impossible budget: optional gone", "optional" not in blocks_out, blocks_out)


def test_silent_when_no_peers():
    d, m = make_tree([])
    check("no peers: silent", run(d, m).strip() == "")


if __name__ == "__main__":
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        print(fn.__name__)
        fn()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("all passed")
