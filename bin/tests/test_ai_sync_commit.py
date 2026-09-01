#!/usr/bin/env python3
"""Regression tests for `ai-sync`'s commit scope.

Plain `python3 bin/tests/test_ai_sync_commit.py` — no pytest, matching
hooks/tests/, because the interpreter this tool runs under has no third-party
packages.

The bug these pin down: `do_commit` ran `git add -A`. One manual `ai-sync` then
swept every dirty path in the tree — plans, session reports, a half-finished
refactor — into a single `sync: <ts>` commit authored by `ai-sync@local`, with
no message describing any of it. Worse in a shared checkout: `git add -A`
followed by a bare `git commit` also picks up whatever a second session had
staged, so one tool's convenience commit silently published another session's
in-flight work.

These run against a throwaway git repo built in a temp dir. Never the real
checkout: the code under test commits and can push.
"""

import os
import subprocess
import sys
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FAILURES = []


def check(label, got, want):
    if got == want:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label} — got {got!r}, want {want!r}")
        FAILURES.append(label)


def git(repo, *args, check_rc=True):
    env = dict(os.environ)
    env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, env=env, check=check_rc)


def load_tool(repo):
    """ai-sync with its module globals repointed at a throwaway repo.

    LINK_DIRS/LINK_FILES are built from REPO at import time, so repointing REPO
    alone would leave managed_paths() pointing at the real checkout.
    """
    m = SourceFileLoader("aisync_under_test", str(REPO / "bin" / "ai-sync")).load_module()
    m.REPO = repo
    m.LINK_DIRS = {"agents": repo / "agents", "commands": repo / "commands",
                   "hooks": repo / "hooks"}
    m.LINK_FILES = {Path("/x/CLAUDE.md"): repo / "global" / "CLAUDE.md",
                    Path("/x/rules"): repo / "rules"}
    m.LOCAL_CONFIG = repo / "local.config.json"
    return m


def build_repo(tmp):
    """A repo with one committed file in every managed dir, plus unmanaged dirt."""
    for rel in ["agents/a.md", "commands/c.md", "hooks/h.sh", "global/CLAUDE.md",
                "rules/r.md", "skills/s/SKILL.md", "docs/plans/p.md", "LESSONS.md"]:
        f = tmp / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("seed\n")
    (tmp / "skills.lock.json").write_text("{}\n")
    # No remote, and push off, so a bug here can never reach a network.
    (tmp / "local.config.json").write_text('{"push": false}\n')
    git(tmp, "init", "-q", "-b", "main")
    git(tmp, "add", "-A")
    git(tmp, "commit", "-q", "-m", "seed")
    return tmp


def dirty(repo):
    return {ln[3:].strip() for ln in
            git(repo, "status", "--porcelain").stdout.splitlines() if ln.strip()}


def run_commit(m):
    """do_commit with its log captured, so the report can be asserted on."""
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        m.do_commit()
    return buf.getvalue()


def main():
    print("ai-sync commit scope")

    # --- managed content is committed; unmanaged is left alone --------------
    with tempfile.TemporaryDirectory() as d:
        tmp = build_repo(Path(d))
        m = load_tool(tmp)
        (tmp / "agents" / "a.md").write_text("changed\n")
        (tmp / "skills" / "s" / "SKILL.md").write_text("changed\n")
        (tmp / "docs" / "plans" / "p.md").write_text("in flight\n")
        (tmp / "LESSONS.md").write_text("in flight\n")
        out = run_commit(m)

        check("managed change is committed", "agents/a.md" in dirty(tmp), False)
        check("managed skills change is committed",
              "skills/s/SKILL.md" in dirty(tmp), False)
        check("unmanaged plan is left uncommitted",
              "docs/plans/p.md" in dirty(tmp), True)
        check("unmanaged root doc is left uncommitted",
              "LESSONS.md" in dirty(tmp), True)
        check("the skip is reported, not silent", "left 2 unmanaged path(s)" in out, True)

    # --- a peer session's staged file does not ride along -------------------
    with tempfile.TemporaryDirectory() as d:
        tmp = build_repo(Path(d))
        m = load_tool(tmp)
        (tmp / "agents" / "a.md").write_text("mine\n")
        (tmp / "docs" / "plans" / "p.md").write_text("a peer's staged work\n")
        git(tmp, "add", "docs/plans/p.md")          # the other session stages it
        run_commit(m)

        head = git(tmp, "show", "--name-only", "--format=", "HEAD").stdout.split()
        check("commit contains the managed file", "agents/a.md" in head, True)
        check("commit does NOT contain the peer's staged file",
              "docs/plans/p.md" in head, False)
        check("the peer's file is still staged and uncommitted",
              "docs/plans/p.md" in dirty(tmp), True)

    # --- nothing managed changed: no commit, but the dirt is still named ----
    with tempfile.TemporaryDirectory() as d:
        tmp = build_repo(Path(d))
        m = load_tool(tmp)
        before = git(tmp, "rev-parse", "HEAD").stdout.strip()
        (tmp / "LESSONS.md").write_text("only unmanaged\n")
        out = run_commit(m)

        check("no commit is made", git(tmp, "rev-parse", "HEAD").stdout.strip(), before)
        check("clean-scope is reported", "nothing to commit" in out, True)
        check("unmanaged dirt is still reported", "left 1 unmanaged path(s)" in out, True)

    # --- an untracked file inside a managed dir is picked up ----------------
    with tempfile.TemporaryDirectory() as d:
        tmp = build_repo(Path(d))
        m = load_tool(tmp)
        (tmp / "agents" / "new.md").write_text("brand new\n")
        run_commit(m)
        head = git(tmp, "show", "--name-only", "--format=", "HEAD").stdout.split()
        check("new managed file is added, not skipped", "agents/new.md" in head, True)

    # --- path classification, including the prefix trap ---------------------
    with tempfile.TemporaryDirectory() as d:
        tmp = build_repo(Path(d))
        m = load_tool(tmp)
        mp = m.managed_paths()
        cases = [(" M agents/x.md", True), ("?? docs/plans/y.md", False),
                 (" M global/CLAUDE.md", True), (" M bin/ai-sync", False),
                 ("R  a.md -> agents/b.md", True), (" M globalize.md", False)]
        bad = [ln for ln, want in cases
               if m._is_managed(m._porcelain_path(ln), mp) != want]
        check("porcelain lines classify correctly (globalize.md != global/)", bad, [])

        # managed_paths() is compared against `git status --porcelain`, which is
        # forward-slash everywhere. A native-separator entry therefore only ever
        # fails on Windows, where it silently demoted global/CLAUDE.md to
        # "unmanaged" and left it uncommitted. The first check keeps the second
        # honest: with no nested entry left, it would pass vacuously.
        check("a nested managed entry exists to get wrong",
              [x for x in mp if "/" in x] != [], True)
        check("managed_paths is git-style, never native separators",
              [x for x in mp if "\\" in x], [])

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s): " + ", ".join(FAILURES[:4]))
        return 1
    print("0 failure(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
