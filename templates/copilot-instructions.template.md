<!-- Template: copy to <repo>/.github/copilot-instructions.md and fill every <angle-bracket>
     placeholder. GitHub Copilot in VS Code loads this file into every chat in this workspace,
     so it is the Copilot equivalent of global/CLAUDE.md — but repo-scoped, not global.

     Two rules for editing it:
       - Keep it short. A long instruction file gets diluted; everything here should earn its line.
       - Say what is true of THIS repo. Generic advice the model already knows is wasted space —
         the value is in the project's own commands, constraints and conventions.

     Not applicable in this file: skills, subagents, hooks, and slash commands. Those are
     Claude Code / Copilot CLI mechanisms; the VS Code extension does not read them. Prompt
     files (.github/prompts/*.prompt.md) are the one adjacent feature that does work here. -->

# Working in this repo

<One or two sentences: what this project is, who uses it, what it must not break.>

**Stack:** <languages, frameworks, notable libraries>

## Commands

Use these exact commands — do not substitute a narrowed or extra-flagged variant, because
a per-file run says nothing about whether the repo-wide gate passes.

| Purpose | Command |
|---|---|
| Tests | `<test command>` |
| Lint | `<lint command>` |
| Types | `<typecheck command>` |
| Run locally | `<run command>` |

## Think before coding

Don't assume. Don't hide confusion. Surface tradeoffs.

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## Simplicity first

Minimum code that solves the problem. Nothing speculative.

- Look before you write: search for an existing helper, util, or pattern first. Re-implementing
  what already lives a few files over is the most common failure.
- Reach for the platform before writing code — a native input type, a CSS rule, or a database
  constraint beats app-level logic doing the same job.
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.
- Cutting a real corner on purpose — a global lock, an O(n²) scan, a naive heuristic —
  leaves a marker: `# debt: <the ceiling>, <what triggers the upgrade>`, e.g.
  `# debt: O(n²) scan, index it above ~1k rows`. A ceiling with no trigger is the one
  that rots, so write both. Read the ledger on demand with a search for `debt:` —
  never into a file that accumulates.

## Surgical changes

When editing existing code: touch only what you must, and clean up only your own mess.

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports and variables that *your* changes made unused; leave pre-existing dead code alone
  unless asked.

Every changed line should trace directly to the request.

## Goal-driven execution

Define success criteria, then loop until verified.

- "Add validation" → write tests for invalid inputs, then make them pass.
- "Fix the bug" → write a test that reproduces it, then make it pass.
- "Refactor X" → confirm tests pass before and after.

For multi-step work, state a brief plan with a verify step for each item.

## Verification habits

Each of these represents a real, expensive mistake. They are about *checking*, and checking is
the step most often skipped.

- **Read the file before prescribing a fix for it.** No summary of a file is the file — not a
  directory listing, not a search result, not a description already in the conversation. Before
  proposing that a file be changed or deleted, open it in that same turn.
- **Never document wiring you have not built.** Describe what exists; name the gap separately.
- **Verify a third-party capability against its primary documentation *before* recommending it**,
  not after it's accepted. An API that sounds right is not an API that exists.
- **Changing a user-visible string isn't done until you search for the old one.** Docs, tests and
  fixtures quote output verbatim.
- **A search result is not an existence check.** An unanchored pattern matches more than you meant,
  and a filtered result answers the pattern you typed rather than the question you had. Anchor it,
  or prove it by running the code.
- **Establish a baseline with the project's canonical command** (the table above). A narrowed run
  tests something else.
- **Look at the rendered output before calling UI work done.** Static checks pass on defects only
  the eye catches.
- **A guard is proven by making it fire, not by reading it.** After writing a check or a test, break
  what it protects and confirm it fails.
- **After a command that changes repo state** (`checkout`, `reset`, `stash`), confirm it applied
  before drawing any conclusion from the resulting tree.

## Git

- Stage explicit paths. Never `git add -A` or `git add .` — a blanket add sweeps whatever else is
  in the tree, including things that should never be committed.
- Review what's staged (`git status`, `git diff --cached`) before committing. If a file looks
  unfamiliar or might carry a secret, open it rather than assuming the filename is honest.
- Don't commit or push unless asked.
- <Branch/PR convention for this repo, if any.>

## Project-specific constraints

<Delete this section if there are none. Otherwise list the things a newcomer breaks by accident:
 files that look editable but are generated, a migration that must not be edited in place,
 an API whose shape is pinned by an external consumer, directories that are vendored.>

- <constraint>
- <constraint>
