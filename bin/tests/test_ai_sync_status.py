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

These run a real install into a throwaway home against a throwaway copy of the
repo. Never the caller's own home, and never the real checkout: `ai-sync`
commits and pushes, so the copy gets its own `git init` with no remote and a
`{"push": false}` config. (It no longer commits with `git add -A` — see
test_ai_sync_commit.py — but it still commits, so the isolation stands.)

The second bug, same reporting surface: a copy install whose files had since
drifted from the repo fell through to that same `NOT linked (real dir)` branch —
so the label misdiagnosed precisely when something was wrong, and sent the
operator back to the installer instead of to `ai-sync`. Sections 5 and 6 pin the
drifted copy and the genuinely never-installed directory apart.

Isolation must override USERPROFILE as well as HOME. `Path.home()` goes through
`ntpath.expanduser` on Windows, which reads USERPROFILE (then HOMEDRIVE +
HOMEPATH) and ignores HOME entirely — so a HOME-only sandbox is a no-op there
and this test would install into the operator's real profile. Windows is the
platform this harness most needs to be safe on; see the human guide's Windows
appendix.
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


def can_symlink():
    """Same probe ai-sync uses. Windows denies symlinks without Developer Mode,
    and corporate policy can pin that off — on such a box a plain install
    legitimately falls back to copy, so the symlink case is not applicable
    rather than failing."""
    with tempfile.TemporaryDirectory() as d:
        try:
            os.symlink(Path(d), Path(d) / "probe")
            return True
        except (OSError, NotImplementedError, AttributeError):
            return False


def skip(label, why):
    print(f"  SKIP  {label} — {why}")


def check(label, got, want):
    if got == want:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label} — got {got!r}, want {want!r}")
        FAILURES.append(label)


def state_of(out, target):
    """The state `status` printed for one target line, e.g. ".claude/agents"."""
    for line in out.splitlines():
        stripped = line.strip()
        if stripped.startswith(target + " "):
            return stripped[len(target):].strip()
    return None


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


def sandbox_env(home):
    """Every name a platform might resolve `~` through, pointed at the sandbox."""
    home = str(home)
    return {**os.environ, "HOME": home, "USERPROFILE": home,
            "HOMEDRIVE": "", "HOMEPATH": home}


def run(root, home, *args):
    return subprocess.run([sys.executable, str(root / "bin" / "ai-sync"), *args],
                          cwd=root, env=sandbox_env(home),
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

        # 2. A normal symlink install must be unaffected — where symlinks exist.
        if not can_symlink():
            skip("symlink install reports symlink mode",
                 "this machine cannot create symlinks; a plain install "
                 "correctly falls back to copy here")
        else:
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

        # 5. A copy install whose contents drifted from the repo. This is the
        #    second half of the same bug: a drifted copy fell through to the
        #    same branch a never-installed directory hits, so the one moment
        #    something IS wrong is the moment the label misdiagnoses it — and
        #    "NOT linked" sends the operator back to the installer, which is
        #    the one response that does not fix drift.
        home = tmp / "h-drift"
        (home / ".agents").mkdir(parents=True)
        run(root, home, "--copy")
        (home / ".claude" / "agents" / "edited-after-install.md").write_text("drift\n")
        (home / ".claude" / "CLAUDE.md").write_text("hand-edited\n")
        out = run(root, home, "status").stdout
        check("drifted copy dir reports stale",
              state_of(out, ".claude/agents"), "copied (stale — re-run ai-sync)")
        check("drifted copy file reports stale in the same words",
              state_of(out, ".claude/CLAUDE.md"), "copied (stale — re-run ai-sync)")
        check("drifted copy is not called unmanaged",
              "NOT linked" in out, False)

        # 6. The counterpart the stale wording must not swallow. In symlink
        #    mode a real directory at a managed path was never installed by
        #    ai-sync at all, and "NOT linked (real dir)" stays the honest word
        #    for it — only the copy-mode fall-through changed.
        if not can_symlink():
            skip("never-installed real dir still reports NOT linked",
                 "symlink mode is unreachable on this machine")
        else:
            home = tmp / "h-foreign"
            (home / ".claude" / "agents").mkdir(parents=True)
            (home / ".claude" / "agents" / "someone-elses.md").write_text("not ours\n")
            (home / ".claude" / "commands").symlink_to(root / "commands")
            out = run(root, home, "status").stdout
            check("never-installed dir case runs in symlink mode",
                  "link mode: symlink" in out, True)
            check("never-installed real dir still reports NOT linked",
                  state_of(out, ".claude/agents"), "NOT linked (real dir)")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s): " + ", ".join(FAILURES))
        return 1
    print("0 failure(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
