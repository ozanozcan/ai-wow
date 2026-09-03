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

5. **Create the board directory.** `taskman init` from the repo root (requires the
   repo's `.taskman.toml` identity). That writes `board/` next to the marker; commit
   it. There is no database to stand up.

6. **Confirm reviewer agents exist for the stack.** Before citing `agent:backend-reviewer` /
   `agent:frontend-reviewer` etc. in protocols.md, verify that agent
   is actually defined in this environment (`.claude/agents/*.md` or equivalent) — a protocols.md
   that names a reviewer that doesn't exist will silently no-op at review-gate time.

7. **Sanity-check the template split.** Run:
   `grep -iE '<the previous repo's stack-specific terms>' docs/agents/protocols.md`
   and confirm it returns nothing — the new repo's protocols.md should read as this repo's own
   document, not a copy with leftover foreign terms.

8. **If this repo is worked on in Copilot for VS Code**, give it standing instructions:
   `cp templates/copilot-instructions.template.md <new-repo>/.github/copilot-instructions.md`
   Fill every `<angle-bracket>` placeholder — the commands table especially, since a canonical
   test/lint command is the single most useful thing that file carries. `ai-sync` does **not**
   render this; the VS Code extension reads no `~/.copilot/` path, so without it that repo has
   no standing-instruction layer at all. Skip for CLI-only or non-Copilot repos.

## If an identifier reached a public push anyway

Set `scrub_patterns` (§9 of the human guide) *before* your first push. If you're
reading this because the check fired late — a pattern too narrow, or set up after
the fact — the identifier is in history, not just the tip, and fixing the tip alone
does nothing: a rewrite has to happen anyway, so widen the pattern and fix the tip
in the same pass as the steps below, not before them.

1. **Back up first, outside any repo.** `git clone --mirror <repo> ~/somewhere-not-a-repo/name.git`
   plus a readable export (`git log --all --reverse --pretty=... --name-status`) for
   anything you'd want to mine later — commit messages don't survive a rewrite under
   their old form, so capture them while they're still attached to real SHAs.
   **Restore-test it**: clone the backup back out and diff it against the live repo.
   A backup nobody has restored from is a claim, not a backup.
2. **Rewrite in a scratch clone, never the live checkout.** `git-filter-repo
   --replace-text <file>` (`brew install git-filter-repo`; not the deprecated
   built-in `filter-branch`). One `old==>new` or `regex:pattern==>new` line per term.
3. **Verify before touching anything real:** commit count unchanged, zero hits for
   every pattern across every commit on every ref, and tracked blob hashes identical
   to the live repo (`git ls-tree -r` diff, not a file diff — a byte-identical tree
   proves it, a directory listing does not).
4. **Push master only, and check what's actually public first.** `git ls-remote
   --heads <repo>` before you rewrite — a local mirror clone often carries refs that
   were never pushed (tooling checkpoints, abandoned branches); rewriting and
   pushing all of them publishes things nobody chose to publish.
5. **Force-push is not enough to finish the job.** GitHub keeps a rewritten commit
   reachable by its old SHA until garbage collection, so the identifier is still
   fetchable even after a clean-looking force-push — completing the removal needs a
   GitHub Support request with no guaranteed timeline. Deleting the repo and
   recreating it under the same name, then pushing the rewritten history, is
   complete immediately and costs only open PRs/issues and the creation date — real
   costs, but bounded and known in advance, unlike the support-request path.
6. **Reconnect every local checkout** — `git fetch && git reset --hard origin/<branch>`
   — and re-run whatever push gate you have (§9's `scrub_patterns` check, if you set
   it up per step 0 above) to confirm the *new* public tip is clean too.

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
