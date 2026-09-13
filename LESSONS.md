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


