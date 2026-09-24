#!/usr/bin/env bash
# git-operation logger — Claude Code entrypoint.
# ai-sync registers this as PostToolUse (Bash) and PostToolUseFailure (Bash).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$HERE/git-ops.py"
