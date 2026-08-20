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
- **`backend-reviewer`'s LLM section keeps only the operational half.** (Grilled
  2026-08-19.) Retain timeouts, retries, fallback paths, token/cost bounds and eval
  hooks — those are production-readiness concerns a backend reviewer should catch.
  Remove prompt injection, untrusted-input-as-instructions, structured-output trust and
  secret isolation, which `llm-sec-review` owns; replace them with a one-line pointer to
  that agent. The routing table already says to run both on model-touching diffs, so
  keeping the security items in both produced duplicate findings on the common path.
  Rejected: keeping G whole (duplication), deleting G (a FastAPI diff reviewed without
  `llm-sec-review` would get no model-layer check at all), and inverting the split.
- **Reviewer dispatch is by file type, with the seam named in both agents.**
  (Grilled 2026-08-19.) `.py` → `backend-reviewer`; templates, `.js`, `.html` →
  `classic-web-reviewer`. So that HTML-built-in-Python is not a blind spot for both,
  `backend-reviewer` carries one item flagging markup constructed in Python
  (`HTMLResponse` with an f-string, manual string-built templates) as an escaping risk
  and naming `classic-web-reviewer` for the markup half; `classic-web-reviewer` carries
  the mirror note that route auth, tenancy and query performance are **not** its job.
  Rejected: overlapping file ownership (forces running both agents on every HTMX diff),
  and a bare file-type split with no handoff (leaves the XSS gap open).
- **The tracker's non-portable calls get a `command -v` cascade, not a caveat.**
  (Grilled 2026-08-19.) Kill: `pkill` → `taskkill` → skip-with-warning. Open: `open` →
  `start` → `xdg-open` → skip. The URL is printed unconditionally in every branch, so a
  shell with none of the three still leaves the operator able to open the board by hand.
  macOS behavior is unchanged. Rejected: documenting the gap in Appendix B only, which
  would leave the wrong-run stale-server board as the *default* on Windows; and
  collision-detect-without-kill, which is portable but makes cleanup a manual chore.

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
- **`templates/protocols.template.md`** — its P1/P2 tables name `<backend-reviewer>` /
  `<frontend-reviewer>` as **placeholders**, and `templates/BOOTSTRAP.md` step 1 already
  instructs the adopter to substitute whatever reviewers exist in their environment. It
  is correct as written and does not enumerate the roster, so the new agents need no
  entry there.

## Operator note — the two-repo skill farm

**Corrected 2026-08-19 during `/mow go` Integrate. The original note had the direction
backwards; it is kept below, struck through, because the plan was executed against it.**

`~/.agents/skills` symlinks to `~/Desktop/dotfiles-ai/skills`. That repo is not just the
*live* copy — it is the **source**. `ai-wow/skills/` is a downstream mirror that a repo
sync re-copies from dotfiles-ai (preserving mtimes) and then auto-commits. Writing to
`ai-wow/skills/**` therefore does not persist: lane B's verified diff was applied at
20:12 UTC and restored to its pre-run state within a minute, never reaching a commit.

The working chain is **edit dotfiles-ai → sync copies into ai-wow → ai-wow pushed →
work PC clones ai-wow**. Lane B's fix was re-applied to dotfiles-ai with operator
approval and has since propagated: ai-wow's HEAD carries the cascade and the two copies
are byte-identical.

> ~~So lane B's edits to `skills/mow/SKILL.md` land in ai-wow — which is what the work PC
> clones — but do **not** change the mow procedure running on this Mac until they are also
> ported to `dotfiles-ai`. That is a feature for this run: the tracker cannot break
> mid-flight by editing itself. It is a trap afterwards.~~

## Correction — the `backend-reviewer` premise was stale

**Recorded 2026-08-19 during Integrate.** This plan and brief `01-reviewer-roster.md`
describe a `backend-reviewer` with a Django→section-F / Flask→section-A stack-detection
table at `:26-27` and an LLM section at `:123-129`. **No such file was in the repo.** The
committed version was 138 lines with zero `django`/`flask` occurrences and its LLM section
at `:69-75` — the plan was written against a version that had been reverted.

Consequences for the record, not the outcome:

- Items 1's sub-clauses "delete the Django checklist sections" and "drop the Flask row"
  were **no-ops**. This run did not fix two live bugs in `backend-reviewer`, because
  those bugs were not present. The `django-reviewer.md` deletion was real.
- The expectation that the file would get *shorter* was based on the same phantom. With
  nothing to remove and a six-item security section added, it went 138 → 149 lines
  (`simplify` took it 152 → 149).
- `django-reviewer.md` was **tracked**, not "the untracked leftover from a reverted
  re-add" as stated under `## Decisions locked`; its deletion required `git rm`.

Lane A built to the end state specified by the Goal and Acceptance check rather than to
the deletion steps, which is why the outcome is correct despite the premise.
