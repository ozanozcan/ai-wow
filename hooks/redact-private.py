#!/usr/bin/env python3
"""Strip <private>…</private> spans from a session transcript before it is archived.

The SessionEnd chain copies the raw transcript JSONL into docs/chat-history/ and
ships it to object storage, so anything said in a session is committed and
uploaded verbatim. This is the choke point that lets a session opt content out:
wrap it in <private>…</private> and it never leaves the machine.

Runs in the global wrapper rather than in each repo's scripts/archive-session.sh,
so every consumer of the payload — the local copy, the MinIO upload, the taskman
session record — sees the redacted transcript, and per-repo implementations need
no change.

Two modes:
  (default)        hook payload on stdin -> sanitized transcript written to a
                   temp file, payload with transcript_path repointed on stdout.
  --file SRC DST   sanitize SRC to DST. Used by the tests.

Privacy fails CLOSED: if the transcript cannot be sanitized, nothing is written
to stdout, so the caller skips archiving rather than archiving unredacted text.
Session end is never blocked either way — the caller always exits 0.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile

# The marker must not itself contain the tag, or the unclosed-fence pass below
# matches its own output and swallows the rest of the line.
MARKER = "[REDACTED: private block]"

# Closed spans first; the second pattern then sweeps an unclosed <private> to the
# end of the string. An unterminated fence redacts *more*, never less.
CLOSED = re.compile(r"<private\s*>.*?</private\s*>", re.IGNORECASE | re.DOTALL)
UNCLOSED = re.compile(r"<private\s*>.*", re.IGNORECASE | re.DOTALL)


class Redactor:
    def __init__(self) -> None:
        self.count = 0

    def text(self, s: str) -> str:
        if "<private" not in s.lower():
            return s
        s, n1 = CLOSED.subn(MARKER, s)
        s, n2 = UNCLOSED.subn(MARKER, s)
        self.count += n1 + n2
        return s

    def walk(self, obj):
        """Recurse over every string in the record.

        Deliberately blunt: message text, tool inputs, and tool results all get
        the same treatment, so a fence works wherever it is written — including
        inside a file the agent happened to read.
        """
        if isinstance(obj, str):
            return self.text(obj)
        if isinstance(obj, list):
            return [self.walk(v) for v in obj]
        if isinstance(obj, dict):
            return {k: self.walk(v) for k, v in obj.items()}
        return obj


def sanitize(src: str, dst: str) -> int:
    """Rewrite JSONL src into dst with private spans removed. Returns span count."""
    r = Redactor()
    with open(src, "r", encoding="utf-8", errors="replace") as fin, \
         open(dst, "w", encoding="utf-8") as fout:
        for line in fin:
            stripped = line.strip()
            if not stripped:
                fout.write(line)
                continue
            try:
                record = json.loads(stripped)
            except (ValueError, UnicodeDecodeError):
                # Unparseable line: fall back to a raw text sweep rather than
                # passing it through. JSON does not escape < or >, so the fence
                # is still literal here.
                fout.write(r.text(line))
                continue
            fout.write(json.dumps(r.walk(record), ensure_ascii=False) + "\n")
    return r.count


def main(argv: list[str]) -> int:
    if len(argv) == 4 and argv[1] == "--file":
        n = sanitize(argv[2], argv[3])
        if n:
            print(f"redact-private: removed {n} private span(s)", file=sys.stderr)
        return 0

    raw = sys.stdin.read()
    payload = json.loads(raw)
    src = payload.get("transcript_path") or ""
    if not src:
        # Nothing to sanitize; hand the payload back untouched.
        print(json.dumps(payload))
        return 0

    fd, dst = tempfile.mkstemp(prefix="redacted-", suffix=".jsonl")
    os.close(fd)
    n = sanitize(src, dst)
    if n:
        print(f"redact-private: removed {n} private span(s)", file=sys.stderr)
    payload["transcript_path"] = dst
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:  # noqa: BLE001 - fail closed, never block session end
        print(f"redact-private: {exc}", file=sys.stderr)
        sys.exit(1)
