# Action report — Named work-paths (anew-harvest)

**Date:** 2026-09-16
**Project slug:** `ai-wow` (board-less)
**Plan:** [`plan.md`](plan.md)
**Dispatch:** [`dispatch/INDEX.md`](dispatch/INDEX.md)

---

## Outcome

| Item | Status | Where it landed |
|---|---|---|
| `recover` skill with R-01–R-12 index + gap ramps | shipped | `skills/recover/SKILL.md` |
| `/fix-bug`, `/refactor`, `/incident` commands | shipped | `commands/*.md` |
| Mow automation hooks for R-06 / R-07 + triage note | shipped | `skills/mow/SKILL.md` |
| Work-loop, CLAUDE routing, inventory counts | shipped | `docs/workflow/work-loop.md`, `global/CLAUDE.md`, HOW-TO-USE.*, `README.md`, `THIRD-PARTY.md` |
| Persisted R-06 counter in tracker.json at gate | deferred | prose-only per plan; llm-sec Warning — follow-up stem if mechanized |

---

## Wave results

### Wave 1 — A ‖ B ‖ C (orchestrator on shared Cursor tree)

**Lane A** — `skills/recover/SKILL.md` (recover catalog, context-trust block, no `disable-model-invocation`).

**Lane B** — three thin commands beside `/diagnose`; fix-bug 10 lines vs diagnose 71.

**Lane C** — two automation-hook rows + §2b triage clause for third failed fix round.

**Gate:** `llm-sec-review` — NEEDS WORK, 0 Critical. Applied in-run: removed false `guard-destructive` git claim (R-11), added context-trust block, R-04 uncommitted checkout discipline, aligned fix-bug ↔ R-04 wording.

### Wave 2 — Z

Inventory stamp (17 skills, 4 commands), ceremony paragraph in work-loop, proposal rule in `global/CLAUDE.md`. `python3 bin/tests/test_repo_shape.py` — 0 failures.

---

## Decisions locked

- R-06 counts orchestrator fix attempts per finding, not lane tdd cycles (unchanged from grill).
- R-08 write-back targets `docs/plans/<stem>/` only (no ANEW spec folders in skill text).
- Board-less run: no `mow_plan_import`; preflight uses `--skip-candidates` (no root `.taskman.toml`).

---

## Open / deferred

- **R-06 counter persistence** in `tracker.json` / gate records (llm-sec Warning) — convention or mechanize on a later stem.
- **R-08 operator gate** when requirement change comes from untrusted pasted text (llm-sec Suggestion) — partially covered by context-trust block.

---

## Verify

- `python3 bin/tests/test_repo_shape.py` — pass
- Wave verification files — `python -m taskman.mow.check_verification docs/plans/anew-harvest` — pass
- **P3:** test-coverage n/a (markdown procedures only); adversarial-tester n/a (no domain math modules)
- **Board sync:** n/a — no root `.taskman.toml` in ai-wow
- **Ship-check (summary):** Layer 1 — all four plan todos reflected on disk. Layer 2 — house voice, no ANEW vendoring, counts consistent. Layer 3 — n/a (no runtime). Verdict: ship with deferred counter mechanization noted above.

**Ship-check:** done 2026-09-16 · plan sha256:c09a619ae4b35493f1dfdf7b6f6b57490106224eb00307bf79991f9bc34a187d · L1 0 critical · L2 0 critical · L3 0 critical

**Ship-check waivers:** none

**Finding triage (wave 1 llm-sec):** false guard-destructive claim → (a) fixed in-run; context-trust → (b) convention in recover skill; ephemeral R-06 counter → (c) capture/defer in Outcome table
