#!/usr/bin/env python3
"""PreToolUse(Bash) hook: refuse an exit status read through a pass-through pipe.

`cmd | tail -5; echo "rc=$?"` reports *tail's* status, which is 0 whatever `cmd`
did. The command prints a plausible `rc=0` and the session reports success. This
is L18/L47, and it is the rare lesson that prose demonstrably cannot hold: across
3439 real Bash calls in this harness the correct `${PIPESTATUS[0]}` form appears
34 times and this defect appears 52 times, so the rule was known and still missed
— a recall failure at composition time, not a knowledge gap.

What makes it worth a hard deny rather than a warning is *what* it measures. The
hits cluster on exactly the commands that produce verdicts:

    uv run pytest -q 2>&1 | tail -3;        echo "pytest=$?"
    git push origin master 2>&1 | tail -25; echo "push exit=$?"
    diff -rq a b | head;                    echo "exit=$? (0 = identical)"

That last one can never report anything but identical. The failure mode is silent
and it corrupts the answer to "did it work?", so the agent cannot catch it by
reading its own output.

A PreToolUse hook cannot rewrite a command — the contract is allow/deny plus a
reason — but the reason is shown to Claude, so a deny costs one round trip and
zero operator attention, and the corrected command is not flagged again.

Fails open — a crash here must never block a session.
"""

from __future__ import annotations

import json
import re
import sys

# Filters that succeed regardless of their input, so $? after them is a constant.
PASSTHROUGH = {
    "tail", "head", "cat", "tee", "sed", "awk", "tr", "cut", "sort", "uniq",
    "nl", "fold", "rev", "column", "paste", "wc", "xargs",
}

# `grep`, `jq`, `python3`, `diff`, `test` can all return a status the caller
# legitimately wants, so a pipeline ending in one of those is never flagged.

HEREDOC_OPEN = re.compile(r"<<-?\s*'?\"?([A-Za-z_][A-Za-z0-9_]*)'?\"?")
SEGMENT_SPLIT = re.compile(r";|&&|\|\||\n")
# `||` is consumed by SEGMENT_SPLIT before this runs, so a plain split is
# exact here; guarding against it would be a branch no input can reach.
PIPE_SPLIT = re.compile(r"\|")
COMMAND_WORD = re.compile(r"([A-Za-z0-9_./-]+)")


def strip_heredocs(command: str) -> str:
    """Drop heredoc bodies — embedded Python is not shell and must not be scanned."""
    lines = command.split("\n")
    kept: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        opener = HEREDOC_OPEN.search(line)
        if opener:
            tag = opener.group(1)
            i += 1
            while i < len(lines) and lines[i].strip() != tag:
                i += 1
        i += 1
    return "\n".join(kept)


def offending_filter(command: str) -> tuple[str, str] | None:
    """Return (pipeline, filter) when $? is read through a pass-through pipe."""
    text = strip_heredocs(command)

    # Already doing it right, or opted into pipefail — no opinion either way.
    if re.search(r"pipestatus", text, re.IGNORECASE):
        return None
    if re.search(r"\bpipefail\b", text):
        return None

    segments = SEGMENT_SPLIT.split(text)
    for index, segment in enumerate(segments):
        if index == 0 or "$?" not in segment:
            continue
        previous = segments[index - 1]
        # `|&` is zsh's stderr pipe; normalise it so the tail parses.
        parts = PIPE_SPLIT.split(previous.replace("|&", "|"))
        if len(parts) < 2:
            continue
        word = COMMAND_WORD.match(parts[-1].strip())
        if not word:
            continue
        name = word.group(1).split("/")[-1]
        if name in PASSTHROUGH:
            return previous.strip(), name
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        command = (payload.get("tool_input") or {}).get("command") or ""
    except Exception:
        print("{}")
        return 0

    try:
        found = offending_filter(command)
    except Exception:
        print("{}")
        return 0

    if not found:
        # No opinion, rather than an affirmative allow — the same reasoning as
        # guard-destructive: an explicit allow would approve every command this
        # hook merely failed to understand.
        print("{}")
        return 0

    pipeline, name = found
    reason = (
        f"`$?` here is `{name}`'s status, not the command you are measuring — "
        f"`{name}` succeeds on any input, so this reports success unconditionally.\n"
        f"  pipeline: {pipeline[:160]}\n"
        f"Use ${{PIPESTATUS[0]}} (zsh: ${{pipestatus[1]}}), or test the command "
        f"before any pipe. If you deliberately want {name}'s status, add "
        f"`set -o pipefail` and this check stands down."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
