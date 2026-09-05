#!/usr/bin/env python3
"""Regression tests for how test_repo_shape.py locates `local.config.json`.

Plain `python3 bin/tests/test_repo_shape_config.py` — no pytest, matching the
other suites here.

The bug these pin down: `local.config.json` holds the private scrub patterns and
is gitignored, so `git worktree add` never checks it out. Running the shape test
from a worktree therefore found no config and quietly degraded to the generic
patterns, printing a SKIP — the private half of the scrub was weakest in exactly
the place an isolated lane pushes from. Two pushes went out that way before
anyone noticed the SKIP was not the clone case it looks like.

The clone case is still real and must keep skipping: a fresh clone genuinely has
no config, and a SKIP there must never masquerade as a pass.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SHAPE = os.path.join(HERE, "test_repo_shape.py")
SENTINEL = "zz-sentinel-pattern"

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAILURES.append(name)


def shape_module(repo):
    """Load test_repo_shape.py with REPO pointed at `repo`."""
    spec = importlib.util.spec_from_file_location("shape_under_test", SHAPE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.REPO = type(mod.REPO)(repo)
    return mod


def make_repo(with_config):
    """A git repo with one commit, optionally carrying a private scrub config."""
    root = os.path.realpath(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q", root], check=True, capture_output=True)
    with open(os.path.join(root, "seed.txt"), "w", encoding="utf-8") as fh:
        fh.write("seed\n")
    if with_config:
        with open(os.path.join(root, "local.config.json"), "w", encoding="utf-8") as fh:
            json.dump({"scrub_patterns": [SENTINEL]}, fh)
    for args in (["add", "seed.txt"], ["commit", "-q", "-m", "seed"]):
        subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)
    return root


def test_a_worktree_reads_the_main_checkouts_config():
    """The gap: gitignored config never lands in a `git worktree add` checkout."""
    root = make_repo(with_config=True)
    tree = os.path.join(root, "wt")
    subprocess.run(["git", "-C", root, "worktree", "add", "--detach", "-q", tree, "HEAD"],
                   check=True, capture_output=True)
    check("worktree: config is genuinely absent there",
          not os.path.isfile(os.path.join(tree, "local.config.json")))

    mod = shape_module(tree)
    check("worktree: resolves to the main checkout's config",
          os.path.realpath(str(mod._config_path()))
          == os.path.realpath(os.path.join(root, "local.config.json")),
          f"got {mod._config_path()}")
    check("worktree: private patterns actually load",
          SENTINEL in mod._private_leak_patterns(),
          f"got {mod._private_leak_patterns()}")


def test_a_clone_without_a_config_still_reports_no_patterns():
    """A real clone has no config; that SKIP must not be papered over."""
    root = make_repo(with_config=False)
    mod = shape_module(root)
    check("clone: no patterns configured", mod._private_leak_patterns() == [],
          f"got {mod._private_leak_patterns()}")


def test_the_main_checkout_still_reads_its_own_config():
    """The common path must not regress while fixing the worktree one."""
    root = make_repo(with_config=True)
    mod = shape_module(root)
    check("main: reads its own config",
          SENTINEL in mod._private_leak_patterns(),
          f"got {mod._private_leak_patterns()}")


if __name__ == "__main__":
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        print(fn.__name__)
        fn()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("all passed")
