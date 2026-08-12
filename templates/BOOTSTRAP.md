# Bootstrap checklist — adopt the harness in a new repo

Ordered steps to wire up `docs/agents/protocols.md` + the `taskman` toolkit map + the shared mow harness in a fresh repo,
without reading anything from another project's repo.

1. **Copy the protocols template.**
   `cp templates/protocols.template.md <new-repo>/docs/agents/protocols.md`
   Fill in the repo-specific deltas only — do not restate generic principles:
   - **P0:** confirm the canonical taskman package is installed (step 2) — preflight is the single go §1 gate.
   - **P1:** replace `<test command>` / `<lint>` / `<typecheck>` with the repo's real commands; replace `<backend-reviewer>` / `<frontend-reviewer>` placeholders with the actual reviewer agent names available in this environment (check `.claude/agents/` or the equivalent); add/remove tag rows to match the repo's actual tag vocabulary.
   - **P2:** same reviewer names as P1; keep **Scope-creep triage** unless the repo explicitly opts out.
   - **P4:** same test/lint/typecheck commands as P1.
   - **P5:** adjust routine cadence/day if weekly-on-Monday doesn't fit the team's rhythm.

2. **Install the canonical taskman package** as an editable path dependency:
   ```bash
   uv add --dev --editable ~/ai-wow/taskman
   ```
   The mow harness gates (preflight, hydrate-specs, grill-writeback check, registry status) and
   their tests ship inside the package — nothing is copied from a sibling repo. After your first
   `/mow plan`, run preflight against that dispatch folder and confirm exit 0.

3. **Render the workflow docs.** Create the repo's front-section files under
   `~/ai-wow/docs/workflow/fronts/<repo-slug>/` (format contract:
   `~/ai-wow/docs/workflow/front-section-format.md`), then run the ai-sync doc render to
   write managed copies of `work-loop.md`, `mow-compact-template.md`, and
   `taskman-dispatch-bridge.md` into `<new-repo>/docs/workflow/`. Hand-edits to rendered copies
   fail the drift gate — edit the core or the front file in ai-wow and re-render instead.

4. **Wire the taskman toolkit map.** Add a `[toolkit]` stanza to the repo's `.taskman.toml`,
   projecting the same tag → skill/agent rows chosen in step 1's P1 table:
   ```toml
   [project]
   slug = "<repo-slug>"
   name = "<Repo Name>"

   [toolkit]
   bug = ["skill:tdd", "skill:diagnose"]
   # ...one row per tag used in protocols.md P1
   ```

5. **Upgrade the shared taskman database.** `uv run taskman db upgrade` from the repo root
   (requires the repo's `.taskman.toml` identity + a reachable Postgres per the package config).
   Migrations are explicit: the CLI warns when the DB is behind the package head but never
   auto-migrates. The repo carries no alembic tree of its own.

6. **Confirm reviewer agents exist for the stack.** Before citing `agent:django-reviewer` /
   `agent:backend-reviewer` / `agent:frontend-reviewer` etc. in protocols.md, verify that agent
   is actually defined in this environment (`.claude/agents/*.md` or equivalent) — a protocols.md
   that names a reviewer that doesn't exist will silently no-op at review-gate time.

7. **Sanity-check the template split.** Run:
   `grep -iE '<the previous repo's stack-specific terms>' docs/agents/protocols.md`
   and confirm it returns nothing — the new repo's protocols.md should read as this repo's own
   document, not a copy with leftover foreign terms.

## Global layer (no per-repo copy)

The **`mow` skill** (`~/ai-wow/skills/mow/SKILL.md`, symlinked to `~/.agents/skills/mow`, Claude Code, and Cursor) already includes Pi practices (preflight gate, compact-template harvest, `## Git rules` in brief template) and Claude Code worktree isolation (§2a merge-back). The workflow-doc cores live in `~/ai-wow/docs/workflow/` and reach repos only via the ai-sync render (step 3). New repos need only the package dependency, the rendered docs, and protocols.md — no per-repo script copies and no second skill edit.

## Worked examples

Two shapes this template has been filled in for, as a sense of the deltas each stack needs:

- **A Django SSR app** — Django/DRF stack deltas in P1/P2/P3/P4; reviewer is `django-reviewer`;
  UI lane is Django templates + Tailwind + htmx, so P1 points at the project's own
  `ui-designer`, never the global Next.js one.
- **A FastAPI + SQLAlchemy service** — async stack deltas in the same four sections; reviewer is
  `backend-reviewer`; adds domain cross-cutting sections for the rules that span lanes.

Your repo's `protocols.md` should read as its own document — if a `grep` for the other stack's
vocabulary returns hits, step 7 hasn't been done.
