# 03-docs-reference-sweep: point every doc, routing row and inventory count at the new roster

**Role:** code-edit   **Wave:** 2   **AFK:** no   **Background:** no

**Decisions / Specs (pointers):** `-` — no taskman board. Read `docs/plans/work-pc-readiness/plan.md` → `## Decisions locked`, especially the **scope limit on the Django sweep**.

## Goal

Every human- and agent-facing document describes the roster that lane A actually built:
eight subagents, no `django-reviewer`, and routing rows that send a diff to the right
one of the four reviewers. No document claims a count that disagrees with `ls agents/`.

## Context & decisions (only what this todo needs)

- **This lane runs after lane A** because it describes A's output. Read the final state
  of `agents/` before editing — do not work from this brief's assumptions about what A
  named things.
- **The three inventory counts already disagree with each other today**, which is how
  this drift stays invisible: [`README.md:192`](../../../../README.md) says "six
  subagents", [`HOW-TO-USE.human.md:255`](../../../../HOW-TO-USE.human.md) says "**Six
  subagents.**", and [`HOW-TO-USE.agent.md:5`](../../../../HOW-TO-USE.agent.md) says
  "7 subagents". After lane A the true count is **eight**. Make all three agree and
  verify against `ls agents/*.md | wc -l`.
- **Four reference sites carry Django and must change:**
  `HOW-TO-USE.agent.md:122` (the `backend-reviewer` row still says "auto-detects
  FastAPI/Django/Flask"), `HOW-TO-USE.agent.md:123` (the whole `django-reviewer` row),
  `global/CLAUDE.md:59` (routing row offering `django-reviewer`), and the subagent table
  at `HOW-TO-USE.human.md:239-244` plus the routing table at `:288-296`.
- **Eight reference sites carry Django and must NOT change.** This is the scope limit:
  `skills/complexity-audit/SKILL.md:17`, `skills/imprint/SKILL.md:10`,
  `templates/ui-designer.template.md:14`, `templates/BOOTSTRAP.md:94-95`,
  `skills/mow/SKILL.md:37,127,200,382,386,517`, `skills/mow/TRACKER.md:214`, and
  everything under `docs/session-reports/`. Those are either stack-agnostic *examples*,
  or references to a **project-supplied** `django-reviewer` (a pattern mow supports and
  BOOTSTRAP already documents as "no longer bundled globally"), or historical record.
  Removing the bundled agent does not invalidate any of them.
- **Routing rows need a dispatch signal, not just a name.** The four reviewers are told
  apart by what is in the diff: `.py` importing FastAPI → `backend-reviewer`; `.py`
  importing Streamlit → `streamlit-reviewer`; `.jsx`/`.tsx` with React →
  `frontend-reviewer`; `.js`/`.html`/`.j2`/`.jinja` with no component framework →
  `classic-web-reviewer`. Write the rows so an agent can pick without asking.
- **The routing rows must also carry the HTMX handoff** (grilled 2026-08-19; plan.md
  `## Decisions locked`). Dispatch is by file type, so a diff that changes both a FastAPI
  route and its Jinja partial needs **both** reviewers. Say that in the routing table —
  one row, not a paragraph — so an agent holding a mixed HTMX diff runs both instead of
  picking one and moving on.

## Files in scope

- `HOW-TO-USE.agent.md`
- `HOW-TO-USE.human.md`
- `README.md`
- `global/CLAUDE.md`

## Depends on

- `01-reviewer-roster` — this lane documents the roster that lane A creates, including
  its final agent names

## Do NOT

- **Do not edit anything under `agents/`, `skills/`, `templates/`, or
  `docs/session-reports/`.** Lane A owns `agents/`, lane B owns `skills/mow/`, and the
  other two are explicitly out of scope per plan.md.
- **Do not scrub the word "Django" from the repo.** Eight sites listed above keep it on
  purpose. Removing them is scope creep and makes the docs worse.
- **Do not renumber, restructure, or reflow sections** in the HOW-TO-USE files. They are
  long documents with a stable table of contents; change the rows and counts, nothing else.
- **Do not rename `frontend-reviewer`** anywhere.
- **Do not update the skills count** — no skill was added or removed by this plan.
- **Do not run `git add -A` or commit.**

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.
- Before commit while parallel lanes are active, run `git status` and confirm only intended paths are staged.

## Acceptance check

- No bundled-agent reference to `django-reviewer` SHALL remain in the four files in
  scope. Verify: `grep -rn "django-reviewer" HOW-TO-USE.agent.md HOW-TO-USE.human.md README.md global/CLAUDE.md` returns nothing.
- All three inventory counts SHALL equal the real file count. Verify:
  `ls agents/*.md | wc -l` equals the number stated in `README.md`,
  `HOW-TO-USE.human.md`, and `HOW-TO-USE.agent.md`.
- GIVEN an agent reading `global/CLAUDE.md`'s routing table and holding a diff that
  touches only `app.py` with `import streamlit as st`, WHEN it consults the table, THEN
  it selects `streamlit-reviewer` without needing to ask the user which reviewer applies.
- GIVEN the same table and a diff touching only `static/js/legacy.js` using jQuery, THEN
  it selects `classic-web-reviewer`, not `frontend-reviewer`.
- The eight out-of-scope Django references SHALL still be present. Verify:
  `grep -rln "django\|Django" skills/ templates/ docs/session-reports/` still lists
  `skills/complexity-audit/SKILL.md`, `skills/imprint/SKILL.md`,
  `templates/ui-designer.template.md`, `templates/BOOTSTRAP.md`, `skills/mow/SKILL.md`,
  `skills/mow/TRACKER.md`, and the session report.
- `python3 bin/ai-sync status` SHALL exit 0.

## QA contract

- `grep -rn "django-reviewer" HOW-TO-USE.agent.md HOW-TO-USE.human.md README.md global/CLAUDE.md` → no output
- `ls agents/*.md | wc -l` compared against each stated count → all equal
- `grep -rn -iE "(six|seven|eight|[0-9]+) subagents" --include="*.md" .` → every hit agrees
- `git status --short` → only the four in-scope paths modified by this lane
- `python3 bin/ai-sync status` → exit 0

## Toolkit

- none — mechanical documentation sweep

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: <none pointed — cite plan.md decisions instead>
