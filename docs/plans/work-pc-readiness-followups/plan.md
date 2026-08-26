# Work-PC readiness — follow-ups

**Stem:** `work-pc-readiness-followups`
**Created:** 2026-08-26
**Predecessor:** [`../work-pc-readiness/plan.md`](../work-pc-readiness/plan.md) (shipped 2026-08-21)

## Goal

A fresh `git clone` of ai-wow on the work PC is **self-sufficient** — it carries every
hook fix that exists, its own regression tests, and an `ai-sync status` that tells the
truth on a machine where symlinks are forbidden. And the state that satisfies all of
that is actually **on `origin/master`**, not sitting staged in one Mac's working tree.

## Why now — what the readiness audit found (2026-08-26)

The audit ran a real fresh-clone install into a sandboxed `HOME`, both link modes. The
harness installs and runs. Four things stood between it and a working work PC:

1. **Nothing is published.** `origin/master` is `8cc65f4`; the 16-skill state (the
   `impeccable` removal, 113 files, −50,506 lines) is staged-only. A work-PC clone today
   gets the old repo. The session-end sync hook runs
   `/Users/ozan/Desktop/dotfiles-ai/bin/ai-sync`, whose `REPO` is dotfiles-ai — so
   **nothing auto-commits ai-wow**. This will not resolve itself.
2. **The `stamp-tracker` fix never reached ai-wow.** `_returns_at_launch` has 2 hits in
   `dotfiles-ai/hooks/stamp-tracker.py` and **0** in ai-wow's. Its regression test lives
   only in dotfiles-ai; ai-wow has no `hooks/tests/` at all. `ai-sync`'s
   `foreign_repo_root()` guard makes `_copy_skills` / `_copy_scripts` **return 0** when
   the source symlinks into another repo — which is exactly this Mac's layout. The
   propagation the predecessor plan was waiting on is structurally blocked, not slow.
3. **`ai-sync --copy` makes `status` lie.** Verified both paths: with the bare flag,
   status prints `link mode: symlink` and 8× `NOT linked (real dir)` on a complete,
   correct install; only `{"link_mode": "copy"}` in `local.config.json` reports
   `copied (in sync)`. Appendix A promises status "always tells you which mode is
   active", and the README quickstart tells you to run it right after installing. On a
   locked-down Windows box the documented flag path reads as a failed install.
4. **The two repos diverged both ways** — neither is a superset. Triaged in
   `## Decisions locked` below.

## What we'll do

1. **Port the `stamp-tracker` fix into ai-wow, test-first.** Bring `_returns_at_launch`
   and the 115-line regression test across from dotfiles-ai, keeping ai-wow's scrubbed
   docstrings. Red first (2 failures), then green (7/7) — so the work PC gets a mow board
   that does not freeze every backgrounded lane at its launch instant.
2. **Make `ai-sync status` report the mode it actually installed.** Read the state on
   disk instead of the machine's symlink *capability*, falling back to the probe only
   when nothing is installed yet — so `--copy` stops reading as a failed install. Fix the
   Appendix A wording alongside it.
3. **Back-port the safer `guard-destructive` to dotfiles-ai.** This Mac runs the version
   that returns an affirmative `allow` — approving every command it fails to recognise.
   ai-wow already has the `{}` no-opinion fix; the machine you work on daily does not.
4. **Verify by fresh clone, then publish.** Re-run the sandboxed install of the merged
   tree in both link modes, then commit and push, so `origin/master` is what the work PC
   would actually want.

## What you'll have at the end

| Area | End state |
|---|---|
| mow board on the work PC | A backgrounded lane's `ended` stays `None` at launch; `python3 hooks/tests/test_stamp_tracker.py` proves it, 7/7, and ships in the clone |
| Hook parity | Every fix that exists in either repo exists in ai-wow, or is recorded here with a reason it does not |
| Locked-down install | `ai-sync --copy` followed by `ai-sync status` reports `copy` and `copied (in sync)` — no phantom `NOT linked` lines |
| This Mac | `guard-destructive` returns no-opinion for commands it does not recognise, instead of allowing them |
| `origin/master` | Carries the 16-skill state and this run's fixes — a work-PC clone is correct on arrival |

**In one line:** Make the repo you download at work carry every fix that exists, tell the
truth about how it installed, and actually be on GitHub.

## Decisions locked

- **The divergence is triaged per file, not synced wholesale.** ai-wow is the *scrubbed,
  publishable* repo; dotfiles-ai carries employer-specific names. `session-start-marker.py`
  differs only in a comment naming real projects (`project-a / project-b` vs `web-app / demo`) — that
  is deliberate sanitization, so **ai-wow's version stands and nothing is ported**. Any
  port into ai-wow must keep the scrub (this is why lane A takes the fix but not the
  docstring).
- **`peer-session-guard.py` / `peer-session-notice.py` are not ported.** They are
  registered *nowhere* — absent from both `hooks.def.json` files and from the live
  `~/.claude/settings.json`. Porting them ships dead code into a repo being published.
  Wiring them is a behavior change for every session, and that is its own decision.
- **`ai-sync status` reports what is installed, not what the machine can do.** Rejected:
  having `--copy` silently persist `link_mode` into `local.config.json` — a flag editing
  machine config as a side effect is its own surprise. Rejected: docs-only, which leaves
  the flag a trap for anyone who does not read Appendix A.
- **The dotfiles-ai back-port is limited to `guard-destructive.sh`.** Porting
  `guard-migrations.sh` and ai-wow's Copilot-aware `hooks.def.json` too would re-render
  the live hook registration on this machine — a bigger blast radius than a follow-up run
  should take on.
- **Plain Python has no reviewer in the roster,** so this run's wave gate carries no stack
  reviewer. `backend-reviewer` is FastAPI-only by the predecessor plan's own decision and
  would hand off. This is the predecessor's open item 3 arriving in practice.
- **Commit and push at the end of Integrate.** The goal is a correct clone at work;
  leaving the result staged on one Mac would restate problem 1 rather than fix it.

## Not yet specified

*Sharpness test: can you state the question precisely now — **not** answer it now? Sharp → a `kind:decision` board row. Not sharp → a line here.*

- Whether ai-wow and dotfiles-ai should stay two repos at all, or whether ai-wow becomes
  the source with a scrub-on-publish step. The audit found divergence in both directions
  and no mechanism that reconciles them; "sync it" is not yet a stateable question.
- What guarantees a fix landing in one repo reaches the other. `foreign_repo_root()`
  blocks the import path by design, so today the answer is "a human remembers" — but the
  replacement is not sharp enough to state.

## Out of scope

*Scope, not sharpness. Never graduates — returns only if this plan's goal is redrawn, and then as a fresh stem.*

- **Wiring the peer-session hooks** — a per-session behavior change, not a portability gap
  (see `## Decisions locked`).
- **`guard-migrations.sh` never fires on this Mac** — the live `settings.json` was rendered
  from dotfiles-ai's `hooks.def.json`, which has no such row. It *will* register on a work
  PC clone from ai-wow's own def, so it is not a work-PC readiness gap.
- **Porting Copilot hook support into dotfiles-ai** — ai-wow's `hooks.def.json` is ahead
  (Copilot CLI 1.0.80, verified live); dotfiles-ai has no Copilot rows at all. Out by the
  blast-radius decision above.
- **taskman on the work PC** — the board needs Postgres. Known and documented; everything
  else runs on a bare clone.
- **`.claude/worktrees/` is still not gitignored** — inherited open item 6 from the
  predecessor plan. This run uses worktree isolation, so it will recreate the gitlinks;
  Integrate keeps them out of the commit by staging explicit paths.
