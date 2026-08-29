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
| `.py` importing FastAPI / SQLAlchemy, ready to commit | `backend-reviewer` |
| `.py` importing Streamlit | `streamlit-reviewer` |
| `.jsx` / `.tsx` React or Next component | `frontend-reviewer` |
| Templates, `.html`, `.js` with no component framework (vanilla, jQuery, HTMX) | `classic-web-reviewer` |
| One diff touching both a Python route and its template (HTMX, Jinja) | **both** `backend-reviewer` and `classic-web-reviewer` — dispatch is by file type, so a mixed diff needs both halves reviewed |
| Non-Python backend diff ready to commit | stack reviewer subagent matching the project |
| Prompts, tool-calling, agents, RAG, model endpoints | llm-sec-review subagent alongside the stack reviewer |
| Auth, payments, uploads, secrets, settings | suggest /security-review before commit |
| Bug fix | regression test first (tdd skill); gnarly/unclear bug → /diagnose |
| Slow page, new list/query endpoint | complexity-audit skill |
| New or changed logic with thin tests | test-coverage skill; critical pure logic → adversarial-tester |
| Feature declared done | /ship-check, then /verify |

Toolkit is advisory, never a gate: recommend or invoke, don't block on it.
</important>

## Verification habits

Each of these cost a real session. One line each, distilled from a lessons ledger
kept outside this repo — which is why the ids are not contiguous.

- **Read the file before prescribing a fix for it** — no summary of a file is the file: not a directory listing, not a `MEMORY.md` index line, not a recalled description already sitting in your context. Before proposing a file be changed, retired, or deleted, open it in that same turn. (L01, L31)
- **Never document wiring you have not built** — describe what exists, name the gap separately. (L02)
- **Look at the rendered output before publishing** — static checks pass on defects only the eye catches. (L03)
- **Verify a third-party capability against its primary docs *before* recommending it**, not after the user accepts. (L04)
- **Changing a user-visible string isn't done until you grep for the old one** — docs quote output verbatim. (L05)
- **Resolve the symlink chain before treating a config/skill/hook edit as live** — the repo you are cwd'd in may not be what the runtime loads. (L06)
- **An unanchored grep is not an existence check** — a name that prefixes its siblings matches all of them. Anchor it, or prove it by import. (L15)
- **Establish a baseline with the project's canonical command** — your narrowed or extra-flagged variant tests something else. Per-file linting says nothing about a repo-wide gate. (L16)
- **Test a shell check by its exit status, not its text** — `grep -c` prints `0` *and* exits non-zero, so `$(cmd || echo 0)` yields two lines and every comparison against it is true. (L18)
- **After a command that mutates repo state** (`stash`/`checkout`/`reset`), **confirm it applied** before drawing any conclusion from the resulting tree. (L23)
- **Before crediting a fix with resolving a symptom reported elsewhere, reproduce that symptom's conditions** — a shared root-cause hypothesis is not evidence. (L24)
- **Announce a substituted choice at the moment you make it** — when the documented routing doesn't cover your case and you pick something else, say which was expected, why it didn't apply, and what you chose. Discovered later, it reads as drift. (L26)
- **In zsh, never name a variable `path`** (it is tied to `PATH`, and assigning it breaks every later command in that shell), **and never rely on an unquoted `$var` word-splitting** — a command held in a variable runs as one literal name. Write the command out, or use an array. When batching, let one real error through before concluding anything from exit codes. (L32)
- **Before adding to an accumulating artifact** (a log, a registry, a backlog), **check something consumes it** — an artifact that only grows is a liability, and contributing to it feels like diligence. (L27)
- **A parent-directory VCS check proves nothing about the directory you edited** — nested repos are invisible from above; run `git -C <dir>` there before declaring work unversioned or "nothing to commit". (L30)
- **A guard is proven by making it fire, not by reading it** — after writing a check, test, or sandbox, break what it protects and confirm it fails, and confirm it fires in the environment it exists for rather than only the one you are standing on. A sweep whose fallback matched *anything anywhere* passed the very case it existed to catch; a `HOME=` sandbox did nothing on Windows, where `Path.home()` reads `USERPROFILE`. (L33)

## Shared checkouts

A git checkout has **one HEAD and one index**. When two sessions share one, a branch switch or a
staging command in either reaches into the other's work — silently, and noticed only afterwards.

**Nothing warns you.** No peer-session hook ships here, so treat a shared checkout as
possibly-shared *by default* and look before doing git work — a commit in `git log` you
did not make, or a modified file you did not touch, is the tell. Then:

- **Offer the user a worktree of your own before doing any git work**, and wait for their answer.
  If they accept, you are authorised to use **`EnterWorktree`** for this case specifically — that
  is what this paragraph exists to permit. Never relocate unasked.
- Check `worktree.baseRef` before assuming what you branched from: `fresh` (the default) branches
  from `origin/<default-branch>`, **not** your current HEAD. If your work depends on uncommitted or
  unpushed state, a fresh worktree will not have it — say so rather than starting from a base the
  user did not expect.
- If they decline, prefer **`git commit -- <paths>`** over `git add` + `git commit`: it commits
  those paths and ignores the index entirely, so it cannot pick up a peer's staged file. Give
  `git add` explicit paths, never switch branches, and never `git stash` / `reset --hard` /
  `clean -fd`.
