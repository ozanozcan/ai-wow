---
date: 2026-08-21 19:13
branch: master
slug: work-pc-readiness-mow-go-and-harness-fixes
project: none
session_id: 4de9e70f-46a7-47ea-bc17-9890fb398fb7
start_sha: 3f61113
---

# Session report — /mow go work-pc-readiness, then three harness fixes it surfaced

## What was done

- **Ran `/mow go work-pc-readiness` to completion.** Two waves, three lanes, shipped.
  Registry row flipped to `shipped`; action report written at
  [`docs/plans/work-pc-readiness/action-report.md`](../plans/work-pc-readiness/action-report.md).
- **Reviewer roster rebuilt for the operator's real stacks** — `backend-reviewer` rewritten
  FastAPI-only with a new security & config section, `classic-web-reviewer` and
  `streamlit-reviewer` added, `django-reviewer` deleted. All eight agents now agree with
  every stated inventory count.
- **mow tracker made portable** — `pkill` → `taskkill` → warn, `open` → `start` →
  `xdg-open` → skip, URL printed unconditionally, no platform sniffing.
- **Discovered `ai-wow/skills` and `ai-wow/agents` are mirrors, not sources.** A verified
  lane diff applied to `ai-wow/skills/` was overwritten within a minute by a sync from
  `~/Desktop/dotfiles-ai` and never reached a commit. Re-targeted to dotfiles-ai with
  operator approval; propagated back byte-identical.
- **Ported the agent roster to dotfiles-ai** (post-Integrate, operator-directed) — closes
  the gap where the new reviewers were live in git but absent from the runtime roster.
- **Fixed `hooks/stamp-tracker.py`** — backgrounded subagents were stamped as finishing at
  launch. Test-first; new `hooks/tests/test_stamp_tracker.py`.

## Files changed

**ai-wow** (`3f61113..HEAD`, this session's paths only):

```
HOW-TO-USE.agent.md              7 +-
HOW-TO-USE.human.md              4 +-
README.md                        2 +-
agents/backend-reviewer.md      55 ++++----
agents/classic-web-reviewer.md 123 +++++++++++++
agents/django-reviewer.md      234 ----------------------
agents/streamlit-reviewer.md   120 +++++++++++
global/CLAUDE.md                 6 +-
skills/mow/SKILL.md             35 ++++-
skills/mow/TRACKER.md           39 ++++--
```

Plus the plan folder: `plan.md` (two corrections), `action-report.md`, `dispatch/INDEX.md`,
`dispatch/tracker.{json,html}`.

**dotfiles-ai** (the source repo — uncommitted):
`agents/backend-reviewer.md`, `agents/classic-web-reviewer.md` (new),
`agents/streamlit-reviewer.md` (new), `agents/django-reviewer.md` (deleted),
`hooks/stamp-tracker.py`, `hooks/tests/test_stamp_tracker.py` (new),
`skills/mow/SKILL.md`, `skills/mow/TRACKER.md`.

Not mine, present in both trees from parallel sessions: `bin/ai-sync`,
`hooks.def.json`, `hooks/guard-destructive.sh`, `hooks/guard-migrations.sh`,
`.gitignore`, `LESSONS.md` (beyond my step-2.5 entries), `docs/brainstorms/*`,
`taskman/taskman/alembic/*`.

## Wrap-up gate

**Not run — unavailable.** No `.taskman.toml` anywhere up the tree, no
`scripts/wrapup_reconcile.py`, no `.session-markers/`. Per the skill's precondition this
is the degraded path: lessons + session report only, no board sync, no harvest.

Attribution was done by hand instead, and it matters here: two other sessions
(`VSCode harness engineering workflows`, `AI-WOW state and IDE compatibility`) were writing
to this same working directory throughout. `bin/ai-sync` was modified at 11:24 by one of
them — that is what blocked the automatic wrap-up during `/mow go` Integrate, correctly.

## Taskman sync

**None — no board in this repo.** No Feature/Task/Requirement rows exist to sync.

## Lessons

- **L06 bumped to seen ×2** (`environment,verification,dotfiles`) — "resolve what the
  runtime actually loads; the repo you are cwd'd in is not necessarily the installed
  source." Recurred in a sharper form: not merely inert, actively overwritten by a sync.
- **L17 logged** (`git,verification,honesty,records`) — in an auto-committing repo, git
  state is not stable between reading it and writing about it; re-check before committing
  a claim to a durable artifact. Provoked by the action report's "ahead 1 and unpushed",
  which was already false when written.
- **L18 logged** (`shell,verification,grep,polling`) — test a shell check by exit status,
  not captured text; `$(grep -c … || echo 0)` yields `0\n0` and every comparison is true.

**`>>> PRUNE` signal fired** on all three writes: `LESSONS.md` is 192 lines (cap 150).
Oldest single-sighting entries named by the script: L01, L02, L03, L05, L07. Nothing
deleted — that is the operator's call.

## Decisions

- **Lane B's fix was re-targeted from ai-wow to dotfiles-ai**, overriding the plan's scope
  boundary, with explicit operator approval. Recorded in `plan.md`'s corrected Operator
  note.
- **The parallel session's two commits were not pushed.** "Push it" was answered by
  checking rather than pushing: the run's own work was already on `origin/master`, and the
  only unpushed commits belonged to another session.
- **`plan.md`'s `backend-reviewer` premise was recorded as wrong** rather than quietly
  worked around — it described a Django/Flask routing table that was not in the repo, so
  two of the plan's six headline items were no-ops.

## Open threads / not finished

- **The hook fix has not reached ai-wow.** `hooks/stamp-tracker.py` and `hooks/tests/` are
  still pending there while `skills/` and `agents/` propagated. A fresh work-PC clone would
  get the buggy hook. Live on this Mac either way, via `~/.claude/hooks` → dotfiles-ai.
- **dotfiles-ai is uncommitted**, mixing my changes with three parallel sessions' work.
  Whenever its session-end hook fires, it will commit all of it together.
- **Four deferred items** from the ship-check, unchanged: no enforcement of the two
  serving blocks' byte-identity; skills-count drift (docs say 14 / 15 / "Fifteen",
  `ls -d skills/*/` says 17); plain-Python diffs have no reviewer now that
  `backend-reviewer` is FastAPI-only; `.claude/worktrees/` is not gitignored.
- **No checkpoint created** — this repo has no `docs/checkpoints/` and no board, so step 4
  has nowhere to write. The leftovers above are the handoff.

## Next steps

- Decide whether the parallel session's `bin/ai-sync` + alembic-guard commits should be
  pushed; they are the only thing `git push` would send.
- Let dotfiles-ai's sync carry the hook fix into ai-wow, or port it deliberately.
- Consider the PRUNE signal on `LESSONS.md`.
- `ai-wow` is dirty with `action-report.md` and `dispatch/.activity`; the background sync
  will commit both shortly without intervention.
