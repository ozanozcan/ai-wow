# Harness protocols — QA around grill → plan → dispatch → taskman

Canonical spec for the automated quality gates wrapped around the build loop.
The `mow` skill reads this file (P1/P2 tables) when planning (`/mow plan`) and dispatching (`/mow go`) in this repo.

**Created:** <date> · **Companion docs:** <links to this repo's own agent-workspace docs, if any — e.g. `docs/workflow/work-loop.md`>

## Principles

1. **Cheapest layer that can enforce it.** Deterministic checks (tests, lint, types, perf assertions) → hooks/CI. Judgment checks (review, security, design) → subagents. Cadence checks (CVEs, drift, board health) → scheduled routines.
2. **Builder ≠ reviewer.** A lane runs its own deterministic checks but never certifies its own quality; review happens in a separate context on the diff.
3. **Evidence or it didn't happen.** Nothing is marked done in taskman without a verification record.
4. **Grill answers live on disk.** `/mow ready` locks must land in `plan.md` + dispatch briefs (and taskman `Task.brief` via re-import) before `/mow go`. Chat-only answers are invisible to blind lanes.

---

## P0 — Grill write-back + preflight (at `/mow ready` and before `/mow go` wave 1)

When the ready-mode grill accepts an answer:

1. **Immediate write-back** — patch `docs/plans/<stem>/plan.md` and every affected `dispatch/NN-*.md` brief *before* the next question. When the repo has [`docs/workflow/mow-compact-template.md`](../workflow/mow-compact-template.md), align write-back with its sections (Key Decisions → locked bullets; Progress → todo statuses).
2. **INDEX evidence** — do not mark `Grill checkpoint: done` without a sibling:
   `**Grill write-back:** plan.md ✓ · briefs: … · taskman: …` (or `no changes — plan held`).
3. **Go hard gate** — `/mow go` refuses fan-out if checkpoint is `done` without write-back. Deterministic check (optional but recommended):

```bash
python scripts/mow_check_grill_writeback.py docs/plans/<stem>
```

4. **Preflight composes the above.** Before wave 1, `/mow go` runs:

```bash
python scripts/mow_preflight.py docs/plans/<stem>
```

Preflight chain: grill write-back (item 3, skipped once the stem is `shipped`) → hydrate (`scripts/mow_hydrate_specs.py`, when any lane's Decisions/Specs cell isn't `-`) → thin-brief validation → brief/INDEX drift → same-wave and cross-plan file overlap — one deterministic exit 0/1. It **subsumes** running `mow_hydrate_specs.py` standalone; do not call both.

The mow skill ready/go sections are the procedural source of truth; this P0 is the repo reminder.

**Optional (Cursor repos):** add a **MOW orchestrator — approval visibility** subsection under P0 — background subagents show native approval cards in the IDE, not chat prompts; the orchestrator must tell the operator to watch for pending cards when AFK lanes fan out.

---

## P1 — Lane QA contracts (at `/mow plan` time)

Every dispatch brief gets a `## QA contract` section derived from the todo's taskman tags / flavor. The lane must run these checks itself and report them in its final `## Verification` block.

| Tag / flavor | Contract (lane runs before reporting done) | Toolkit |
|---|---|---|
| `backend`, `service` (default for code-edit) | Scoped `<test command>` for touched modules · `<lint>` · `<typecheck>` if wired · new list endpoints paginated | `agent:<backend-reviewer>` |
| `api`, `auth` | Backend contract, plus: endpoint auth + user-scoping asserted in a test | — |
| `llm` | Backend contract, plus: lane flagged for **llm-sec-review** in the review wave (P2) · **eval regression:** if prompts, few-shots, or parser/agent logic changed, run the project's eval harness (`<eval command>`) and report pass rate before/after in the Verification block — a drop below the project's threshold is a failed contract item | `agent:llm-sec-review` |
| `bug` | **Regression test written first and failing, then the fix** (tdd skill); test name references the bug | `skill:tdd` · `skill:diagnose` |
| `ui` | Screenshot attached at the project's target viewport(s) · design-consistency pass after merge | `skill:impeccable` · `skill:imprint` · `agent:<frontend-reviewer>` |
| `perf` | Before/after evidence (query counts or timings) · an assertion added so the win can't regress silently | `skill:complexity-audit` |
| `migration` | Migration dry-run output reviewed in-brief · reversibility stated · schema change separated from data backfill | `agent:<backend-reviewer>` |
| `docs`, `chore` | No contract beyond acceptance check | — |
| `test` | — | `skill:adversarial-tester` · `skill:test-coverage` |
| `refactor` | — | `skill:improve-codebase-architecture` |

### Parallel lanes — git safety

When multiple lanes share one working tree (parallel `/mow go` without worktree isolation — see the mow skill's Runtime resolution for when Claude Code's `isolation: "worktree"` applies instead):

- Stage **explicit paths only** from each lane's **Files in scope** — never `git add -A` or `git add .`.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.
- Before any commit while parallel lanes are active, run `git status` and confirm only intended paths are staged.

**Toolkit map.** The Toolkit column is the tag → recommended-skills/agents map; `.taskman.toml [toolkit]` is its machine-readable projection, and `taskman task show <id>` renders a `toolkit:` line from a task's tags (union across tags, deduped; explicit `skill:<name>` / `agent:<name>` tags pass through verbatim). **P0 makes the listed automation hooks auto-run at the named triggers** — Toolkit is still the decompose-time hint for which tools a brief should list; an empty Toolkit is not a thin brief, but skipping a P0 trigger without n/a is a failed lane.

**Verification block (required in every lane's final message):**

```markdown
## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <screenshot/report paths, or "none">
```

The orchestrator refuses to mark a taskman task done without this block, and records it:
`taskman capture add --kind verify --summary "<task-id>: <one-line>" --source-ref <brief path>`.

---

## P2 — Review wave (at dispatch time, per wave)

After a wave's lanes report done and **before the next wave starts**, the orchestrator reviews the wave's combined diff:

| Reviewer | Trigger | Scope |
|---|---|---|
| `<stack-reviewer>` (the repo's backend reviewer agent) | any lane touched backend files | combined wave diff |
| `llm-sec-review` | any lane tagged `llm` (prompts, tools, model endpoints) | combined wave diff |
| `<frontend-reviewer>` | any lane touched frontend code | combined wave diff |

Rules:

- Reviewers run **in parallel, in isolated contexts**, on the diff — never the lane's own context.
- **Critical findings block the next wave.** Fix (new lane or orchestrator foreground) → re-review the fix.
- Warnings/suggestions → taskman tasks tagged `review-finding`, severity in title; they queue, they don't block.
- General auth/API security is covered by the stack reviewer's security section; a dedicated deep security-review pass is per-merge (P4) and periodic (P5), not per-wave.

### Scope-creep triage (ask-user-authority rubric)

Applied to every **Critical** finding before choosing "fix now" vs. "escalate to the operator" — Warnings/suggestions are unaffected and still queue per the Rules above.

1. **Reconstruct the accepted contract from the brief itself** — the lane's original Acceptance check and Do-NOT bullets, never the reviewer's language. A reviewer's finding cannot amend the contract.
2. **Classify the fix the finding implies:**
   - **In-contract fix** — genuinely necessary to satisfy the brief's own accepted Acceptance/Do-NOT, even if technically hard. Fix now, per the existing Rules above.
   - **Contract expansion** — the fix would add a new guarantee, subsystem, abstraction, threat model, compatibility surface, state machine, continuous-monitoring requirement, or generalized framework the brief never asked for. Escalate to the operator instead of auto-fixing in a new lane.
3. **Labels are evidence, not authority.** A finding labeled "correctness," "security," "fail-closed," or "required" by the reviewer is evidence about the finding — not permission to broaden the task.
4. **Escalation format (contract-expansion findings only)** — replaces a bare "Critical: fix this" note with all five:
   1. The brief's original Acceptance/Do-NOT statement or accepted intent.
   2. The proposed expansion the finding implies.
   3. The smallest fix that satisfies the accepted brief without the expansion.
   4. The concrete consequences of accepting vs. declining the expansion.
   5. A recommendation, with the reason it best serves the accepted brief.
5. **Repeated-theme rule.** If a Critical finding in the same causal theme recurs across more than one fix-and-re-review round on the same lane, escalate before another fix round — that's a signal a shaky abstraction is being patched around, not an independent new defect.
6. **The destructive/irreversible/security-sensitive override always wins**, regardless of the classification above — see the auth/API security rule in the Rules above; this rubric does not weaken, duplicate, or override it.

---

## P3 — Post-build testing (after the final build wave)

1. **Drive the affected flow** in the real app (not just the automated test suite) — the repo's own `/verify`-equivalent skill if one exists.
2. **Test-coverage pass** on modules created this batch — find untested paths while context is fresh.
3. **Adversarial pass** (if the repo has an adversarial-testing skill): mutation testing on touched modules + property tests for pure-logic code. Surviving mutants → taskman tasks tagged `adversarial`. Run per batch, not per lane.

---

## P4 — Merge gauntlet (per PR/merge)

1. CI green: `<test command>` + `<lint>` + `<typecheck>`.
2. A code-review pass (`/code-review ultra <PR#>` for large/risky merges; plain `/code-review` otherwise) — or the repo's equivalent.
3. A security-review pass when the merge touches auth surfaces or settings.
4. Babysit CI with a polling skill/loop instead of manual polling, if the repo has one.
5. Critical findings from `/code-review ultra` or `/security-review` get triaged with P2's [Scope-creep triage rubric](#p2--review-wave) before fixing.

---

## P5 — Periodic routines (`/schedule`, planned)

| Routine | Cadence | Does |
|---|---|---|
| Security sweep | Weekly | Review of the week's merge range + dependency vulnerability scan (e.g. `pip-audit`, `npm audit`) + framework security-release check → taskman tasks |
| Test health | Weekly | Full suite; flaky/slow report; coverage drift |
| Board hygiene | Weekly | taskman tasks `in_progress` too long, stale checkpoints, unharvested sessions |

Build these only after their manual versions have run once or twice and the output shape is stable. Capture each manual dry-run as a runbook in `docs/agents/routines/<name>.md` (Purpose / Commands / This run's output / Findings filed / Cadence notes) before creating any scheduled routine from it.

---

## Deliberate omissions

- **No run-tests-on-every-agent-stop hook** — P1/P2 enforce at the right granularity (lane/wave) instead; a global stop-hook fires too often and too broadly.
- **No per-wave general security review** — the stack reviewer covers auth basics per-wave; deep passes are per-merge and weekly (P4/P5).
