#!/usr/bin/env python3
"""Regression tests for skills/mow/board_table.py number formatting.

Plain `python3 skills/mow/tests/test_board_table.py` — no pytest, matching
hooks/tests: the interpreter these run under carries no third-party packages.

The bug these pin down: `fmt_tokens` was ported from tracker.html's `fmtTokens`,
where a trailing `.0` is dropped with `.replace(/\\.0$/, "")`. The port used
`.rstrip("0")`, which strips trailing zeros from the *whole* string — so a lane
that burned 80,464 tokens rendered as `8k tok`, 20k as `2k`, and 100k as `1k`.
An under-reported cost reads as plausible, which is what makes it worth a test.

The page is the reference implementation; every expectation here is what
`fmtTokens` returns for the same input.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import board_table  # noqa: E402

FAILURES = []


def check(label, got, want):
    if got != want:
        FAILURES.append(f"{label}: got {got!r}, want {want!r}")


def test_fmt_tokens():
    cases = [
        (None, None),
        (0, "0 tok"),
        (500, "500 tok"),
        (999, "999 tok"),
        (1000, "1k tok"),
        (1500, "1.5k tok"),
        (9999, "10k tok"),
        (10000, "10k tok"),
        (10500, "11k tok"),          # toFixed rounds half away from zero
        (20000, "20k tok"),          # trailing zero — the reported bug class
        (46836, "47k tok"),
        (80464, "80k tok"),          # the lane A figure that rendered as 8k
        (100000, "100k tok"),        # would render as 1k
        (127300, "127k tok"),
        (999999, "1000k tok"),
        (1000000, "1M tok"),
        (1300000, "1.3M tok"),
        (10000000, "10M tok"),
        (12500000, "13M tok"),
    ]
    for value, want in cases:
        check(f"fmt_tokens({value})", board_table.fmt_tokens(value), want)


def test_lane_row_carries_full_token_count():
    """The symptom as the operator saw it: a lane row in the rendered table."""
    board = {
        "schema": 1, "stem": "t", "title": "T", "run_status": "running",
        "updated": "2026-08-26T19:24:03Z",
        "waves": [{
            "wave": 1, "status": "running", "parallelism": "parallel",
            "gate": {"status": "pending"},
            "lanes": [
                {"lane": "A", "status": "issues", "tokens": 80464,
                 "agents": [{"name": "tdd-builder", "status": "done"},
                            {"name": "general-purpose", "status": "done"},
                            {"name": "general-purpose", "status": "running"}]},
                {"lane": "B", "status": "done", "tokens": 46836,
                 "agents": [{"name": "tdd-builder", "status": "done"}]},
            ],
        }],
    }
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "tracker.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(board, fh)
        out = board_table.build(path)

    lane_a = next(l for l in out.splitlines() if l.startswith("| **W1**"))
    lane_b = next(l for l in out.splitlines() if "| B |" in l or l.startswith("|  | B"))
    check("lane A row tokens", "80k tok" in lane_a, True)
    check("lane B row tokens", "47k tok" in lane_b, True)
    # the wave roll-up was always right; keep it that way
    gate = next(l for l in out.splitlines() if "_gate_" in l)
    check("gate row roll-up", "127k tok" in gate, True)


def test_parity_with_the_page():
    """The claim the table makes for itself is that it cannot disagree with
    tracker.html. Assert it against the page's real `fmtTokens`, executed —
    reading the source and believing it is how the `.rstrip("0")` bug shipped.

    Skips when node is absent; this is a desk check, not a gate."""
    if shutil.which("node") is None:
        print("  (skipped parity check: node not on PATH)")
        return
    page = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tracker.html")
    src = open(page, encoding="utf-8").read()
    fn = re.search(r"function fmtTokens\(n\) \{.*?\n\}", src, re.S)
    if not fn:
        FAILURES.append("parity: no fmtTokens in tracker.html — did the page change?")
        return
    values = [0, 500, 999, 1000, 1500, 9999, 10000, 10500, 20000, 46836, 80464,
              100000, 127300, 999999, 1000000, 1300000, 10000000, 12500000]
    script = "%s\nfor (const v of %s) console.log(v + ' ' + fmtTokens(v));" % (fn.group(0), values)
    out = subprocess.run([shutil.which("node"), "-e", script],
                         capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        FAILURES.append(f"parity: node failed — {out.stderr.strip()[:200]}")
        return
    for line in out.stdout.splitlines():
        value, want = line.split(" ", 1)
        check(f"parity fmt_tokens({value})", board_table.fmt_tokens(int(value)), want)


def main():
    test_fmt_tokens()
    test_lane_row_carries_full_token_count()
    test_parity_with_the_page()
    if FAILURES:
        print(f"FAIL ({len(FAILURES)})")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
