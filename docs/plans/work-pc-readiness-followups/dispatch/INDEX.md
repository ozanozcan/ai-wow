# Dispatch index — Work-PC readiness follow-ups

Source plan: docs/plans/work-pc-readiness-followups/plan.md

## What we'll do
1. **Port the `stamp-tracker` fix into ai-wow, test-first** — `_returns_at_launch` plus its 115-line regression test, keeping ai-wow's scrubbed docstrings. Red first, then green.
2. **Make `ai-sync status` report the mode it actually installed** — read disk state instead of the machine's symlink capability, so `--copy` stops reading as a failed install. Fix the two docs that quote the output verbatim.
3. **Back-port the safer `guard-destructive` to dotfiles-ai** — this Mac currently returns an affirmative `allow` for every command its guard cannot parse.
4. **Verify by fresh clone, then publish** — re-run the sandboxed install of the merged tree in both link modes, then commit and push.

## What you'll have at the end
| Area | End state |
|---|---|
| mow board on the work PC | A backgrounded lane's `ended` stays `None` at launch; `python3 hooks/tests/test_stamp_tracker.py` proves it, 7/7, and ships in the clone |
| Hook parity | Every fix that exists in either repo exists in ai-wow, or is recorded with a reason it does not |
| Locked-down install | `ai-sync --copy` then `status` reports copy mode and `copied (in sync)` — no phantom `NOT linked` lines |
| This Mac | `guard-destructive` returns no-opinion for unrecognised commands instead of allowing them |
| `origin/master` | Carries the 16-skill state and this run's fixes — a work-PC clone is correct on arrival |

**In one line:** Make the repo you download at work carry every fix that exists, tell the truth about how it installed, and actually be on GitHub.

## Waves
- **Wave 1 (parallel, AFK, worktree-isolated):** A | B
- **Wave 2 (foreground, sequential):** C → Z

Each wave ends with a **review gate** before the next starts.

## Lanes
| Lane | Todos (in order) | PBI / Feature | Files owned | Role | Review flags | AFK | Background | Decisions / Specs | Brief |
|---|---|---|---|---|---|---|---|---|---|
| A | stamp-tracker-parity | - / - | `hooks/stamp-tracker.py`, `hooks/tests/` | code-edit | - | yes | yes | - | [01-stamp-tracker-parity.md](01-stamp-tracker-parity.md) |
| B | copy-mode-truth | - / - | `bin/ai-sync`, `HOW-TO-USE.human.md`, `HOW-TO-USE.agent.md` | code-edit | - | yes | yes | - | [02-copy-mode-truth.md](02-copy-mode-truth.md) |
| C | dotfiles-guard-backport | - / - | `~/Desktop/dotfiles-ai/hooks/guard-destructive.sh` (out of repo) | shell | - | no | no | - | [03-dotfiles-guard-backport.md](03-dotfiles-guard-backport.md) |
| Z | fresh-clone-verify | - / - | none (scratch only) | shell | - | no | no | - | [04-fresh-clone-verify.md](04-fresh-clone-verify.md) |

`PBI / Feature`: `-` throughout — this repo has no root `.taskman.toml`, so no board rows exist.

`Review flags`: `-` for every lane. The run's diff is plain Python (`hooks/`, `bin/ai-sync`), shell, and markdown. `backend-reviewer` is FastAPI-only by the predecessor plan's decision and would hand off; no roster agent owns plain Python. This is the predecessor's open item 3 arriving in practice, and it is recorded rather than papered over.

`Decisions / Specs`: `-` throughout — no taskman board. Each brief points at `plan.md` → `## Decisions locked` and cites the binding bullet in its own Do NOT / Acceptance.

**Hydrated specs:** n/a — no board, every Decisions / Specs cell is `-`.

**Grill checkpoint:** done 2026-08-26
**Grill write-back:** plan.md ✓ (`## Decisions locked` bullets 2–5, `## Out of scope` bullets 1 and 3) · briefs: 01, 02, 03 (scope narrowed by the answers before first write) · taskman: n/a — repo has no `.taskman.toml`

Grill was run as one batched checkpoint in the origin chat rather than four round-trips, at the operator's explicit "ready then go" instruction. Four questions, all answered, all written back before any brief was written:
1. `--copy` false-failure fix → **status reads disk** (rejected: flag persists to config; rejected: docs-only) → shaped lane B's Signatures + Do NOT.
2. Port `peer-session-*.py`? → **no, they are registered nowhere** → removed a lane; recorded in `## Out of scope`.
3. Back-port `guard-destructive` to dotfiles-ai? → **yes, foreground lane** → created lane C, scoped to one file.
4. Git close-out → **commit and push** → Integrate publishes.

## Conflicts check
No two same-wave lanes share a file.
- Wave 1: A owns `hooks/stamp-tracker.py` + `hooks/tests/`; B owns `bin/ai-sync` + the two `HOW-TO-USE` files. Disjoint — no shared path, and neither owns a directory that is a prefix of the other's.
- Wave 2: C writes only outside the repo; Z writes only to scratch. Disjoint.
- A reads `~/Desktop/dotfiles-ai/hooks/*` read-only; C writes one file there. Different waves, and A's brief forbids writing there — no collision.
- Cross-plan: `docs/plans/INDEX.md` has one other row, `work-pc-readiness`, status `shipped`. No active run to overlap with.
**Action report:** [`../action-report.md`](../action-report.md)
