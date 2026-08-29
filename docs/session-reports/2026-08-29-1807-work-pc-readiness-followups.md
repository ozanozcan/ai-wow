---
date: 2026-08-29 18:07
branch: master
slug: work-pc-readiness-followups
project: none
session_id: none — no .taskman.toml in this repo
start_sha: 8cc65f4
---

# Session report — audit of work-PC readiness, then a mow run closing what it found

## What was done

- **Audited work-PC readiness against evidence, not docs.** Cloned the repo into a sandboxed
  `HOME` and ran the install both ways. Four blockers surfaced: nothing was published
  (`origin/master` still bundled `impeccable`), the `stamp-tracker` fix had never propagated
  from dotfiles-ai, `ai-sync --copy` made `status` report a correct install as eight failures,
  and the two repos had diverged in both directions.
- **Planned and ran a 4-lane mow run** (`work-pc-readiness-followups`) closing all four:
  wave 1 backgrounded A ‖ B in isolated worktrees, wave 2 foreground C → Z.
- **Ported the `stamp-tracker` backgrounded-agent fix + its 115-line regression test** into
  ai-wow, keeping the scrub. Red first (2 failures), green after (7/7).
- **Made `ai-sync status` read the installed mode off disk** (`installed_mode()`), so a
  `--copy` install stops reading as a failed one. Both docs quoting that output updated.
- **Back-ported the safer `guard-destructive`** to dotfiles-ai — this Mac had been returning an
  affirmative `allow` for every command the guard could not parse.
- **Added two durable regression suites plus a repo-shape suite** — `hooks/tests/`,
  `bin/tests/test_ai_sync_status.py`, `bin/tests/test_repo_shape.py`. Each proven red against
  the unfixed code before being trusted green.
- **Documented the harness's own tests in `README.md`**, which forced a Windows check the claim
  did not survive (below).
- **Published.** `origin/master` moved `8cc65f4 → 65c57a0`, eight commits.

## Files changed

`git diff --stat 8cc65f4..HEAD` — 128 files, +2,946 / −50,517 (the bulk is the 113-file
`impeccable` removal). Substantive:

- `hooks/stamp-tracker.py`, `hooks/tests/test_stamp_tracker.py` (new)
- `bin/ai-sync`, `bin/tests/test_ai_sync_status.py` (new), `bin/tests/test_repo_shape.py` (new)
- `README.md`, `HOW-TO-USE.human.md`, `HOW-TO-USE.agent.md`, `THIRD-PARTY.md`, `skills.lock.json`
- `docs/plans/work-pc-readiness-followups/**` (plan, 4 briefs, INDEX, action report, tracker)
- Outside this repo: `dotfiles-ai/hooks/guard-destructive.sh`, `dotfiles-ai/global/CLAUDE.md`,
  `dotfiles-ai/LESSONS.md`

## Wrap-up gate

**n/a** — this repo has no `.taskman.toml` and no `scripts/wrapup_reconcile.py`, so the
deterministic gate could not run. Per the wrap-up skill's preconditions, this session took the
no-board path: lessons + session report only. Evidence was instead carried by the mow run's own
gates (both wave gates re-run independently by the orchestrator) and by the tracker reconcile.

## Taskman sync

**None** — no board in this repo. No Feature/Task/Requirement rows exist to sync.

## Lessons

- **L33 → `claude-md`** (new). *A guard is proven by making it fire, not by reading it.* Two
  independent instances this session: a fail-loud coverage sweep whose fallback matched anything
  anywhere and so passed the exact case it existed to catch, and a `HOME=` test sandbox that does
  nothing on Windows because `Path.home()` reads `USERPROFILE`. Edit landed in
  `dotfiles-ai/global/CLAUDE.md` → `## Verification habits` and verified on `~/.claude/CLAUDE.md`,
  the path the runtime actually loads.
- No other lesson qualified. The remaining corrections were project facts or one-offs.

## Decisions

- **The two repos are triaged per file, never synced wholesale.** ai-wow is the scrubbed,
  publishable side; `session-start-marker.py`'s difference is deliberate sanitization.
- **`peer-session-*.py` not ported** — registered nowhere, so porting ships dead code.
- **`ai-sync status` reports what is installed, not what the machine can do.** Rejected: a flag
  silently persisting `link_mode` to config; rejected: docs-only.
- **The dotfiles-ai back-port stayed at one file** — porting `guard-migrations.sh` and the
  Copilot-aware `hooks.def.json` would re-render live hook registration.
- **Published before verifying, deliberately.** Worktrees branch from a committed base and the
  scrub lane A had to preserve was staged-only, so the audited base was pushed before wave 1.

## Open threads / not finished

1. **`global/CLAUDE.md` diverges both ways, newly found during this wrap-up.** ai-wow's published
   copy has **no `## Verification habits` section at all** — 39 lines, the entire destination the
   lessons ledger routes to, exists only in dotfiles-ai. Meanwhile ai-wow's routing table is
   *newer*, carrying file-type dispatch and `classic-web-reviewer` / `streamlit-reviewer` rows
   that dotfiles-ai lacks. Neither side is a superset. Not acted on — it is the same class as
   action-report open item 4 and wants an operator decision, not a unilateral sync.
2. **`stamp-tracker` parity is still incomplete** — dotfiles-ai has `_prompt_names_run` /
   `_stem_of` and a two-arg `_find_board(cwd, prompt)`; ai-wow attributes a spawn to the most
   recently written board unconditionally.
3. **Copy-install drift is misdiagnosed** — a drifted copy fails `_is_copy_of`, falls back to the
   probe, and prints `NOT linked (real dir)`, which is the wrong diagnosis for "copied but stale".
4. **Nothing reconciles the two repos.** `foreign_repo_root()` blocks the import path by design;
   this session carried three fixes across by hand.
5. **dotfiles-ai has six modified files, uncommitted** — two from this session
   (`hooks/guard-destructive.sh`, `global/CLAUDE.md` + `LESSONS.md`), the rest pre-existing drift
   from other runs there. That repo gets its own operator pass.
6. **ai-wow's working tree carries predecessor-run files** — `work-pc-readiness/action-report.md`,
   two `.activity` trails, and an untracked session report from 2026-08-21. Not this session's to
   attribute.

## Next steps

- Decide open thread 1 — whether ai-wow should carry `## Verification habits`, and which side of
  the routing table wins. It is the highest-value one: it is where every future lesson lands.
- No checkpoint created: this repo has no `docs/checkpoints/` and no board, so the wrap-up
  skill's leftover-bundling path (step 4) does not apply. Open threads above are the handoff.
- Resume pointer: `docs/plans/work-pc-readiness-followups/plan.md` ·
  `docs/plans/work-pc-readiness-followups/action-report.md` · this report.
