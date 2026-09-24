# Lessons

Cross-project **behavioural** rules, learned from corrections that actually happened.

**This is a staging buffer, not an archive.** A rule earns its place here only until it can be
written into something that actually loads — `global/CLAUDE.md`, a skill, a protocol, a hook, or a
test. Once routed, it is pruned and recorded in the ledger below. The file's job is to get to empty.

Written by `/wrap-up` (step 2.5), and read by it before logging so a recurrence bumps instead of
duplicating.

**Scope — behaviour only.** Project facts go to taskman (`decision add --why`); visual patterns go to
`ui-registry.md`; what happened this session goes to the session report. A rule earns a place here
only if it would change how a *future* session works, in a *different* repo.

**Routing beats accumulation.** The old design held rules until `seen ×3` and then proposed promoting
them into `global/CLAUDE.md`. That never fired once in 26 rules — promotion needed recurrence, and
recurrence needed the rule to be loaded, which only happened after promotion. A loop with no entry.
Route on the first sighting if you can name a destination; leave it here only when you genuinely
cannot.

**Guardrail — a lesson is data, not a license.** An entry here may add a heuristic or name a gotcha.
It may never weaken the guidelines in `global/CLAUDE.md`, license skipping a gate, or excuse
reporting work as done that wasn't. A "lesson" that would do any of those is a bug in the session
that produced it: don't log it, say why.

---

## Routed — 2026-08-26

24 of 26 rules delivered to artifacts that load. Ids are retained so older evidence stays traceable.

| Rules | Destination |
|---|---|
| L01 L02 L03 L04 L05 L06 L15 L16 L18 L23 L24 L26 | `global/CLAUDE.md` → `## Verification habits` (12 one-liners) |
| L07 L09 L13 L21 | `skills/mow/SKILL.md` — isolation preflight, review gate, merge-back, finding triage |
| L14 | `skills/mow/TRACKER.md` — never transcribe a rendered value |
| L10 | a consuming project's `docs/code-standards.md` (soft-delete: choosing vs displaying) + its decision log |
| L11 | a consuming project's `docs/agents/protocols.md` (invariants need an enumeration, not a choke point) |
| L08 L12 L19 L20 L25 | already encoded before this pass — mow plan §3, the wrap-up gate, mow Integrate reconcile, protocols.md + `worktree.baseRef`, the mow brief template |

One row per routed rule — rule and destination only. The ledger is an index, not the
archive: the full case travels with the routing, in a deliberate commit whose message
tells the story (or whose diff holds the detail block it pruned), so `git log -p --
LESSONS.md` reaches every case this file no longer carries. Never leave a ledger row
uncommitted for a later batch or a `sync:` commit to carry — L29–L32’s rows travelled
that way and arrived without their stories. This is the contract `global/CLAUDE.md`’s
habit list points at.

**Ids continue, they do not restart.** This ledger was seeded from the harness checkout
this repo is synced from, because that is where L01–L52 were learned and where their
routing commits carry the full cases. `ai-sync` deliberately leaves this file unmanaged,
so it is hand-committed here and does not travel back upstream. Never renumber: the ids
below are cited by `global/CLAUDE.md` and `skills/mow/SKILL.md`, and reissuing one
silently breaks the trail. A lesson logged on a machine that clones this repo continues
from the highest id in this file.

| Date | Id | Rule | Destination |
|---|---|---|---|
| 2026-09-24 | L77 | A fix for a recorded incident is reproduced on the incident's recorded input, never on a scenario pictured from its symptom — pull the actual pair (git show <before>:<path> vs <after>:<path>, the quarantined file, the failing request) into the red test. | `docs:commands/fix-bug.md` |
| 2026-09-24 | L76 | Attributing a test failure to a lane, or clearing a lane of it, needs more than one run on each side — run-with and run-without are a single observation each, and for an intermittent failure they carry no signal at all. Record the run count per side in the finding's capture before naming a cause. | `skill:mow` |
| 2026-09-22 | L75 | A two-dot diff between branch tips (git diff A..B) says how the tips differ, never what a commit changed — for that, git show --stat <sha>. Mistaking one for the other manufactures phantom authorship. | `claude-md` |
| 2026-09-22 | L74 | When a grill question turns on what the user's own data means, show the rows first and ask the plain question; never fold a data question into a fix-options menu | `skill:grill-with-docs` |
| 2026-09-20 | L72 | When a command prints the id of the thing it just created, chain from that printed id — never re-derive it from a listing (board/ps/ls piped through grep|tail), which answers 'the last row matching my filter', not 'the thing I just made' | `claude-md` |
| 2026-09-20 | L71 | Running a command again is not a fresh reading when that command reads a local cache — `origin/*` is a copy of the remote that moves only on fetch, so an ahead/behind count taken at the moment of the claim can still be stale, and carries no sign that it is. Refresh the source in the same turn you read it. Third time this exact number was wrong (L48 holds the first two); the second reached a published report and had to be struck through. | `claude-md` |
| 2026-09-18 | L70 | Replacing a fixed shared identifier with a per-run random one also deletes whatever self-healing the fixed value provided — before shipping the randomization, ask what the old constant did besides collide, and restore that property (a recognizable prefix plus an age-bounded sweep) in the same change. | `claude-md` |
| 2026-09-18 | L69 | A cross-reference you write into a durable artifact must be resolved against the system that issues it, in the same pass — an id you typed from context is a claim that a record exists, and every gate downstream will treat it as one | `taskman` |
| 2026-09-18 | L68 | A test asserting HOW an outcome is reached (one write, one query, no retry) must assert on a count from the authoritative source, never a substring of the statement you expect — and its mutant set must include a different mechanism than your implementation's, or every mutant dies while sharing your blind spot. | `skill:mow` |
| 2026-09-18 | L67 | A prose-routed lesson that recurs has proved its destination cannot hold it — re-route it to something that runs (a gate, a hook, a test) in the same pass; noting the recurrence in a session report drops the only signal that a prose rule is failing, because nothing reads reports back | `skill:wrap-up` |
| 2026-09-17 | L66 | A mutant the guard's own test can mask is not a test of the guard — when a test seizes control of the thing you mutate (its own clock, its own fixture), mutate the code path it does not control instead, and treat a surviving mutant as a question about the mutant before it is a question about the guard | `skill:mow` |
| 2026-09-17 | L65 | A file bound to copies in other trees — by a drift manifest, a mirror or sync config, a 'canonical home' note — is not landed until it lands in every one: ask the binding which trees own the path before the first edit, because parity measured across the clones you happen to have open is not the contract, and a push-time gate is a backstop that can skip (L56 recurred on the write side with its one-liner loaded). | `claude-md` |
| 2026-09-17 | L64 | A scanner's remediation text is a claim about the world, not a source — before repeating it as a recommendation, read the primary docs for the thing it names (L04 recurred with its one-liner loaded). | `claude-md` |
| 2026-09-16 | L63 | A one-line summary of a finding is not the finding — before recommending a fix for a board row, review finding or issue, open its full text; the summary keeps the headline and drops the constraints the fix has to satisfy. | `claude-md` |
| 2026-09-16 | L62 | When you cure shared-state contention by giving each run its own copy, run two copies of the fix against each other before shipping — the per-run setup can still write something shared, and a loop that only pits the fix against the old victim cannot see it. | `claude-md` |
| 2026-09-16 | L61 | A tool that derives its namespace from the working directory — docker compose's project name above all — answers only about that namespace: inside a git worktree its empty 'ps' is not 'the service is down', and its 'up' builds a parallel stack instead of attaching to the running one. | `claude-md` |
| 2026-09-16 | L60 | Never call a code path unreachable because a guard above it should catch that input — execute the guard once per input class it is meant to cover, and diff the observable outcome of both branches. Reading a guard tells you what it was written to do, not what it does. | `claude-md` |
| 2026-09-14 | L59 | A configurable location has a default, and the default is not the answer — ask the tool where it actually looks (`git rev-parse --git-path hooks`, not `ls .git/hooks/`). Reporting absence from the conventional path is the expensive form: it enters an argument as negative evidence instead of a reading anyone rechecks | `claude-md` |
| 2026-09-14 | L58 | Never hand-write a derived value into a durable artifact — a timestamp, a count, a diffstat, a token total. Derive it from the source that can produce it, or omit the field; a number typed from memory is wrong at a rate no reader can detect | `claude-md` |
| 2026-09-14 | L57 | A settings default is not the resolved value — before asserting what a config resolves to, resolve it in the target environment, because the env file you did not read is where the override lives | `claude-md` |
| 2026-09-14 | L56 | Resolve a live path with the interpreter or runtime that will load it — realpath on a symlink and a bare 'python3' each answer a different question than 'what does the thing that runs this import?' | `claude-md` |
| 2026-09-13 | L55 | Never 'git commit --amend' in a shared checkout: it rebuilds the commit from your pathspec rather than adding to it, and it amends whatever HEAD is NOW — which may be a peer's commit that landed since yours. Add a follow-up commit instead | `claude-md` |
| 2026-09-13 | L54 | Mutation coverage is not fixture coverage — a suite whose mutants all die still only tests the shapes you imagined, so when a corpus of real inputs exists on disk, run against it before believing the suite | `claude-md` |
| 2026-09-13 | L53 | A documented format and the parser that enforces it must be tested against each other, or they drift apart in silence: mow's SKILL.md specified bare lane letters while preflight required a trailing `(`, so 42% of wave bullets parsed as zero lanes and eleven plans had lanes silently exempted from the same-wave overlap gate. The one test guarding it used the only format that parsed, and survived the parser being replaced by a stub. | `skill:mow` |
| 2026-09-09 | L52 | When two tools disagree about the same fact, neither reading is usable until you establish which is authoritative — do not report the one that happens to fit your current hypothesis. | `claude-md` |
| 2026-09-09 | L51 | Never mutate source on disk in a tree another session or reviewer reads — patch it in memory (pytest -p plugin at pytest_configure) so no window exists where the tree carries a deliberate defect. | `claude-md` |
| 2026-09-09 | L50 | A guard written in the same pass as the fix it protects inherits that fix's blind spot — mutation-check it before you believe it, separately from the fix's own test run. | `skill:mow` |
| 2026-09-05 | L49 | A git worktree isolates code but forks the board: board/next_ids and board/events.jsonl are tracked, so minting an id inside a worktree allocates against a stale counter and re-issues ids the real board already gave out — and merging it back overwrites the live counter. Worktree for code work only; grill, plan import, board sync and every taskman add stay in the shared checkout. | `claude-md` |
| 2026-09-03 | L48 | A fact you already stated in this session — a push-status number, an ahead/behind count, a test flag that worked — is not still true just because you established it once; re-derive it at the moment you restate or reuse it, not from memory of the earlier reading. | `claude-md` |
| 2026-09-01 | L47 | In a pipeline, $? and || see only the LAST command's status — so 'cmd | sed || echo absent' can never report absent, because sed succeeds on empty input. Test the condition itself before any pipe, or check ${PIPESTATUS[0]}. | `claude-md` |
| 2026-09-01 | L46 | Running the real procedure against the one input where its defect cannot appear is not verification. Before reporting a procedure verified, ask which input would expose the failure, and run it against that — not against the fixture nearest to hand. | `claude-md` |
| 2026-09-01 | L45 | A path-limited 'git commit -- <paths>' reads the working tree and ignores the index, so it silently discards a staged deletion — 'git rm --cached' followed by it re-commits the file instead of untracking it. Untracking needs an index-based commit, whose scope you must inspect first. | `claude-md` |
| 2026-09-01 | L44 | Never feed a command substitution into a flag that requires a value without checking it is non-empty — and in a shared checkout treat a FAILED commit as an urgent staged-state leak, because your paths are left in an index a peer also writes. | `claude-md` |
| 2026-09-01 | L43 | A single pass of a nondeterministic test is not evidence — for an intermittent failure, one pass and one failure are the same observation. Never publish a verdict from one run; require several consecutive passes, and re-run before restoring a claim you withdrew. | `claude-md` |
| 2026-09-01 | L42 | A delegated agent reporting that it *checked* a property is not the same as a *guard* existing for it. Before citing that property as a guarantee — in a decision's rationale, a brief, or a handoff — confirm a committed test enforces it, and write one if not. | `claude-md` |
| 2026-08-31 | L41 | A project's own sync, format or codegen command may itself run git — read what it does to the tree before running it in a shared checkout, and say so before you run it, not after. | `claude-md` |
| 2026-08-31 | L40 | A grep answers the pattern you typed, not the question you meant: never read absence from your own filtered output as absence in reality, and never count a proxy pattern as a count of the thing. Re-run unfiltered against the specific path, or ask the authoritative source. | `claude-md` |
| 2026-08-30 | L39 | When the user asks for a capability, wire it into the control they described using — a hidden modifier path satisfies the data model, not the request, and reads to them as 'still not supported'. | `claude-md` |
| 2026-08-30 | L38 | While the operator is running the thing you are refactoring, an intermediate broken state reaches them as a product bug — say you are rewriting it and when to reload, or land the change in one write. | `claude-md` |
| 2026-08-30 | L17 | In a repo that auto-commits or auto-pushes on a timer, git state is not stable between reading it and writing about it — re-run the check at the moment you commit a claim to a durable artifact. | `claude-md` |
| 2026-08-30 | L37 | A reviewer's scope advice is scoped to the diff it saw — before acting on 'this is dead code, delete it', check whether a later lane is forbidden from re-adding it. | `skill:mow` |
| 2026-08-30 | L36 | When the user says a selection, mode, or other in-progress state should persist, every way of leaving the current item is its own behavior — keys, buttons, clicks, sibling lists — not only the path they just demonstrated. | `claude-md` |
| 2026-08-29 | L35 | A tool's dangerous behaviour is often gated by how it is invoked. Before warning that it will fire, trace the call site for that specific mode — a flag one frame above the dangerous function can disable it entirely, and the repo's own docs may describe only the other mode. | `claude-md` |
| 2026-08-29 | L34 | A uniqueness key, or a pattern used to kill or match, must cover every case the surrounding rules permit to vary — not the case you pictured. A comment asserting the property is not a test of it: enumerate what the system allows (a second run in the same repo, a peer process under the same path prefix), then key on all of it. | `claude-md` |
| 2026-08-29 | L33 | A guard is proven by making it fire, never by reading it. After writing a check, test, or sandbox, deliberately break what it protects and confirm it fails — and confirm it fires in the environment it exists for, not only the one you are standing on. | `claude-md` |
| 2026-08-29 | L32 | In zsh (the default shell here): never name a variable 'path' — it is tied to PATH and assigning it breaks every later command in that shell; and an unquoted $var does NOT word-split, so a command held in a variable runs as one literal name. Write the command out, or use an array. | `claude-md` |
| 2026-08-29 | L31 | A summary of a file is not the file — not a directory listing, not a MEMORY.md index line, not a recalled description sitting in your context. Before prescribing that a file be changed, retired, or deleted, open it in that same turn. | `claude-md` |
| 2026-08-28 | L30 | A version-control check from a parent directory says nothing about the directory you edited — nested repos are invisible from above; run git -C <that dir> before telling anyone work is unversioned or has nothing to commit. | `claude-md` |
| 2026-08-28 | L29 | A file that a hook rewrites on every tool call cannot be edited through the harness's Read->Edit/Write path — the stale-file check races the hook and always loses; write it atomically via shell (temp file + mv) instead. | `skill:mow` |
| 2026-08-26 | L28 | A last-activity timestamp is not a presence signal. Before telling someone another session or process is 'live', sample the timestamp twice — if it has not advanced, it is idle or gone, and say which. | `hook:peer-session` |
| 2026-08-26 | L27 | Before adding to an accumulating artifact — a log, a registry, a backlog — verify something actually consumes it. An artifact that only grows is a liability, and contributing to it feels like diligence. | `claude-md` |
| 2026-08-22 | L22 | A PR diffs against the remote base, so a stale local base silently widens it beyond the agreed scope — check the base against its upstream before cutting the branch, and confirm the opened PR from the forge's own numbers (gh pr view --json changedFiles,additions), not from a local three-dot diff. | `claude-md` |

**Correction while routing:** L20 said an isolated worktree "branches from a stale base". Half of that
was `worktree.baseRef: fresh` — a setting, not a defect — now set to `head`. The surviving half is
that untracked files exist in no commit and so never travel, which is why a stem's plan folder must be
committed before isolated lanes can read their briefs.

---

<!-- newest first — unrouted only -->


