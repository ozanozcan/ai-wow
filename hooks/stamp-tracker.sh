#!/usr/bin/env bash
# mow tracker.json `updated` stamper — Claude Code + Cursor entrypoint.
# ai-sync registers this as PostToolUse (Write|Edit) / afterFileEdit.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$HERE/stamp-tracker.py"
