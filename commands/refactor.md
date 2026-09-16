Improve structure without changing observable behavior. **Iron rule: structure changes, behavior does not.**

## Flow

1. Baseline: the project's test command is **green** before you edit structure. If the area has no tests, write **characterization tests** first — pin current behavior, warts included.
2. State boundaries in plain language: what improves, what is untouched, and the sentence **"no observable behavior change."**
3. **Forbidden:** mixing a behavior change or feature into the same pass. **Forbidden:** editing test expectations only to "make the refactor green" — that is a feature, not a refactor.
4. Use the **`tdd`** skill when you need a safety net; do not paste the whole tdd skill here.
5. Perf-sensitive refactors: **`/recover R-12`** or **`complexity-audit`** before guessing.
6. If you drifted off the plan or briefs, **`/recover R-07`** (deviation list + stop — do not revert files from this command).
7. Multi-file or cross-cutting refactors: **`/grill-with-docs`** then **`/mow`** when the plan says so.
