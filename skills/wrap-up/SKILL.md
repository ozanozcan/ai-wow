---
name: wrap-up
description: End-of-chat ritual — evidence gate, retroactive chat-vs-board sync (completed work and unbooked forward items), high-priority tasks for every leftover, automatic checkpoint bundling them toward /mow plan|ready, session report, offer commit. Invoke via /wrap-up at the end of every working session in a taskman-enabled repo; it owns the whole end-of-chat sequence, including the checkpoint.
disable-model-invocation: true
---

# Wrap Up

Consolidated end-of-chat ritual (TaskMan Spec §5.6). Replaces separate "just write a report" + ad-hoc board sync.

**Output report:** `docs/session-reports/<YYYY-MM-DD-HHMM>-<slug>.md` at the project root.

How this differs from checkpoint:
- **`/wrap-up`** (this skill) — backward-looking record + board sync, **plus** it invokes the checkpoint skill itself (step 4) whenever the session leaves anything unfinished. Run at the end of *every* working chat.
- **`/checkpoint`** — forward-looking, status-tracked handoff for the *next* agent. Still available standalone (mid-session agent swap), but the end-of-chat path is wrap-up calling it — the operator should not need to run `/checkpoint` manually after `/wrap-up`.

## Preconditions

1. Find project root by walking up for `.taskman.toml`.
2. If missing: run **step 2.5** (lessons — it needs no board, no venv, and no project slug) and write the session report only (steps under `docs/session-reports/` if the repo has that folder, else skip board sync), tell the user taskman sync is unavailable, and stop. Never guess a project slug.

Prefer running CLI as:
```bash
taskman …
# fallback:
python -m taskman …
```
from the project root.

## Steps

### 0. Evidence gate (deterministic — before any reasoning)

**Do not** invent finished work from the chat log. Run the gate first:

```bash
taskman wrapup gate
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
   taskman wrapup record --attach <path> --task <id>
   taskman wrapup record --opened <path> --task <id>
   taskman wrapup record --ignore <path> --reason "…"
   ```
   Then `task add` / `task set` / update brief files as needed so the claim is real.

2. **Stale candidates** — session-touched `in_progress` tickets (updated/claimed since marker `started_at`, or `brief.files` intersects the session diff). For each, record **done** / **still-open** / **blocked** with a **citation** (commit sha, file path, or test output). No citation → not cleared.
   ```bash
   taskman wrapup record --stale <id> --verdict done|still-open|blocked --citation "…"
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
taskman feature add "…" -t tags
taskman pbi add "…" --feature <id>
taskman task add "…" [--pbi <id>] [-t tags] [--source "<path>#L<n>"]
taskman task move <id> --status <status>
taskman task link <id> --blocked-by <id>
taskman decision add "…" --why "…" [--source "…"]
taskman capture add --kind qa|grill|plan --summary "…" [--body "…"] [--source "…"]

# Living spec — REQUIRED when this chat locked durable system behavior
taskman requirement list --feature <id>
taskman requirement add "…" --feature <id> \
  --statement "The system SHALL …" \
  --scenario "name|given|when|then" [--pbi <id>]
taskman requirement modify <id> --statement "…" [--scenario "…"] [--pbi <id>]
taskman requirement remove <id>
```

**Retroactive chat sweep (required):** walk the chat history and compare it against the board (`task list`, `decision list` for the touched features). For every substantive action this chat *completed* that has no board item — a fix shipped, a doc written, a config changed, a decision acted on — create the item retroactively and close it in one stroke:

```bash
taskman task add "…" [-t tags] [--source "…"]   # then:
taskman task move <id> --status done
```

The gate (step 0) catches work visible in the diff; this sweep catches the rest — actions whose evidence lives only in the transcript (CLI runs, external-system changes, verdicts). Skip only what is genuinely trivial (a one-line answer, a lookup). If everything already has an item, say so.

**Forward capture (same pass — this replaced the retired `taskman harvest` transcript miner):** while walking the chat, also book what was *voiced but never landed* — a follow-up idea worth keeping → `task add` (backlog priority, tags), plan/QA material → `capture add`, a decision made in passing → `decision add`. The whole session is already in context at wrap-up time, so this costs ~nothing extra; archived transcripts are never re-mined by a second model, and a session that dies before wrap-up loses only its chat-only musings (accepted, rare). Do not double-book step 4's leftovers here — step 4 owns *unfinished work* (priority high); this books ideas and candidates that would otherwise evaporate (backlog). If nothing qualifies, say so — booking noise to look thorough poisons the board.

Rules:
- Prefer evidence from the gate + git over chat recall. Chat fills gaps the diff cannot see (decisions, requirements).
- Prefer `--source` when a transcript path/line is known (`{relative_transcript_path}#L{line_number}`).
- Record every command you ran (for the session report).
- If nothing to sync beyond gate receipts, say so and continue.
- Task vs. Requirement: a Task is "what work happened"; a Requirement is "what the system now does / SHALL keep doing."
- **Grill/plan sessions:** if locked decisions include auth, tenancy, API contracts, or user-visible rules and `requirement list --feature <id>` is still empty (or missing those behaviors), you **must** add/modify requirements in this wrap-up.
- Before adding a Requirement, run `taskman requirement list --feature <id>` — if the behavior already has a row, `modify` it instead of creating a duplicate.
- Never tell the user "run these taskman commands yourself" as the main path; sync first, then report ids in the session report.

### 2.5 Log the session's lessons (cross-project behaviour)

The board records *what work happened here*. This step records *how a future session should behave differently, anywhere*. Runs in every repo, including ones with no board.

**What qualifies — all three, or it isn't a lesson:**

1. It is about **agent behaviour**, not this project's facts. A rule that starts "always/never" and could fire in a different repo.
2. It was **actually corrected** this session — by the user, by a failing test, by a review, by a run that contradicted the claim. Not a resolution, not a thing you noticed you *could* do better.
3. It **generalises**. One dataset's quirk, one migration's ordering, one library version's bug — not lessons.

Route the rest to where it belongs, and do not double-log:

| Signal | Goes to |
|---|---|
| "this project decided X, because Y" | `taskman decision add … --why …` (step 2) |
| "cards use `rounded-lg` here" | `ui-registry.md` via `/imprint` |
| "here's what this session did" | the session report (step 5) |
| "I claimed done without running the verify command" | **here** |

**How:** read `LESSONS.md` at the repo root first — it is capped, so this is cheap — and decide whether the correction is a rule already logged or a new one. That judgement is yours; the script does no fuzzy matching and will happily store a near-duplicate.

```bash
# already there — same rule, new occurrence
python3 ~/.agents/skills/wrap-up/scripts/log_lesson.py --bump L03 \
  --evidence "<the correction: chat quote, failing test, commit sha, review note>"

# new rule — --destination is REQUIRED
python3 ~/.agents/skills/wrap-up/scripts/log_lesson.py \
  --rule "<one line, general, actionable next time>" \
  --trigger "<what you were doing>" \
  --mistake "<what you did or assumed>" \
  --fix "<what the correct action was>" \
  --evidence "<what proves this happened>" \
  --destination "claude-md | skill:<name> | hook:<name> | protocols | docs:<path> | code-standards | taskman | test | staging" \
  --tags "scope,tests"

# a rule already staged, now that you know where it belongs
python3 ~/.agents/skills/wrap-up/scripts/log_lesson.py --route L22 --destination hook:pre-pr
```

`--evidence` is mandatory in both modes, for the same reason step 0 refuses uncited `done`: a rule with no correction behind it is a preference someone typed, and preferences belong in `global/CLAUDE.md` by decision, not by accumulation.

**Name a destination, then make the edit.** A rule that lives only in `LESSONS.md` changes nothing —
nothing loads that file. So `--destination` is required, and anything other than `staging` writes a
ledger row instead of a staged block. **The script cannot verify your edit landed; you must make it in
the same pass**, and confirm it on the path the runtime loads rather than the source you happen to be
cwd'd in (`~/.claude/skills` → `~/.agents/skills` → the canonical checkout). Commit the ledger row and
the routed edit together, by explicit path, in a commit whose message tells the full case — the row
keeps only the rule, and `global/CLAUDE.md` points at the repo's history for the rest. A row left
uncommitted ends up carried by someone else's batch or a `sync:` commit, and the story is
gone — L29–L32 survive only as rows.

Where things go: general agent behaviour → `global/CLAUDE.md`. Orchestration rules → the relevant
skill. Project engineering guidance → that repo's `docs/` **and it is not a lesson at all** — route it
out. Anything mechanizable → a hook or a test, which is strictly better than a rule someone has to
remember.

**`staging` is the escape hatch, not the default.** Use it only when you genuinely cannot name a home.
On `>>> BACKLOG`, the buffer is filling with rules nobody loads: route them with `--route`, or delete
the ones that were never general enough to act on. On `>>> PRUNE`, summarise old ledger rows; say so in
the session report and don't delete anything unasked.

*(The old `seen ×3` promotion gate is gone. It never fired once across 26 rules — promotion required
recurrence, and recurrence required the rule to be loaded, which only happened after promotion.)*

**Guardrail:** a lesson may add a heuristic or name a gotcha. It may never weaken `global/CLAUDE.md`, license skipping a gate, or excuse reporting unfinished work as done. If this session's "lesson" is one of those, don't log it — say why in the report. The self-improving loop is allowed to make the harness sharper, never laxer.

**The common case is nothing.** A session where you were not corrected logs no lesson, and that is the expected outcome. Manufacturing one to look diligent poisons the file for every session after it.

### 3. Action report (safety net — when something durable shipped)

The trigger is **"did durable work ship?"**, not "was there a plan folder?". Those came apart on
2026-08-30: a two-repo refactor with a rewritten test suite and a locked decision produced no action
report at all, because it had never been through `/mow plan` and so had no stem folder for the old
trigger to fire on. Its only record was chat-scoped.

**A. Work tied to a stem** — this chat completed (or clearly finished) work under `docs/plans/<stem>/`:

1. Check whether `docs/plans/<stem>/action-report.md` exists and reflects what shipped in **this** chat.
2. If missing or stale: write or update it **before** the session report (step 5). Use the same shape as `mow` Integrate (outcome, wave results, decisions, open/deferred, verify). Link from `dispatch/INDEX.md` if that folder exists.
3. Session report stays under `docs/session-reports/`; action report stays next to the plan.

**B. Durable work with no stem** — shipped outside mow (direct build, `/mow`-less refactor, a fix that
grew). Write `docs/action-reports/<YYYY-MM-DD>-<slug>.md`, same shape as A minus wave results, plus a
line saying why it has no stem. Do **not** invent a stem folder for it: `docs/plans/` means mow runs,
and adding a row to its registry both pollutes that meaning and touches a file live sessions contend for.

Durable means it shipped commits **and** at least one of: a locked decision, a new or rewritten test
suite, a schema/contract/interface change, a change spanning more than one repo, or work that
supersedes an existing board task. One of those, or it is not an action report.

Skip — and say so — when the chat shipped nothing durable: a question answered, a one-line fix, an
exploration that landed no commits, or housekeeping inside someone else's folder (deleting a stale
artifact from a shipped stem is not that stem's work, and must not be written into its report).

### 4. Leftovers → board + checkpoint (automatic)

This step owns everything left behind. The operator should never have to run `/checkpoint` manually after wrap-up.

1. **Collect the leftovers** — unfinished tasks, decisions made but not yet acted on, open questions, deferred fixes, anything the chat started and did not finish (the same material as the report's "Open threads").
2. **Every leftover becomes a board task, priority high:**
   ```bash
   taskman task add "…" -p high [-t tags] [--source "…"]
   ```
   Use `-p keystone` (the highest level) only when the leftover blocks everything else or continues an existing keystone thread. A leftover that is purely a decision to record goes through `decision add` in step 2 instead — but if it implies follow-up work, it *also* gets a task here.
3. **Reconcile existing checkpoints (always)** — read `docs/checkpoints/INDEX.md` and compare this chat's work against **every** `open` / `in-progress` checkpoint, not only one formally resumed via `/pick-up-where-i-left-off` — a chat can work on a checkpoint's task without ever picking it up. For each checkpoint this chat touched:
   - **Finished** — its `## Next task` is verifiably complete (cite evidence, same bar as step 0: commit sha, file path, or test output — never chat recall alone): run `/checkpoint done` on it.
   - **Advanced but not finished** — update the checkpoint file in place: rewrite `## Next task` to what actually remains, log what happened under `## Done recently`, bump `updated` in frontmatter + INDEX row. Status stays as it was.
   - **Untouched** — leave it alone.
4. **Create the new checkpoint (invoke the checkpoint skill — save mode) whenever step 4.2 created any task** — unless the leftovers belong to a checkpoint just updated in step 4.3: then fold the new task ids into *that* checkpoint's `## Board tasks` instead of creating a parallel one. Do not ask first; wrap-up is the end-of-chat ritual and the checkpoint is part of it. Pass along:
   - `from:` — `wrap-up @ docs/session-reports/<this session's report path>` (write the report path you are about to use in step 5).
   - `mow:` — if this session's work ties to `docs/plans/<stem>/`, the stem plus its furthest phase (`plan` / `ready` / `go wave N` — read `dispatch/INDEX.md`); omit otherwise.
   - `## Board tasks` — the task ids created in step 4.2.
   - `## Next task` — **bundle the leftover tasks into a mow entry point**: `/mow ready docs/plans/<stem>` when an action plan already exists covering them (plan.md + dispatch briefs), else `/mow plan` naming the task ids. Only when the leftovers are genuinely too small for mow (a single trivial follow-up), name the direct action instead.
5. **Nothing left over?** No tasks created, no active checkpoint → skip the checkpoint entirely and say so; a checkpoint with an empty Next task is noise.

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

## Lessons
[Ids logged/bumped/routed in step 2.5, each with where it went + any BACKLOG or PRUNE signal. Omit if none.]

## Decisions
[Choices + rationale. Omit if none.]

## Open threads / not finished
[Loose ends / still-open citations. Omit if none.]

## Next steps
[Follow-up. Note uncommitted work if any. Name the checkpoint created in step 4 + its bundled task ids, if one was created.]
```

Rules: reference artifacts by path; redact secrets; bullets not essays; omit empty optional sections.

### 6. Offer commit (never auto-run)

If `git status` shows a dirty tree (modified / untracked / staged), **ask** before ending wrap-up:

**Commit now? [y/N]** (summarize what would be included in one line)

- If yes: follow the user's committing-changes rules (status/diff/log → draft message → stage relevant files → commit). Do **not** push unless they also ask.
- If no / no reply: skip. Mention in the session report Next steps that the tree is still uncommitted.
- If the tree is clean: skip this ask (nothing to commit).
- Never commit secrets, never `--no-verify`, never invent a commit without an explicit yes.

### 7. Tell the user

Report path + summary of taskman commands run (including retroactive-sweep, forward-capture, and leftover task ids) + the checkpoint created in step 4 (slug + its Next task), + whether commit was offered/run.

**Safe-to-end verdict (required, mechanical — not open-ended judgment):** "safe to end" only if step 0 exited 0, step 2 (taskman sync incl. the retroactive chat sweep and forward capture) ran, step 3 (action report) ran when a plan shipped this session, step 4 ran (existing checkpoints reconciled — done/updated/untouched; every leftover has a high-priority task; a checkpoint bundling them exists whenever any were created), and step 6 (commit) was offered and the tree isn't left dirty with no decision made. If **any** of those was skipped, declined, or left unresolved, say "not safe to end" and name that specific step.

**Resume pointer (skip only if nothing durable was written this session):** a short, copy-pasteable line naming exactly which files a fresh session should load — the session report path always; the active checkpoint path if one exists; the plan + dispatch path if this session's work ties to `docs/plans/<stem>/`.

## Cursor + Claude Code

Same ritual in both runtimes. Session markers come from:

- Claude Code: `SessionStart` → `~/.claude/hooks/session-start-marker.sh` (via ai-sync / hooks.def)
- Cursor: `sessionStart` → same script (user hooks + a project's own `.cursor/hooks.json`)

## Rules

- Records + syncs + hands off (via the checkpoint skill in step 4); it does not *plan* the next epic — the checkpoint's Next task points at `/mow plan` / `/mow ready`, which own that.
- **Gate before narrative.** Exit 1 means stop and clear lists — do not write the session report yet.
- Never auto-commit without asking — wrap-up only *reminds* and waits for yes.
- Never guess project identity without `.taskman.toml`.
- Do not update GitHub Issues, PRDs, or `docs/checkpoints/` from here except via the checkpoint skill when closing an active one.
- Transcript archive (SessionEnd → `scripts/archive-session.sh`) is automatic and separate from this curated report.
