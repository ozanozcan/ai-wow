#!/usr/bin/env python3
"""Regression tests for `ai-sync`'s MCP render.

Plain `python3 bin/tests/test_ai_sync_mcp.py` — no pytest, matching the sibling
suites, because the interpreter this tool runs under has no third-party packages.

The bug these pin down: do_render_mcp wrote one `desired` dict to every target.
That is correct only for Cursor, which infers a remote server's transport from
`url`. The other three refuse to — `claude mcp list` reports

    [context7] Skipped — has a "url" but no "type"; add "type": "http"

and drops the server while still calling the config valid, so the tool simply
has no context7 and nothing says why. `copilot mcp add --transport http` and VS
Code both write type:http themselves. _typed() supplies it per target so
mcp.json stays tool-neutral.

VS Code is also the one target with no foreignness signal -- this repo links
nothing into its config dir -- so the `servers` gate is what keeps a tree that
ships no canonical servers from rendering an empty set over another tree's work.
That gate is asserted here too, because this repo is exactly such a tree.

This repo's own mcp.json ships no servers, so the whole defect is invisible when
exercised against it — these build a canonical file that has one stdio and one
remote entry, which is the input that can actually fail.

Runs against throwaway dirs. Never the real HOME: the code under test overwrites
live tool config.
"""

import json
import os
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


def load_tool():
    return SourceFileLoader("aisync", str(REPO / "bin" / "ai-sync")).load_module()


CANONICAL = {
    "mcpServers": {
        "local-one": {"command": "serena", "args": ["start-mcp-server"]},
        "remote-one": {"url": "https://mcp.example.com/mcp"},
    }
}


def main():
    with tempfile.TemporaryDirectory() as td:
        home, repo = Path(td) / "home", Path(td) / "repo"
        (home / ".cursor").mkdir(parents=True)
        (home / ".copilot").mkdir(parents=True)
        repo.mkdir(parents=True)
        (repo / "mcp.json").write_text(json.dumps(CANONICAL), encoding="utf-8")

        m = load_tool()
        m.REPO, m.HOME = repo, home
        m.CURSOR, m.COPILOT = home / ".cursor", home / ".copilot"
        m.CLAUDE, m.CLAUDE_JSON = home / ".claude", home / ".claude.json"
        m._backup_dir = None
        # vscode_user_dir() reads APPDATA on Windows, which points at the real
        # user profile; without this the suite would write live config there.
        saved_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = str(home / "AppData" / "Roaming")
        try:
            vsdir = m.vscode_user_dir()
            assert home in vsdir.parents, f"vscode dir escaped the sandbox: {vsdir}"
            vsdir.mkdir(parents=True)
            m.do_render_mcp()
        finally:
            if saved_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = saved_appdata

        cursor = json.loads((home / ".cursor" / "mcp.json").read_text())["mcpServers"]
        copilot = json.loads((home / ".copilot" / "mcp-config.json").read_text())["mcpServers"]
        claude = json.loads((home / ".claude.json").read_text())["mcpServers"]
        vscode_raw = json.loads((vsdir / "mcp.json").read_text())
        vscode = vscode_raw["servers"]

        # Vacuity guard: a skipped render leaves no file, and every assertion
        # below would then fail on a KeyError rather than pass silently.
        check("all four targets were actually written",
              sorted(cursor) == sorted(copilot) == sorted(claude) == sorted(vscode), True)

        check("VS Code is keyed on `servers`, not `mcpServers`",
              sorted(vscode_raw), ["servers"])
        check("VS Code gets an explicit type on a remote entry",
              vscode["remote-one"].get("type"), "http")

        check("Cursor leaves a remote entry untyped (it infers from url)",
              "type" in cursor["remote-one"], False)
        check("Copilot gets an explicit type on a remote entry",
              copilot["remote-one"].get("type"), "http")
        check("Claude gets an explicit type on a remote entry",
              claude["remote-one"].get("type"), "http")

        stdio = CANONICAL["mcpServers"]["local-one"]
        check("stdio entries are passed through untouched, every target",
              [cursor["local-one"], copilot["local-one"],
               claude["local-one"], vscode["local-one"]],
              [stdio, stdio, stdio, stdio])

        check("canonical mcp.json is not mutated in place",
              json.loads((repo / "mcp.json").read_text()), CANONICAL)

    # A tree that ships no servers -- this one -- must leave VS Code alone
    # rather than render {} over whatever tree is actually driving it.
    with tempfile.TemporaryDirectory() as td:
        home, repo = Path(td) / "home", Path(td) / "repo"
        (home / ".cursor").mkdir(parents=True)
        (home / ".copilot").mkdir(parents=True)
        repo.mkdir(parents=True)
        (repo / "mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")

        m = load_tool()
        m.REPO, m.HOME = repo, home
        m.CURSOR, m.COPILOT = home / ".cursor", home / ".copilot"
        m.CLAUDE, m.CLAUDE_JSON = home / ".claude", home / ".claude.json"
        m._backup_dir = None
        saved_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = str(home / "AppData" / "Roaming")
        try:
            vsdir = m.vscode_user_dir()
            vsdir.mkdir(parents=True)
            incumbent = '{"servers": {"driven-by-another-tree": {"url": "https://x/mcp"}}}'
            (vsdir / "mcp.json").write_text(incumbent, encoding="utf-8")
            m.do_render_mcp()
            check("an empty canonical set leaves VS Code's file untouched",
                  (vsdir / "mcp.json").read_text(), incumbent)
        finally:
            if saved_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = saved_appdata

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s): " + ", ".join(FAILURES[:4]))
        return 1
    print("0 failure(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
