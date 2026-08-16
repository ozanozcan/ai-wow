#!/bin/bash
# PreToolUse hook: ask before running commands that destroy data.
# Catches: Django admin ops, direct SQL drops/truncates/deletes,
# SQLAlchemy drop_all, alembic downgrade-to-base, and dev db file removal.
# Expanded for broader Python stack coverage (FastAPI, Django, Flask, plain Python).
# Fails open — a hook crash never blocks the agent.

# Resolve Python interpreter: python3 preferred, fall back to python (Windows).
PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "python3")

input=$(cat)
command=$(printf "%s" "$input" | "$PYTHON" -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except:
    print('')
" 2>/dev/null)

if echo "$command" | grep -qiE \
    'manage\.py\s+flush|manage\.py\s+migrate\s+--fake|manage\.py\s+sqlflush|\
DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE\s+TABLE|\
DELETE\s+FROM\s+[a-zA-Z_]+\s*;|\
rm\s+.*db\.sqlite3|\
\.drop_all\s*\(|Base\.metadata\.drop_all|\
alembic\s+downgrade\s+(base|--?\s*[0-9])'; then
    command="$command" "$PYTHON" -c "
import json, os
command = os.environ['command']
print(json.dumps({
    'systemMessage': f'Guardrail: this command looks destructive — review before allowing: {command}',
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'ask',
        'permissionDecisionReason': f'Flagged as potentially destructive: {command}',
    },
}))
"
    exit 0
fi

echo '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}'
exit 0
