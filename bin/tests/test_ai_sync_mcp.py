#!/usr/bin/env python3
"""Regression tests for `ai-sync`'s MCP render.

Plain `python3 bin/tests/test_ai_sync_mcp.py` — no pytest, matching the sibling
suites, because the interpreter this tool runs under has no third-party packages.

**This file is shared between the two harness trees and classified `match` in
`bin/tests/tree-drift.json` — the copies must stay byte-identical.** The trees
do not render the same target set: the published one also drives Copilot CLI.
So nothing here hardcodes how many targets exist. Copilot is exercised only
where the tree defines it, and the run prints which targets it covered, because
a tree that quietly stopped rendering one must not read as coverage.

The bug these pin down: do_render_mcp built one `desired` dict and wrote it to
every target. That is right only for Cursor, which infers a remote server's
transport from `url` and documents no type on remote entries. Claude Code
refuses to infer it, and does not fail loudly:

    $ claude mcp list
    [context7] Skipped — has a "url" but no "type"; add "type": "http"

The server is dropped, the config still reads as valid, and the tool simply does
not have it. `copilot mcp add --transport http` and VS Code both write type:http
themselves. _typed() supplies the transport per target, so mcp.json stays
tool-neutral: command+args for stdio, url for remote.

VS Code is also the one target with no foreignness signal — neither tree links
anything into its config dir, so there is no symlink to resolve back to the repo
driving it. The `servers` gate carries that weight instead: a tree shipping no
canonical servers renders nothing rather than writing {} over whatever tree is
maintaining the file. One tree ships exactly that, so the gate is asserted here.

Runs against throwaway dirs. Never the real HOME or APPDATA: the code under test
overwrites live tool config, and vscode_user_dir() reads the real environment on
Windows — the platform this target most exists for.
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


def sandbox(m, home, repo):
    """Point every target this tree renders at throwaway dirs.

    Any target left unpatched is written for real, so this returns the list it
    redirected and the caller prints it — an unpatched target must not pass as
    an untested one.
    """
    m.REPO, m.HOME = repo, home
    m.CURSOR = home / ".cursor"
    m.CLAUDE, m.CLAUDE_JSON = home / ".claude", home / ".claude.json"
    covered = ["cursor", "claude", "vscode"]
    (home / ".cursor").mkdir(parents=True)
    if hasattr(m, "COPILOT"):
        m.COPILOT = home / ".copilot"
        (home / ".copilot").mkdir(parents=True)
        covered.insert(1, "copilot")
    m._backup_dir = None
    return covered


def render(m, home):
    """Run do_render_mcp with APPDATA pinned inside the sandbox."""
    saved = os.environ.get("APPDATA")
    os.environ["APPDATA"] = str(home / "AppData" / "Roaming")
    try:
        vsdir = m.vscode_user_dir()
        assert home in vsdir.parents, f"vscode dir escaped the sandbox: {vsdir}"
        vsdir.mkdir(parents=True, exist_ok=True)
        m.do_render_mcp()
        return vsdir
    finally:
        if saved is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = saved


def main():
    with tempfile.TemporaryDirectory() as td:
        home, repo = Path(td) / "home", Path(td) / "repo"
        repo.mkdir(parents=True)
        (repo / "mcp.json").write_text(json.dumps(CANONICAL), encoding="utf-8")

        m = load_tool()
        covered = sandbox(m, home, repo)
        print(f"  targets this tree renders: {', '.join(covered)}")
        vsdir = render(m, home)

        cursor = json.loads((home / ".cursor" / "mcp.json").read_text())["mcpServers"]
        claude = json.loads((home / ".claude.json").read_text())["mcpServers"]
        vscode_raw = json.loads((vsdir / "mcp.json").read_text())
        vscode = vscode_raw["servers"]
        targets = {"cursor": cursor, "claude": claude, "vscode": vscode}
        if "copilot" in covered:
            targets["copilot"] = json.loads(
                (home / ".copilot" / "mcp-config.json").read_text())["mcpServers"]

        # Vacuity guard: a target that was never written has no file to read,
        # so the reads above raise rather than letting a skip look like a pass.
        check("every target this tree renders was written",
              sorted(targets), sorted(covered))
        check("each target carries both canonical servers",
              {n: sorted(t) for n, t in targets.items()},
              {n: ["local-one", "remote-one"] for n in covered})

        check("Cursor leaves a remote entry untyped (it infers from url)",
              "type" in cursor["remote-one"], False)
        for name in [n for n in covered if n != "cursor"]:
            check(f"{name} gets an explicit type on a remote entry",
                  targets[name]["remote-one"].get("type"), "http")

        check("VS Code is keyed on `servers`, not `mcpServers`",
              sorted(vscode_raw), ["servers"])

        stdio = CANONICAL["mcpServers"]["local-one"]
        check("stdio entries are passed through untouched, every target",
              {n: t["local-one"] for n, t in targets.items()},
              {n: stdio for n in covered})

        check("canonical mcp.json is not mutated in place",
              json.loads((repo / "mcp.json").read_text()), CANONICAL)

    # A tree that ships no servers must leave VS Code alone rather than render
    # {} over the tree that is actually driving it.
    with tempfile.TemporaryDirectory() as td:
        home, repo = Path(td) / "home", Path(td) / "repo"
        repo.mkdir(parents=True)
        (repo / "mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")

        m = load_tool()
        sandbox(m, home, repo)
        incumbent = '{"servers": {"driven-by-another-tree": {"url": "https://x/mcp"}}}'
        saved = os.environ.get("APPDATA")
        os.environ["APPDATA"] = str(home / "AppData" / "Roaming")
        try:
            vsdir = m.vscode_user_dir()
            vsdir.mkdir(parents=True, exist_ok=True)
            (vsdir / "mcp.json").write_text(incumbent, encoding="utf-8")
            m.do_render_mcp()
            check("an empty canonical set leaves VS Code's file untouched",
                  (vsdir / "mcp.json").read_text(), incumbent)
        finally:
            if saved is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = saved

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s): " + ", ".join(FAILURES[:4]))
        return 1
    print("0 failure(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
