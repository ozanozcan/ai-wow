---
name: pick-up-where-i-left-off
description: Start a session by listing saved checkpoints, asking which one to continue, and resuming it without re-explaining context. Use at the start of any session that continues previous work — invoke only via /pick-up-where-i-left-off, not via checkpoint.
disable-model-invocation: true
---

# Pick Up Where I Left Off

Resume work from a saved checkpoint in **`docs/checkpoints/`** at the project root.

**Do not write code until the user confirms.**

## Steps

0. **Reconcile stale `done` checkpoints (always run, silent unless it finds something)** — a checkpoint can end up marked `status: done` without ever being physically archived (hand-edit, interrupted `/checkpoint done`, a `/wrap-up` that got skipped). This is the other touchpoint (besides `/checkpoint`) that always runs, so it's the other place to self-heal it:

   ```bash
   mkdir -p docs/checkpoints/archive
   for f in docs/checkpoints/*.md; do
     [ "$(basename "$f")" = "INDEX.md" ] || [ ! -f "$f" ] && continue
     if grep -q '^status: done$' "$f"; then
       slug=$(basename "$f" .md); ts=$(date +%Y-%m-%d-%H%M)
       git mv "$f" "docs/checkpoints/archive/${slug}-${ts}.md" 2>/dev/null \
         || mv "$f" "docs/checkpoints/archive/${slug}-${ts}.md"
       echo "reconciled: archived stale done checkpoint $slug"
     fi
   done
   ```

   If it moved anything, bump that row's `Updated` date in `INDEX.md` and mention it in one line before moving on.

1. **Read the index** — `docs/checkpoints/INDEX.md`.
   - If missing or no `open`/`in-progress` rows exist, tell the user to run `/checkpoint` first, then stop.

2. **List and ask which to continue**
   - Show the `open` and `in-progress` checkpoints **sorted by `Updated`, newest first**, with these columns: slug, title, updated, status, **from** (where it was checkpointed from — the `From` cell / `from:` frontmatter, e.g. `wrap-up @ <session-report file>` or `manual`), and **mow lineage** (`mow:` frontmatter — plan stem + furthest phase, e.g. `docs/plans/<stem> · go wave 2`) when present. Older checkpoints without `from:`/`mow:` show `-`. Hide `done` rows unless asked.
   - **Ask the user which checkpoint to continue.** If exactly one is available, propose it and confirm. Do not guess silently.
   - **For every `in-progress` row that is not the one chosen this time:** ask once, alongside the list — *"`<slug>` is still marked in-progress from a previous session — is that actually finished? Run `/checkpoint done` on it before we continue, or leave it as-is?"* This is the case `/checkpoint`'s own step 0b can't reach: work finished, `/wrap-up` ran, its checkpoint-close offer got skipped or the "not safe to end" verdict got missed, and the very next thing run is `/pick-up-where-i-left-off` (not `/checkpoint`) — so this is the only remaining place that catches it. Act on the answer, then proceed to step 3 either way.

3. **Mark it in-progress** (this is the resume marker — archiving happens later via `/checkpoint done`, never here):
   - Edit the chosen `docs/checkpoints/<slug>.md` frontmatter → `status: in-progress`, bump `updated`.
   - Edit the matching `INDEX.md` row → `Status: in-progress`, bump `Updated`.

4. **Read the checkpoint** — `docs/checkpoints/<slug>.md` in full.

5. **Read backlog (optional steer)**
   - Read `.cursor/rules/tasks.mdc` only if the user might prioritize backlog goals over this checkpoint.

6. **Orient** — summarize in plain language:
   - Next task (from the checkpoint or a user override). When it is a `/mow plan` / `/mow ready` bundle, say so — that command is the resume path, not a fresh plan.
   - **Provenance** — restate `from:` (which session report / wrap-up produced this checkpoint; offer to open the report for detail).
   - **Mow lineage** — if `mow:` is set, read `docs/plans/<stem>/dispatch/INDEX.md` and restate where the previous mow run stopped (waves done, lanes open) so the previous `/mow go` state is visible before resuming.
   - **Board tasks** — if `## Board tasks` lists ids, run `taskman task show <id>` on them and fold their titles/status into the summary.
   - Context, open questions, blockers
   - `## Agent briefing` from the checkpoint if present
   - What changed on disk since the checkpoint (`git status --short`, `git diff --stat HEAD` if useful)

7. **Grill (when building something new)**
   - If the next task involves non-trivial implementation, run **`/grill-with-docs`** on it before planning.
   - One question at a time; recommend an answer before asking for confirmation.
   - Cover: desired behavior, files involved, edge cases, mobile (~390px) impact.

8. **Propose a plan** — concrete step-by-step implementation plan.

9. **Confirm** — ask "Ready to start?" before writing any code.

## Rules

- This skill is **resume only**. Saving is `/checkpoint`; finishing + archiving is `/checkpoint done`.
- Resuming sets `in-progress` and never archives — a checkpoint you pick up but don't finish stays available.
- Do not duplicate PRD/plan bodies — reference paths only.
- Do not update GitHub Issues or plan files from this skill.
