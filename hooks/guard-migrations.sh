#!/bin/bash
# PreToolUse / beforeShellExecution hook: block alembic migrations that would
# destroy data, BEFORE they run.
#
# Asks alembic to render the migration offline (--sql) and inspects the SQL it
# would actually execute. Reading rendered SQL rather than the Python source
# also catches raw op.execute("... DROP COLUMN ..."). Denies rather than asks,
# because the global config runs bypassPermissions, where an "ask" may be
# auto-approved and silently become a no-op.
#
#   upgrade:   DROP COLUMN / DROP TABLE / ALTER COLUMN TYPE  -> deny
#   downgrade: `base`, DROP TABLE, DROP COLUMN, TYPE change  -> deny
#              constraints and indexes only                  -> no opinion
#
# No-ops unless the working dir is an Alembic project, and defers to a
# project-local guard if one exists (project-b ships its own).
#
# Fails open: a migration that cannot be rendered cannot be applied either.
# Escape hatch: prefix the command with ALEMBIC_ALLOW_DESTRUCTIVE=1.
#
# Emits {} (no opinion) rather than an explicit "allow" so this hook never
# overrides another guard's decision on unrelated commands.

pass() { echo '{}'; exit 0; }

input=$(cat)
cmd=$(echo "$input" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('tool_input', {}).get('command', ''))
except Exception:
    print('')
" 2>/dev/null)

case "$cmd" in
  *[Aa]lembic*) ;;
  *) pass ;;
esac
case "$cmd" in
  *--sql*) pass ;;                       # offline render, never touches the DB
  *ALEMBIC_ALLOW_DESTRUCTIVE=1*) pass ;; # explicit operator override
esac
case "$cmd" in
  *downgrade*) mode=downgrade ;;
  *upgrade*)   mode=upgrade ;;
  *) pass ;;
esac

root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
if   [ -f alembic.ini ];        then proj="$PWD"
elif [ -f "$root/alembic.ini" ]; then proj="$root"
else pass
fi
cd "$proj" 2>/dev/null || pass

# A project shipping its own guard already covers this; don't double-block.
[ -f scripts/guard_migration_apply.sh ] && pass

if   [ -x .venv/bin/alembic ]; then ALEMBIC=(.venv/bin/alembic)
elif command -v alembic >/dev/null 2>&1; then ALEMBIC=(alembic)
elif command -v uv >/dev/null 2>&1; then ALEMBIC=(uv run alembic)
else pass
fi

target=$(GUARD_CMD="$cmd" GUARD_MODE="$mode" python3 -c '
import os, re, shlex, sys
cmd, mode = os.environ["GUARD_CMD"], os.environ["GUARD_MODE"]
try:
    tokens = shlex.split(cmd)
except ValueError:
    sys.exit(0)
if mode not in tokens:
    sys.exit(0)
skip = False
for tok in tokens[tokens.index(mode) + 1:]:
    if skip:
        skip = False; continue
    if re.fullmatch(r"-\d+", tok):        # relative target, e.g. -1
        sys.stdout.write(tok); sys.exit(0)
    if tok in ("--tag", "-t"):
        skip = True; continue
    if tok.startswith("-"):
        continue
    sys.stdout.write(tok); sys.exit(0)
if mode == "upgrade":
    sys.stdout.write("head")
')
[ -z "$target" ] && pass

current=$("${ALEMBIC[@]}" current 2>/dev/null \
  | grep -vE '^INFO|^WARNING' \
  | grep -oE '^[0-9a-zA-Z_]+' \
  | head -1)
[ -z "$current" ] && pass   # fresh database: no data to lose

case "$target" in
  *:*) range="$target" ;;
  *)   range="${current}:${target}" ;;
esac

sql=$("${ALEMBIC[@]}" "$mode" "$range" --sql 2>/dev/null) || pass
[ -z "$sql" ] && pass

hits=$(echo "$sql" | grep -inE \
  'DROP[[:space:]]+TABLE|DROP[[:space:]]+COLUMN|ALTER[[:space:]]+COLUMN.*[[:space:]]TYPE[[:space:]]' || true)
[ -z "$hits" ] && pass

GUARD_HITS="$hits" GUARD_MODE="$mode" GUARD_TARGET="$target" \
GUARD_CURRENT="$current" GUARD_PROJ="$proj" python3 -c '
import json, os

hits = os.environ["GUARD_HITS"].strip()
mode, target = os.environ["GUARD_MODE"], os.environ["GUARD_TARGET"]
current, proj = os.environ["GUARD_CURRENT"], os.environ["GUARD_PROJ"]

if mode == "upgrade":
    lead = (
        "BLOCKED — pending migration(s) would DESTROY DATA.\n\n"
        f"Applying {current} -> {target} in {proj} runs:\n\n{hits}\n\n"
        "If this is a rename, alembic autogenerate got it wrong: it emits "
        "drop+add, and every value in that column is lost. Rewrite it as "
        "op.alter_column(..., new_column_name=...)."
    )
elif target == "base":
    lead = (
        "BLOCKED — `downgrade base` tears down the entire schema.\n\n"
        f"This reverts every migration from {current} to base in {proj}, "
        f"dropping all tables and their data:\n\n{hits}"
    )
else:
    lead = (
        f"BLOCKED — this downgrade reverts {current} -> {target} in {proj} "
        f"and destroys data:\n\n{hits}\n\n"
        "Expected when undoing a migration — but confirm you do not need "
        "these values first."
    )

print(json.dumps({
    "systemMessage": "Migration BLOCKED — would destroy data",
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": lead + (
            "\n\nIf this is genuinely intended, back up first, then re-run with "
            "the override:\n  ALEMBIC_ALLOW_DESTRUCTIVE=1 <your command>"
        ),
    },
}))
'
