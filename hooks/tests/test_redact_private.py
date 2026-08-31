#!/usr/bin/env python3
"""Regression tests for hooks/redact-private.py.

Plain `python3 hooks/tests/test_redact_private.py` — no pytest, matching
test_stamp_tracker.py: the interpreter these hooks run under has no
third-party packages.

What these pin down: the SessionEnd chain copies the transcript verbatim into
docs/chat-history/ and uploads it, so a leak here is a leak into git and into
object storage. Every case below is a way content could survive the fence.
"""

import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "redact-private.py")

SECRET = "SUPERSECRET-CANARY-9174"
FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAILURES.append(name)


def run_file_mode(lines):
    """Sanitize a transcript built from `lines` (raw strings). Returns output text."""
    d = tempfile.mkdtemp()
    src, dst = os.path.join(d, "in.jsonl"), os.path.join(d, "out.jsonl")
    with open(src, "w", encoding="utf-8") as f:
        f.write("".join(l if l.endswith("\n") else l + "\n" for l in lines))
    proc = subprocess.run([sys.executable, HOOK, "--file", src, dst],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    with open(dst, encoding="utf-8") as f:
        return f.read()


def test_user_message():
    out = run_file_mode([json.dumps({
        "type": "user",
        "message": {"role": "user", "content": f"keep this <private>{SECRET}</private> and this"},
    })])
    check("user message: secret gone", SECRET not in out, out)
    check("user message: surroundings kept", "keep this" in out and "and this" in out)


def test_queue_operation():
    """The enqueue record carries the raw prompt in a top-level `content` field."""
    out = run_file_mode([json.dumps({
        "type": "queue-operation", "operation": "enqueue",
        "content": f"do the thing <private>{SECRET}</private>",
    })])
    check("queue-operation: secret gone", SECRET not in out, out)


def test_content_blocks_and_tool_results():
    out = run_file_mode([json.dumps({
        "type": "assistant",
        "message": {"content": [
            {"type": "text", "text": f"<private>{SECRET}</private>"},
            {"type": "tool_result", "content": [{"type": "text", "text": f"<private>{SECRET}</private>"}]},
        ]},
    })])
    check("nested blocks + tool_result: secret gone", SECRET not in out, out)


def test_unclosed_fence_redacts_to_end():
    out = run_file_mode([json.dumps({
        "type": "user",
        "message": {"content": f"before <private>{SECRET} and everything after"},
    })])
    check("unclosed fence: secret gone", SECRET not in out, out)
    check("unclosed fence: text before kept", "before" in out)


def test_unparseable_line_still_swept():
    """A line that is not valid JSON must not be passed through verbatim."""
    out = run_file_mode(["{this is not json <private>" + SECRET + "</private>}"])
    check("unparseable line: secret gone", SECRET not in out, out)


def test_multiline_and_case():
    out = run_file_mode([json.dumps({
        "message": {"content": f"a <PRIVATE>line1\nline2 {SECRET}\nline3</PRIVATE> b"},
    })])
    check("multiline + uppercase tag: secret gone", SECRET not in out, out)


def test_clean_transcript_untouched():
    record = {"type": "user", "message": {"content": "nothing sensitive"}}
    out = run_file_mode([json.dumps(record)])
    check("clean transcript: record preserved",
          json.loads(out.strip())["message"]["content"] == "nothing sensitive")


def test_payload_mode_repoints_transcript():
    d = tempfile.mkdtemp()
    src = os.path.join(d, "t.jsonl")
    with open(src, "w", encoding="utf-8") as f:
        f.write(json.dumps({"message": {"content": f"<private>{SECRET}</private>"}}) + "\n")
    payload = {"cwd": d, "session_id": "abc", "transcript_path": src}
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                          capture_output=True, text=True)
    check("payload mode: exit 0", proc.returncode == 0, proc.stderr)
    out = json.loads(proc.stdout)
    check("payload mode: transcript repointed", out["transcript_path"] != src)
    check("payload mode: other fields kept", out["session_id"] == "abc")
    with open(out["transcript_path"], encoding="utf-8") as f:
        check("payload mode: temp copy is clean", SECRET not in f.read())
    with open(src, encoding="utf-8") as f:
        check("payload mode: original untouched", SECRET in f.read())
    os.unlink(out["transcript_path"])


def test_fails_closed_on_missing_transcript():
    """Privacy fails closed: an unreadable transcript emits no payload, so the
    wrapper skips archiving instead of archiving the raw file."""
    payload = {"cwd": "/tmp", "session_id": "abc", "transcript_path": "/nonexistent/nope.jsonl"}
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                          capture_output=True, text=True)
    check("fail closed: non-zero exit", proc.returncode != 0)
    check("fail closed: no payload on stdout", proc.stdout.strip() == "", proc.stdout)


if __name__ == "__main__":
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        print(fn.__name__)
        fn()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("all passed")
