# Global coding guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Apply to all projects.

## Think before coding

Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.
- Every question, option, or finding you surface to the operator includes **your recommendation and why** — not a bare menu.

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
| Loop stuck / fix-round limit / plan drift mid-go | recover skill (`/recover`, R-06 / R-07) |
| Bug with a repro path | `/fix-bug` (tdd + diagnose pointers) |
| Refactor — structure only, no behavior change | `/refactor` |
| Production incident | `/incident` (human stabilizes first) |
| Slow page, new list/query endpoint | complexity-audit skill |
| New or changed logic with thin tests | test-coverage skill; critical pure logic → adversarial-tester |
| Feature declared done | /ship-check, then the project's own /verify-equivalent post-build protocol if it defines one — this harness ships none |

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

- **Read the file before prescribing a fix for it** — no summary of a file is the file: not a directory listing, not a `MEMORY.md` index line, not a recalled description already sitting in your context. Before proposing a file be changed, retired, or deleted, open it in that same turn. The same holds for a *finding*: its one-line summary in a report or verification record keeps the headline and drops the constraints, so open the board row or review body before recommending a fix. Working from a summary of a board row, I recommended "reuse the placeholder only if inactive"; the row's own condition added "and no usable password", because every signup is created inactive *with* one — the recommended check would have adopted it. (L01, L31, L63)
- **Running a procedure against the one input where its defect cannot appear is not verification** — ask which input would expose the failure, and rehearse against that rather than the fixture nearest to hand. A documented setup was rehearsed from inside the tool's own directory, which carries its own project marker; every step printed success, and shipped telling readers to configure *their* project while targeting the tool's test project. Sibling instances in the same session: a grep whose pattern could not match its own claim, an exit code read through a pipe, a count that matched a comment, a diff blind to untracked files. One shape — a check exercised where it cannot fail. (L46)
- **Mutation coverage is not fixture coverage** — a suite whose mutants all die still only exercises the shapes you imagined, so when a corpus of real inputs already exists on disk, run against it before believing the suite. A rewritten wave-membership parser had 36 green tests and five of five mutants dying, and still dropped a lane on `A — judge-rules ‖ B — judge-reference-set` (the em dash labels each lane there, it does not end the list) — on a stem that was running at the time. Every fixture was hand-invented; the 105-bullet corpus that had diagnosed the original bug was the thing that exposed the fix's own. Re-run the real inputs through the new code, not just the old. (L54)
- **Never document wiring you have not built** — describe what exists, name the gap separately. (L02)
- **Look at the rendered output before publishing** — static checks pass on defects only the eye catches. (L03)
- **Verify a third-party capability against its primary docs *before* recommending it**, not after the user accepts. A scanner's or linter's remediation text is a claim, not a source: a skylos "pin to a dated model id" finding became advice to pin `claude-opus-5`, which the models overview says is already a pinned snapshot, and the user had accepted the advice before anyone read the docs. (L04, L64)
- **Changing a user-visible string isn't done until you grep for the old one** — docs quote output verbatim. (L05)
- **Resolve the symlink chain before treating a config/skill/hook edit as live** — the repo you are cwd'd in may not be what the runtime loads. (L06)
- **When two tools disagree about the same fact, neither reading is usable until you know which is authoritative** — and never report the one that fits your current hypothesis. Twice in one session a healthy background agent was reported as stalled: `wc -c` read a subagent transcript at 1,764,831 bytes while `stat` reported 129 and a frozen mtime, and `find -newermt '-90 minutes'` returned nothing while `git status` listed six modified files in the same tree. For subagent transcripts use `wc -c`, never `stat`/`ls`; for tree state use `git status`, never `find -newermt`. (L52)
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
- **Never call a code path unreachable because a guard above it should catch that input** — execute the guard once per input class it is meant to cover, and diff the observable outcome of both branches. Reading a guard tells you what it was written to do, not what it does. A defensive `x or {}` was called behaviour-preserving because the arity guard above it "makes None unreachable"; the guard's helper unioned team rows with the sport's *system* set, so it covered only one sport, and for the other the None reached the call and flipped a rejected draft into a resolved play — inside a commit whose whole premise was zero drift. One run of the guard per sport would have shown it. (L60)
- **A delegated agent reporting that it *checked* something is not a guard that it stays true** — a subagent's one-off probe leaves no artifact, so before citing that property as a guarantee in a decision's rationale, a brief, or a handoff, grep for the test that enforces it and write one in the same pass if it is missing. Reading a lane's "purity probe → django-free: True" as a committed AST test put a guarantee that did not exist into a decision's reasoning and into the next lane's brief. (L42)
- **A key or match pattern must cover every case the surrounding rules permit, not the one you pictured** — and a comment asserting that it does is not a test of it. Ask what the system is allowed to vary, then key on all of it: a tracker port hashed from the repo path alone collided the instant two runs shared a repo, which the same skill's own parallel-run rule expressly allowed; a cleanup `pkill` scoped to a path prefix killed a peer session's live server. (L34)
- **The same holds for a fix's own setup: when you cure shared-state contention by giving each run its own copy, run two copies of the fix against each other before shipping** — the per-run setup can still write something shared, and a loop that only pits the fix against the old victim cannot see it. A flaky suite was fixed by giving migration tests a private database per session, verified 0/20 beside the old victim, guards shown to fire, full suite green — and review still found it broken: building each database from base re-ran a migration that `ALTER ROLE`s a cluster-wide role and holds the row until the whole upgrade commits, so two overlapping sessions failed one of them outright (`tuple concurrently updated`, 6 of 6 rounds). An advisory lock around the build made it 0 of 6; removing only the lock brought it back. Ask what the per-run step still touches globally — catalog rows, a port, a lockfile — and overlap two runs of it. (L62, extending L34 from a key to a setup's side effects)
- **And the constant you are replacing was doing a second job: ask what it did besides collide** — swapping a fixed shared identifier for a per-run random one removes whatever self-healing the fixed value provided, because the next run no longer knows the last one's id. Hard-coded test tenants made two overlapping pytest runs destroy each other, and `uuid4` per run fixed that on every check I ran — 0 of 30 overlapping rounds against 30 of 30 before, full suite green, every mutant dying. Review still found it broken: the fixed ids were also what let each run delete the rows a SIGKILLed predecessor left behind, and a nearby test asserts on a whole table, so one killed run would have failed it forever. Keep a recognizable marker inside the random id and sweep marked rows older than any live test could hold them — then prove it by killing a run mid-test and watching its leftovers survive while fresh and vanish once backdated. (L70, the inverse of L62 — there the per-run copy still touched something global, here it stopped touching something it should have)
- **When the user says a selection, mode, or other in-progress state should persist, every way of leaving the current item is its own behavior** — keys, buttons, clicks, sibling lists — not only the path they just demonstrated. A test and a fix for next/prev is not a persist fix if a thumbnail click still clears it. (L36)
- **When the user asks for a capability, wire it into the control they described using** — a hidden modifier path satisfies the data model, not the request. After building it, walk their own route to it: the button they named, the key they press, the click they described. Non-adjacent grouping shipped and tested behind ⌘-click while the Group button they actually press still built a contiguous span, so the answer to "can I group 1 with 5" was still no. (L39)
- **While the operator is running the thing you are refactoring, an intermediate broken state reaches them as a product bug** — say you are rewriting it and name the reload point, or land the change in one write. Treat any bug reported *during* an active refactor as suspect-yours first: a half-written file that referenced both the removed binding and its replacement was reported as a data bug, and cost a hunt through the model before the breakage turned out to be one turn old. (L38)
- **A single pass of a nondeterministic test is not evidence** — for an intermittent failure, one pass and one failure are the same observation, so a green run tells you it *has not failed yet*. Never let a durable artifact carry a verdict drawn from one run: publish after several consecutive passes, and when a claim has already been withdrawn once, re-run before restoring it. A concurrency spike was written up as "viable, build the port" on a single green Windows run; the next run failed the same test, the verdict had to be withdrawn in public, and it took four consecutive greens to earn back. (L43)
- **A PR's scope is whatever the forge says it is, not what your local diff says** — a pull request diffs against the *remote* base, so a local base that has drifted behind silently widens it beyond what was agreed. Check the base against its upstream before cutting the branch (`git rev-list --count origin/main..main`), and confirm the opened PR from the forge's own numbers (`gh pr view --json changedFiles,additions`), never from a three-dot diff against local. A fix agreed as "just this one change" was reported as 2 files / +25 from that local diff; the base was two commits stale, GitHub carried 15 files / +2205 including a backfill nobody had agreed to merge, and the wrong number stood for two turns. Same habit covers CI: read `gh pr checks` when the PR opens, not when someone asks to merge. (L22)
- **A two-dot diff between branch tips is not a commit's contents** — `git diff A..B` answers "how do these two tips differ", which in a shared checkout is dominated by whatever one side simply has not pulled. Ask a commit what it changed (`git show --stat <sha>`), and a range only what a range knows. Checking whether a peer's unpushed commit had reverted a PR I had just merged, I read `git diff --name-only origin/main..main` as that commit's file list: four of the five were the PR's own files, so it read as a revert, and I said so before checking. They were listed only because local `main` lacked the merge `origin` already had — the commit itself touched one unrelated docs file. The failure mode is specific and expensive: it manufactures phantom authorship, and the accusation lands on a peer. (L75, the range-vs-commit cousin of L22)
- **Resolve a live path with the interpreter or runtime that will load it** — `realpath` on a symlink and a bare `python3` each answer a different question than *"what does the thing that runs this actually import?"*. A hook symlink resolves fine that way; an editable-install package does not, because its root lives in `site-packages/*.pth` and depends on which interpreter you asked. A mid-run fix to `taskman`'s `check_verification` was written, tested and passed 15/15 in a second clone of the harness — a checkout nothing runs — because the path was confirmed with bare `python3`, while the gate under test loads from the other clone via the project venv. The real gate kept failing after a "passing" fix. Read the `.pth`, or import through the exact interpreter the runtime uses. (L56, extending L06 — whose "symlink chain" wording did not reach this case)
- **A configurable location has a default, and the default is not the answer — ask the tool where it actually looks.** Reporting *absence* from the conventional path is the expensive form, because it enters an argument as negative evidence rather than a reading anyone thinks to check. Asked whether anything blocked pushing, I listed `.git/hooks/`, saw only `*.sample`, and reported there was no pre-push hook — half the evidence for "no push policy exists". The push then ran one: `core.hooksPath` pointed at the repo's own `githooks/`, and `git rev-parse --git-path hooks` would have said so in a single call. Every configurable root has this shape — `core.hooksPath`, `PYTHONPATH`, `$ZDOTDIR`, `XDG_CONFIG_HOME`, pytest's `rootdir`, a `--config` flag one frame up. Ask the tool, never the convention. (L59, extending L06/L56 to the case where the *mechanism*, not the file, sits at an address you never checked — and L40, since absence sought at the wrong address reads exactly like absence)
- **That same question applies to a tool's *namespace*, not just its path** — anything that derives a project or scope from the working directory answers only about that scope. Inside a git worktree `docker compose` builds its project name from the directory, so it addresses a *different* stack than the main checkout: its empty `ps` is not "the service is down", and its `up` starts a parallel container rather than attaching to the running one. Diagnosing 38 pytest failures I read a header-only `docker compose ps` as the database being down and said so; the real database container had been up nine hours, and the `up` that followed died on the bound port and left a stray container, volume and network behind. Ask the resource, not the scoped view — `docker ps --filter publish=<port>` names the container *and* its compose project. (L61, extending L59 from a path to a namespace)
- **A freshly-run command is not a fresh reading when it reads a local cache** — `origin/master` is not the remote, it is a copy that moves only on `git fetch`, so `git rev-list --count origin/master..master` answers "ahead of the last time I fetched" and answers it with no hint that it is stale. Asked to push two repos, I ran that fresh at the moment of the claim and reported one "5 unpushed" when a background sync had already pushed it to zero — and the same number had been wrong twice before (L48's evidence: 2 vs. the true 39, and "exactly at origin/master" vs. the true 5 behind), once in a published artifact that had to be struck through. So re-deriving is not enough when the source is itself a cache: refresh it in the same turn you read it (`git fetch` before any ahead/behind, `--refresh`/`--no-cache` before a version or index claim, a re-fetch before a memoized client's answer). (L71 — L48 says re-derive at the point you act, and I did; L58 says cite the command that prints the number, and here that command prints a stale one)
- **A file bound to copies in other trees is not landed until it lands in every one** — before the first edit, ask the binding which trees own the path (a drift manifest, a mirror or sync config, a `canonical home` note), not the clones you happen to have open. Rescuing three deleted taskman tests, I proved the modules under test byte-identical between a stale source clone and the private harness clone, made the regressions fire under a mutant, committed, and called it five minutes — while the drift manifest locked every tracked `taskman/tests/` path as `match` to this published tree, which lacked the tests too, and the `taskman/pyproject.toml` I had already read said `canonical home: ai-wow`. I even ran L56's check — through the private clone's own venv, which can only ever answer for that clone. Only the pre-push drift gate caught the half-landing, and that gate skips on a machine with no sibling configured and merely reports a drift left uncommitted: it is a backstop, not the check. (L65, extending L56 from what a runtime imports to which trees a write must reach)
- **A settings default is not the resolved value** — before asserting what a config resolves to, resolve it *in the target environment*, because the env file you did not read is where the override lives. Enabling dev rate limits with a comment reasoning about "the default `LocMemCache`" shipped a regression: `.env.local` sets `CACHE_REDIS_URL`, so the default cache was Redis, and `django_ratelimit` catches only `socket.gaierror` — a `ConnectionError` escapes before `RATELIMIT_FAIL_OPEN` is ever reached, turning a stopped container into a 500 on every login. Reading the settings modules is not reading the environment. (L57)
- **Never hand-write a derived value into a durable artifact** — a timestamp, a count, a diffstat, a token total. Derive it from the source that can produce it, or omit the field; a number typed from memory is wrong at a rate no reader can detect. A long orchestration wrote ~10 wrong values into its own board and report, including an agent span ending 9h21m *before* it started and "22 mutants" where a table row said one was proved without a mutant. None survived a fresh reader. Spawn that reader before calling a run finished: the author is structurally blind to their own dropped writes. Diffstats are now gated: the action-report gate refuses a `+N/−M` with no `--numstat`/`--shortstat` or `a..b` range on its line (L58; recurred 2026-09-17 with this line loaded, gated 2026-09-18)
- **When a command prints the id of the thing it just created, chain from that printed id** — a listing piped through `grep`/`tail` answers "the last row matching my filter", never "the thing I just made", and on a board four sessions are writing those are different rows seconds apart. Filing a follow-up task and setting its status in one shell line, I read the id back with `taskman board | grep -oE '#[0-9]+' | tail -1` although `task add` had already printed `#12252`; the pipeline returned `#12240` and moved *another session's* task to `todo`. Recovered only because the move echoes the title it changed — the original status came from that task's own `task.add` event in `board/events.jsonl`, not from memory. Capture the id at creation, or ask the issuing system for it by a key you supplied. (L72, the identifier case of L40 — and a cousin of L58, since an id re-derived from a listing is a hand-written value wearing a command's clothes)

## Shared checkouts

A git checkout has **one HEAD and one index**. When two sessions share one, a branch switch or a
staging command in either reaches into the other's work — silently, and noticed only afterwards.

The `peer-session-notice` SessionStart hook warns when another session is live in this
same checkout, and `peer-session-guard` asks before the destructive git commands below.
Neither is a substitute for looking: a hook that fails open tells you nothing when it
fails, and a stale marker means idle, not absent. When you are sharing:

- **A grep answers the pattern you typed, not the question you meant** — never read absence from your own filtered output as absence in reality, and never count a proxy pattern as a count of the thing. A `git status | grep` whose filter omitted the path made a still-dirty file look committed, and a whole causal story got built on it and sent to a peer as fact; a `grep -c` over source text counted tuple-open parens and published the wrong row count. For existence, ask the specific path unfiltered (`git status --porcelain -- <path>`); for counts, ask the authoritative source, not a regex. (L40)
- **A failed commit in a shared checkout is a staged-state leak, not a retry** — your `git add`ed paths stay in an index the peer also writes, one path-less `git commit` away from riding into their work. Drain it in the same turn, before diagnosing. And never build the commit out of an unverified lookup: `git -c user.name="$(git config user.name)"` expanded to empty on a machine where that key was unset, aborted with `empty ident name`, and left eight paths staged while a peer session was actively committing. Let git use the repo's own identity. (L44)
- **Never mutate source on disk in a tree another session or reviewer reads** — patch it in memory (a `pytest -p <plugin>` at `pytest_configure`, patching the module or the template loader) so no window exists where the tree carries a deliberate defect. A reviewer rewriting files on disk left ~90 seconds where a page had its entire error block deleted; a peer attributed four intermittent failures to it and had to re-measure in a pristine `git archive` tree. If a source-text guard forces a real file, point its `__file__` at a scratch copy. (L51)
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
- **`git commit --amend` is the wrong tool in a shared checkout, twice over** — it rebuilds the commit
  from your pathspec rather than adding to it, so everything else in that commit silently falls back
  out; and it amends whatever `HEAD` is *now*, which here may be a peer's commit that landed in the
  seconds since yours. Both fired at once: a ledger row left out of its routing commit was folded in
  with `git commit --amend -F msg -- <paths>`, and in *both* trees a peer had committed in the gap, so
  the amend rewrote **their** commit under my message — absorbing 84 lines of their work while dropping
  my own two files out. Caught only by reading the diffstat (`3 files, 84 insertions` where ~3 were
  expected). Add a follow-up commit that says why it is separate. To recover a clobbered commit,
  `git reset --soft <its sha>` from the reflog — it leaves the worktree alone — then re-commit by
  explicit path and confirm the original sha still reaches `HEAD`. (L55)
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
