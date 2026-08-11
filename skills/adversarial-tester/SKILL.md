---
name: adversarial-tester
description: Write tests that hunt bugs instead of chasing coverage. Runs three attacks on a named module: property-based tests (Hypothesis) for invariants, mutation testing (mutmut) to prove the suite catches injected bugs, and a hostile-input/boundary sweep. Use when the user wants "challenging tests", "test the tests", mutation testing, property-based testing, or doubts that green tests would actually catch a regression. Requires a scoped target — refuses whole-repo runs.
---

# Adversarial Tester

Coverage measures which lines ran, not whether anything would fail if the logic broke. This skill attacks that gap: it makes the test suite **prove** it can catch bugs, using tools whose feedback is objective — a surviving mutant is a fact, not an opinion.

**Verdict vocabulary:** every finding ends as one of `KILLED` (test now catches it), `BUG` (real defect found in product code), `EQUIVALENT` (mutant can't matter — documented), `DEFERRED` (filed to tracker with reason).

---

## 0. Scope gate (refuse before running)

Require a **named target**: a module, package, or small set of files (e.g. `workouts/stats.py`, `taskman/plan.py`). Refuse whole-repo mutation runs — they take hours and drown signal in noise.

Best targets are **pure-ish logic**: math, aggregation, parsing, state machines, date handling. Poor targets: thin views, templates, glue code, generated code. If the user names a poor target, say so and suggest the logic underneath it.

Also establish:
- **Test conventions** — read the project's existing tests first (runner, fixtures, factories, naming, assertion style). New tests must look native.
- **Dependencies** — check `hypothesis` and `mutmut` are importable in the project venv. If missing, ask before adding them to dev requirements (never to production deps).
- **Timebox** — default ~30 min of tool runtime; say what was skipped if it's hit.

## 1. Baseline

Run the target's existing tests. All green is the required starting state — adversarial work on a red suite just re-finds known breakage. Note (don't chase) current line coverage for the target; it's context for the report, not the goal.

## 2. Attack: properties (Hypothesis)

Identify **invariants** of the target — statements that must hold for *all* valid inputs, not just the examples in existing tests:

| Invariant family | Example |
|---|---|
| Bounds / signs | total volume is never negative; a percentage stays in [0,100] |
| Monotonicity | adding a set never decreases weekly volume |
| Conservation | sum of per-day stats equals the period total |
| Round-trip | parse(format(x)) == x |
| Idempotence | recomputing targets twice equals once |
| Invariance | result unchanged by input order when order shouldn't matter |

Write Hypothesis tests for the strongest 3–6. Rules:
- Test the invariant, **never a mirror of the implementation** (re-deriving the answer with the same algorithm proves nothing).
- Constrain strategies to *valid* domain inputs; hostile/invalid inputs belong to Attack 4.
- Keep generated cases fast; mark anything slow with the project's slow-test convention.
- When Hypothesis finds a counterexample, minimize it, then decide: test wrong (fix the test) or code wrong (**BUG** — see Rules of engagement).

## 3. Attack: mutation testing (mutmut)

1. Scope mutmut to the target only (e.g. `[tool.mutmut]` in `pyproject.toml`: `paths_to_mutate`, `tests_dir` — check the installed version's config format). If the project file must change, keep the diff minimal and revert scoping-only changes at the end unless the user wants them kept.
2. Run, then list survivors. Every surviving mutant = a proven hole: that exact code change would ship past the suite.
3. Triage each survivor:
   - **Killable** → write the test that kills it (the mutant tells you exactly what behavior is unpinned). Re-run to confirm `KILLED`.
   - **Equivalent** (mutant provably can't change observable behavior) → document as `EQUIVALENT` with one line of why. Be skeptical — most "equivalent" claims are lazy triage.
   - **Dead / unreachable code** → report it; do not delete (that's the user's call).
4. Loop kill → re-run until survivors are only documented equivalents, or the timebox hits (remainder → `DEFERRED`, filed to the tracker).

## 4. Attack: hostile inputs & boundaries

A targeted sweep the generators may miss — pick what applies to the domain:

- Empty / zero / singleton collections; None where a value is assumed
- Negative, huge, float-edge (NaN, inf, 0.1+0.2) numbers
- Unicode, whitespace-only, absurdly long strings
- Duplicates; out-of-order sequences; equal timestamps
- Timezone/DST edges; end-of-month/year dates
- Concurrency where the domain has races (double-submit, two sessions completing the same entity) — use real transactions/threads only when the project already has that test style; otherwise pin the guard logic directly

Each case becomes a normal example test (not Hypothesis) with a name that states the scenario.

## 5. Verify the new tests can fail

A test that can't fail is decoration. For each new test, its killing power must be demonstrated by at least one of: it kills a specific mutant (Attack 3 gives this for free), it failed against the pre-fix code (bug-derived tests), or you briefly broke the target logic and watched it fail. State which, in the report.

## Rules of engagement

- **Never weaken or delete an existing test** to make anything pass.
- **Never "fix" product code silently.** A real defect found is a **BUG**: report it with a minimal reproducing test. If the user wants it fixed now, the failing test lands first (red → green). Otherwise mark the test with the project's expected-failure convention and file it.
- New tests match project conventions — a reviewer shouldn't be able to tell they came from a different author.
- Scoped-tool config changes are temporary unless the user keeps them.
- If the repo has taskman (`.taskman.toml`), file `DEFERRED` items and `BUG`s as tasks (tag `adversarial`), and record the run: `capture add --kind qa --summary "<target>: X killed / Y equivalent / Z bugs"`.

## Report format

```markdown
# Adversarial test report — <target>

**Baseline:** N existing tests green · coverage <x>% (context only)
**Verdict:** <suite now proves its bugs are caught / holes remain — see DEFERRED>

## Bugs found (in product code)
- <BUG: one line + reproducing test path>  (or "None.")

## Mutation results
before → after: <survived S₀ → S₁> · killed by new tests: K · equivalent (documented): E · deferred: D

## Invariants now pinned
- <invariant → test name>

## Hostile-input cases added
- <scenario → test name>

## Tests added
<count> in <files> — each verified able to fail (see §5)

## Deferred / filed
- <taskman ids or "none">
```
