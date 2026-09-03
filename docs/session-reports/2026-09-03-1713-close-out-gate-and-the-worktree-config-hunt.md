---
date: 2026-09-03 17:13
branch: master
slug: close-out-gate-and-the-worktree-config-hunt
project: none
session_id: 4fab3fda-2f0e-415a-adbf-2589931bd8d6
start_sha: f2560236df2abc59d8c55acd6b18170154531f9a
---

# Session report — the mow close-out gate, and root-causing core.bare/core.worktree

Spans two repos (`ai-wow`, `dotfiles-ai`) and a third clone (`~/dotfiles/ai`) throughout — neither `ai-wow` nor `dotfiles-ai` carries a `.taskman.toml`, so per wrap-up preconditions this report is the only durable record; no board sync ran.

## What was done

**The mow close-out gate — prose made enforceable.** `/mow go` §4 said "invoke ship-check before `Status: shipped`", "write the action report — do not skip", "reconcile the tracker" — all prose, nothing read any of it back. Built `taskman.mow.closeout` as the bookend to `preflight`: composes four checks (`check_ship_check`, `check_action_report`, `check_tracker`, and later `check_verification` + `check_board_sync`) and wired it into `set_registry_status <stem> shipped`, which now exits 3 and writes nothing if a run isn't actually finished. Landed in two waves — the first three checks (dotfiles-ai `94d9d25`), then `check_verification` + `check_board_sync` + eleven `scripts/` shims once a Cursor-session collaborator built them (dotfiles-ai `a5191b9`, mirrored to ai-wow `80e4931`). Verified by making the gate fire, not by reading it: stubbing either new `check_stem` to `return []` turned tests red; run read-only against ai-wow's four already-`shipped` stems it would have stopped all four (`taskman-no-db` had no frontmatter at all).

**Two config drifts diagnosed to root cause, not just patched.** `core.bare` had flipped to `true` in ai-wow's shared `.git/config` three times across this session and one prior one, each time "fixed" by writing `false` back to that same shared file — which is why it kept recurring. Root cause: `extensions.worktreeConfig = true` makes `core.bare` **per-worktree**, and nothing had ever created the main checkout's own `config.worktree` override (linked worktrees get theirs automatically from `git worktree add`; the main one never does). Fixed properly — `git config --worktree core.bare false` on every worktree — and proved it by reproducing the failure: with the shared config forced back to `bare = true`, the main checkout and all linked worktrees kept working. `core.worktree` turned out to be the same bug, worse: a stray shared value doesn't error, it silently makes **every** worktree report on the wrong tree (`git status` exit 0, wrong files). Same fix, same proof. A peer session (`mow-go-taskman-port`) hit and independently confirmed the exact failure mode within the hour — three of its worktrees had been reporting 214–230 "dirty" files under the stray value — and used the fix to finish a wave-2 teardown it had stalled on.

**Cross-repo git hygiene, done carefully in a live shared checkout.** Ran under the session's own peer-session-guard rules throughout: `git commit -- <paths>` scoped to exactly the files I touched, re-sampled `git status`/`HEAD` immediately before every commit or push rather than trusting an earlier read, and drained the index in the same turn after a blocked push rather than leaving staged state for a peer to inherit. Two pushes were genuinely blocked by the repos' own gates and fixed rather than bypassed: dotfiles-ai's `tree-drift.json` refused an unclassified shared file (fixed by classifying it `match` — `b12f21f`, `be76f32`), and ai-wow's `test_repo_shape.py` refused a stale test-count claim in `README.md` (210 vs. the real 232 — `7d653dd`). Kept `~/dotfiles/ai` (the clone two sibling projects import `taskman` from) fast-forwarded to the other two throughout, so those projects' close-out gates stayed current.

**Cross-session coordination.** Sent four messages to peer sessions this chat — the `core.bare` root cause, the `core.worktree` root cause, a traced-identity report on five orphaned uncommitted files plus a wave-2 hazard (deleting nine `tree-drift.json`-locked paths would have blocked a *different* repo's push), and a correction to that hazard's blast radius (staged vs. committed changes the window). All four were acted on or acknowledged by the receiving session.

## Files changed

- `dotfiles-ai`: `94d9d25`, `b12f21f`, `a5191b9`, `be76f32` — the close-out gate, its tests, and drift classification (34 files across the four commits)
- `ai-wow`: `7eddeb1`, `f3bef63`, `80e4931`, `7d653dd` — mirrored gate + docs + the README fix (31 files across the four commits)
- `dotfiles-ai` (this wrap-up, uncommitted until step 6): `LESSONS.md` (+L48), `global/CLAUDE.md` (§Verification habits, +1 bullet)
- Config only, not git-tracked: `core.bare`/`core.worktree` per-worktree overrides in `.git/config.worktree` (ai-wow, 5 worktrees) and the equivalent in the peer's worktrees
- Memory: `ai-wow-core-bare-flips.md` rewritten from "cause unknown" to the solved root cause (both settings); `MEMORY.md` index line updated to match

## Wrap-up gate

No `.taskman.toml` at the ai-wow project root — taskman sync unavailable for this session, per wrap-up preconditions. Step 0 (evidence gate) and step 2 (board sync) did not run.

## Taskman sync

None — no board in either repo this session touched.

## Lessons

**L48** logged and routed to `claude-md` in the same pass (dotfiles-ai `global/CLAUDE.md`, §Verification habits — confirmed live on the symlinked path `~/.claude/CLAUDE.md` actually loads). Rule: a fact stated once in a session — a push-status count, a test flag that worked — is not still true when reused; re-derive it at the point of reuse rather than repeating an earlier reading. Two occurrences this session: an unpushed-commit count for `~/dotfiles/ai` reported from a stale local remote-tracking ref, twice (2 vs. actual 39; "exactly at origin/master" vs. actual 5 behind), both self-caught only after a later fetch contradicted the claim; and a `--noconftest` flag recommended to a peer session that went stale when that peer's own lane made the target repo's `conftest.py` DB-free, then broke two tests when reused unchanged. Checked against `LESSONS.md` first — no near-duplicate; the closest existing rule (L17, already routed and loaded) covers *not re-sampling shared state before acting on it*, which didn't stop this specific shape recurring twice, so per the routing script's own design ("a routed rule that recurs is evidence its destination is not working — log a new entry saying so") this is a new, narrower entry rather than a bump.

## Decisions

- Left `docs/plans/taskman-port/action-report.md`'s "210 tests" claim untouched when fixing the same number in `README.md` — the action report is a point-in-time record of what that run shipped and was true when written; only the README makes a live claim about the tree as it stands.
- Declined to touch `core.bare`/`core.worktree` in the *shared* `.git/config` as the fix — that file is legitimately meant to carry the "wrong-looking" value under `extensions.worktreeConfig`; the fix belongs in each worktree's own `config.worktree`, which is exactly the distinction the recurring bug turned on.

## Open threads / not finished

- `core.worktree`'s known gap: `git worktree add` auto-protects a new worktree against `core.bare` but not `core.worktree`. The peer session (`mow-go-taskman-port`) has since added the re-cover command to its own project memory as part of `mow go` §2a, so future fan-out there runs it after spawning lanes — but this is per-session memory, not a repo-level fix, so a *different* future session spawning worktrees in ai-wow has no automatic protection.
- Session `3061ab69` (five files it edited mid-session — `HOW-TO-USE.*`, `README.md`, `templates/BOOTSTRAP.md`, `taskman/taskman/README.md`) was never mapped to a `ListAgents` name; traced only by transcript timestamp correlation. Left for the user to identify from their own open windows. Unclear whether it landed those edits before this session closed.

## Next steps

- **Commit dotfiles-ai's `LESSONS.md` + `global/CLAUDE.md` together** (step 6 below handles this) — L48's ledger row and its routed edit must land in one commit whose message carries the case, per the wrap-up skill's own rule (a ledger row committed separately arrives without its story).
- If either `ai-wow` or `dotfiles-ai` ever adopts a board (`.taskman.toml`), this session's work — two-repo test suites, a new enforcement chokepoint, a root-caused recurring config bug — is exactly the shape step 3 (action report) exists for; worth a retroactive one if that happens.
- Resume pointer: this report, plus the `ai-wow-core-bare-flips` memory record for the config fix, plus `dotfiles-ai/skills/mow/SKILL.md` §4 (Integrate) for the close-out gate's operating contract.
