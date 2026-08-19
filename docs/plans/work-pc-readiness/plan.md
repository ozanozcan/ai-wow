# Work-PC readiness — reviewer roster + portable tracker

**Stem:** `work-pc-readiness`
**Created:** 2026-08-19

## Goal

A fresh `git clone` of ai-wow on the work machine gives the operator (a) reviewer
subagents matching the stacks actually in use there — FastAPI backend, modern JS
frontend, classic web, Streamlit, **no Django** — and (b) a mow live tracker that
starts and stops cleanly in Git Bash on a locked-down Windows box.

## What we'll do

1. **Rewrite `backend-reviewer` to FastAPI-only.** Delete the Django checklist sections
   and the stack-detection routing table, drop the Flask row (which today applies async
   checks to sync code), and add the missing security & config section — the one real
   gap, since FastAPI ships less secure-by-default than Django did.
2. **Add `classic-web-reviewer`** for vanilla JS, jQuery, hand-written HTML, HTMX and
   Tailwind — the stacks nothing in the roster currently covers.
3. **Add `streamlit-reviewer`** for Streamlit's execution-model failure modes.
4. **Delete `django-reviewer`** — the untracked leftover from a reverted re-add.
5. **Make the mow tracker portable** — replace the two shell assumptions (`pkill`,
   `open`) that fail in Git Bash, so `/mow go` produces a live board on Windows.
6. **Sweep every doc reference and inventory count** to the new eight-subagent roster.

## What you'll have at the end

| Area | End state |
|---|---|
| Backend review | `backend-reviewer` fires on FastAPI + SQLAlchemy async diffs only; no Django sections; CORS-with-credentials, unverified-JWT, and exposed-`/docs` findings are reachable |
| Frontend review | Three agents split by what owns the DOM: `frontend-reviewer` (React/Next), `classic-web-reviewer` (vanilla/jQuery/HTMX/templates), `streamlit-reviewer` |
| Repo hygiene | No `django-reviewer` file; no Django routing rows in `global/CLAUDE.md` or the HOW-TO-USE tables; all three inventory counts read the same number |
| mow tracker | `/mow go` starts, serves, and stops the tracker on macOS **and** in Git Bash on Windows — no `pkill: command not found`, no silent stale-server reuse |

**In one line:** Make the bundled reviewers match the stacks the operator actually has, and make the mow board survive a Windows work laptop.

## Decisions locked

- **Django is out of ai-wow entirely** — the bundled agent, the routing rows, the
  detection table. Projects that need it can still supply their own `django-reviewer`;
  mow already supports project-supplied reviewers, so `skills/mow/SKILL.md:517` stays.
- **`backend-reviewer` covers FastAPI only.** No second Python stack. Litestar was
  considered and rejected — it is Starlette+Pydantic-shaped, so ~90% of its checklist is
  already sections A/B/D; it would be detection nuance, not a stack.
- **`js-backend-reviewer` is not built.** No Node backend was confirmed at work.
  Building a reviewer for a stack that may not exist is speculative.
- **Streamlit gets its own agent, not a section.** It was originally proposed as a
  `backend-reviewer` section because its bugs are Python execution-model bugs, not DOM
  bugs. Once backend became FastAPI-only that home disappeared, so it stands alone.
- **One reviewer spans vanilla JS + jQuery + HTMX + hand-written HTML + Django/Jinja
  templates.** The unifying property is that no framework owns the DOM, so the checklist
  is shared across languages; splitting it by language would duplicate the same XSS and
  a11y sections twice.
- **`frontend-reviewer` is not renamed.** A rename costs ~15 reference updates across 8
  files including `templates/protocols.template.md`, which ships into other repos. It
  buys no disambiguation once the other two agents exist.
- **Scope limit on the Django sweep:** remove the bundled agent and its routing rows
  only. Django stays as an *example* in stack-agnostic guidance
  (`skills/complexity-audit`, `skills/imprint`, `templates/ui-designer.template.md`,
  `templates/BOOTSTRAP.md`) — deleting it there makes those docs worse, and the global
  guideline is to touch only what the request requires.
- **Session reports are never edited** — `docs/session-reports/` is historical record.

## Not yet specified

*Sharpness test: can you state the question precisely now — **not** answer it now? Sharp → a `kind:decision` board row. Not sharp → a line here.*

- Whether `frontend-reviewer` needs Vue or Angular sections — unknown until the work JS
  repos are actually opened. The operator listed "modern JS frameworks" but confirmed
  only React/Next concretely.
- Whether a `js-backend-reviewer` is ever needed — depends on whether any Express/Nest
  service exists at work.
- Whether the two-repo skill farm (ai-wow vs the live `dotfiles-ai` source) should be
  collapsed. It is the reason a `skills/` edit here is not live on this Mac.

## Out of scope

*Scope, not sharpness. Never graduates — returns only if this plan's goal is redrawn, and then as a fresh stem.*

- **The taskman refactor** — needs a reachable Postgres and should happen on one machine;
  bundling it here would block the move on a database.
- **Installing taskman on the work PC** — a Tier-B follow-up gated on what Postgres the
  work environment allows; nothing in this plan depends on it.
- **Removing Django from stack-agnostic skills and templates** — those are illustrative
  examples, not the bundled agent (see Decisions locked).
- **Vendoring `impeccable`** — Apache-2.0, ~99 files, deliberately added via
  `npx skills add pbakaus/impeccable` rather than committed here.

## Operator note — the two-repo skill farm

`~/.agents/skills` symlinks to `~/Desktop/dotfiles-ai/skills`, **not** to this repo. So
lane B's edits to `skills/mow/SKILL.md` land in ai-wow — which is what the work PC
clones — but do **not** change the mow procedure running on this Mac until they are also
ported to `dotfiles-ai`. That is a feature for this run: the tracker cannot break
mid-flight by editing itself. It is a trap afterwards.
