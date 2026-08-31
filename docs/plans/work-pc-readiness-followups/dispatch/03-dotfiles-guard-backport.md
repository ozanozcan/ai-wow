# dotfiles-guard-backport: this Mac stops auto-allowing commands its guard cannot parse

**Role:** shell   **Wave:** 2   **AFK:** no   **Background:** no

**Decisions / Specs (pointers):** `-` — no taskman board. Binding decision: [`../plan.md`](../plan.md) → `## Decisions locked`, fourth bullet (scope limited to `guard-destructive.sh`).

**Foreground, out-of-repo, operator watching.** This lane edits a file outside ai-wow and
changes a hook that is live on this machine. It is never backgrounded and never handed to
a subagent — in Claude Code the `shell` role runs in the foreground with Bash.

## Goal

`~/Desktop/dotfiles-ai/hooks/guard-destructive.sh` returns `{}` — no opinion — for a
command it does not recognise, instead of an affirmative `allow`. This is the version
ai-wow already carries; the machine the operator works on every day does not.

## Context & decisions (only what this todo needs)

- `~/.claude/hooks` symlinks into `~/Desktop/dotfiles-ai`, so **dotfiles-ai's copy is the
  one that actually fires here.** ai-wow's copy is what ships to the work PC.
- dotfiles-ai's final line is
  `echo '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}'`.
  An affirmative allow approves every command the hook does not recognise — **including one
  it failed to parse**, if a tool ever sends a payload shape its inline Python cannot read.
- ai-wow's copy already returns `{}` plus the four-line comment explaining exactly that.
  Returning `{}` hands the decision back to the normal permission flow rather than
  pre-approving it.
- The two files are otherwise identical: same shebang, same detection regex, same `ask`
  branch. This is a one-hunk change.
- **Scope is this file only.** Porting `guard-migrations.sh` and ai-wow's Copilot-aware
  `hooks.def.json` was considered and rejected — those re-render the live hook
  registration, a bigger blast radius than a follow-up run should take.

## Files in scope

- `~/Desktop/dotfiles-ai/hooks/guard-destructive.sh` — modify (final `echo` + the comment above it)

## Depends on

- Wave 1 complete. This is deliberately last-ish: the hook is live, so changing it
  mid-run could start routing this session's own unrecognised Bash calls through the
  permission flow.

## Do NOT

- Do NOT `git commit` or `git push` in dotfiles-ai. It is a private repo with its own
  session-end sync; leave the change in its working tree and tell the operator.
- Do NOT port `guard-migrations.sh`, `hooks.def.json`, `peer-session-*.py`, or
  `session-start-marker.py`. Explicitly out of scope.
- Do NOT touch ai-wow's own `hooks/guard-destructive.sh` — it is already correct and is
  the source being copied *from*.
- Do NOT re-render hook registration (`ai-sync` in either repo).

## Acceptance check

- The hook SHALL return `{}` for a command outside its detection regex, and SHALL still
  return an `ask` decision for one inside it.
- GIVEN a `PreToolUse` payload whose command is `ls -la`, WHEN the hook runs, THEN stdout
  is exactly `{}` and the exit status is 0.
- GIVEN a payload whose command contains `DROP TABLE users;`, WHEN the hook runs, THEN
  stdout carries `"permissionDecision": "ask"` and the exit status is 0.
- Verify: `bash -n ~/Desktop/dotfiles-ai/hooks/guard-destructive.sh` → exit 0.
- Verify: `diff <(sed -n '30,$p' hooks/guard-destructive.sh) <(sed -n '30,$p' ~/Desktop/dotfiles-ai/hooks/guard-destructive.sh)` → no differences in the tail.

## QA contract

- Both payload smoke tests above, run against the **dotfiles-ai** copy, output pasted.
- `bash -n` parse check.
- Confirm with `git -C ~/Desktop/dotfiles-ai status --short` that exactly one file changed
  and nothing was committed.

## Toolkit

- none — a one-hunk shell edit with two payload smoke tests.
