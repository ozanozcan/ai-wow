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

6. **Confirm reviewer agents exist for the stack.** Before citing `agent:backend-reviewer` /
   `agent:frontend-reviewer` etc. in protocols.md, verify that agent
   is actually defined in this environment (`.claude/agents/*.md` or equivalent) — a protocols.md
   that names a reviewer that doesn't exist will silently no-op at review-gate time.

7. **Sanity-check the template split.** Run:
   `grep -iE '<the previous repo's stack-specific terms>' docs/agents/protocols.md`
   and confirm it returns nothing — the new repo's protocols.md should read as this repo's own
   document, not a copy with leftover foreign terms.

## UI bootstrap (frontend repos only)

Do these once per repo with a UI surface, in order — this is what makes the anti-slop
machinery (impeccable / imprint / ui lanes) actually fire instead of no-oping. Full audit
rationale: `docs/brainstorms/ui-anti-slop-pipeline.md`.

1. **`$impeccable init`** (existing UI: `$impeccable document`) → `PRODUCT.md` + `DESIGN.md`.
   Without PRODUCT.md every impeccable run detours into setup; without DESIGN.md each
   session re-derives the visual system — the root cause of AI-generic drift.
   Requires impeccable installed (`npx skills add pbakaus/impeccable`).
2. **`/imprint audit`** → confirmed baseline in repo-root `ui-registry.md` before any
   capture. On an existing untracked UI, skipping the audit codifies today's inconsistency.
3. **One token file** as the only color/spacing/radius source, named in DESIGN.md and
   `ui-registry.md`; fix or ticket the hardcoded hexes the audit surfaces.
4. **Project ui-designer agent:** `cp templates/ui-designer.template.md <repo>/.claude/agents/ui-designer.md`
   and fill every placeholder (stack, token file path, fonts, target viewport). Mandatory on
   non-Next stacks — the global agent is Next.js/shadcn-only. The template's anti-slop bans
   stay verbatim; they are also the fallback when impeccable is absent.
5. **`$impeccable hooks on`** — the design-detector PostEdit hook, the only always-on
   anti-slop gate (everything else fires only when an agent invokes a skill).
6. **Commit a font decision** in DESIGN.md — pairing axis or single family; Inter-by-default
   is itself a tell.
7. **Fill the protocols.md P1 `ui` row with real values** — actual target viewport(s) and
   reviewer names; placeholders make the screenshot QA contract silently no-op. P2's
   design-review row (impeccable `critique`) applies to ui-tagged stems.
8. **Prove the screenshot loop** — one successful screenshot at the target viewport via
   playwright-cli (or the repo's equivalent), committed as evidence. A QA contract that says
   "screenshot attached" in a repo where the browser can't run is a dead gate.

## Global layer (no per-repo copy)

The **`mow` skill** (`~/ai-wow/skills/mow/SKILL.md`, symlinked to `~/.agents/skills/mow`, Claude Code, and Cursor) already includes Pi practices (preflight gate, compact-template harvest, `## Git rules` in brief template) and Claude Code worktree isolation (§2a merge-back). The workflow-doc cores live in `~/ai-wow/docs/workflow/` and reach repos only via the ai-sync render (step 3). New repos need only the package dependency, the rendered docs, and protocols.md — no per-repo script copies and no second skill edit.

## Worked examples

Two shapes this template has been filled in for, as a sense of the deltas each stack needs:

- **A Django SSR app** — Django/DRF stack deltas in P1/P2/P3/P4; reviewer was a project-supplied `django-reviewer` (no longer bundled globally);
  UI lane is Django templates + Tailwind + htmx, so P1 points at the project's own
  `ui-designer`, never the global Next.js one.
- **A FastAPI + SQLAlchemy service** — async stack deltas in the same four sections; reviewer is
  `backend-reviewer`; adds domain cross-cutting sections for the rules that span lanes.

Your repo's `protocols.md` should read as its own document — if a `grep` for the other stack's
vocabulary returns hits, step 7 hasn't been done.
