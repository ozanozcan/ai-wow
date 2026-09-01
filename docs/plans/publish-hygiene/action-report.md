# Action report — Publish hygiene

**Date:** 2026-09-01
**Project slug:** `publish-hygiene`
**Plan:** [`plan.md`](plan.md)
**Dispatch:** [`dispatch/INDEX.md`](dispatch/INDEX.md)
**Predecessor:** [`../work-pc-readiness-followups/action-report.md`](../work-pc-readiness-followups/action-report.md)
**Sibling (parallel):** `taskman-no-db` — disjoint file sets, verified by both stems independently
**Waves:** 3 (A ‖ B ‖ C → Z → Z2) · **Lanes:** 5 · **Agent tokens:** ~174k across 2 backgrounded lanes

---

## Outcome

| Item | Status | Where it landed |
|---|---|---|
| Three dead `scripts/wrapup_reconcile.py` references repointed | shipped | `hooks/session-start-marker.py`, `skills/wrap-up/SKILL.md`, `skills/mow/SKILL.md` |
| SessionStart hook names the gate only when a board exists | shipped | `hooks/session-start-marker.py` (`_has_board`) |
| Regression test for the `f6b25f9` marker guard | shipped | `hooks/tests/test_session_start_marker.py` (new, 16 checks) + registered in `githooks/pre-push` |
| `django-review` row no longer asserts an absent agent | shipped | `skills/mow/SKILL.md:526`, `skills/checkpoint/SKILL.md:110` |
| Drifted copy install reports `copied (stale — re-run ai-sync)` | shipped | `bin/ai-sync` (`COPY_STALE`, both branches) |
| `.claude/worktrees/` gitignored | shipped | `.gitignore` |
| Orphaned 2026-08-21 session report committed | shipped | `docs/session-reports/` |
| Board-less posture documented as a decision | shipped | `HOW-TO-USE.human.md` §6 |
| **29 repo-root `.venv/` prefixes removed** | shipped, **unplanned** | `skills/wrap-up` (20), `grill-with-docs` (7), `bs` (2) |
| **Bootstrap corrected to target the reader's project** | shipped, **unplanned** | `HOW-TO-USE.human.md` §6 steps 3–4 |
| **Durable dead-path check** | shipped, **unplanned** | `bin/tests/test_repo_shape.py` |

Run diff: **17 files, +657 / −52** over `b182dda..HEAD`, in four commits.

The last three rows are wave 3, which did not exist at plan time. The ship-check gate created it.

---

## Wave results

### Wave 1 — A ‖ B backgrounded in isolated worktrees, C foreground

**Lane A — reference honesty** (`tdd-builder`, ~97k tokens, ~8m30s)

Added `_has_board()` and made the wrap-up sentence conditional on it. Red evidence was captured by
**re-injecting the `f6b25f9` early return** — the assertion passed on arrival, so the lane broke what
it guards rather than trusting green: `FAIL board-less: marker written markers=[]`. Four red→green
slices.

It also surfaced two things rather than quietly resolving them: it walks from the resolved **cwd**
rather than the worktree (a superset chain — deliberate, and the more correct behaviour for a session
opened inside a sub-project), and it could not satisfy the contract item "`pre-push` output names the
new suite" literally, because every suite in that hook is redirected to `/dev/null`. It substituted
two stronger proofs — `sh -x` showing the line execute, and breaking the suite to show `pre-push`
exit 1 before `pre-push: clean` — and said so (L26).

**Lane B — copy-drift diagnosis** (`tdd-builder`, ~77k tokens, ~6m30s)

One shared `COPY_STALE` constant used by both the directory and file branches, so the wording cannot
drift apart. Three red→green slices; where an assertion passed on arrival it was proven by dropping
the `mode == "copy"` condition and watching it fail, then restoring the file and confirming by
SHA-256.

Reported an honest limitation rather than widening scope: the only discriminator between "drifted
copy" and "never installed" is `mode == "copy"`, so on a box with nothing installed *and* no symlink
capability, an unmanaged directory reads as a stale copy. Fixing it means touching `installed_mode()`,
which the brief forbade. Deferred below.

**Lane C — tree hygiene** (foreground, orchestrator)

`.claude/worktrees/` ignored, proven **while two real lane worktrees were live on disk** — `?? .claude/`
before, absent after. Committed the 2026-08-21 session report, which had sat untracked across three
sessions. Reported the stray screenshot and `.agent-times.json` without touching them.

**Merge-back:** neither backgrounded lane committed — correct per their build-lane contract. Each was
committed on its own worktree branch, both merged into a disposable integration branch, diffed against
the wave base and applied as one combined diff. No conflicts. The diffstat named exactly the eight
in-scope files (L13). Teardown was fail-closed: a byte-comparison of all eight files against the
integration branch ran *before* any worktree was removed.

**Gate:** all five suites re-run independently by the orchestrator in the merged tree, plus the hook
exercised directly in a board-less and a boarded repo. Review flags `-` throughout: no roster agent
owns a hook + shell + markdown diff.

### Wave 2 — Z, foreground

Documented the board-less posture in §6 with its measured evidence, and closed a gap lane B had found
but could not fix inside its own scope: Appendix A's copy-mode sample showed only `copied (in sync)`
while the paragraph directly beneath described the drift scenario without naming the state that
reports it.

### Wave 3 — Z2, foreground, created by the ship-check gate

See **Ship-check** below for why this wave exists.

---

## Decisions locked

- **ai-wow stays board-less, and now says so.** Measured, not assumed: a root `.taskman.toml` with no
  reachable Postgres makes `taskman wrapup gate` exit **2**, which the wrap-up skill's own table reads
  as "no session marker" — the wrong diagnosis, pointing at a command that fails identically. Revisit
  after `taskman-no-db`, when the objection dissolves.
- **`django-reviewer` stays out.** Django is not widely used at the operator's company. The fix was to
  make the references honest, not to ship the agent — upholding the `harness-boundary` decision rather
  than overturning it.
- **One way to invoke taskman: the console script on PATH.** Strictly better than a relative venv
  prefix, because `find_project()` resolves the project by walking up from cwd — the CLI must run from
  the reader's project, and a relative prefix fights that. The "where does the CLI live" hint now lives
  in exactly one place.
- **The dead-path check is scoped to markdown.** Its first draft flagged
  `hooks/guard-migrations.sh:59`, which probes `[ -x .venv/bin/alembic ]` with two fallbacks and a
  `pass` — correct defensive code. A `.md` line is a promise; a shell conditional is a probe.

---

## Verify

| Check | Result |
|---|---|
| `hooks/tests/test_session_start_marker.py` | 16 checks, exit 0 (red proven by re-injecting `f6b25f9`) |
| `hooks/tests/test_stamp_tracker.py` | 7/7, exit 0 |
| `bin/tests/test_ai_sync_status.py` | 14 checks, exit 0 (4 pre-fix failures quoted) |
| `bin/tests/test_ai_sync_commit.py` | 13 checks, exit 0 |
| `bin/tests/test_repo_shape.py` | 0 failures, incl. the new dead-path check |
| `sh githooks/pre-push` | `pre-push: clean`, new suite registered and shown load-bearing |
| Hook in a board-less repo | marker written, no wrap-up command named |
| Hook in a boarded repo | names `wrapup gate` |
| Bootstrap re-run against a **scratch** project | `project 'my-service' (id=1)` · `# board: my-service` |
| `grep .venv/bin\|scripts/wrapup_reconcile hooks/ skills/ --include="*.md"` | exit 1, no matches |
| Toolchain probe inside a throwaway worktree (L07) | 4/4 suites passed before fan-out |

**P3 post-build:** no `docs/agents/protocols.md`, so the default applied. `test-coverage` — n/a, every
changed surface got a purpose-written suite this run. `adversarial-tester` — n/a: `_has_board` is a
filesystem walk, `COPY_STALE` a constant, and Hypothesis/mutmut are absent from this interpreter by
design. `taskman/tests` not run: nothing in the diff touches it.

**Ship-check:** **one Critical, found and fixed this run.** Layer 1: 2 · Layer 2: 0 · Layer 3: 1.

The Critical was mine. The plan promised no repo-root `.venv/` path would survive in a shipped file;
**29 did**. The lane-A grep that "verified" it searched `\.venv/bin/python scripts/` — which requires
`scripts/` immediately after and so could only ever match the two together, never a bare
`.venv/bin/python`. The check passed while the criterion failed (L40). Investigating it exposed a
worse defect in work pushed earlier the same day (`1693827`): the bootstrap told the reader to put a
`.taskman.toml` at *their* repo root and then run `init-db` from **ai-wow's** taskman directory,
registering `taskman-tests` instead — while displaying the correct output beneath the wrong command.
It had been "verified" against taskman's own test project, the single case where the bug cannot show.

Both closed in wave 3.

**Finding triage:**
- **(a) mechanizable** — the Critical → `bin/tests/test_repo_shape.py` now fails if any shipped
  markdown names a path this repo lacks. Added **this run**, proven by making it fire.
- **(a) mechanizable** — the bootstrap defect → re-verified against a scratch project rather than the
  easy case, and the step now carries a self-check ("if it names a slug you did not expect, you are in
  the wrong directory").
- **(c) one-off** — lane A's `pre-push` contract substitution; reasoned and recorded, no artifact.

**Tracker reconcile:** a fresh `general-purpose` reader audited the board against the commits.
**Eleven discrepancies, all real, all applied** — the orchestrator wrote the board from memory and was
blind to its own dropped writes, which is exactly why this step is not self-audit.

| # | Discrepancy | Fix |
|---|---|---|
| 1 | Lane Z2 `done` with an Acceptance SHALL literally unmet — the deviation lived only in a commit message | Deviation recorded in the brief on disk, with the reason |
| 2 | Wave 1's gate read clean, but lane A's SHALL was unmet when it passed | Gate detail now says so; no `issues` status because findings need taskman ids, unavailable board-less |
| 3 | Wave 1 had no `tokens` rollup | Set to 174,426 |
| 4 | Five real edited files never recorded as artifacts | Lane A gained three, lane Z2 gained two |
| 5 | Z2's label attributed all 29 removals to one file | Split to the measured 20 / 7 / 2 |
| 6 | Wave 3 `started` identical to wave 2 `ended`, giving the ship-check gate zero seconds | Lane start moved to the first plan write, with a `detail` saying it is derived |
| 7 | Both wave-1 agent starts back-filled to the wave start | Corrected from `.agent-times.json` — 23:26:21Z and 23:26:31Z |
| 8 | `parallelism` free text on waves 2 and 3 | Legal literals; prose moved to `detail` |
| 9 | Lane A tool entry claimed 17 checks | Suite emits 16 — corrected |
| 10 | Run still `running` with all waves done | Closed out below |
| 11 | The reconcile agent itself had no board representation | Recorded deliberately in wave 3's gate detail |

Finding 1 is the one worth remembering: it is the **same shape** as the L40 miss that wave 3 existed
to close, committed while closing it.

---

## Open / deferred

1. **`installed_mode()` can misreport an unmanaged directory as a stale copy.** The only discriminator
   is `mode == "copy"`; with nothing installed and no symlink capability, the probe returns `copy` and
   an unmanaged real directory reads `copied (stale — re-run ai-sync)`. Bounded — the remedial advice
   stays correct. Fixing it means touching `installed_mode()`, which lane B's brief forbade. Reported
   by the lane rather than quietly worked around.
2. **`HOW-TO-USE.agent.md:342` still shows only the healthy `copied (in sync)` sample.** Lane B found
   it; that file is reserved for `taskman-no-db`, and this stem's INDEX says so. Currently owned by
   neither plan.
3. **`skills/mow/TRACKER.md:345` still names `django-reviewer`** in a worked tracker-row example. Out
   of scope for lane A, and it reads as illustration rather than roster claim — but it is the one
   surviving mention in `skills/`.
4. **The stray screenshot and `dispatch/.agent-times.json` files** remain untracked and unactioned, by
   design. `.agent-times.json` is a candidate for the same gitignore treatment `.claude/worktrees/` got.
5. **`.claude/settings.local.json` is invisible to git only via the operator's *global* ignore file.**
   On a fresh work-PC clone that rule will not exist and the file will show as untracked. Lane C found
   it and correctly declined to add a speculative entry.
6. **Lane `## Verification` blocks on disk are unfilled templates** — lane reports reach the
   orchestrator in-transcript, so lanes A and B cannot be corroborated from disk alone. The reconcile
   auditor worked around it by re-running every suite. Worth deciding whether reports should be
   persisted.
