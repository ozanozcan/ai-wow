# Publish hygiene — make the shipped harness tell the truth about itself

**Stem:** `publish-hygiene`
**Created:** 2026-09-01
**Sibling stem:** `taskman-no-db` (planned in parallel — owns `taskman/**`, `README.md:161`, invariant I10)
**Predecessor:** [`../work-pc-readiness-followups/plan.md`](../work-pc-readiness-followups/plan.md) (shipped 2026-08-26)

## Goal

Every instruction ai-wow ships can actually be followed in a fresh clone, and every
claim it makes about itself is true. The repo is about to go public and become the
operator's work-PC harness at the same time — two audiences who both meet it as a
clone with nothing pre-installed, and both of whom hit any lie on their first session.

## Why now — what a real fresh-clone pass found (2026-09-01)

The `docs/` scrub and the board bootstrap procedure landed today (`573a6a2`, `1693827`).
Verifying them turned up four defects that the previous two readiness runs missed, because
each one is a *reference* that only fails when someone follows it:

1. **Three places tell you to run a script that does not exist.** `scripts/wrapup_reconcile.py`
   has no counterpart in this repo — there is no `scripts/` directory and no repo-root `.venv/`
   either. The SessionStart hook prints this instruction to **every session**, so it is the
   first thing a work-PC clone says. The obvious replacement is not a fix either — see grill Q1
   in `## Decisions locked`: `python -m taskman wrapup gate` needs `taskman/.venv`, which a fresh
   clone does not have until `uv sync` runs.
2. **The mow skill routes to an agent this repo does not ship.** `skills/mow/SKILL.md:526`
   maps role `django-review` → agent `django-reviewer` in both runtime columns. `agents/` has
   no such file. The role falls back and notes the downgrade, so nothing crashes — but a
   shipped routing table asserting a missing agent is a claim, not a nicety.
3. **A drifted copy-install reports the wrong diagnosis.** `bin/ai-sync:960,982` print
   `NOT linked (real dir)` when `_is_copy_of` fails and the capability probe takes over. The
   misleading output returns *precisely* when something is actually wrong, on the locked-down
   Windows box this whole effort exists to serve. Flagged by lane B of the predecessor run and
   correctly left alone as out of scope then.
4. **`.claude/worktrees/` is still not gitignored.** Inherited across two runs. Both worktrees
   created today were kept out of commits by hand, which is not a mechanism.

**One correction to the record:** both predecessor reports list the `stamp-tracker` parity gap
(`_prompt_names_run` / `_stem_of` / two-arg `_find_board`) as open. It is **closed** — all three
landed in `3ad521f`. Verified in the tree, not read from the reports. No lane should rebuild it.

## What we'll do

1. **Repoint the three `wrapup_reconcile` references at the entry point that exists**, so the
   first instruction a work-PC session receives is one it can follow.
2. **Make the copy-install diagnosis correct** — a stale copy reports that it is stale, not that
   it was never linked.
3. **Stop asserting an agent we do not ship**, and gitignore the worktree directory so isolation
   stops depending on the orchestrator remembering.
4. **Write the board-less decision down as a decision**, so `Board sync: n/a` reads as a choice
   rather than an omission, and a cloner knows to bring their own `.taskman.toml`.
5. **Make `taskman` invocable the same way everywhere** — one PATH line in the bootstrap instead
   of 29 relative venv prefixes, and a bootstrap that targets the reader's project rather than
   taskman's own test project. Added mid-run by the ship-check gate (wave 3).

## What you'll have at the end

| Area | End state |
|---|---|
| First session on a work-PC clone | The SessionStart notice names no command the clone cannot run — board present, it names the gate; board-less, it says nothing about wrap-up, and still writes its marker |
| `/wrap-up` in a board-less repo | No reference to a missing `scripts/` path or a repo-root `.venv/` survives in any shipped file |
| Drifted copy install | `ai-sync status` distinguishes "copied but stale" from "never linked"; a regression test pins both |
| Agent roster | `grep -r django-reviewer` over shipped surfaces returns only honest, conditional references — no table asserting the agent exists |
| Worktrees | `.claude/worktrees/` is gitignored; `git status` is clean immediately after a worktree run |
| Board posture | The docs state ai-wow is deliberately board-less and why, with the reachable-Postgres caveat named |

**In one line:** Make every instruction the harness ships followable in a fresh clone, and every
claim it makes about itself true.

## Decisions locked

- **Two stems, sequenced — hygiene first** (operator, 2026-09-01). The one-sentence test failed
  ("clean up the harness **and also** replace the board's storage engine"). Deciding factors:
  the storage shape is still undecided (B vs C3), so its briefs would fail the thin-brief gate
  today; and both stems want `README.md:161` and invariant I10, which is a cross-plan overlap
  rather than a merge conflict waiting to happen. `taskman-no-db` is being planned in a
  parallel session and **owns** `taskman/**`, `README.md`, and `HOW-TO-USE.agent.md`.
- **ai-wow stays board-less, and says so** (operator, 2026-09-01). Measured, not assumed: with a
  root `.taskman.toml` and no reachable Postgres, `taskman wrapup gate` exits **2** — which the
  wrap-up skill's own table reads as "no session marker", the wrong diagnosis, pointing at a
  command that fails identically. Adding a board today would break `/wrap-up` on the work PC on
  day one and contradict the README's "the harness needs no database" claim in the very repo
  people clone to evaluate it. Revisit **after** `taskman-no-db`, when the objection dissolves.
- **`django-reviewer` stays out of ai-wow** (operator, 2026-09-01). Django is not widely used at
  the operator's company; other Python backends and frontends are the target. This upholds the
  `harness-boundary` decision rather than overturning it — so the fix is to make the *references*
  honest, not to ship the agent.
- **The SessionStart hook names the evidence gate only when a board exists** (operator,
  2026-09-01, grill Q1). Found during the grill: the replacement command this plan specified,
  `python -m taskman wrapup gate`, fails on a fresh clone exactly like the path it replaces —
  `No module named taskman.__main__`, because the CLI lives in `taskman/.venv` and only exists
  after `uv sync`. Naming a venv-qualified path would trade one unfollowable instruction for
  another. So the hook walks up for a `.taskman.toml` and names the gate **only** when it finds
  one; a board-less clone gets the marker line and nothing else. **Critical constraint:** this
  must affect the *message text only*. An earlier `.taskman.toml` gate in this same hook caused
  an early return that stopped markers being written at all, fixed in `f6b25f9` — re-introducing
  that is the failure mode to avoid.

- **A drifted copy-mode install prints `copied (stale — re-run ai-sync)`** (operator, 2026-09-01,
  grill Q2). Applies to **both** the directory and the file branch, replacing the fall-through to
  `NOT linked (real dir)` / `NOT linked (real file)` in copy mode only. Chosen to stay inside the
  `copied (...)` family so the line reads as "installed, but out of date" rather than "not
  installed", and to name the remedy inline — on a locked-down Windows box the operator has no
  reason to know that re-running `ai-sync` is the fix. `NOT linked (...)` survives unchanged for
  a genuinely never-linked path.

- **Lane A owns its regression test *and* its registration in the push gate** (operator,
  2026-09-01, grill Q3). The hook change needs a test that the board-less branch still writes a
  marker — the `f6b25f9` regression returns silently otherwise. `hooks/tests/` held only
  `test_stamp_tracker.py`, and `githooks/pre-push` (which is what actually runs these suites) was
  in no lane's scope, so a durable test would have shipped unregistered. That is the exact failure
  `githooks/pre-push`'s own header names: "A check nobody runs is not enforcement." Lane A's
  `Files owned` therefore gains `hooks/tests/test_session_start_marker.py` and
  `githooks/pre-push`. Neither collides — no other lane touches `hooks/tests/` or `githooks/`.

- **Lane C commits the orphaned session report; everything else it only reports** (operator,
  2026-09-01, grill Q4). The plan's goal says "squeaky clean" while lane C's brief said
  report-don't-action — a mismatch the lane would have resolved by following the brief. Resolved
  by splitting on kind: `docs/session-reports/2026-08-21-1913-work-pc-readiness-mow-go-and-harness-fixes.md`
  is **record content** that has sat untracked across three sessions and gets committed; the stray
  screenshot and `dispatch/.agent-times.json` are reported with a recommendation and left for the
  operator. **No agent deletes a file it did not create.** Note the report is untracked, so it
  needs `git add <path>` before a path-limited commit can see it — and once tracked it falls under
  the widened `docs/` scrub, so the lane must confirm it passes the gate (it was checked clean on
  2026-09-01).

- **`docs/` is scrubbed and gated as of today.** `SCRUBBED_DIRS` now includes `docs`, and the
  scan reads git-tracked files rather than walking the working tree — an ignored file exposes
  nothing, and walking the tree blocked a push on `docs/brainstorms/`, which `.gitignore` keeps
  out of the repo entirely. Any lane adding docs must keep them codename-free; the push gate
  will refuse otherwise.
- **No board import gate this run.** The mow taskman steps (`plan from-decisions`, `mark-shipped`)
  are **n/a** — they require a root `.taskman.toml`, which the decision above declines. There is
  also no `scripts/` directory, so `mow_preflight.py` / `mow_hydrate_specs.py` do not exist here;
  their checks are performed manually at go.

- **Wave 3 was added mid-run by the ship-check gate** (operator, 2026-09-01). The gate found a
  Critical Layer-1 miss: the plan promised no repo-root `.venv/` path would survive in a shipped
  file, and **29 did** — `skills/wrap-up` (20), `skills/grill-with-docs` (7), `skills/bs` (2).
  ai-wow has no root `.venv/`, so `/wrap-up` still named an unrunnable path. The lane-A grep that
  "verified" this searched `\.venv/bin/python scripts/`, which requires `scripts/` immediately
  after and so could only ever match the combination — never a bare `.venv/bin/python`. The check
  passed; the criterion did not hold (L40). The defect was in the brief I wrote, not in the lane.

- **Investigating that found a second, worse defect in already-pushed work.** The `### Standing one
  up` bootstrap shipped in `1693827` tells the reader to put a `.taskman.toml` at *their* repo root,
  then run `cd taskman && uv run python -m taskman init-db` — which executes in **ai-wow's** taskman
  directory. `find_project()` walks up from cwd, so that registers `taskman-tests`, not the reader's
  project. Proven directly: `resolved from my-service dir -> ('my-service', …)` vs
  `resolved from ai-wow/taskman -> ('taskman-tests', …)`. It was "verified" on the rehearsal, but
  only against taskman's own test project — the single case where the bug cannot show. Same shape as
  the grep miss: a check that passed because it checked the easy case.

- **The fix for both is one thing: put the console script on PATH.** `uv sync` installs
  `taskman/.venv/bin/taskman`. On PATH, every skill line becomes a bare `taskman …`, true in every
  repo. This is strictly better than a relative venv prefix, because `find_project()` resolves the
  project by walking up from cwd — the CLI *must* be run from the reader's project directory, and a
  relative `.venv/bin/python` prefix quietly fights that. The "where does the CLI live" hint moves
  from 29 fragile prefixes to one PATH line in the bootstrap.

## Not yet specified

*Sharpness test: can you state the question precisely now — **not** answer it now? Sharp → a board row. Not sharp → a line here.*

- **The peer-session hooks protect nobody in an already-running session.** Both fire at
  SessionStart and both sides need a marker, so the first new session in a shared checkout still
  sees nothing. Today's session hit this exact case — the peer was found by listing sessions, not
  by any warning. Whether the fix is a periodic re-check, a PreToolUse probe, or accepting the
  limitation is not yet a stateable question.
- **Nothing reconciles ai-wow and dotfiles-ai.** `foreign_repo_root()` blocks the import path by
  design, so a fix landing in one reaches the other only when a human carries it. Four have been
  carried by hand across the last three sessions. Whether this wants tooling, a checklist, or
  nothing at all is still fog.

## Out of scope

*Scope, not sharpness. Never graduates — returns only if this plan's goal is redrawn, and then as a fresh stem.*

- **taskman's default credentials and its connection-error message** — the `taskman:taskman`
  fallback in `taskman/taskman/config.py` makes a working install look broken. Real, and the
  documentation half already landed today (three troubleshooting rows). The code half lives in
  `taskman/**`, which the sibling stem owns. (→ `taskman-no-db`)
- **Invariant I10 and `README.md:161`** — both assert Postgres outright and both must be amended
  if the storage refactor lands. Editing them here would collide with the stem that rewrites them.
  (→ `taskman-no-db`)
- **Whether the work PC can run Postgres at all** — a fact-find, not a change to this repo.
  Recorded in `enterprise-migration` as still open. (→ operator)
