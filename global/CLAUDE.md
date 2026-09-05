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

- Look before you write: grep for an existing helper, util, or pattern first — re-implementing what already lives a few files over is the most common slop.
- Reach for the platform before writing code: a native input type, a CSS rule, or a DB constraint beats app-level logic doing the same job.
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.
- Cutting a real corner on purpose — a global lock, an O(n²) scan, a naive heuristic — leaves a marker: `# debt: <the ceiling>, <what triggers the upgrade>`, e.g. `# debt: O(n²) scan, index it above ~1k rows`. A ceiling with no trigger is the one that rots, so write both. Read the ledger on demand with `grep -rnE '(#|//) ?debt:' .` — never into a file that accumulates (L27).

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
| Cross-file Python rename/delete, or "who calls this?" on a colliding name | serena `find_referencing_symbols` / `rename_symbol` before editing — grep cannot separate 18 same-named `main`s |
| Bug fix | regression test first (tdd skill); gnarly/unclear bug → /diagnose |
| Slow page, new list/query endpoint | complexity-audit skill |
| New or changed logic with thin tests | test-coverage skill; critical pure logic → adversarial-tester |
| Feature declared done | /ship-check, then /verify |

Toolkit is advisory, never a gate: recommend or invoke, don't block on it.
</important>

## Reading accumulated context

Session reports, checkpoints, brainstorm ledgers, plan folders and lessons files
grow every session. Reading them whole is the expensive failure mode — most of a
long file is irrelevant to the question in hand, and the cost is paid in the
context you then don't have for the work.

Read in three layers, stopping at the first that answers you:

1. **Index** — filenames, index lines, one-liners, headings.
   Cheap, and usually enough to tell you which items are candidates.
2. **Neighbours** — for a candidate, the items next to it in time. What was
   happening around a session explains it more often than the session's own
   write-up does.
3. **Bodies** — open only what survived layers 1 and 2, and open those in full.

Never open bodies before reading the index. If you are opening a fourth file to
answer one question, you skipped a layer.

This is a rule about *search*, not about editing: an index line is never the file
(L01). Layer 1 tells you which file to open — it never tells you what the file
says, so anything you are about to change, retire, or delete still gets opened
first, in the same turn.

## Verification habits

Each of these cost a real session. One line each, distilled from a lessons ledger
kept outside this repo — which is why the ids are not contiguous.

- **Read the file before prescribing a fix for it** — no summary of a file is the file: not a directory listing, not a `MEMORY.md` index line, not a recalled description already sitting in your context. Before proposing a file be changed, retired, or deleted, open it in that same turn. (L01, L31)
- **Running a procedure against the one input where its defect cannot appear is not verification** — ask which input would expose the failure, and rehearse against that rather than the fixture nearest to hand. A documented setup was rehearsed from inside the tool's own directory, which carries its own project marker; every step printed success, and shipped telling readers to configure *their* project while targeting the tool's test project. Sibling instances in the same session: a grep whose pattern could not match its own claim, an exit code read through a pipe, a count that matched a comment, a diff blind to untracked files. One shape — a check exercised where it cannot fail. (L46)
- **Never document wiring you have not built** — describe what exists, name the gap separately. (L02)
- **Look at the rendered output before publishing** — static checks pass on defects only the eye catches. (L03)
- **Verify a third-party capability against its primary docs *before* recommending it**, not after the user accepts. (L04)
- **Changing a user-visible string isn't done until you grep for the old one** — docs quote output verbatim. (L05)
- **Resolve the symlink chain before treating a config/skill/hook edit as live** — the repo you are cwd'd in may not be what the runtime loads. (L06)
- **An unanchored grep is not an existence check** — a name that prefixes its siblings matches all of them. Anchor it, or prove it by import. (L15)
- **Establish a baseline with the project's canonical command** — your narrowed or extra-flagged variant tests something else. Per-file linting says nothing about a repo-wide gate. (L16)
- **Test a shell check by its exit status, not its text** — `grep -c` prints `0` *and* exits non-zero, so `$(cmd || echo 0)` yields two lines and every comparison against it is true. (L18)
- **A pipeline throws away the exit status you care about** — `$?` and `||` see only the *last* command, so `cmd | sed || echo absent` can never print `absent`: `sed` succeeds on empty input. Test the condition itself before any pipe (`if [ -d "$p" ]`), or read `${PIPESTATUS[0]}`. Three times in one session a missing path printed nothing and the silence got read as "inconclusive" rather than "absent", twice reporting a state that had never been established. (L47)
- **A reading of shared state goes stale the moment you stop looking at it** — re-sample at the point you act, not once per session. Concurrent sessions, hooks and timers rewrite `HEAD`, the index, `tracker.json` and registry rows underneath you, and a reading carried across a long session becomes a confident false claim. (L17)
- **After a command that mutates repo state** (`stash`/`checkout`/`reset`), **confirm it applied** before drawing any conclusion from the resulting tree. (L23)
- **Before crediting a fix with resolving a symptom reported elsewhere, reproduce that symptom's conditions** — a shared root-cause hypothesis is not evidence. (L24)
- **Announce a substituted choice at the moment you make it** — when the documented routing doesn't cover your case and you pick something else, say which was expected, why it didn't apply, and what you chose. Discovered later, it reads as drift. (L26)
- **In zsh, never name a variable `path`** (it is tied to `PATH`, and assigning it breaks every later command in that shell), **and never rely on an unquoted `$var` word-splitting** — a command held in a variable runs as one literal name. Write the command out, or use an array. When batching, let one real error through before concluding anything from exit codes. (L32)
- **Before adding to an accumulating artifact** (a log, a registry, a backlog), **check something consumes it** — an artifact that only grows is a liability, and contributing to it feels like diligence. (L27)
- **A parent-directory VCS check proves nothing about the directory you edited** — nested repos are invisible from above; run `git -C <dir>` there before declaring work unversioned or "nothing to commit". (L30)
- **A tool's dangerous behaviour is usually gated by how it is invoked** — before warning that something will fire, trace the call site for *that* mode; a flag one frame above the dangerous function can disable it entirely, and the repo's own docs may describe only the other mode. (L35)
- **A guard is proven by making it fire, not by reading it** — after writing a check, test, or sandbox, break what it protects and confirm it fails, and confirm it fires in the environment it exists for rather than only the one you are standing on. A sweep whose fallback matched *anything anywhere* passed the very case it existed to catch; a `HOME=` sandbox did nothing on Windows, where `Path.home()` reads `USERPROFILE`. (L33)
- **A delegated agent reporting that it *checked* something is not a guard that it stays true** — a subagent's one-off probe leaves no artifact, so before citing that property as a guarantee in a decision's rationale, a brief, or a handoff, grep for the test that enforces it and write one in the same pass if it is missing. Reading a lane's "purity probe → django-free: True" as a committed AST test put a guarantee that did not exist into a decision's reasoning and into the next lane's brief. (L42)
- **A key or match pattern must cover every case the surrounding rules permit, not the one you pictured** — and a comment asserting that it does is not a test of it. Ask what the system is allowed to vary, then key on all of it: a tracker port hashed from the repo path alone collided the instant two runs shared a repo, which the same skill's own parallel-run rule expressly allowed; a cleanup `pkill` scoped to a path prefix killed a peer session's live server. (L34)
- **When the user says a selection, mode, or other in-progress state should persist, every way of leaving the current item is its own behavior** — keys, buttons, clicks, sibling lists — not only the path they just demonstrated. A test and a fix for next/prev is not a persist fix if a thumbnail click still clears it. (L36)
- **When the user asks for a capability, wire it into the control they described using** — a hidden modifier path satisfies the data model, not the request. After building it, walk their own route to it: the button they named, the key they press, the click they described. Non-adjacent grouping shipped and tested behind ⌘-click while the Group button they actually press still built a contiguous span, so the answer to "can I group 1 with 5" was still no. (L39)
- **While the operator is running the thing you are refactoring, an intermediate broken state reaches them as a product bug** — say you are rewriting it and name the reload point, or land the change in one write. Treat any bug reported *during* an active refactor as suspect-yours first: a half-written file that referenced both the removed binding and its replacement was reported as a data bug, and cost a hunt through the model before the breakage turned out to be one turn old. (L38)
- **A single pass of a nondeterministic test is not evidence** — for an intermittent failure, one pass and one failure are the same observation, so a green run tells you it *has not failed yet*. Never let a durable artifact carry a verdict drawn from one run: publish after several consecutive passes, and when a claim has already been withdrawn once, re-run before restoring it. A concurrency spike was written up as "viable, build the port" on a single green Windows run; the next run failed the same test, the verdict had to be withdrawn in public, and it took four consecutive greens to earn back. (L43)
- **A PR's scope is whatever the forge says it is, not what your local diff says** — a pull request diffs against the *remote* base, so a local base that has drifted behind silently widens it beyond what was agreed. Check the base against its upstream before cutting the branch (`git rev-list --count origin/main..main`), and confirm the opened PR from the forge's own numbers (`gh pr view --json changedFiles,additions`), never from a three-dot diff against local. A fix agreed as "just this one change" was reported as 2 files / +25 from that local diff; the base was two commits stale, GitHub carried 15 files / +2205 including a backfill nobody had agreed to merge, and the wrong number stood for two turns. Same habit covers CI: read `gh pr checks` when the PR opens, not when someone asks to merge. (L22)

## Shared checkouts

A git checkout has **one HEAD and one index**. When two sessions share one, a branch switch or a
staging command in either reaches into the other's work — silently, and noticed only afterwards.

The `peer-session-notice` SessionStart hook warns when another session is live in this
same checkout, and `peer-session-guard` asks before the destructive git commands below.
Neither is a substitute for looking: a hook that fails open tells you nothing when it
fails, and a stale marker means idle, not absent. When you are sharing:

- **A grep answers the pattern you typed, not the question you meant** — never read absence from your own filtered output as absence in reality, and never count a proxy pattern as a count of the thing. A `git status | grep` whose filter omitted the path made a still-dirty file look committed, and a whole causal story got built on it and sent to a peer as fact; a `grep -c` over source text counted tuple-open parens and published the wrong row count. For existence, ask the specific path unfiltered (`git status --porcelain -- <path>`); for counts, ask the authoritative source, not a regex. (L40)
- **A failed commit in a shared checkout is a staged-state leak, not a retry** — your `git add`ed paths stay in an index the peer also writes, one path-less `git commit` away from riding into their work. Drain it in the same turn, before diagnosing. And never build the commit out of an unverified lookup: `git -c user.name="$(git config user.name)"` expanded to empty on a machine where that key was unset, aborted with `empty ident name`, and left eight paths staged while a peer session was actively committing. Let git use the repo's own identity. (L44)
- **Offer the user a worktree of your own before doing any *code* work**, and wait for their answer.
  If they accept, you are authorised to use **`EnterWorktree`** for this case specifically — that
  is what this paragraph exists to permit. Never relocate unasked. Board work is the carve-out in
  the next bullet: it stays in the shared checkout even when a worktree is already on offer.
- **A worktree isolates code; it forks the board** — `board/next_ids` and `board/events.jsonl` are
  tracked files, so a worktree carries a *copy* of the id counters at its base commit. Anything that
  mints an id in there — `taskman task add` / `capture add`, a plan import, a `/wrap-up` board sync —
  allocates against that stale counter and hands out ids the real board has already issued. Torn
  down, that work is lost; merged back it is worse, because the stale `next_ids` overwrites the live
  one and the next session re-mints ids that already exist. **Worktree for code work only.** Grill,
  plan import, board sync and every `taskman … add` stay in the shared checkout, and an isolated lane
  that needs a board row reports it in its `## Verification` instead, for the orchestrator to file
  from the main checkout after merge-back. Scope any lane isolation to lanes that touch source only.
  (L49)
- Check `worktree.baseRef` before assuming what you branched from: `fresh` (the default) branches
  from `origin/<default-branch>`, **not** your current HEAD. If your work depends on uncommitted or
  unpushed state, a fresh worktree will not have it — say so rather than starting from a base the
  user did not expect.
- If they decline, prefer **`git commit -- <paths>`** over `git add` + `git commit`: it commits
  those paths and ignores the index entirely, so it cannot pick up a peer's staged file.
  Everything after `--` is a pathspec, so the message flag goes *before* it:
  `git commit -F <msgfile> -- <paths>`, never `git commit -- <paths> -m "…"`, which fails with
  `pathspec '-m' did not match any file(s)`. The pathspec matches only *tracked* files, so a file
  you just created needs `git add <that path>` first — then confirm the index holds only it
  (`git diff --cached --name-only`) before you commit. Give
  `git add` explicit paths, never switch branches, and never `git stash` / `reset --hard` /
  `clean -fd`.
- **That same blindness to the index makes `git commit -- <paths>` the wrong tool for untracking** —
  it reads the working tree, so a staged deletion from `git rm --cached` is discarded and the file is
  re-committed from disk. A commit whose message said "untrack the activity trails" reported
  `4 files changed, 166 insertions(+)` and left all three still tracked. Untracking needs a bare
  `git commit`, which respects the index — and is therefore the form that *can* sweep up a peer's
  staging, so inspect it first (`git diff --cached --name-status`) and confirm it holds only your
  paths. The two forms do not compose. (L45)
- **A repo's own sync, format or codegen command may itself run git** — read what it does to the
  tree before running it here, and say so *before* you run it, not after. `bin/ai-sync` auto-commits
  its managed categories (`agents/`, `hooks/`, `skills/`, `global/`) — exactly what a peer working
  on this harness is dirtying — and one run swept six of a live session's uncommitted files, three
  of them brand new, into a `sync:` commit that told none of their story. That one is gated now;
  the next such command will not be. (L41)
- **A fact stated once in a session is not still true when you reuse it** — a push-status count, an
  ahead/behind number, a test flag that worked — re-derive it at the point you restate or rely on it
  again, in the specific clone or context at hand, rather than repeating an earlier reading from memory
  or a prior message to someone else. Twice in one session an unpushed-commit count for a git clone was
  reported from a stale local remote-tracking ref never re-fetched before the claim (2 vs. the true 39;
  "exactly at origin/master" vs. the true 5 behind), caught only after a later fetch contradicted it.
  Separately, a `--noconftest` flag recommended to a peer session went stale when that peer's own lane
  converted the target repo's `conftest.py` to no longer need a database — the same flag, reused hours
  later without re-checking, then broke two new tests by skipping a fixture they needed. (L48)
