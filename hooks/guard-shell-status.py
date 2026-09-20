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

# `xargs` is the one PASSTHROUGH member whose status is not a constant: it
# returns 123-127 when the command it runs fails. For the `$?` rule that is
# still a defect (the status measured is not the upstream command's), but a
# `| xargs cmd || fallback` CAN reach its fallback, so the `||` rule exempts it.
# One hit in 23890 corpus commands, hand-checked.
OR_EXEMPT = {"xargs"}

SUBST = re.compile(r"\$\([^()]*\)")

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


def strip_substitutions(text: str) -> str:
    """Blank out `$( )` bodies before scanning for `||`.

    `if [ "$H" = "a$(git rev-parse HEAD | cut -c8-)" ] || cmd` otherwise reads as
    a pipeline ending in `cut`, and the `||` is the test's own fallback. Scanning
    inside a substitution is given up deliberately: a dead branch in there is
    missed, which is the safe direction — a deny that misfires gets switched off.
    """
    previous = None
    while previous != text:
        previous = text
        text = SUBST.sub(" ", text)
    return text


def dead_or_branch(command: str) -> tuple[str, str] | None:
    """Return (pipeline, filter) when a trailing `|| ...` can never run.

    `cmd | sed -n 1p || echo absent` never prints `absent`: sed succeeds on empty
    input, so the pipeline's status is 0 and the fallback is unreachable. The
    command then reports absence it never established, and the empty output
    reads as proof of it.

    This is L47's own worked example, and `offending_filter` cannot see it —
    there is no `$?` anywhere in the shape. Measured over 23890 real Bash calls
    from this harness's transcripts: 234 hits, 0.98%, 213 distinct, one false
    positive (the xargs shape, now exempt).
    """
    text = strip_heredocs(command)

    if re.search(r"pipestatus", text, re.IGNORECASE):
        return None
    if re.search(r"\bpipefail\b", text):
        return None

    text = strip_substitutions(text)

    for match in re.finditer(r"\|\|", text):
        # Bound the pipeline at the nearest separator, including an earlier `||`.
        segment = re.split(r";|\n|\|\|", text[: match.start()])[-1]
        # `(A && B) || C` runs C when A fails, so that fallback is reachable.
        if "&&" in segment:
            continue
        parts = PIPE_SPLIT.split(segment.replace("|&", "|"))
        if len(parts) < 2:
            continue
        word = COMMAND_WORD.match(parts[-1].strip())
        if not word:
            continue
        name = word.group(1).split("/")[-1]
        if name in PASSTHROUGH and name not in OR_EXEMPT:
            return segment.strip(), name
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
        kind = "status"
        if not found:
            found = dead_or_branch(command)
            kind = "dead-branch"
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
    if kind == "dead-branch":
        reason = (
            f"This `||` can never run: `{name}` succeeds on any input, empty "
            f"included, so the pipeline's status is always 0.\n"
            f"  pipeline: {pipeline[:160]}\n"
            f"Whatever the fallback says — absent, none, not found — is a claim "
            f"this command cannot establish, and its empty output then reads as "
            f"proof of it. Test the condition itself before any pipe "
            f"(`if [ -d \"$p\" ]`, `grep -q`), or read the pipe-status array. "
            f"MIND THE SHELL: zsh (this harness's default) wants "
            f"${{pipestatus[1]}} (lowercase, 1-indexed); bash wants "
            f"${{PIPESTATUS[0]}}. `set -o pipefail` stands this check down."
        )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            },
        }))
        return 0

    reason = (
        f"`$?` here is `{name}`'s status, not the command you are measuring — "
        f"`{name}` succeeds on any input, so this reports success unconditionally.\n"
        f"  pipeline: {pipeline[:160]}\n"
        f"Use your shell's pipe-status array, or test the command before any "
        f"pipe. MIND THE SHELL: in zsh (this harness's default) PIPESTATUS is "
        f"unset, so ${{PIPESTATUS[0]}} expands to the EMPTY STRING and reports "
        f"nothing at all — zsh wants ${{pipestatus[1]}} (lowercase, 1-indexed); "
        f"bash wants ${{PIPESTATUS[0]}}. If you deliberately want {name}'s "
        f"status, add `set -o pipefail` and this check stands down."
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
