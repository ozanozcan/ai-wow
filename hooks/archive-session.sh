#!/usr/bin/env bash
# Thin wrapper: resolve project root from hook cwd, redact <private> spans from the
# transcript, then exec in-repo archive-session.sh.
# Fail-open — never block session end. The redaction step is the one exception:
# it fails CLOSED (skips archiving) rather than shipping unredacted text, because
# the implementation copies the transcript into the repo and uploads it.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

input=$(cat || true)
[ -n "$input" ] || exit 0

cwd=$(printf "%s" "$input" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
print(d.get(\"cwd\") or \"\")
" 2>/dev/null) || exit 0

[ -n "$cwd" ] && [ -d "$cwd" ] || exit 0

dir=$cwd
root=""
while [ -n "$dir" ] && [ "$dir" != "/" ]; do
  if [ -f "$dir/.taskman.toml" ] && [ -f "$dir/scripts/archive-session.sh" ]; then
    root=$dir
    break
  fi
  dir=$(dirname "$dir")
done

[ -n "$root" ] || exit 0
# Run from the repo root: the implementation writes repo-relative paths
# (docs/chat-history/...) and resolves the taskman slug by walking up from pwd.
cd "$root" || exit 0

# Strip <private>...</private> before anything copies or uploads the transcript.
# On failure the redactor writes nothing to stdout and we skip the archive.
redacted=$(printf "%s" "$input" | python3 "$HERE/redact-private.py") || exit 0
[ -n "$redacted" ] || exit 0

printf "%s" "$redacted" | bash "$root/scripts/archive-session.sh"

# Drop the sanitized temp copy; the implementation has taken its own copy by now.
tmp=$(printf "%s" "$redacted" | python3 -c \
  'import sys, json; print(json.load(sys.stdin).get("transcript_path", ""))' 2>/dev/null) || tmp=""
case "$tmp" in
  */redacted-*.jsonl) rm -f "$tmp" ;;
esac

exit 0

