# Action report — Work-PC readiness follow-ups

**Date:** 2026-08-26
**Project slug:** `work-pc-readiness-followups`
**Plan:** [`plan.md`](plan.md)
**Dispatch:** [`dispatch/INDEX.md`](dispatch/INDEX.md)
**Predecessor:** [`../work-pc-readiness/action-report.md`](../work-pc-readiness/action-report.md)
**Waves:** 2 (A ‖ B, then C → Z) · **Lanes:** 4 · **Agent tokens:** ~129k

---

## Outcome

| Item | Status | Where it landed |
|---|---|---|
| `stamp-tracker` backgrounded-agent fix ported to ai-wow | shipped | `hooks/stamp-tracker.py` (`_returns_at_launch` + call site) |
| Its regression test ported | shipped | `hooks/tests/test_stamp_tracker.py` (new dir, 115 lines, 7/7) |
| `ai-sync status` reads the installed mode off disk | shipped | `bin/ai-sync` (`installed_mode()`, `_is_copy_of`) |
| Docs that quote status output verbatim | shipped | `HOW-TO-USE.human.md:596`, `HOW-TO-USE.agent.md:341` |
| Safer `guard-destructive` back-ported to dotfiles-ai | shipped | `~/Desktop/dotfiles-ai/hooks/guard-destructive.sh` (uncommitted, by design) |
| Durable regression test for `ai-sync` status | shipped, **unplanned** | `bin/tests/test_ai_sync_status.py` (9 checks) |
| Publish sweep + this run's fixes on `origin/master` | shipped | `909c64c`, `f9bf363`, `ec2e6a7`, `ede873b` |

Run diff in ai-wow: **6 files**, +331 / −11 (`ec2e6a7^..ede873b`), plus the 113-file publish sweep that preceded
wave 1. One file changed in dotfiles-ai by this run; that repo also carries unrelated
`.activity` drift from another run, which this run did not touch.

---

## Wave results

### Wave 1 — lanes A ‖ B, backgrounded in isolated git worktrees

**Lane A — stamp-tracker parity** (`tdd-builder`, ~54k tokens, 3m)

Ported `_returns_at_launch` and its single call site, and nothing else. Red evidence
captured against the unfixed hook first — two failures, both backgrounded cases:

```
FAIL  backgrounded agent does NOT get ended — ended='2026-08-26T19:59:49Z'
FAIL  Agent with no run_in_background key does NOT get ended — ended='2026-08-26T19:59:49Z'
```

7/7 green after. The five synchronous-path assertions passed **both** before and after,
which is what pins down that the fix did not trade one bug for another.

The lane declined to port dotfiles-ai's extra docstring paragraph, reading "leave every
other line alone" as binding. Correct call — the brief was unambiguous — and it surfaced
the omission rather than acting on its own judgement.

**Lane B — copy-mode truth** (`tdd-builder`, ~75k tokens, 5m)

Added `installed_mode()` and `_is_copy_of`, rewired `do_status` / `_dir_link_state`, and
left `can_symlink()`'s two install-time callers untouched. Reused the pre-existing
`_trees_equal` rather than writing a second tree comparison.

It also raised the label question rather than deciding silently: the old
`copy (no symlink privilege)` asserts something about the *machine*, which is false once
copy mode can be reported on a symlink-capable box. Changed to plain `copy`, both
doc sites updated.

**Merge-back:** neither lane committed — both cited their build-lane contract, which is
correct behavior. Committed each on its own worktree branch, merged both into a disposable
integration branch, diffed against the wave-start commit and applied as one combined diff.
No conflicts. The diffstat named exactly the five in-scope files, which is the L13 tell
that the diff was taken against the right base. Worktrees and branches torn down after the gate.

**Gate:** every acceptance check re-run independently by the orchestrator in the merged
tree — 7/7 on lane A's test, and lane B's full four-case matrix (copy install → `link mode:
copy`, 8× `copied (in sync)`, **0** `NOT linked`; symlink install → 8× `linked`; empty HOME
→ exit 0; stability across two runs). Review flags were `-` throughout: the diff is plain
Python, and no roster agent owns it.

### Wave 2 — lanes C → Z, foreground

**Lane C — dotfiles-ai back-port.** One hunk: affirmative `allow` → `{}` plus the comment
explaining why. Smoke-tested both directions (`ls -la` → `{}`, `DROP TABLE` → `ask`),
`bash -n` clean, tails now byte-identical to ai-wow's. Left uncommitted in dotfiles-ai
by design — that repo has its own session-end sync and its own operator decision to make.

**Lane Z — fresh-clone verification.** 15/15 against a clone installed into two virgin
`HOME`s. First run reported 1 failure, which was **the harness, not the product**:
`git diff HEAD` does not carry untracked files, so the two new test files never reached
the clone. The harness now warns when untracked paths exist rather than silently testing
the wrong tree.

---

## Decisions locked

- **The two repos are triaged per file, not synced wholesale.** ai-wow is the scrubbed,
  publishable side; `session-start-marker.py`'s difference is deliberate sanitization and
  ai-wow's version stands. Any port must keep the scrub — lane A took the fix and not the
  docstring for exactly this reason.
- **`peer-session-guard.py` / `peer-session-notice.py` stay out.** Registered nowhere —
  not in either `hooks.def.json`, not in the live `~/.claude/settings.json`. Porting them
  ships dead code into a published repo.
- **Publish moved earlier than the plan said.** The plan put commit+push at Integrate;
  the base was pushed before wave 1 because worktrees branch from a committed base and the
  scrub lane A had to preserve was staged-only. Verified afterwards that both worktrees
  branched from `f9bf363`.
- **A test that has never failed is not a test.** Both new suites were run against the
  unfixed code first. `test_ai_sync_status.py` produced 3 failures pre-fix — exactly the
  copy-mode assertions — with the symlink and empty-HOME cases passing both sides.

---

## Verify

| Check | Result |
|---|---|
| `python3 hooks/tests/test_stamp_tracker.py` | 7/7, exit 0 (2 failures pre-fix) |
| `python3 bin/tests/test_ai_sync_status.py` | 9/9, exit 0 (3 failures pre-fix) |
| `grep -c _returns_at_launch hooks/stamp-tracker.py` | 2 |
| `grep -riE 'project-a\|project-b\|fitness' hooks/` | 0 hits — scrub intact |
| `python3 -m py_compile bin/ai-sync hooks/stamp-tracker.py` | exit 0 |
| Copy install → status | `link mode: copy`, 8× `copied (in sync)`, **0** `NOT linked` |
| Symlink install → status | `link mode: symlink`, 8× `linked` — unchanged |
| Empty HOME → status | exit 0, targets `missing` |
| Fresh-clone sweep (both modes, virgin HOMEs) | **15/15** — "fresh clone is work-PC ready" |
| `guard-destructive` in dotfiles-ai | `ls -la` → `{}` · `DROP TABLE` → `ask` · `bash -n` clean |
| Toolchain probe inside a throwaway worktree (L07) | passed before fan-out |

**P3 post-build protocol:** no `docs/agents/protocols.md` in this repo, so the default
applied. `test-coverage` — n/a, both changed surfaces got purpose-written suites this run.
`adversarial-tester` — n/a: `_returns_at_launch` is a 3-line boolean predicate with every
branch exercised, `installed_mode()` is filesystem-state inspection, and Hypothesis/mutmut
are third-party packages this interpreter deliberately does not have. `taskman/tests` not
run: nothing in the diff touches it, `pytest` is not installed in the active interpreter,
and there is no venv at the repo root. Recorded as n/a rather than skipped silently.

**Ship-check:** run against `plan.md` + the shipped diff. **One Critical, fixed this run.**
Layer 1: 3 · Layer 2: 1 · Layer 3: 1.

The Critical was mine, in `bin/tests/test_ai_sync_status.py`: sandboxing by `HOME` alone
is a no-op on Windows, where `Path.home()` resolves through `ntpath.expanduser` via
`USERPROFILE`, then `HOMEDRIVE`/`HOMEPATH`. On the work PC this plan exists to serve, the
test would have installed into the operator's real profile. Fixed in `ede873b` — the
sandbox now overrides all four names, proven by asserting the child process's
`Path.home()` is the sandbox and is not the real home.

**Finding triage:**
- **(a) mechanizable** — lane B's "no durable regression test for `bin/ai-sync`" →
  check **added this run** (`bin/tests/test_ai_sync_status.py`), per the rule that a
  mechanizable finding is closed in the same run rather than deferred.
- **(a) mechanizable** — the ship-check Critical → fixed, with a per-variable assertion
  that locks it in.
- **(c) one-off** — the lane Z harness gap (untracked files invisible to a clone) → fixed
  in the scratch harness; it is not a repo artifact.

**Tracker reconcile:** a fresh `general-purpose` reader audited the board against the
repo. **Seven discrepancies, all real** — the orchestrator wrote the board from memory and
was blind to its own dropped writes, which is exactly why this step is not self-audit:

| # | Discrepancy | Fix |
|---|---|---|
| 1 | Lane Z listed `scratchpad/verify-fresh-clone.sh` as an artifact — no such path in the repo | Entry removed; a session scratch file is not a run artifact |
| 2 | Lane A/B agents both stamped 8m30s — the *wave's* span copied onto each agent | Re-derived: starts from `dispatch/.agent-times.json`, ends from measured runtime (A 3m10s, B 5m22s) |
| 3 | Wave-2 lanes had `started == ended` — zero duration for real work | Bracketed by surrounding commit timestamps, with a `detail` saying the bounds are derived, not measured |
| 4 | Run `ended` stamped at close-out, ~8h after the last real activity — board rendered 8h12m instead of ~16m | Set to the final commit, `20:13:22Z` |
| 5 | Action report was **untracked** and `dispatch/INDEX.md` linked `../action-report.md` — a dead link in the very clone this plan exists to make correct | Committed and pushed (below) |
| 6 | "6 files, +317 / −11" counted `ec2e6a7` only, omitting `ede873b` — the ship-check fix the same report describes | Corrected to +331 / −11 over `ec2e6a7^..ede873b` |
| 7 | dotfiles-ai showed two modified files, not one | Clarified: the second is unrelated `.activity` drift from another run there |

Finding 4 is the stale-wall-clock case `skills/mow/TRACKER.md` warns about, arriving in
practice. Finding 5 is the one that mattered: the run had marked itself `shipped` in the
registry while its own record was invisible to a clone.

Worth recording alongside: `dispatch/.agent-times.json` carries `ended: null` for both
backgrounded lanes. That is **this run's own fix observed working** — the hook correctly
declined to stamp a launch-time return as a completion.

**Board sync:** n/a — this repo has no root `.taskman.toml`, so no Feature/Task rows exist.

---

## Open / deferred

1. **Copy-install drift is misdiagnosed.** A copy install whose files have drifted fails
   `_is_copy_of`, falls back to the capability probe, and prints `NOT linked (real dir)` —
   the misleading output returns precisely when something is actually wrong, and "not
   linked" is the wrong diagnosis for "copied but stale". Pre-existing wording; lane B
   flagged it and correctly left it alone.
2. **`stamp-tracker` parity is still incomplete.** dotfiles-ai's copy also has
   `_prompt_names_run` / `_stem_of` and a two-arg `_find_board(cwd, prompt)` that refuses
   to attribute a spawn to a board the prompt does not name, plus a drain-on-each-spawn
   retry. ai-wow takes "most recently written board" unconditionally. Out of scope here;
   the ported test passes either way.
3. **ai-wow's module docstring is now silent on the backgrounded case** — dotfiles-ai
   carries an explanatory paragraph that was deliberately not ported.
4. **Nothing reconciles the two repos.** `foreign_repo_root()` blocks the import path by
   design, so a fix landing in one reaches the other only when a human carries it. This
   run carried two by hand. Recorded in `plan.md` → `## Not yet specified`.
5. **`.claude/worktrees/` is still not gitignored** — inherited. This run created three
   worktrees and kept them out of every commit by staging explicit paths.
6. **`guard-migrations.sh` never fires on this Mac** — the live `settings.json` was
   rendered from dotfiles-ai's `hooks.def.json`, which has no such row. It *will* register
   on a work-PC clone from ai-wow's own def, so it is not a readiness gap.
7. **The dotfiles-ai change is uncommitted** in that repo, awaiting its own operator pass.
8. **Nothing durable asserts the *shape* of the published repo.** The fresh-clone sweep
   checks 16 skills / 8 subagents / no `impeccable` / no employer strings, but it lives in
   a session scratch directory and will not survive. `bin/tests/test_ai_sync_status.py`
   covers the install, not the inventory — which is the drift class the predecessor run
   already had to fix once (counts reading 14 / 15 / 17). A `bin/tests/test_repo_shape.py`
   would close it; deliberately not added, since this run already shipped one unplanned
   test and the second is the operator's call.
