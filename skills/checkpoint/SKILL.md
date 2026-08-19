---
name: checkpoint
description: Save a named, status-tracked session handoff for the next agent. Multiple checkpoints coexist without overwriting. Use /checkpoint at session end or before an agent swap, /checkpoint done to finish+archive one, /checkpoint list to see all.
disable-model-invocation: true
---

# Checkpoint

Multi-checkpoint session handoff. Canonical store: **`docs/checkpoints/`** at the project root.

- **`docs/checkpoints/INDEX.md`** — status table, single source of truth.
- **`docs/checkpoints/<slug>.md`** — one curated handoff per task (while `open` or `in-progress`).
- **`docs/checkpoints/archive/<slug>-<ts>.md`** — `done` checkpoints land here.
- **`handoff.md`** — one-line stub pointing at the index. Do not write handoffs into it.

Resume in a new chat with **`/pick-up-where-i-left-off`** (not checkpoint).

## Modes

| Invocation | Mode | When |
|---|---|---|
| `/checkpoint` | **save** (default) | Mid-session agent swap — create a new checkpoint by hand |
| via `/wrap-up` step 4 | **save** | The normal end-of-chat path — wrap-up invokes save mode itself, prefilled (`from:`, `mow:`, `## Board tasks`, bundled Next task); skip step 4's freetext ask, wrap-up already gathered it |
| `/checkpoint done` | **done** | A picked-up task is finished — archive it |
| `/checkpoint list` | **list** | Show the index table |

Parse the user message: `done` → done mode; `list` → list mode; otherwise → save.

Status lifecycle: **`open`** (saved, not yet picked up) → **`in-progress`** (resumed in a chat, set by `/pick-up`) → **`done`** (finished + archived, set by `/checkpoint done`). Saving never overwrites or archives another checkpoint; the only archive trigger is `done`.

---

## Mode: save (default)

Create a new checkpoint for the current chat. Does **not** touch any other checkpoint.

0a. **Reconcile stale `done` checkpoints (always run, silent unless it finds something)** — a checkpoint can end up marked `status: done` in its own frontmatter (or in `INDEX.md`) without ever being physically archived, e.g. from a hand-edit or an interrupted `/checkpoint done`. Guard against it every time a new checkpoint is about to be created, since that's a touchpoint that always happens even when `/wrap-up`/`/checkpoint done` got skipped:

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

    If it moved anything, also bump that row's `Updated` date in `INDEX.md` (`Status` is already `done`) and mention it to the user in one line — don't make a ceremony of it.

0b. **Flag a lingering `in-progress` checkpoint** — read `INDEX.md`. If any row is still `in-progress` (from a previous session that picked it up), ask once: *"`<slug>` is still marked in-progress — finished? Run `/checkpoint done` on it, or leave it open?"* Act on the answer, then continue creating the new checkpoint either way — don't block on this.

0c. **Close completed dispatch batches (conditional — skip if N/A)** — only when the repo has `.cursor/plans/*.dispatch/` with all lanes **done** in `INDEX.md`:

   ```bash
   bash .cursor/hooks/archive-dispatch.sh
   ```

   - No-op if no dispatch folder or lanes still open — normal checkpoints skip this instantly.
   - If something moved: keep stale `.cursor/plans/` refs out of the new checkpoint; point to `docs/plans-archive/<name>/` and the plan's `action-report.md` under `docs/plans/<stem>/`.

1. **Gather signal**: `git diff --stat HEAD`, `git status`, `git branch --show-current`. Note linter errors if relevant. If step 0 ran, include what was archived.

2. **Draft the title**: format `Project - one-sentence summary of the task`. One concrete next task — name the feature, file, or behavior. Confirm or edit with the user.

3. **Derive the slug**: slugify the title — lowercase, spaces/punctuation → hyphens, drop the `→`/articles noise, keep it readable and unique. Example: `FitnessManager - Add status tracking to checkpoint skill` → `project-a-add-status-tracking-to-checkpoint-skill`. If a file with that slug already exists, append a short disambiguator.

4. **Ask the user** (optional freetext): context, open questions, gotchas, relevant files.

5. **Write `docs/checkpoints/<slug>.md`** with frontmatter + body:

   ```markdown
   ---
   slug: <slug>
   title: <title>
   branch: <git branch>
   status: open
   created: <YYYY-MM-DD>
   updated: <YYYY-MM-DD>
   from: <what created it — "wrap-up @ docs/session-reports/<file>.md" or "manual @ <branch>">
   mow: <plan lineage — "docs/plans/<stem> · <furthest phase: plan|ready|go wave N>"; omit if none>
   ---

   # <title>

   ## Next task
   [One clear description. When this checkpoint bundles board tasks (below), this is the
   mow entry point: `/mow ready docs/plans/<stem>` if an action plan covering them exists,
   else `/mow plan` naming the task ids — not a hand-written re-plan.]

   ## Board tasks
   [Optional — taskman ids bundled for the next session (one per line, `#id — title`).
   Wrap-up fills this with the high-priority leftovers it just created.]

   ## Context
   [Optional]

   ## Open questions
   [Optional]

   ## Done recently
   [Optional — newest first]

   ## Agent briefing
   - **Decisions made**: [choices and rationale]
   - **Dead ends**: [what was tried and failed — do not retry]
   - **Suggested skills**: [e.g. diagnose, django-reviewer, grill-with-docs]
   - **Artifacts**: [paths or URLs only — do not paste bodies]
   - **Do not**: [scope traps, anti-patterns]
   ```

   Rules: reference artifacts by path; redact secrets; bullets not essays; omit empty sections. Only `## Next task` is required.

6. **Add a row to `docs/checkpoints/INDEX.md`** (newest at the bottom of the table): `| <slug> | <title> | <branch> | <created> | <updated> | open | <from> |`. The `From` cell is the compact form of the frontmatter `from:` (`wrap-up @ <report file>` / `manual`), plus ` · mow: <stem> <phase>` when `mow:` is set. If the repo's existing INDEX predates the `From` column, add the column header once and backfill old rows with `-`.

7. **Tell the user**: name the concrete file just written — `Saved to docs/checkpoints/<slug>.md — next session, run /pick-up-where-i-left-off.`

---

## Mode: done

Finish a checkpoint that was picked up (or one named by the user) and archive it.

1. **Identify the checkpoint**: prefer the one currently `in-progress` in `INDEX.md`. If multiple are `in-progress`, or the user names one, use that. If none, ask.

2. **Move the file**: `docs/checkpoints/<slug>.md` → `docs/checkpoints/archive/<slug>-$(date +%Y-%m-%d-%H%M).md`.

   ```bash
   ts=$(date +%Y-%m-%d-%H%M); mkdir -p docs/checkpoints/archive && \
     git mv "docs/checkpoints/<slug>.md" "docs/checkpoints/archive/<slug>-$ts.md" 2>/dev/null || \
     mv "docs/checkpoints/<slug>.md" "docs/checkpoints/archive/<slug>-$ts.md"
   ```

3. **Update the archived file's frontmatter**: `status: done`, bump `updated`.

4. **Update `INDEX.md`**: set that row's `Status` to `done` and bump `Updated`. Keep the row (history); do not delete it.

---

## Mode: list

Print the `docs/checkpoints/INDEX.md` table as-is, sorted by status (`in-progress` first, then `open`, then `done`). Read-only — change nothing.

---

## Daily flow

```
End of session:                 /wrap-up   (creates the checkpoint itself when anything is left over)
Mid-session swap / manual save: /checkpoint
See what's saved:               /checkpoint list
Next session (pick which):      /pick-up-where-i-left-off
A picked-up task is finished:   /checkpoint done   (wrap-up also runs this for the active one)
```

Do not use this skill to update GitHub Issues, PRDs, or `plans/*.md` — link from the checkpoint instead. The raw per-session transcript archive (MinIO via `.cursor/hooks/archive-session.sh`) is a separate layer — checkpoints are curated, that pipeline is the firehose.
