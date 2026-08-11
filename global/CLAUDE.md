# Global coding guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Apply to all projects.

## Think before coding

Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## Simplicity first

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

<important if="you are editing existing code">
## Surgical changes

Touch only what you must. Clean up only your own mess.

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that YOUR changes made unused; don't remove pre-existing dead code unless asked.

Every changed line should trace directly to the user's request.
</important>

<important if="the task is a feature, bugfix, or refactor">
## Goal-driven execution

Define success criteria. Loop until verified.

- "Add validation" → write tests for invalid inputs, then make them pass
- "Fix the bug" → write a test that reproduces it, then make it pass
- "Refactor X" → ensure tests pass before and after

For multi-step tasks, state a brief plan with a verify step for each item.
</important>

<important if="skills or subagents are available in this session">
## Toolkit routing

Route work to the specialist toolkit proactively — announce what you're invoking and why. Project protocols (e.g. `docs/agents/protocols.md`) refine this table; the user's explicit instructions always win.

| Task smells like | Reach for |
|---|---|
| UI — page, screen, template, component, styling, mobile | impeccable skill while building; imprint after; mobile-width screenshot for QA |
| Backend diff ready to commit | stack reviewer subagent (django-reviewer / backend-reviewer / frontend-reviewer) |
| Prompts, tool-calling, agents, RAG, model endpoints | llm-sec-review subagent alongside the stack reviewer |
| Auth, payments, uploads, secrets, settings | suggest /security-review before commit |
| Bug fix | regression test first (tdd skill); gnarly/unclear bug → /diagnose |
| Slow page, new list/query endpoint | complexity-audit skill |
| New or changed logic with thin tests | test-coverage skill; critical pure logic → adversarial-tester |
| Feature declared done | /ship-check, then /verify |

Toolkit is advisory, never a gate: recommend or invoke, don't block on it.
</important>
