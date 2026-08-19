# 01-reviewer-roster: FastAPI-only backend reviewer, plus classic-web and Streamlit reviewers

**Role:** code-edit   **Wave:** 1   **AFK:** yes   **Background:** yes

**Decisions / Specs (pointers):** `-` — this repo has no taskman board. Locked decisions live in `docs/plans/work-pc-readiness/plan.md` → `## Decisions locked`; read that section before starting.

## Goal

`agents/` contains exactly four reviewer subagents — `backend-reviewer` (FastAPI only),
`frontend-reviewer` (untouched), `classic-web-reviewer` (new), `streamlit-reviewer`
(new) — and no `django-reviewer`. Every checklist section in `backend-reviewer` applies
to every review it will ever run, with no inert stack branches.

## Context & decisions (only what this todo needs)

- **The operator's real stacks are FastAPI (backend), React/Next, vanilla JS + jQuery +
  HTMX + hand-written HTML + Tailwind, and Streamlit.** No Django, no Node backend.
  Build for those and nothing else.
- **`backend-reviewer` has two live bugs today.** [`agents/backend-reviewer.md:26`](../../../../agents/backend-reviewer.md)
  routes Django to section `F`, which is titled *"Alembic migration safety"* — Django
  reviews get audited against the wrong migration tool. [`:27`](../../../../agents/backend-reviewer.md)
  routes Flask to section `A`, *"Async correctness"* — every finding against sync Flask
  code is a false positive. Deleting Django and Flask removes both bugs; do not attempt
  to fix them in place.
- **The one genuine gap is FastAPI security config.** Django got section `E_D`
  (`DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, secure cookies); FastAPI has no equivalent,
  which is backwards — FastAPI ships less by default.
- **Streamlit's failure modes are Python execution-model bugs, not DOM bugs.** Its
  reviewer shares nothing with the classic-web one beyond output format.
- **`classic-web-reviewer` spans two languages on purpose.** `|safe` in a Jinja template
  and `innerHTML` in a jQuery file are the same XSS finding; one section covers both.
- **Match the existing agent file shape exactly** — frontmatter (`name`, `description`,
  `tools: Read, Grep, Glob, Bash`, `readonly: true`), then `## On invoke`, lettered
  checklist sections, `## Severity mapping`, `## Output format`, `## Rules of engagement`.
  Read [`agents/frontend-reviewer.md`](../../../../agents/frontend-reviewer.md) first as
  the template — it is the shortest and cleanest of the three existing reviewers.

## Files in scope

- `agents/backend-reviewer.md` — rewrite to FastAPI-only
- `agents/django-reviewer.md` — delete
- `agents/classic-web-reviewer.md` — create
- `agents/streamlit-reviewer.md` — create

## Signatures

Frontmatter contract every new agent file must expose, since `bin/ai-sync` and the
runtime agent registry both read it:

```yaml
---
name: <kebab-case, matching the filename stem>
description: <one line; states the stacks it covers AND names the sibling agent to use instead when the diff is a different stack>
tools: Read, Grep, Glob, Bash
readonly: true
---
```

## Depends on

- none

## Do NOT

- **Do not touch `agents/frontend-reviewer.md`.** It is correct for React/Next as-is and
  is explicitly not being renamed.
- **Do not edit any file outside `agents/`.** Doc references, routing tables and
  inventory counts belong to lane Z; editing them here creates a wave-2 conflict.
- **Do not carry any Django section forward** into the new files — not into
  `classic-web-reviewer` as a "Django templates" subsection heading, not as a
  detection branch. Template-level findings must be written stack-neutrally
  (`{% for %}` and `{{ }}` are fine as *syntax examples* inside a shared checklist item).
- **Do not add a stack-detection routing table to `backend-reviewer`.** With one stack
  there is nothing to route; replace it with a short guard that confirms
  FastAPI+SQLAlchemy from the changed files' imports and names the right sibling agent
  when it is something else.
- **Do not make these agents write code.** `readonly: true`, diff-only, report-never-fix
  — the harness invariant is that reviewers never build.
- **Do not run `git add -A` or `git commit`.** Stage nothing; the orchestrator commits.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.
- Before commit while parallel lanes are active, run `git status` and confirm only intended paths are staged.

## Acceptance check

- The reviewer roster SHALL contain no Django-specific bundled agent, and
  `backend-reviewer` SHALL contain no Django or Flask checklist section.
  Verify: `grep -riE "django|flask" agents/` returns **no** hits in
  `backend-reviewer.md` and no `django-reviewer.md` file exists.
- `backend-reviewer` SHALL be able to raise a finding for each of: CORS
  `allow_origins=["*"]` combined with `allow_credentials=True`; a JWT decoded with
  `verify_signature=False`; `/docs` reachable in production; config read via scattered
  `os.environ` instead of `pydantic-settings`; a route with no rate limit on an auth
  path. Verify: `grep -cE "allow_credentials|verify_signature|pydantic-settings" agents/backend-reviewer.md` ≥ 3.
- GIVEN a diff that adds `el.innerHTML = userInput` in a `.js` file and `{{ value|safe }}`
  in a template, WHEN `classic-web-reviewer`'s checklist is applied, THEN both are
  reachable as Critical findings from the **same** XSS checklist item — not two
  language-split items.
- GIVEN a Streamlit diff that calls a paid API at module scope with no
  `@st.cache_data`, WHEN `streamlit-reviewer` is applied, THEN the rerun-cost finding is
  reachable, because Streamlit re-executes the whole script on every widget interaction.
- Every new and modified agent file SHALL parse as valid frontmatter and be picked up by
  the sync script. Verify: `python3 bin/ai-sync status` exits 0.

## QA contract

- `grep -riE "django|flask" agents/` — inspect every hit; zero permitted in
  `backend-reviewer.md`, zero files named `django-reviewer.md`
- `head -6` each new/changed agent file — frontmatter block is well-formed YAML with all
  five keys
- `python3 bin/ai-sync status` — exits 0, agents directory still reports linked
- `git status --short agents/` — shows exactly the four intended paths, nothing else

## Toolkit

- `Invoke: skill:simplify` if `backend-reviewer` ends up longer after the rewrite than
  before — the point of dropping a stack is a shorter file, not a longer one.

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: <none pointed — this repo has no board; cite plan.md decisions instead>
