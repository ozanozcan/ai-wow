#!/usr/bin/env python3
"""Regression tests for `ai-sync`'s text encoding.

Plain `python3 bin/tests/test_ai_sync_encoding.py` — no pytest, matching the
sibling suites, because the interpreter this tool runs under has no
third-party packages.

The bug these pin down: every text read and write in `bin/ai-sync` was bare —
`path.read_text()`, `path.write_text(s)` — and a bare call uses the *locale*
encoding rather than UTF-8. On macOS and Linux the locale encoding is UTF-8
anyway, so the defect was invisible on the machine this tool was written on.
On Windows it is cp1252: most bytes decode to the wrong character with no
error at all, and a character cp1252 cannot encode raises on the way out.

The published tree fixed the identical defect at six call sites in its
`test_repo_shape.py` on 2026-09-01, found by running the Windows CI matrix
for the first time. The same fix was owed in `bin/ai-sync` itself, in both
trees, and had been carried as an open thread since: the managed-doc render
reads `docs/workflow/` core files during a sync, and every one of those
carries non-ASCII bytes, so it is not a hypothetical.

**This file is shared between the two harness trees and classified `match` in
`bin/tests/tree-drift.json` — the copies must stay byte-identical.** It is
written to depend only on what both trees have: `REPO`, `local_config`,
`load_json`, `write_json`, `render_managed_doc`, and a `docs/workflow/`
core doc. Nothing here hardcodes a call-site count or a line number, so it
keeps working as either tree's `ai-sync` grows.

Two layers, because neither alone is worth much:

- The behavioural checks run ai-sync's own readers in a subprocess pinned to
  an ASCII locale, which makes the bug FIRE on this machine. Without that
  pinning they are green before and after the fix and prove nothing. ASCII
  raises where cp1252 mangles silently, but the cause under test is the one
  both share: the call site asked the locale instead of naming UTF-8.
- The AST check covers every call site in the file, including the ones that
  would need a whole rendered repo to exercise. It is the layer that stays
  true as the file grows: a bare `read_text()` added next month fails here.

If the ASCII sandbox cannot be established (some interpreter builds force
UTF-8 mode on), the behavioural layer prints SKIP and says so rather than
passing quietly — a check that cannot fire must not read as coverage. The AST
layer still runs and is the real guarantee.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
AI_SYNC = REPO / "bin" / "ai-sync"
FAILURES = []

# A character that is *not* representable in ASCII and not in cp1252 either,
# so the same fixture exercises both the raise-on-read and the raise-on-write
# halves of the defect. U+011F LATIN SMALL LETTER G WITH BREVE.
NON_ASCII = "ğ"


def check(label, got, want):
    if got == want:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label} — got {got!r}, want {want!r}")
        FAILURES.append(label)


# ---------------------------------------------------------------------------
# layer 1 — AST: no locale-dependent text decoding anywhere in the harness
# ---------------------------------------------------------------------------

TEXT_IO = {"read_text", "write_text"}
# subprocess in text mode decodes the child's output with the locale encoding
# too, exactly like a bare read_text. Every one of these call sites runs git
# and reads back paths, refs and config values.
TEXT_MODE_KWARGS = {"text", "universal_newlines"}


def scanned_files():
    """The harness's own Python surface: the sync tool and every hook.

    A glob rather than a hardcoded list, because the two trees do not carry
    the same set of hooks and this file is byte-identical in both.
    """
    files = [REPO / "bin" / "ai-sync"]
    files += sorted((REPO / "hooks").glob("*.py"))
    return [f for f in files if f.is_file()]


def _opens_in_binary(node: ast.Call) -> bool:
    """True for open(..., 'rb') / open(..., mode='wb') — no encoding wanted."""
    modes = [a for a in node.args[1:2]] + [
        k.value for k in node.keywords if k.arg == "mode"]
    return any(isinstance(m, ast.Constant) and isinstance(m.value, str)
               and "b" in m.value for m in modes)


def _in_text_mode(node: ast.Call) -> bool:
    """True for subprocess calls asking for str output via text/universal_newlines."""
    return any(kw.arg in TEXT_MODE_KWARGS
               and isinstance(kw.value, ast.Constant) and kw.value.value is True
               for kw in node.keywords)


def _names_encoding(node: ast.Call) -> bool:
    return any(kw.arg == "encoding" for kw in node.keywords)


def _classify(node: ast.Call):
    """Return a short label if this call decodes text, else None."""
    fn = node.func
    name = fn.attr if isinstance(fn, ast.Attribute) else (
        fn.id if isinstance(fn, ast.Name) else None)
    if name in TEXT_IO:
        return name
    if name == "open" and not _opens_in_binary(node):
        return "open"
    # subprocess.run / check_output / Popen(..., text=True)
    if name in {"run", "check_output", "Popen"} and _in_text_mode(node):
        return f"subprocess.{name}(text=True)"
    return None


def scan_sites():
    """(relpath, label, lineno, names_encoding) for every text-decoding call."""
    out = []
    for f in scanned_files():
        rel = f.relative_to(REPO).as_posix()
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            label = _classify(node)
            if label:
                out.append((rel, label, node.lineno, _names_encoding(node)))
    return out


# ---------------------------------------------------------------------------
# layer 2 — behavioural: run the real readers under an ASCII locale
# ---------------------------------------------------------------------------

CHILD = r'''
import json, locale, sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

ai_sync_path, tmp = sys.argv[1], Path(sys.argv[2])
result = {"preferred": locale.getpreferredencoding(False)}

m = SourceFileLoader("aisync_under_test", ai_sync_path).load_module()

# local_config() reads a fixed module-level path; point it at the fixture.
m.LOCAL_CONFIG = tmp / "local.config.json"
try:
    result["local_config"] = m.local_config()
except Exception as exc:
    result["local_config_error"] = type(exc).__name__

# load_json() is the shared reader every rendered config file goes through.
try:
    result["load_json"] = m.load_json(tmp / "settings.json", "DEFAULT")
except Exception as exc:
    result["load_json_error"] = type(exc).__name__

# render_managed_doc() reads this repo's REAL docs/workflow/ core file, which
# carries hundreds of non-ASCII bytes. tmp has no .taskman.toml, so there is
# no slug and no front file — this isolates the core-body read.
try:
    rendered = m.render_managed_doc(tmp, "work-loop.md")
    result["render_nonascii"] = bool(rendered) and any(ord(c) > 127 for c in rendered)
except Exception as exc:
    result["render_error"] = type(exc).__name__

print(json.dumps(result))
'''


def run_under_ascii_locale(tmp: Path):
    """Execute CHILD with the locale encoding pinned away from UTF-8."""
    child = tmp / "child.py"
    child.write_text(CHILD, encoding="utf-8")
    env = dict(os.environ)
    env.update(LC_ALL="C", LANG="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0")
    env.pop("PYTHONIOENCODING", None)
    proc = subprocess.run(
        [sys.executable, "-X", "utf8=0", str(child),
         str(AI_SYNC), str(tmp), NON_ASCII],
        capture_output=True, text=True, encoding="utf-8", env=env,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return {"crashed": (proc.stderr or "").strip().splitlines()[-1:]}
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main():
    print("ai-sync encoding")

    print("\n AST — every text-decoding call in the harness names an encoding")
    files = scanned_files()
    sites = scan_sites()
    # Two anti-vacuity checks. If the glob stopped matching, or the code
    # stopped decoding text entirely, "no bare sites" would pass while
    # guarding nothing at all.
    check("the scan found files to check", len(files) > 1, True)
    check("there are text-decoding sites to get wrong", len(sites) > 0, True)
    bare = [s for s in sites if not s[3]]
    for rel, label, line, _ in bare:
        print(f"        bare {label} at {rel}:{line}")
    check("no locale-dependent text decoding in the harness",
          [f"{rel}:{line}" for rel, _, line, _ in bare], [])

    print("\n behaviour — ai-sync's own readers under a non-UTF-8 locale")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        # ensure_ascii=False is load-bearing: json.dumps escapes non-ASCII to
        # \uXXXX by default, which would write a pure-ASCII fixture and make
        # every check below pass without ever exercising the defect.
        (tmp / "local.config.json").write_text(
            json.dumps({"managed_repos": ["~/pro" + NON_ASCII + "ects"]},
                       ensure_ascii=False),
            encoding="utf-8")
        (tmp / "settings.json").write_text(
            json.dumps({"hooks": {"note": NON_ASCII}}, ensure_ascii=False),
            encoding="utf-8")
        for f in ("local.config.json", "settings.json"):
            raw = (tmp / f).read_bytes()
            check(f"fixture {f} really carries non-ASCII bytes",
                  any(b > 127 for b in raw), True)

        r = run_under_ascii_locale(tmp)

        if "crashed" in r:
            check("child process ran", r, "no crash")
        elif r.get("preferred", "").lower().replace("-", "") in ("utf8", "utf_8"):
            print("  SKIP  this interpreter forces UTF-8 mode "
                  f"(preferred={r['preferred']!r}); the ASCII sandbox could not "
                  "be established, so these checks would pass without firing. "
                  "The AST layer above is the guarantee here.")
        else:
            check("sandbox really is non-UTF-8 (else the rest is vacuous)",
                  r.get("preferred", "").lower().replace("-", "") not in
                  ("utf8", "utf_8"), True)
            check("local_config() reads a non-ASCII value, no error",
                  r.get("local_config"),
                  {"managed_repos": ["~/pro" + NON_ASCII + "ects"]})
            check("load_json() reads a non-ASCII value, no fallback",
                  r.get("load_json"), {"hooks": {"note": NON_ASCII}})
            check("render_managed_doc() reads the real work-loop.md body",
                  r.get("render_nonascii"), True)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s): " + ", ".join(FAILURES[:4]))
        return 1
    print("0 failure(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
