Fix a bug with a repro-first discipline. **Iron rule: no fix before a failing reproduction** you trust (test, script, or `/diagnose` loop).

## Flow

1. If you do not have a loop yet, run **`/diagnose`** — spend effort on Phase 1 only; do not copy the full phase list into this chat.
2. With a failing signal, invoke the **`tdd`** skill: red test first, then minimal fix, suite green; keep the repro test.
3. After the fix, run the project's tests; get **independent review** of the diff (builder ≠ reviewer).
4. Small, single-file bugs do not need **`/mow`**. If the fix changes observable product behavior beyond the reported bug, say so and route to **`/grill-with-docs`** or **`/mow`** — do not silently widen scope.
5. If the fix caused a new failure on main, **`/recover R-04`** (revert-to-green order). Do not run `git revert` unless R-04's operator-approval condition is met.
6. If the loop itself is stuck (wrong ramp, fix-round limit), **`/recover`** or **`/recover R-06`**.
