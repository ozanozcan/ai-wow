# docs-routing-inventory: Ceremony, routing, published counts

**Role:** code-edit   **Wave:** 2   **AFK:** yes   **Background:** yes

**Decisions / Specs (pointers):** `-`

## Goal

An operator reading the work-loop knows when *not* to mow and which named command to use instead. Published inventory sentences match disk. Toolkit routing names recover and the new commands. `test_repo_shape` is green.

## Context & decisions (only what this todo needs)

- Wave 1 has already added `skills/recover/SKILL.md` and `commands/{fix-bug,refactor,incident}.md`. This lane **stamps the maps**, it does not rewrite those files.
- `docs/workflow/work-loop.md` is the **canonical core** (see `docs/workflow/front-section-format.md`). Edit it here. Add to the "What to invoke when" table: recover (loop broken), `/fix-bug`, `/refactor`, `/incident`. Add a short ceremony paragraph: small work still gets independent review + `/wrap-up`; `/mow` is for multi-todo or cross-file work. Do not introduce a lite/strict flag.
- `global/CLAUDE.md` — (1) proposal rule as one line under Think-before-coding: every question/option/finding includes your recommendation and rationale; (2) Toolkit routing rows: stuck loop → recover; bug with a repro → `/fix-bug` (tdd); structure-only → `/refactor`; production down → `/incident`. Do not delete existing rows. Surgical.
- `HOW-TO-USE.human.md` — skill-family mermaid: add `recover` under ORCH (or CONT if you judge it continuity — **ORCH is correct**, it is a process). Routing table: same four rows as work-loop. Count: **Sixteen skills** → **Seventeen skills** (the test matches `**([A-Za-z]+) skills**`).
- `HOW-TO-USE.agent.md` — frontmatter `inventory: 16 skills · 8 subagents · 1 command` → `17 skills` and `4 command`/`4 commands` (match surrounding grammar; the skills number is what `test_repo_shape` pins via `inventory:\s*(\d+)\s+skills`). §4.2 add a `recover` row (refuses to duplicate diagnose/tdd; indexes ramps). §0 decision tree: a "loop is stuck / wrong work type" branch may stay prose in §4.3 rather than a mermaid rewrite — do not restyle the whole tree. Windows §9 mermaid node `{"16 skills listed?"}` **must** become the new count — that pattern is a CLAIMS row.
- `README.md` — Skills count 16→17; Slash commands 1→4 with names (`/diagnose`, `/fix-bug`, `/refactor`, `/incident`); `skills/` layout line; "thirteen original skills" → fourteen (`the thirteen original` is a CLAIMS kind `original`). License paragraph stays MIT. Do not claim ANEW is bundled.
- `THIRD-PARTY.md` — only if it contains an original-skill word count that would drift. If it does not state a remaining-original number, do not touch it.
- `bin/tests/test_repo_shape.py` — **read, do not edit.** After your doc edits, run it. Failures are missed inventory sentences — fix the docs, not the test. COUNT_SHAPED will FAIL LOUDLY on a new "N skills" phrasing it does not classify; if you invent a new sentence shape, you must either match an existing CLAIMS pattern or add an EXEMPT — adding a CLAIMS row **is** in scope if a legitimate new sentence has no pattern, and then `bin/tests/test_repo_shape.py` becomes a file you own. Prefer matching existing patterns so you do not need to edit the test.
- Copilot-instructions template: skip unless it lists `/diagnose` as the only command and would become a lie — then one surgical line.

## Files in scope

- `docs/workflow/work-loop.md`
- `global/CLAUDE.md`
- `HOW-TO-USE.human.md`
- `HOW-TO-USE.agent.md`
- `README.md`
- `THIRD-PARTY.md` (only if a count sentence lives there)
- `bin/tests/test_repo_shape.py` (only if a new count-shaped sentence has no CLAIMS pattern — prefer not to)
- `templates/copilot-instructions.template.md` (only if it lists commands and would lie)

## Depends on

- recover-skill
- work-type-commands

## Do NOT

- Do not edit `skills/recover/SKILL.md` or `commands/*.md` or `skills/mow/SKILL.md` except if a count sentence in mow asserts "16 skills" — grep first; if mow has no inventory claim, leave it.
- Do not add `scripts/check` or change `templates/BOOTSTRAP.md` (out of scope).
- Do not shorten CLAUDE.md into a signpost. One proposal-rule line, a few routing rows.
- Do not reopen `copilot-only-harness`.
- Do not bump subagent or hook counts.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- Prefer **`git commit -- <paths>`** over `git add` + `git commit`.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.
- Before commit while parallel lanes are active, run `git status` and confirm only intended paths are staged.

## Acceptance check

- Published docs SHALL state seventeen skills and four slash commands wherever they currently state sixteen and one, and `python3 bin/tests/test_repo_shape.py` SHALL exit 0.
- GIVEN `docs/workflow/work-loop.md` WHEN an operator looks up "what to invoke" THEN they see rows for `/recover` (or recover), `/fix-bug`, `/refactor`, `/incident`, and a sentence that `/mow` is for multi-todo/cross-file work.
- GIVEN `global/CLAUDE.md` WHEN an agent is about to ask the user a question THEN the Think-before-coding section requires a recommendation with the question.
- Verify: `python3 bin/tests/test_repo_shape.py`

## QA contract

- Run `python3 bin/tests/test_repo_shape.py` — exit 0.
- `grep -n 'fix-bug' docs/workflow/work-loop.md HOW-TO-USE.human.md` hits.
- `grep -n 'Seventeen skills\\|17 skills' README.md HOW-TO-USE.human.md HOW-TO-USE.agent.md` covers every previous "sixteen skills" inventory claim in those files (historical plan folders are exempt per the test).

## Toolkit

- Invoke: skill:docs
- Invoke: agent:llm-sec-review (wave gate — routing is agent-facing)

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: none pointed

**Also write that block to** `docs/plans/anew-harvest/dispatch/verification/04-docs-routing-inventory.md`. Chat is not a record. Create the `verification/` folder if missing.
