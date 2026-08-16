#!/usr/bin/env python3
"""PostToolUse hook — keep a mow tracker.json's `updated` field honest.

TRACKER.md's contract says every write to `dispatch/tracker.json` also bumps
`updated`. Orchestrators forget: a live FTM run was observed rewriting the file
every few seconds while the field sat 19 minutes stale, which made the board's
staleness indicator call a healthy run behind. The field is mechanical, so stamp
it mechanically instead of relying on the writer to remember.

Deliberately narrow: only a file literally named tracker.json, inside a
`dispatch/` directory, whose JSON is an object carrying `waves`. Anything else
is left alone. Never raises and never blocks the tool — a tracker is disposable
run state and must never fail a run.
"""

import datetime
import json
import os
import sys


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_input = payload.get("tool_input") or {}
    tool_response = payload.get("tool_response") or {}
    path = tool_response.get("filePath") or tool_input.get("file_path") or ""
    if not path or os.path.basename(path) != "tracker.json":
        return

    parts = path.replace("\\", "/").split("/")
    if "dispatch" not in parts:
        return

    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return                      # mid-write or malformed — leave it be

    if not isinstance(data, dict) or "waves" not in data:
        return                      # not a mow board

    stamp = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    if data.get("updated") == stamp:
        return                      # already current to the second

    data["updated"] = stamp
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
    except Exception:
        return


main()
