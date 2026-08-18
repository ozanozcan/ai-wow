#!/usr/bin/env python3
"""Render a mow board as a chat-widget fragment, derived from tracker.html.

The chat board and the browser board are the same board. This script does not
reimplement the compact view — it *derives* it from tracker.html, so the two
surfaces cannot drift: change a colour or a hub in tracker.html and the next
widget carries it. What it strips is everything a chat message cannot use.

  - the embedded Onest face (43KB of base64). The widget inherits the host's
    typeface, which keeps one family per surface — the house rule — and is most
    of the weight saved.
  - the 2s poll. A chat message is a snapshot: the board is inlined at render
    time. The 1s duration ticker stays, so a widget posted mid-wave keeps
    counting its running agents.
  - the header's segmented pickers. Nothing to toggle in a transcript.

Output goes to stdout as a fragment (no doctype/html/head/body), which is what
`show_widget` wants. Every render is one message's worth of tokens, so keep it
to wave boundaries rather than every write.

    python3 widget.py docs/plans/<stem>/dispatch/tracker.json
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _section(src: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", src, re.S)
    if not m:
        raise SystemExit(f"widget.py: no <{tag}> in tracker.html — layout changed?")
    return m.group(1)


def _strip_font(css: str) -> str:
    """Drop the @font-face rule carrying the base64 payload."""
    return re.sub(r"@font-face\s*\{[^{}]*\}", "", css, flags=re.S)


def _squeeze_css(css: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s*\n\s*", "\n", css)
    return re.sub(r"\n{2,}", "\n", css).strip()


def build(board_path: str, source: str | None = None) -> str:
    src_path = source or os.path.join(HERE, "tracker.html")
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    with open(board_path, encoding="utf-8") as fh:
        board = json.load(fh)

    css = _squeeze_css(_strip_font(_section(src, "style")))
    body = _section(src, "body")
    script = _section(body, "script")

    # compact is the whole point of the chat surface — no query string to read
    script = re.sub(
        r"let VIEW = new URLSearchParams\([^;]*;",
        'let VIEW = "compact";',
        script,
        count=1,
    )
    if 'let VIEW = "compact";' not in script:
        raise SystemExit("widget.py: could not pin VIEW — tracker.html changed?")

    # a snapshot has nothing to fetch; keep the ticker so running agents count on
    script = script.replace(
        "poll();\nsetInterval(poll, POLL_MS);",
        "render(BOARD);\nmarkFresh([BOARD]);",
    )
    if "render(BOARD);" not in script:
        raise SystemExit("widget.py: could not replace the poll bootstrap")

    waves = board.get("waves") or []
    running = [w for w in waves if w.get("status") == "running"]
    summary = "{} — {} of {} wave(s) running, run {}".format(
        board.get("title") or board.get("stem") or "mow run",
        len(running), len(waves), board.get("run_status") or "unknown",
    )

    return (
        f'<h2 class="sr-only">{summary}</h2>\n'
        f"<style>\n{css}\n"
        ".sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}\n"
        ".controls{display:none!important}\n"
        "</style>\n"
        '<div id="app"></div>\n'
        f"<script>\nconst BOARD = {json.dumps(board, separators=(',', ':'))};\n{script}\n</script>"
    )


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    sys.stdout.write(build(sys.argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
