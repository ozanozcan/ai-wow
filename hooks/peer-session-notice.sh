#!/usr/bin/env bash
# Peer-session notice — Claude Code + Cursor entrypoint.
# ai-sync registers this; see hooks.def.json for the events.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$HERE/peer-session-notice.py"
