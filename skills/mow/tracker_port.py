#!/usr/bin/env python3
"""Pick the port this repo's tracker board is served on.

**One board per repo**, not per run. The board is the plans root
(`docs/plans/`), and every `/mow go` in the repo appears on it — live runs
under `?runs=live`, finished ones under `?runs=archive`. So the port is keyed
on the repo path alone, two concurrent runs deliberately *share* it, and the
URL is one bookmark that outlives any single run.

Ownership is settled by **asking the server**, never by guessing from the port.
A mow board serves a `.board` marker naming the repo it was started in, so:

  - a port held by another repo's board (or by anything else) is stepped over,
    never killed;
  - a board already serving *this* repo is reused, not restarted.

That marker is what keeps a hash collision between two projects from handing
you a page of someone else's runs. Keying on the repo path with no marker was
wrong in exactly that way: `docs/plans/` looks identical from the outside
whichever project it belongs to, so the loser of a collision would render the
winner's waves and lanes as if they were its own. The per-run variant of this
bug was observed 2026-08-29 (`builder-restrictions` and `product-analysis-ui` both
computed 8378, `tracker.json` answered 200 so the board looked healthy).
Nothing in this module kills anything.

    python3 tracker_port.py                 -> "8362 serve" | "8362 reuse"
    python3 tracker_port.py --owned         -> "8362", or nothing + exit 1
    python3 tracker_port.py --owned --wait 5

Printing `serve` also writes the marker, so the server started next answers for
this repo. `--owned` is the proof step: it answers "is the board on this port
really this repo's?", so a start is verified instead of assumed. Empty output
plus a non-zero exit is the whole contract — never pipe it through `head`,
which exits 0 on empty input and would report a peer's board as healthy.
"""

import hashlib
import os
import socket
import sys
import time
import urllib.request

BASE = 8300
SPAN = 80
PROBE_TIMEOUT = 0.4       # loopback: a live server answers in ~1ms
PLANS = os.path.join("docs", "plans")
MARKER = ".board"         # written into PLANS; served, so the probe can read it

USAGE = "usage: tracker_port.py [--owned [--wait SECONDS]]\n"

# a configured http_proxy must never swallow a loopback probe
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def repo(cwd=None):
    """The repo's identity: one resolved path.

    Resolving first means one repo reached two ways — a symlink, or /tmp vs
    /private/tmp on macOS — is one board and not two.
    """
    return os.path.realpath(os.getcwd() if cwd is None else cwd)


def derive(cwd=None):
    """This repo's home port. Same repo, same URL, every run."""
    return BASE + int(hashlib.md5(repo(cwd).encode()).hexdigest(), 16) % SPAN


def mark(cwd=None):
    """Name this repo in the folder about to be served. Returns the marker path."""
    path = os.path.join(os.getcwd() if cwd is None else cwd, PLANS, MARKER)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(repo(cwd) + "\n")
    return path


def listening(port, host="127.0.0.1"):
    with socket.socket() as sock:
        sock.settimeout(PROBE_TIMEOUT)
        return sock.connect_ex((host, port)) == 0


def _fetch(port, name):
    try:
        with _opener.open("http://127.0.0.1:%d/%s" % (port, name),
                          timeout=PROBE_TIMEOUT) as resp:
            return resp.read(65536)
    except Exception:     # 404, refused, dropped, not HTTP at all
        return None


def serves(port, cwd=None):
    """True when the server on `port` is serving THIS repo's plans root."""
    body = _fetch(port, MARKER)
    if body is None:
        return False
    try:
        return body.decode().strip() == repo(cwd)
    except UnicodeDecodeError:
        return False


def pick(cwd=None):
    """(port, "serve"|"reuse") — the first port that is free, or already ours.

    Walks forward from the home port so a collision with another project costs
    one port, not a shared board. Reuse is safe: a server answering this repo's
    marker is serving this repo's plans root, and `http.server` reads from disk
    per request, so it is already showing every current run.
    """
    home = derive(cwd)
    for step in range(SPAN):
        port = BASE + (home - BASE + step) % SPAN
        if not listening(port):
            return port, "serve"
        if serves(port, cwd):
            return port, "reuse"
    raise SystemExit("tracker_port: no free port in %d-%d" % (BASE, BASE + SPAN - 1))


def owned(cwd=None, wait=0.0):
    """The port this repo's board is really live on, or None.

    Walks the same range `pick` does, so it still finds the board when a
    collision pushed it off its home port. `wait` polls for a server that is
    still binding.
    """
    home = derive(cwd)
    deadline = time.monotonic() + wait
    while True:
        for step in range(SPAN):
            port = BASE + (home - BASE + step) % SPAN
            if listening(port) and serves(port, cwd):
                return port
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.2)


def main(argv):
    args = argv[1:]
    wait = 0.0
    if "--wait" in args:
        at = args.index("--wait")
        try:
            wait = float(args[at + 1])
        except (IndexError, ValueError):
            sys.stderr.write(USAGE)
            return 2
        del args[at:at + 2]
    if args == ["--owned"]:
        port = owned(wait=wait)
        if port is None:
            sys.stderr.write("tracker_port: no live board for %s\n" % repo())
            return 1
        print(port)
        return 0
    if args:
        sys.stderr.write(USAGE)
        return 2
    port, action = pick()
    if action == "serve":
        mark()
    print("%d %s" % (port, action))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
