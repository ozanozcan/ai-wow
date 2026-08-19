#!/usr/bin/env bash
# Session-open marker — Claude Code + Cursor entrypoint.
# ai-sync registers this as SessionStart / sessionStart.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$HERE/session-start-marker.py"
