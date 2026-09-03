# Action report — taskman-port (land the dbless board)

**Date:** 2026-09-03
**Project slug:** `taskman-port` (repo is board-less; slug is the stem)
**Plan:** [`plan.md`](plan.md)
**Dispatch:** [`dispatch/INDEX.md`](dispatch/INDEX.md)
**Predecessor:** [`../taskman-no-db/action-report.md`](../taskman-no-db/action-report.md)
**CI:** https://github.com/ozanozcan/ai-wow/actions/runs/33741328650 (ubuntu-latest + windows-latest, both green, 210 pytest)
**ai-wow HEAD:** `908c13c`

---

## Outcome

| Item | Status |
|---|---|
| Full-board event-log store + fail-closed replay | shipped |
| Home-relative transcript (and notes/brief/`source_ref`) paths | shipped |
| One-way `pgexport` + `--verify` zero-diff gate | shipped |
| CLI on the store; `db.py` / `models.py` / alembic deleted | shipped |
| Converted pytest suite in the CI matrix on both runners | shipped — 210 tests; Windows TEMP-symlink case fixed in `908c13c` |
| Both live boards on committed `board/`, ids preserved | shipped and pushed (`f31c66e`, `551604a`) |
| dotfiles-ai mirror + drift guards + PATH venv | shipped and pushed (`98be0b7` + hook canary `7b5c3ea` + lockstep `5a20c2a`) |
| I10 + README Requirements amended dbless | shipped (`4b9bfb8`, `e51a53b`) |
| Work-PC published URL rewritten | **not rewritten** — see Open / deferred. Source HTML patched on disk. |

---

## Wave results

**Wave 1 (parallel)** — store + portable paths. Gate: 8-angle review, 7 criticals fixed test-first, residual closed. Suites green (store / bootstrap / concurrency / metrics).

**Wave 2 (parallel)** — exporter + CLI rewire. Gate: 6 criticals fixed foreground. 209 pytest at that merge; inventory later corrected to 210. DB layer deleted.

**Wave 3 (foreground, this chat's close)** — freeze, final `--verify` 0 diffs both boards, PATH smoke, mirror, I10/README, push ai-wow, CI both runners, board commits pushed, df pushed. Work-PC claude.ai URL not writable from this runtime.

---

## Decisions locked

d-p1…d-p10 held as planned. Nothing dropped or weakened to get CI green. Postgres left as archive (d-p3). Compaction still `# debt:`. Shape C3; SQLite still retired.

---

## Open / deferred

1. **Work-PC published page.** The plan named the claude.ai artifact "ai-wow on the Work PC" (`https://claude.ai/code/artifact/f760f524-f28a-41c2-b099-250fafe66020` and the Turkish twin). This runtime has no Artifact tool; unsigned fetch is 404. The source HTML that last published those URLs was patched on disk (venv/board copy no longer claims Postgres; "prototyped but not landed" removed). Republish from Claude Code if those URLs still matter.
2. **When (if ever) the old Postgres databases are dropped** — parked at plan time (d-p3). `.env` `DATABASE_URL` lines left in the consuming repos.
3. **dotfiles-ai CI of its own** — still fog, as planned.
4. **This clone's `core.worktree`** points the main `.git/config` at a linked sanitization worktree. Not a port defect; it made pre-push run in the wrong tree until the push was aimed at the real checkout. Do not "fix" git config from an agent session.

---

## Verify

| Check | Result |
|---|---|
| Final `pgexport --verify` both boards | 0 field-level diffs (d-p10) |
| PATH `taskman` smoke from both consuming repos | board / show / claim-release / decision / requirement / wrapup gate |
| `test_tree_drift` + source-only `check_drift` | exit 0 after lockstep `5a20c2a` |
| CI `33741328650` | ubuntu 32s green; windows 2m15s green including `pytest taskman/tests` |
| I10 | "The board is a committed event log under `board/`" |
| README Requirements | Core = Python 3 and git; Board = optional `board/` |
| L05 live-doc sweep this close | one leftover in `HOW-TO-USE.human.md` ("sharing one Postgres") amended this wrap-up |

**Board sync:** n/a — this repo is board-less by decision (no `.taskman.toml` at the harness root).

**P3 post-build:** no `docs/agents/protocols.md` in this repo, so the default applied. `test-coverage` — the converted suite is the coverage; CI collected 210. `adversarial-tester` — ran inside wave 2 lanes, not re-run at close-out. `imprint` — n/a, no UI.

**Ship-check:** done 2026-09-03 · plan sha256:9dcaf5b5 · L1 1 critical · L2 0 critical · L3 0 critical

**Ship-check waivers:** L1 work-PC claude.ai artifact URL not rewritten — Cursor has no Artifact tool and the unsigned URL 404s, so the source HTML was patched on disk instead, and I10 plus README already match

---

## Appendix — lane D test-conversion ledger (backfilled)

> **Provenance: backfilled 2026-09-03 from the session transcript. This was NOT
> recorded at the wave gate.** The per-lane `dispatch/verification/<brief>` rule
> (`check_verification`, commit `80e4931`) landed *after* this run shipped, so no
> stem in this repo has a `verification/` directory and this run cannot re-pass its
> own close-out gate. That red is accurate and deliberately left standing — the
> gate asserts evidence was written *before* the gate ran, and a backfilled file
> would make it green without the property it asserts. This appendix preserves the
> audit content without faking that.
>
> Below is lane D's own reported ledger, transcribed verbatim in substance. The
> file-level claims (2 deletions absent, 4 new files present, 17 survivors present)
> were re-verified against the tree at backfill time; the per-row rationales are the
> lane's account, not an independent re-audit. Lane A–C verification blocks, and
> lane D's fuller command/red-evidence lines, remain only in the session transcript
> under `~/.claude/projects/`. Lane Z ran in a separate window and never reported here.

Why it is worth keeping: this is the audit trail for "did the SQLAlchemy→event-log
rewire silently drop test coverage?" Every deletion below has a named reason.

| # | File | Disposition |
|---|---|---|
| 1 | `test_capture_task_link.py` | converted — assertions via `store.state` |
| 2 | `test_claim_budget_ancestry.py` | converted — `claimed_at` asserted as a board field |
| 3 | `test_db_upgrade.py` | **deleted** — subject (alembic revisions, `warn_if_behind`) has no referent; replacement guard asserted CLI-level in new `test_init_and_replay_refusal.py` (future-`v` event → refusal naming the line) |
| 4 | `test_decision_show.py` | converted |
| 5 | `test_decision_tags.py` | converted; `test_decision_add_project_workflow_override` **deleted** — `--project` / workflow project removed by d-p6 |
| 6 | `test_matching.py` | untouched (already DB-free) |
| 7 | `test_metrics_paths.py` | untouched (lane B's; now CI-reachable) |
| 8 | `test_mow_closeout.py` | untouched |
| 9 | `test_mow_hydrate_specs_parse.py` | converted — `resolve_entries` tests now state-dict based; the two cross-project-scoping tests **replaced** by plain resolve + not-found tests: project scoping has no referent on a one-board repo (d-p6) |
| 10 | `test_mow_plan_import.py` | untouched |
| 11 | `test_mow_preflight.py` | untouched (always injects `decisions=`) |
| 12 | `test_mow_ship_check.py` | untouched |
| 13 | `test_plan_mark_shipped.py` | converted |
| 14 | `test_recommend_next.py` | converted — stale timestamp set via `store.update` instead of SQL UPDATE |
| 15 | `test_schema_cli_footguns.py` | converted; `test_decision_move_creates_workflow_project` + `test_project_override_does_not_auto_create_typos` **deleted** (d-p6: Project table/override gone); `test_capture_list_all_projects_honors_task_filter` → `test_capture_list_honors_task_filter` (flag removed, surviving behavior kept); pbi-remove assertions now via reader invisibility + reparent refusal (soft delete) |
| 16 | `test_task_set.py` | converted |
| 17 | `test_taskman_recommend_next.py` | **deleted** — verbatim duplicate of `test_recommend_next.py`; its only delta was throwaway-DB cleanup against slug `demo`, which has no referent |
| 18 | `test_toolkit.py` | untouched |
| 19 | `test_wrapup_gate.py` | converted — tasks' briefs set via `store.update`, `Task(...)` constructions → dicts |

**Files added by lane D:** `test_init_and_replay_refusal.py`, `test_claim_race.py`
(subprocess-level claim CAS race), `test_session_events.py`, `test_recommend_scoring.py`.

**Net:** 2 test files deleted (one obsolete subject, one exact duplicate), 4 added,
4 individual test functions deleted — each tied to a surface d-p6 removed
(Project/Tag tables, `--project`, `--all-projects`, `decision move`). No assertion
was blunted to get green; the wave-2 gate reviewed this diff and its 6 criticals
were fixed before the flip.
