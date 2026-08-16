#!/usr/bin/env bash
# Session-open marker — Claude Code + Cursor entrypoint.
# ai-sync registers this as SessionStart / sessionStart.
# Tries python3 first, falls back to python (Windows / some Linux installs).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "")
[ -n "$PYTHON" ] || exit 0
exec "$PYTHON" "$HERE/session-start-marker.py"
