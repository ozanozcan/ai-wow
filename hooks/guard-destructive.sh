#!/bin/bash
# beforeShellExecution hook: ask before running commands that destroy data.
# Catches: manage.py flush, migrate --fake, DROP TABLE, DELETE without WHERE,
# sqlflush, and deleting the dev database file.
# Fails open — a hook crash never blocks the agent.

input=$(cat)
command=$(echo "$input" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except:
    print('')
" 2>/dev/null)

if echo "$command" | grep -qiE \
    'manage\.py\s+flush|manage\.py\s+migrate\s+--fake|DROP\s+TABLE|DELETE\s+FROM\s+[a-zA-Z_]+\s*;|manage\.py\s+sqlflush|rm\s+.*db\.sqlite3'; then
    command="$command" python3 -c "
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

# No opinion, rather than an explicit "allow". An affirmative allow here would
# approve every command this hook does not recognise -- including one it failed
# to parse, if a tool ever sends a payload shape it cannot read. Returning {}
# lets the normal permission flow decide instead.
echo '{}'
exit 0
