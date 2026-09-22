#!/usr/bin/env python3
"""Regression tests for hooks/guard-shell-status.py.

Plain `python3 hooks/tests/test_guard_shell_status.py` — no pytest, matching
the other hook tests.

What these pin down: the guard denies an exit status read through a filter that
always succeeds, and — the half that decides whether it survives contact — it
stays silent on every shape where `$?` after a pipe is legitimate. A deny that
misfires gets switched off, so the stand-down cases are the real test, and the
corrected form must never be flagged or the agent cannot escape the deny.

The fixtures marked "corpus" are real commands taken from this harness's own
session transcripts, not invented shapes (L54).
"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK_PY = os.path.join(HERE, "..", "guard-shell-status.py")
HOOK_SH = os.path.join(HERE, "..", "guard-shell-status.sh")

spec = importlib.util.spec_from_loader(
    "guard", importlib.machinery.SourceFileLoader("guard", HOOK_PY))
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILURES.append(name)


def decide(command):
    """Drive the real entrypoint, not just the function."""
    payload = json.dumps({
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    out = subprocess.run(["bash", HOOK_SH], input=payload,
                         capture_output=True, text=True, timeout=30).stdout
    return json.loads(out).get("hookSpecificOutput", {}).get(
        "permissionDecision", "none")


def test_denies_status_through_passthrough():
    # corpus: every one of these was really run in this harness
    for cmd in [
        'uv run pytest -q 2>&1 | tail -3; echo "pytest=$?"',
        'sh githooks/pre-push 2>&1 | tail -25; echo "EXIT=$?"',
        'git push origin master 2>&1 | tail -25; echo "=== push exit=$? ==="',
        'git commit -q -F /tmp/m.txt -- a b 2>&1 | tail -3; echo "exit=$?"',
        'diff -rq a b 2>&1 | head -10; echo "exit=$? (0 = identical)"',
        'python3 bin/ai-sync status 2>&1 | head -40; echo "exit=$?"',
        'taskman/.venv/bin/python -m taskman wrapup gate 2>&1 | tail -4; echo "EXIT=$?"',
        'HOME="$H" python3 bin/ai-sync status | sed -n "1,4p" | sed "s/^/ /"; echo "exit: $?"',
        # zsh's `|&` is `2>&1 |`; without normalising it the tail parses as `&`
        # and the whole pipeline reads as unpiped.
        'uv run pytest -q |& tail -3; echo "rc=$?"',
    ]:
        check(f"deny: {cmd[:52]}", decide(cmd) == "deny", cmd)


def test_stands_down_when_status_is_real():
    for label, cmd in [
        ("corrected with PIPESTATUS",
         'uv run pytest -q 2>&1 | tail -3; echo "rc=${PIPESTATUS[0]}"'),
        ("corrected with zsh pipestatus",
         'git push 2>&1 | tail -25; echo "rc=${pipestatus[1]}"'),
        # corpus: pipestatus with a $? fallback -- the only shape that reaches
        # the exclusion, since the others contain no literal `$?` at all.
        ("pipestatus with a $? fallback",
         'git push origin master 2>&1 | tail -25; echo "exit: ${pipestatus[1]:-$?}"'),
        # `$?` BEFORE the pipeline: segment 0 has no predecessor to measure.
        ("$? precedes the pipeline",
         'echo "rc=$?"; cat x | tail -1'),
        ("deliberate pipefail",
         'set -o pipefail; uv run pytest 2>&1 | tail -3; echo "rc=$?"'),
        ("grep -q status is meaningful",
         'cat f | grep -q needle; echo "found=$?"'),
        ("jq status is meaningful",
         'cat f.json | jq -e .key; echo "has=$?"'),
        ("python status is meaningful",
         'cat in | python3 check.py; echo "rc=$?"'),
        ("no pipeline at all",
         'uv run pytest -q; echo "rc=$?"'),
        ("bare $? with no pipeline anywhere",
         'echo "rc=$?"'),
    ]:
        check(f"stand down: {label}", decide(cmd) == "none", cmd)


def test_heredoc_body_is_not_shell():
    # A python heredoc mentioning $? or a `path=` assignment is not shell and
    # must not be scanned -- the only thing a naive scan matched in 3439 real
    # commands was embedded Python.
    cmd = 'python3 <<PY\nimport x\npath = "a"\nprint("$?")\nPY'
    check("heredoc python ignored", decide(cmd) == "none", cmd)
    # The body must contain a pipe AND a later `$?`, or stripping is a no-op
    # and the fixture proves nothing.
    piped = 'python3 <<PY\nrows = a | tail\nprint("rc=$?")\nPY'
    check("heredoc with a pipe in the body ignored", decide(piped) == "none", piped)


def test_denies_dead_or_branch_after_passthrough():
    """L47's own example, which the `$?` rule above cannot see.

    `cmd | sed -n 1p || echo absent` never prints `absent` -- sed succeeds on
    empty input, so the fallback is unreachable and the absence it claims was
    never established. There is no `$?` anywhere in these, so the original rule
    misses every one. Measured over 23890 real Bash calls from this harness's
    transcripts: 234 hits, 0.98%, 213 distinct.

    Paths are neutralised for publication (this tree is the published one and
    its shape gate rejects personal paths) — the command SHAPES are verbatim
    from the corpus, only the directory names are swapped.
    """
    # corpus: every one of these was really run in this harness
    for cmd in [
        'grep -rln "full case is in" ~/Desktop/notes --include="*.md" 2>/dev/null | head -3 || echo "claim not present"',
        'git -C ../sibling-tree remote -v | head -2 || echo "(no remote)"',
        'grep -n "status:" docs/checkpoints/gate-1.md 2>/dev/null | head -2 || echo "  file gone"',
        'ls board/ 2>/dev/null | head -5 || echo "(no board dir)"',
        'ls -d ~/Desktop/some-project 2>/dev/null | sed "s/^/  local Django repo: /" || echo absent',
        'uv run python -m taskman board --feature 692 2>&1 | head -20 || uv run python -m taskman board 2>&1 | head -30',
        'pgrep -fl "uvicorn|next dev" 2>/dev/null | head -3 || echo "(nothing running)"',
        'git diff --cached --name-status | head || echo "(index empty)"',
    ]:
        check(f"deny ||: {cmd[:52]}", decide(cmd) == "deny", cmd)


def test_stands_down_on_reachable_or_branches():
    """The half that decides whether the rule survives contact.

    Each of these has a `||` after a pipe that CAN fire, so a deny here would be
    a false positive -- and a deny that misfires gets switched off.
    """
    for label, cmd in [
        # corpus: `(A && B) || C` runs C when A fails. Splitting on && and
        # looking only at B is the false positive this excludes.
        ("|| after an && chain is reachable",
         'ls -d docs/action-reports 2>/dev/null && ls docs/action-reports | tail -5 || echo "does not exist yet"'),
        # corpus: the one PASSTHROUGH member whose status is not a constant --
        # xargs returns 123-127 when its child fails, so this || can really run.
        ("xargs propagates its child's status",
         'lsof -ti tcp:8399 | xargs -I{} kill {} 2>/dev/null || echo "nothing to kill"'),
        ("grep status is meaningful",
         'grep -q needle file || echo absent'),
        ("jq status is meaningful",
         'cat f.json | jq -e .key || echo "key missing"'),
        ("no pipe at all",
         'test -f x || echo missing'),
        # corpus: `if [ "$X" = "a$(... | cut -c8-)" ] || cmd` -- the pipe lives
        # inside a substitution, and the || is the test's own fallback.
        ("pipe inside a command substitution",
         'if [ "$H" = "f378998$(git rev-parse HEAD | cut -c8-)" ] || git log -1 --format=%s | grep -q "^mow"; then echo y; fi'),
        ("deliberate pipefail",
         'set -o pipefail; cat f | head -1 || echo absent'),
        ("corrected with pipestatus",
         'cat f | head -1; [ "${pipestatus[1]}" -eq 0 ] || echo absent'),
    ]:
        check(f"stand down ||: {label}", decide(cmd) == "none", cmd)


def test_fails_open():
    for label, payload in [("malformed json", "not json at all"),
                           ("empty payload", "{}"),
                           ("no command key", '{"tool_input": {}}')]:
        out = subprocess.run(["bash", HOOK_SH], input=payload,
                             capture_output=True, text=True, timeout=30).stdout
        check(f"fail open: {label}", json.loads(out) == {}, out)


def test_reason_names_the_fix():
    payload = json.dumps({"tool_input": {
        "command": 'uv run pytest -q 2>&1 | tail -3; echo "rc=$?"'}})
    out = subprocess.run(["bash", HOOK_SH], input=payload,
                         capture_output=True, text=True, timeout=30).stdout
    reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
    # The deny is only useful if it says how to escape it.
    check("reason names PIPESTATUS", "PIPESTATUS" in reason, reason)
    # zsh leaves PIPESTATUS unset, so naming only the bash form would trade a
    # wrong `0` for a silent empty string. Both forms must appear.
    check("reason names the zsh form", "pipestatus[1]" in reason, reason)
    check("reason warns PIPESTATUS is empty in zsh",
          "EMPTY STRING" in reason and "zsh" in reason, reason)
    check("reason names the filter", "tail" in reason, reason)
    check("reason names the pipefail opt-out", "pipefail" in reason, reason)


if __name__ == "__main__":
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        print(fn.__name__)
        fn()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("all passed")
