#!/usr/bin/env python3
"""Regression tests for `ai-sync status` mode reporting.

Plain `python3 bin/tests/test_ai_sync_status.py` — no pytest, matching
hooks/tests/, because the interpreter this tool runs under has no third-party
packages.

The bug these pin down: `status` reported the machine's symlink *capability*
instead of the mode the harness was actually *installed* with. After a
`--copy` install on a machine that can symlink, it printed `link mode:
symlink` and eight `NOT linked (real dir)` lines for a complete, correct
install — so the documented path for a locked-down Windows box read as a
failed install.

These run a real install into a throwaway HOME against a throwaway copy of the
repo. Never the caller's own HOME, and never the real checkout: `ai-sync`
commits with `git add -A` and pushes, so the copy gets its own `git init` with
no remote and a `{"push": false}` config.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
# Only what ai-sync actually reads — copying the whole checkout would drag in
# .git, taskman/.venv and 60-odd MB for no added coverage.
NEEDED = ["skills", "agents", "commands", "hooks", "global", "bin",
          "hooks.def.json", "mcp.json"]
FAILURES = []


def check(label, got, want):
    if got == want:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label} — got {got!r}, want {want!r}")
        FAILURES.append(label)


def build_repo(root):
    """A throwaway checkout with its own git and no remote."""
    for item in NEEDED:
        src = REPO / item
        if not src.exists():
            continue
        dst = root / item
        if src.is_dir():
            shutil.copytree(src, dst, symlinks=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, dst)
    (root / "local.config.json").write_text(json.dumps({"push": False}) + "\n")
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
    subprocess.run(["git", "init", "-q"], cwd=root, env=env, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, env=env,
                   check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, env=env,
                   check=True, capture_output=True)
    return root


def run(root, home, *args):
    return subprocess.run([sys.executable, str(root / "bin" / "ai-sync"), *args],
                          cwd=root, env={**os.environ, "HOME": str(home)},
                          capture_output=True, text=True)


def main():
    print("ai-sync status mode reporting")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        root = build_repo(tmp / "repo")

        # 1. --copy install, no link_mode in config. This is the regression:
        #    the flag is one-shot, so a later `status` sees an empty config and
        #    used to fall back to probing the machine.
        home = tmp / "h-copy"
        (home / ".agents").mkdir(parents=True)
        run(root, home, "--copy")
        out = run(root, home, "status").stdout
        check("copy install reports copy mode",
              "link mode: copy" in out, True)
        check("copy install shows no NOT-linked targets",
              "NOT linked" in out, False)
        check("copy install reports every target in sync",
              out.count("copied (in sync)"), 8)
        check("copy-mode status is stable across runs",
              run(root, home, "status").stdout, out)

        # 2. A normal symlink install must be unaffected.
        home = tmp / "h-link"
        (home / ".agents").mkdir(parents=True)
        (home / ".agents" / "skills").symlink_to(root / "skills")
        run(root, home)
        out = run(root, home, "status").stdout
        check("symlink install reports symlink mode",
              "link mode: symlink" in out, True)
        check("symlink install reports every target linked",
              len([ln for ln in out.splitlines() if ln.rstrip().endswith(" linked")]), 8)

        # 3. Nothing installed yet: fall back to the capability probe rather
        #    than crashing or inventing a mode.
        home = tmp / "h-empty"
        home.mkdir()
        res = run(root, home, "status")
        check("empty HOME exits cleanly", res.returncode, 0)
        check("empty HOME reports targets missing",
              "missing" in res.stdout, True)

        # 4. The label is about the install, not the machine. A box that CAN
        #    symlink but was installed with --copy must not be told it lacks
        #    the privilege.
        check("label makes no claim about symlink privilege",
              "no symlink privilege" in run(root, tmp / "h-copy", "status").stdout, False)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s): " + ", ".join(FAILURES))
        return 1
    print("0 failure(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
