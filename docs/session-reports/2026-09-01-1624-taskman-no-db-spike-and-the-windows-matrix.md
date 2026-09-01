---
date: 2026-09-01 16:24
branch: master
slug: taskman-no-db-spike-and-the-windows-matrix
project: none (ai-wow is deliberately board-less — no .taskman.toml)
session_id: cc21e892-098b-47e8-874c-4510028974b4
start_sha: b182dda08d4e310a479476cfef9af824dab027fb
---

# Session report — the C3 spike answered, and a CI matrix that found three real Windows bugs on its first run

Ran `/mow go taskman-no-db` end to end, in a checkout shared with a live peer session running
`publish-hygiene` in parallel. Both stems shipped.

## What was done

- **Ran the mow spike to completion.** Wave 1 (A ‖ B) in isolated worktrees, wave 2 (Z) foreground.
  Cross-plan overlap against the concurrently-running `publish-hygiene` verified disjoint before
  fan-out, so both stems ran in parallel rather than sequentially.
- **Built CI from zero** — `.github/workflows/ci.yml`, Linux + Windows, `fail-fast: false`,
  discovering tests by directory scan. It found 11 test files where the repo had 8, picking up lane
  B's new tests *and* the peer stem's, with no workflow edit.
- **Built the dbless `Task` store** — `taskman/taskman/eventlog/`: `O_EXCL` lockfile, append-only
  JSONL, state by replay, id counter via atomic `os.replace`. Zero third-party imports, enforced by
  a committed AST test.
- **Answered the spike: C3 is viable on Windows. Build the port.** Shape B (SQLite) retired.
- **Fixed three Windows bugs the matrix surfaced**, two of them pre-existing and one silent.

## Files changed

| Path | What |
|---|---|
| `.github/workflows/ci.yml` | new — the matrix (lane A) |
| `taskman/taskman/eventlog/{__init__,locking,log,store}.py` | new — the store (lane B) |
| `taskman/taskman/eventlog/tests/{test_store,test_concurrency}.py` | new — 42 checks |
| `bin/tests/test_repo_shape.py` | cp1252 fix — explicit `encoding="utf-8"` at 6 call sites |
| `bin/ai-sync` | `as_posix()` — Windows separator bug in `managed_paths()` |
| `bin/tests/test_ai_sync_commit.py` | regression guard + anti-vacuity assertion |
| `skills/mow/tests/test_tracker_port.py` | `sandbox()` — stop servers before the temp dir is removed |
| `docs/plans/taskman-no-db/{plan,spike-result,action-report}.md` + `dispatch/` | the run's record |

Commits: `b0fe9ad` `5e4d82e` `52e3278` `5254553` `86f2f79` `d93283c` — all pushed, master green.

## Wrap-up gate

**Not run — unavailable.** No `.taskman.toml` anywhere up the tree, and no `scripts/wrapup_reconcile.py`
in this repo. Per the skill's preconditions this is the board-less path: lessons + session report only,
no board sync, no gate, no project slug guessed.

Evidence came from git instead: session marker `start_sha=b182dda`, per-commit diffstats, and CI run
results — not chat recall.

## Taskman sync

**None — no board exists in this repo, by decision.** Work that would have been booked is recorded in
committed documents instead: [`action-report.md`](../plans/taskman-no-db/action-report.md) and
[`spike-result.md`](../plans/taskman-no-db/spike-result.md), both pushed.

## Lessons

| Id | Rule | Destination |
|---|---|---|
| **L43** | A single pass of a nondeterministic test is not evidence — one pass and one failure are the same observation for an intermittent failure. Never publish a verdict from one run. | `global/CLAUDE.md` → Verification habits |
| **L44** | A failed commit in a shared checkout is a staged-state leak, not a retry — and never build the commit from an unverified lookup. | `global/CLAUDE.md` → Shared checkouts |

Both **routed and verified through the symlink** (`~/.claude/CLAUDE.md` → `dotfiles-ai/global/CLAUDE.md`),
committed with their ledger rows in dotfiles-ai `1a878ff`.

**One bump refused, correctly.** Tried to bump L40 (filtered output ≠ absence) after piping an
existence check through `head -2` and briefly misreporting a pushed fix as missing. The script
refused: L40 is already routed, and a routed rule recurring means its destination isn't working.
Here it *did* work — I caught it myself in the same turn — so no third lesson was manufactured.

No BACKLOG or PRUNE signal from the ledger.

## Decisions

- **C3 (append-only event log) is viable on Windows; shape B (SQLite) retired.** `O_EXCL` makes
  `claim` and id allocation trustworthy without a transaction. Evidence: 4 consecutive green Windows
  runs after the fix, against 2-of-3 failures before it.
- **Nothing was quarantined to reach green.** `WINDOWS_SKIP` is empty in the shipped workflow. Two
  red tests were fixed, not skipped.
- **The spike amends no shipped guarantee.** Invariant I10 and `README.md:161` untouched; that belongs
  to the change that *lands* the port.
- **Withdrew a published verdict rather than defending it.** Both superseded verdicts are kept in
  `spike-result.md` rather than tidied away.

## Open threads / not finished

Recorded in the action report; no board to book them on.

- **`bin/ai-sync` has 11 bare `read_text()` calls**, incl. line 618 reading arbitrary source files
  during a sync — the same cp1252 defect fixed in `test_repo_shape.py`, latent until a synced file
  carries a non-ASCII byte on Windows. **Highest-value follow-up.**
- `hooks/peer-session-{guard,notice}.py` read JSON markers with bare `read_text()`.
- Ship-check Minors: `store.py` reaches into `log.py`'s private API (`_lock_path`, `_append_locked`);
  no `# debt:` marker on the full-replay-under-global-lock corner; stale-lock debris on a committed
  board; `plan.md`'s "behind the existing CLI" wording is ambiguous.
- Open `# debt:` at `taskman/taskman/eventlog/locking.py:76` — the `stat`→`rename` window.
- **The port itself:** event shape + version tolerance, compaction policy, migrating the two live
  Postgres boards, CLI wiring, relativizing `AgentSession.transcript_path`
  (`taskman/taskman/metrics.py:250`), and amending I10 + `README.md:161`.

**No checkpoint created.** This repo has no `docs/checkpoints/` and no board, so leftovers live in the
committed action report and spike result instead. Flagged as a deviation from the skill's step 4
rather than silently skipped.

## Next steps

1. `/mow plan` the port, using `spike-result.md`'s "What the port now needs" as the todo source.
2. Fix `bin/ai-sync`'s remaining bare `read_text()` calls before anyone runs it on the work PC.
3. **Uncommitted:** `docs/plans/work-pc-readiness/action-report.md` is dirty and belongs to the peer
   session, not this one. Left untouched deliberately — attributing another session's file is exactly
   what the wrap-up gate exists to prevent.

---

## Addendum — after the first wrap-up

The session continued past its own report. Recorded here rather than in a second file, since it
is one session with one `session_id`.

### Pushing exposed a second tree with the same bug

`git push` on dotfiles-ai was **refused by that repo's own `test_tree_drift` guard**: four shared
files had drifted. The guard was right, and one of the four was mine — `bin/tests/test_ai_sync_commit.py`,
drifted the moment I fixed ai-sync's copy and not the sibling.

Investigating the other three showed **none was a deliberate public/private split**; every one was
"the published tree got fixed, this one didn't":

| File | Why it had drifted |
|---|---|
| `hooks/session-start-marker.py` | Told every session `/wrap-up must run: python scripts/wrapup_reconcile.py` — a path absent from *both* trees. It misled this session at startup |
| `skills/bs/SKILL.md`, `skills/grill-with-docs/SKILL.md` | Still said `.venv/bin/python -m taskman`; dotfiles-ai has no root `.venv`, so that prefix was wrong there too |

**The `ai-sync` separator bug was live in dotfiles-ai as well** — the tree that actually holds
`global/CLAUDE.md`, the exact file it would silently refuse to commit on Windows. The copy fixed
first was the less important one.

Commits: `1abef7e` (my drift + the ai-sync fix), `2e90517` (the other three), `392b7c6` (the test).

### Porting a hook without its test

`2e90517` shipped `session-start-marker.py` with no test, leaving that tree with fixed behaviour and
nothing enforcing it. The drift guard could not catch this: the test existed in only one tree, so it
was not a shared path at all. Closing it took three steps, not one —

1. the file, ported verbatim;
2. a line in `githooks/pre-push`, since that tree has no CI and its hook enumerates suites by name,
   so an unlisted test never runs;
3. a `match` row in `tree-drift.json`, because porting created a new shared path and the guard fails
   any it cannot classify.

Verified it fires rather than merely passes: stubbing `_has_board()` to `False` took the suite to
exit 1, restoring returned 0.

### `taskman` on PATH

Both trees now instruct a bare `taskman ...`, which resolved nowhere on this machine. `uv sync` turned
out to have been run already — console scripts existed in both trees since August — so the only gap
was PATH. Added one `export` to `~/.zshrc` pointing at the dotfiles-ai tree, since that is where the
live skills load from.

**Left unmanaged deliberately.** `~/.zshrc` is not a symlink, `$HOME` is not a repo, and `ai-sync`'s
`LINK_FILES` covers only `CLAUDE.md` and `rules`. The file is machine-specific in three places
(conda's hardcoded prefix, an Apple-Silicon homebrew path, a `$HOME/Desktop/...` tree location), so
tracking it wholesale would ship a config that breaks on the work PC — the same defect class as the
`.venv/bin/python` prefix removed earlier today.

### Lessons — none new

Two candidates considered and both declined:

- **Porting a fix without its test.** Close to L42, and I flagged the gap myself before it was raised.
  A rule for something self-caught is the padding the skill warns against.
- **`zsh -l -c` reported the PATH change as broken** when it had worked — a non-interactive login
  shell sources `.zprofile`, never `.zshrc`, so the probe skipped the file under test. A real
  mistake, but an instance of L16 (establish the baseline with the command that actually applies)
  and L33 (a guard must fire in the environment it exists for), both already routed and both of
  which I applied unprompted on re-check.

### Open threads added

- **A shared-file drift guard cannot see a test that exists in only one tree.** `test_tree_drift`
  classifies shared paths; a fix ported without its test leaves no shared path to flag, so the gap
  is invisible to it. Mechanizable — the guard could warn when a `match` source file's sibling test
  is one-tree-only — but that is design work, not this session's.
- `bin/tests/tree-drift.json` was reformatted as a side effect of adding one entry (`ensure_ascii`
  flipped, unescaping ~30 em-dashes). Semantically identical, nothing writes the file
  programmatically, so no ping-pong risk — noted as churn, not corrected.
