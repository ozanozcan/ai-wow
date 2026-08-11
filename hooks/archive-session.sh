#!/usr/bin/env bash
# Thin wrapper: resolve project root from hook cwd, then exec in-repo archive-session.sh.
# Fail-open — never block session end.
set -uo pipefail

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
printf "%s" "$input" | bash "$root/scripts/archive-session.sh"
exit 0

