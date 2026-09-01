#!/usr/bin/env python3
"""Regression tests for skills/mow/tracker_port.py.

Plain `python3 skills/mow/tests/test_tracker_port.py` — no pytest, matching
test_board_table.py: the interpreter these run under carries no third-party
packages.

The board is now **one page per repo** (`docs/plans/`, filtered live/archive),
so the port is keyed on the repo path alone and two concurrent `/mow go` runs
deliberately share it. That re-opens, one level up, the bug the per-stem key
was introduced to close on 2026-08-29: a plans root looks identical from the
outside whichever project it belongs to, so two *repos* whose paths hash to one
port would each render the other's runs under their own bookmarked URL — with
`tracker.html` answering 200, which is what made the per-run version of this
look healthy while it was lying. A served `.board` marker naming the repo is
what settles ownership now, and these tests are what hold that claim up.

They use real `http.server` processes rather than fakes: the whole mechanism is
"what is actually listening on this port, and whose repo is it", and a mock
cannot fail the way a socket does.
"""

import os
import subprocess
import shutil
import sys
import tempfile
import time
from contextlib import contextmanager

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import tracker_port  # noqa: E402

FAILURES = []
SERVERS = []


def check(label, got, want):
    if got != want:
        FAILURES.append(f"{label}: got {got!r}, want {want!r}")


def make_repo(tmp, *stems):
    """A repo skeleton: the plans root the board is served from, runs under it."""
    os.makedirs(os.path.join(tmp, "docs", "plans"), exist_ok=True)
    with open(os.path.join(tmp, "docs", "plans", "tracker.html"), "w") as fh:
        fh.write("<html>the board</html>")
    for stem in stems:
        d = os.path.join(tmp, "docs", "plans", stem, "dispatch")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "tracker.json"), "w") as fh:
            fh.write('{"schema": 1, "stem": "%s", "run_status": "running"}' % stem)


def free_repo(parent, name):
    """A repo path whose home port nothing is listening on right now.

    Keeps the suite honest on a machine already running real mow boards —
    which, given what this file is about, is exactly when it will be run.
    """
    for n in range(200):
        path = os.path.join(parent, f"{name}-{n}")
        if not tracker_port.listening(tracker_port.derive(path)):
            os.makedirs(path, exist_ok=True)
            return path
    raise SystemExit("no repo path with a free home port — is the range full?")


def serve(cwd, port, root="docs/plans"):
    """Start a real server for `cwd`'s board on `port`; wait until it answers."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "-d", root],
        cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    SERVERS.append(proc)
    for _ in range(50):
        if tracker_port.listening(port):
            return proc
        time.sleep(0.1)
    raise SystemExit(f"server for {cwd} never came up on {port}")


def stop_servers():
    """Terminate every server started so far, and wait for it to actually exit."""
    for proc in SERVERS:
        proc.terminate()
    for proc in SERVERS:
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    # Windows cannot remove a directory a live process holds open, so the wait
    # above is the whole point of draining here. Prove it happened rather than
    # trusting terminate() to have been enough.
    check("every server exited before its sandbox was removed",
          [proc.pid for proc in SERVERS if proc.poll() is None], [])
    SERVERS.clear()


@contextmanager
def sandbox():
    """A temp dir whose servers are stopped *before* the dir is removed.

    Every server here runs with its cwd inside the sandbox. Windows refuses to
    delete a directory a live process holds open, so draining the servers in
    main()'s finally — after each `with` had already exited — raised
    PermissionError [WinError 32] and failed the whole file on that runner.
    POSIX unlinks an open directory happily, which is why it went unseen.
    """
    with tempfile.TemporaryDirectory() as tmp:
        try:
            yield tmp
        finally:
            stop_servers()


def test_one_port_per_repo():
    """One repo, one board, one bookmark — and never two repos on one page."""
    repo_a, repo_b = "/srv/project-a", "/srv/project-b"
    check("derive is deterministic", tracker_port.derive(repo_a), tracker_port.derive(repo_a))
    check("two projects, two boards",
          tracker_port.derive(repo_a) != tracker_port.derive(repo_b), True)
    for path in (repo_a, repo_b):
        port = tracker_port.derive(path)
        if not 8300 <= port <= 8379:
            FAILURES.append(f"derive({path}) out of range: {port}")
    # one repo reached two ways is one board: /tmp is a symlink to /private/tmp
    # on macOS, and an unresolved key would have split it into two pages
    if os.path.islink("/tmp"):
        check("a symlinked path resolves to the same board",
              tracker_port.derive("/tmp"), tracker_port.derive("/private/tmp"))


def test_another_repos_board_is_stepped_over_and_survives():
    """The hard requirement: a peer project's board is never taken, never killed."""
    with sandbox() as tmp:
        mine, peer = free_repo(tmp, "mine"), free_repo(tmp, "peer")
        make_repo(mine, "a-run")
        make_repo(peer, "other-run")
        tracker_port.mark(peer)
        home = tracker_port.derive(mine)

        # force the collision: the peer project's board is on MY home port
        proc = serve(peer, home)
        for _ in range(50):
            if tracker_port.serves(home, peer):
                break
            time.sleep(0.1)
        check("peer's board is not mistaken for mine", tracker_port.serves(home, mine), False)
        check("peer's board is recognised as the peer's", tracker_port.serves(home, peer), True)
        port, action = tracker_port.pick(mine)
        check("collision steps to another port", port != home, True)
        check("and starts a server there", action, "serve")
        check("peer server still alive", proc.poll(), None)
        # the check that replaces `lsof | head` — empty result, non-zero exit
        check("owned() reports no board of mine", tracker_port.owned(mine), None)


def test_my_own_board_is_reused_not_restarted():
    """Two `/mow go` runs in one repo share the board — the second reuses it."""
    with sandbox() as tmp:
        mine = free_repo(tmp, "mine")
        make_repo(mine, "first-run", "second-run")
        tracker_port.mark(mine)
        home = tracker_port.derive(mine)
        serve(mine, home)
        for _ in range(50):
            if tracker_port.serves(home, mine):
                break
            time.sleep(0.1)
        check("own board on home port is reused", tracker_port.pick(mine), (home, "reuse"))
        check("owned() finds it", tracker_port.owned(mine), home)


def test_a_single_runs_dispatch_server_is_not_adopted():
    """A per-run server (the pre-refactor shape, and still live on this machine
    while an old run finishes) serves tracker.json and no marker — the repo
    board must step over it rather than adopt it as its own page."""
    with sandbox() as tmp:
        mine = free_repo(tmp, "mine")
        make_repo(mine, "a-run")
        tracker_port.mark(mine)
        home = tracker_port.derive(mine)
        serve(mine, home, root="docs/plans/a-run/dispatch")
        for _ in range(50):
            if tracker_port.listening(home):
                break
            time.sleep(0.1)
        check("a dispatch folder is not this repo's board", tracker_port.serves(home, mine), False)
        port, action = tracker_port.pick(mine)
        check("so the board steps past it", (port != home, action), (True, "serve"))


def test_cli_serve_writes_the_marker():
    """`serve` promises the next server can be identified — so it writes first."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tracker_port.py")
    with sandbox() as tmp:
        mine = free_repo(tmp, "mine")
        make_repo(mine, "a-run")
        out = subprocess.run([sys.executable, script], cwd=mine,
                             capture_output=True, text=True, timeout=60)
        check("exit 0", out.returncode, 0)
        check("prints port + action", out.stdout.split(),
              [str(tracker_port.derive(mine)), "serve"])
        marker = os.path.join(mine, "docs", "plans", tracker_port.MARKER)
        check("marker written", os.path.exists(marker), True)
        with open(marker) as fh:
            check("marker names this repo", fh.read().strip(), os.path.realpath(mine))


def test_cli_owned_is_empty_and_nonzero_for_another_repos_board():
    """The `head` trap, pinned: `lsof … | head` exits 0 on empty input, so an
    absent board read as a healthy one. `--owned` must say nothing and fail."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tracker_port.py")
    with sandbox() as tmp:
        mine, peer = free_repo(tmp, "mine"), free_repo(tmp, "peer")
        make_repo(mine, "a-run")
        make_repo(peer, "other-run")
        tracker_port.mark(peer)
        serve(peer, tracker_port.derive(mine))
        for _ in range(50):
            if tracker_port.serves(tracker_port.derive(mine), peer):
                break
            time.sleep(0.1)
        out = subprocess.run([sys.executable, script, "--owned"], cwd=mine,
                             capture_output=True, text=True, timeout=60)
        check("no port printed for a board that is not mine", out.stdout.strip(), "")
        check("exit code says not-ours", out.returncode, 1)
        out = subprocess.run([sys.executable, script, "--owned"], cwd=peer,
                             capture_output=True, text=True, timeout=60)
        check("the peer's own --owned finds it",
              out.stdout.strip(), str(tracker_port.derive(mine)))


def test_kill_pattern_matches_only_this_repos_board():
    """The documented close-out pattern, dry-run through pgrep. Every board now
    serves a folder called `docs/plans`, so the pattern must carry the repo's
    absolute path — a relative `-d docs/plans` makes two projects' command
    lines identical, and one repo's close-out would kill the other's board."""
    pgrep = shutil.which("pgrep")
    if pgrep is None:
        print("  (skipped kill-pattern check: pgrep not on PATH)")
        return
    with sandbox() as tmp:
        mine, peer = free_repo(tmp, "mine"), free_repo(tmp, "peer")
        make_repo(mine, "a-run")
        make_repo(peer, "other-run")
        my_proc = serve(mine, tracker_port.derive(mine),
                        root=os.path.join(mine, "docs", "plans"))
        peer_proc = serve(peer, tracker_port.derive(peer),
                          root=os.path.join(peer, "docs", "plans"))

        def matches(repo_path):
            out = subprocess.run(
                [pgrep, "-f", f"http.server .* -d {repo_path}/docs/plans"],
                capture_output=True, text=True, timeout=30)
            return {int(p) for p in out.stdout.split()}

        check("pattern matches my own board", my_proc.pid in matches(mine), True)
        check("pattern never matches another repo's", peer_proc.pid in matches(mine), False)
        # the relative pattern is the one that must not be documented
        loose = subprocess.run([pgrep, "-f", "http.server .* -d docs/plans"],
                               capture_output=True, text=True, timeout=30)
        check("(a relative -d would have matched both — why the path is absolute)",
              {my_proc.pid, peer_proc.pid} & {int(p) for p in loose.stdout.split()}, set())


def main():
    try:
        test_one_port_per_repo()
        test_another_repos_board_is_stepped_over_and_survives()
        test_my_own_board_is_reused_not_restarted()
        test_a_single_runs_dispatch_server_is_not_adopted()
        test_cli_serve_writes_the_marker()
        test_cli_owned_is_empty_and_nonzero_for_another_repos_board()
        test_kill_pattern_matches_only_this_repos_board()
    finally:
        stop_servers()  # backstop: each sandbox() already drained its own
    if FAILURES:
        print(f"FAIL ({len(FAILURES)})")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
