# Dispatch index — Work-PC readiness

Source plan: docs/plans/work-pc-readiness/plan.md

## What we'll do

1. Rewrite `backend-reviewer` to FastAPI-only — delete the Django sections and the
   stack-detection table, drop the Flask row (which applies async checks to sync code),
   and add the missing security & config section.
2. Add `classic-web-reviewer` for vanilla JS, jQuery, hand-written HTML, HTMX and Tailwind.
3. Add `streamlit-reviewer` for Streamlit's execution-model failure modes.
4. Delete `django-reviewer`.
5. Make the mow tracker portable — replace the `pkill` and `open` calls that fail in Git Bash.
6. Sweep every doc reference and inventory count to the new eight-subagent roster.

## What you'll have at the end

| Area | End state |
|---|---|
| Backend review | `backend-reviewer` fires on FastAPI + SQLAlchemy async diffs only; no Django sections; CORS-with-credentials, unverified-JWT, and exposed-`/docs` findings are reachable |
| Frontend review | Three agents split by what owns the DOM: `frontend-reviewer` (React/Next), `classic-web-reviewer` (vanilla/jQuery/HTMX/templates), `streamlit-reviewer` |
| Repo hygiene | No `django-reviewer` file; no Django routing rows; all three inventory counts agree with `ls agents/` |
| mow tracker | `/mow go` starts, serves and stops the tracker on macOS **and** in Git Bash on Windows |

**In one line:** Make the bundled reviewers match the stacks the operator actually has, and make the mow board survive a Windows work laptop.

## Waves

- **Wave 1 (parallel, AFK):** A | B
- **Wave 2 (after wave 1, foreground):** Z

Each wave ends with a **review gate** (see go mode) before the next starts.

## Lanes

| Lane | Todos (in order) | PBI / Feature | Files owned | Role | Review flags | AFK | Background | Decisions / Specs | Brief |
|---|---|---|---|---|---|---|---|---|---|
| A | 01-reviewer-roster | - / - | `agents/backend-reviewer.md`, `agents/django-reviewer.md`, `agents/classic-web-reviewer.md`, `agents/streamlit-reviewer.md` | code-edit | - | yes | yes | `-` | [01-reviewer-roster.md](01-reviewer-roster.md) |
| B | 02-mow-tracker-portability | - / - | `skills/mow/SKILL.md`, `skills/mow/TRACKER.md` | code-edit | - | yes | yes | `-` | [02-mow-tracker-portability.md](02-mow-tracker-portability.md) |
| Z | 03-docs-reference-sweep | - / - | `HOW-TO-USE.agent.md`, `HOW-TO-USE.human.md`, `README.md`, `global/CLAUDE.md` | code-edit | - | no | no | `-` | [03-docs-reference-sweep.md](03-docs-reference-sweep.md) |

`PBI / Feature`: `-` throughout — this repo has no root `.taskman.toml`, so no board rows exist.

`Review flags`: `-` throughout. The changed files are agent definitions, a skill, and
documentation — there is no application code for a stack reviewer to audit. The wave
gate is the orchestrator reading each lane's `## Verification` block against its QA
contract, plus the acceptance greps.

`Decisions / Specs`: `-` throughout — no taskman board. Locked decisions live in
`plan.md` → `## Decisions locked`; every lane brief points there in its header.

**Hydrated specs:** n/a — every lane's Decisions / Specs cell is `-`, so
`hydrated-specs.md` is not generated.

**Grill checkpoint:** done 2026-08-19
**Grill write-back:** plan.md ✓ (3 decisions locked: tracker `command -v` cascade · file-type reviewer dispatch with named seam · section G trimmed to operational + pointer) · briefs: 01-reviewer-roster.md, 02-mow-tracker-portability.md, 03-docs-reference-sweep.md · taskman: n/a — no root `.taskman.toml` in this repo

## Conflicts check

No two same-wave lanes share a file.

- Wave 1: lane A owns `agents/**` only; lane B owns `skills/mow/{SKILL,TRACKER}.md` only.
  Disjoint — no path is a prefix of the other.
- Wave 2: lane Z runs alone.
- Cross-plan: `docs/plans/INDEX.md` has no other `planned`/`running`/`paused` stem, so
  there is nothing to union against.

**Risk noted:** lane B edits the mow skill *while a mow run is executing*. This is safe
here because `~/.agents/skills` resolves to `~/Desktop/dotfiles-ai/skills`, not to this
repo — the live procedure is read from elsewhere, and lane B cannot alter the run in
flight. The corollary is that lane B's fix is **not live on this Mac** until it is also
ported to `dotfiles-ai`.
