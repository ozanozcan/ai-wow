---
name: wrap-up
description: End-of-chat ritual — evidence gate, session report, taskman board sync, optional checkpoint close, offer harvest, offer commit when the tree is dirty. Invoke via /wrap-up at the end of every working session in a taskman-enabled repo.
disable-model-invocation: true
---

# Wrap Up

Consolidated end-of-chat ritual (TaskMan Spec §5.6). Replaces separate "just write a report" + ad-hoc board sync.

**Output report:** `docs/session-reports/<YYYY-MM-DD-HHMM>-<slug>.md` at the project root.

How this differs from checkpoint:
- **`/wrap-up`** (this skill) — backward-looking record + board sync. Run at the end of *every* working chat.
- **`/checkpoint`** — forward-looking, status-tracked handoff for the *next* agent. Only when handing off.

They are independent. Use both when you finished work *and* want to hand off.

## Preconditions

1. Find project root by walking up for `.taskman.toml`.
2. If missing: write the session report only (steps under `docs/session-reports/` if the repo has that folder, else skip board sync), tell the user taskman sync/harvest are unavailable, and stop. Never guess a project slug.

Prefer running CLI as:
```bash
.venv/bin/python -m taskman …
# fallback:
python -m taskman …
```
from the project root.

## Steps

### 0. Evidence gate (deterministic — before any reasoning)

**Do not** invent finished work from the chat log. Run the gate first:

```bash
.venv/bin/python scripts/wrapup_reconcile.py
# equiv: .venv/bin/python -m taskman wrapup gate
```

| Exit | Meaning |
|---|---|
| 0 | Both worklists clear — continue |
| 1 | Unattributed paths and/or stale `in_progress` remain — **must clear before continuing** |
| 2 | No session marker — run `taskman wrapup open` (or `--since <sha>`) then re-run |

The gate uses the worktree session marker written at session open
(`.session-markers/<session_id>.json`: `start_sha`, branch, worktree). Parallel Cursor / Claude Code sessions do not share markers.

**Worklists:**

1. **Unattributed** — every path in `git diff <start_sha>..HEAD` plus dirty/untracked, minus paths claimed by open tickets (`brief.files`). For each leftover path, either:
   - attach to an existing ticket, or
   - open a retroactive ticket, or
   - ignore with an explicit reason
   ```bash
   .venv/bin/python -m taskman wrapup record --attach <path> --task <id>
   .venv/bin/python -m taskman wrapup record --opened <path> --task <id>
   .venv/bin/python -m taskman wrapup record --ignore <path> --reason "…"
   ```
   Then `task add` / `task set` / update brief files as needed so the claim is real.

2. **Stale candidates** — session-touched `in_progress` tickets (updated/claimed since marker `started_at`, or `brief.files` intersects the session diff). For each, record **done** / **still-open** / **blocked** with a **citation** (commit sha, file path, or test output). No citation → not cleared.
   ```bash
   .venv/bin/python -m taskman wrapup record --stale <id> --verdict done|still-open|blocked --citation "…"
   ```
   - **Code tickets with a verify command** (from `brief.verify` or Acceptance): run it; pass `--verify-ok` only when it passed. Then `task move <id> --status done` when verdict is done.
   - **Design / spike tickets** (`kind:design`, `spike`, explore-without-verify): `--operator-ack` required for `done` — ask the user; do not self-ack.
   - For `still-open` / `blocked`: leave board status (or `task move … blocked`) and cite why.

Re-run the gate until exit 0. **Markdown instructions are not the enforcer — the nonzero exit is.**

If the session-start hook never fired: `taskman wrapup open` (anchors at HEAD) or `wrapup gate --since <sha>`.

Optional full-board hygiene: `wrapup gate --all-stale` (every `in_progress`, not only session-touched).

### 1. Gather signal

- `git branch --show-current`
- Gate report from step 0 (paths + stale ids) — primary evidence
- `git diff --stat <start_sha>` when marker known (`$WRAPUP_START_SHA` or marker file)
- `git log --oneline -10`
- Chat scan is **secondary** only: decisions, requirements, captures not visible in the diff
- Note test/lint results surfaced in the chat / verify runs from step 0

### 2. Sync the taskboard (taskman CLI only — agent runs it)

**You** run the CLI. Do not hand the user a command list as the primary outcome. Do **not** write to Postgres directly.

Apply board moves implied by step 0 receipts (`done` / `blocked`) plus any chat-only decisions/requirements:

```bash
.venv/bin/python -m taskman feature add "…" -t tags
.venv/bin/python -m taskman pbi add "…" --feature <id>
.venv/bin/python -m taskman task add "…" [--pbi <id>] [-t tags] [--source "<path>#L<n>"]
.venv/bin/python -m taskman task move <id> --status <status>
.venv/bin/python -m taskman task link <id> --blocked-by <id>
.venv/bin/python -m taskman decision add "…" --why "…" [--source "…"]
.venv/bin/python -m taskman capture add --kind qa|grill|plan --summary "…" [--body "…"] [--source "…"]

# Living spec — REQUIRED when this chat locked durable system behavior
.venv/bin/python -m taskman requirement list --feature <id>
.venv/bin/python -m taskman requirement add "…" --feature <id> \
  --statement "The system SHALL …" \
  --scenario "name|given|when|then" [--pbi <id>]
.venv/bin/python -m taskman requirement modify <id> --statement "…" [--scenario "…"] [--pbi <id>]
.venv/bin/python -m taskman requirement remove <id>
```

Rules:
- Prefer evidence from the gate + git over chat recall. Chat fills gaps the diff cannot see (decisions, requirements).
- Prefer `--source` when a transcript path/line is known (`{relative_transcript_path}#L{line_number}`).
- Record every command you ran (for the session report).
- If nothing to sync beyond gate receipts, say so and continue.
- Task vs. Requirement: a Task is "what work happened"; a Requirement is "what the system now does / SHALL keep doing."
- **Grill/plan sessions:** if locked decisions include auth, tenancy, API contracts, or user-visible rules and `requirement list --feature <id>` is still empty (or missing those behaviors), you **must** add/modify requirements in this wrap-up.
- Before adding a Requirement, run `taskman requirement list --feature <id>` — if the behavior already has a row, `modify` it instead of creating a duplicate.
- Never tell the user "run these taskman commands yourself" as the main path; sync first, then report ids in the session report.

### 3. Action report (safety net — when a plan shipped)

If this chat completed (or clearly finished) work tied to `docs/plans/<stem>/`:

1. Check whether `docs/plans/<stem>/action-report.md` exists and reflects what shipped in **this** chat.
2. If missing or stale: write or update it **before** the session report (step 5). Use the same shape as `mow` Integrate (outcome, wave results, decisions, open/deferred, verify). Link from `dispatch/INDEX.md` if that folder exists.
3. Session report stays under `docs/session-reports/`; action report stays next to the plan.

Skip when the chat did not touch any `docs/plans/<stem>/` work (pure refactor, unrelated bugfix, etc.).

### 4. Checkpoint (only if one was active)

If this chat picked up a checkpoint (`docs/checkpoints/` in-progress), offer or run `/checkpoint done` per that skill. Do not create a new checkpoint unless the user asks to hand off.

### 5. Write the session report

Slug: short, lowercase, hyphenated. Path:

`docs/session-reports/<YYYY-MM-DD-HHMM>-<slug>.md`

```markdown
---
date: <YYYY-MM-DD HH:MM>
branch: <git branch>
slug: <slug>
project: <slug from .taskman.toml or "none">
session_id: <WRAPUP_SESSION_ID or marker id>
start_sha: <anchor sha>
---

# Session report — <one-line summary>

## What was done
[Bullets — concrete outcomes. Required.]

## Files changed
[From gate / git diff vs start_sha. Omit if empty.]

## Wrap-up gate
[Exit 0; note unattributed/stale clearances + citations.]

## Taskman sync
[CLI commands run, or "none".]

## Decisions
[Choices + rationale. Omit if none.]

## Open threads / not finished
[Loose ends / still-open citations. Omit if none.]

## Next steps
[Follow-up. Note uncommitted work if any. If handing off: "see /checkpoint".]
```

Rules: reference artifacts by path; redact secrets; bullets not essays; omit empty optional sections.

### 6. Offer harvest (never auto-run)

Ask: **Run harvest now? [y/N]**

- If yes: from project root, ` .venv/bin/python -m taskman harvest ` (interactive approve). Do not pass `--auto-approve` unless the user explicitly asks.
- If no / no reply: skip.
- Do not reimplement harvest — invoke the CLI only.

### 7. Offer commit (never auto-run)

If `git status` shows a dirty tree (modified / untracked / staged), **ask** before ending wrap-up:

**Commit now? [y/N]** (summarize what would be included in one line)

- If yes: follow the user's committing-changes rules (status/diff/log → draft message → stage relevant files → commit). Do **not** push unless they also ask.
- If no / no reply: skip. Mention in the session report Next steps that the tree is still uncommitted.
- If the tree is clean: skip this ask (nothing to commit).
- Never commit secrets, never `--no-verify`, never invent a commit without an explicit yes.

### 8. Tell the user

Report path + summary of taskman commands run + whether harvest/commit were offered/run. If meaningful work should be handed off, suggest `/checkpoint`.

**Safe-to-end verdict (required, mechanical — not open-ended judgment):** "safe to end" only if step 0 exited 0, step 2 (taskman sync) ran, step 3 (action report) ran when a plan shipped this session, step 4 (checkpoint) ran when one was active, step 6 (harvest) was offered and not left declined-with-something-to-capture, and step 7 (commit) was offered and the tree isn't left dirty with no decision made. If **any** of those was skipped, declined, or left unresolved, say "not safe to end" and name that specific step.

**Resume pointer (skip only if nothing durable was written this session):** a short, copy-pasteable line naming exactly which files a fresh session should load — the session report path always; the active checkpoint path if one exists; the plan + dispatch path if this session's work ties to `docs/plans/<stem>/`.

## Cursor + Claude Code

Same ritual in both runtimes. Session markers come from:

- Claude Code: `SessionStart` → `~/.claude/hooks/session-start-marker.sh` (via ai-sync / hooks.def)
- Cursor: `sessionStart` → same script (user hooks + project `.cursor/hooks.json` on web-app/demo)

## Rules

- Records + syncs; does not plan the next epic — that's `/checkpoint` / planning skills.
- **Gate before narrative.** Exit 1 means stop and clear lists — do not write the session report yet.
- Never auto-run harvest without asking.
- Never auto-commit without asking — wrap-up only *reminds* and waits for yes.
- Never guess project identity without `.taskman.toml`.
- Do not update GitHub Issues, PRDs, or `docs/checkpoints/` from here except via the checkpoint skill when closing an active one.
- Transcript archive (SessionEnd → `scripts/archive-session.sh`) is automatic and separate from this curated report.
