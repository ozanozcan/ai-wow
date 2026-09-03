# relativize-transcript-paths: stop writing machine-absolute paths into board-bound records

**Role:** code-edit   **Wave:** 1   **AFK:** yes   **Background:** yes

**Decisions / Specs (pointers):** `-` — board-less repo; the working decision is d-p9 in
`docs/plans/taskman-port/plan.md` §Decisions locked, restated below.

## Goal

`metrics.py` never emits a machine-absolute transcript path. A shared helper converts
transcript paths to home-relative `~/...` form at write time and expands them at read
time; `build_meta`'s output and everything downstream of it carry the portable form. The
defect is pinned by a regression test that fails on today's code first.

## Context & decisions (only what this todo needs)

- **The defect (measured in the spike):** `taskman/taskman/metrics.py:250` stores
  `"transcript_path": str(transcript)` verbatim into the meta dict that becomes both
  `meta.json` and the session record. On a committed board this is a portability defect
  before it is a privacy one — `~/...` is wrong on every other machine.
- **Why home-relative (plan d-p9):** transcripts live under `~/.claude/projects/...`,
  outside any repo, so repo-relative is impossible. `~`-prefixed paths survive a different
  username on the work PC. Contrast: `source_ref` is already repo-relative by locked format
  (`taskman/taskman/models.py:36`) — leave that convention alone; it is not this defect.
- **The helper is a seam:** lane C (the Postgres exporter, wave 2) will call it to
  relativize the `transcript_path` column of existing session rows during migration. Export
  it from `metrics.py` with the exact signatures below.
- Readers to audit and fix in this file: `meta_path_for` callers are path-based and fine;
  `detect_source`/`detect_project_slug`/`session_id_from_path` operate on the `Path` before
  storage, unaffected. Check every place the *stored string* is later consumed (grep
  `transcript_path` across `taskman/`) and report — but only edit `metrics.py` and its
  test; if a consumer outside this file needs a change, write it into your Verification as
  a handoff note for lane D (which owns `cli.py`/`wrapup.py`) rather than editing it here.
- The meta.json sidecar format has existing files on disk from `session backfill`. Readers
  of old sidecars may still meet absolute paths — the expand helper must accept both forms
  (absolute in = returned as-is after `Path`), so old sidecars stay readable.

## Files in scope

- `taskman/taskman/metrics.py`
- `taskman/tests/test_metrics_paths.py` (new)

## Signatures (optional — the seam lane C consumes)

```python
# metrics.py
def portable_transcript_path(transcript: Path) -> str   # '~/.claude/...' when under home; posix separators
def expand_transcript_path(stored: str) -> Path         # inverse; absolute or '~' input both accepted
```

## Depends on

- none (wave 1)

## Do NOT

- Do not touch `models.py`'s `source_ref` format or anything that writes `source_ref` —
  locked, repo-relative, different convention, not this defect.
- Do not edit `cli.py` or `wrapup.py` (lane D owns them in wave 2) — hand findings off via
  Verification instead.
- Do not rewrite meta.json sidecars on disk or add a migration for old sidecars — readers
  tolerate the old form instead.
- Do not introduce any non-stdlib import into `metrics.py` beyond what it already has.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- Prefer **`git commit -- <paths>`** over `git add` + `git commit`; the new test file must
  be `git add`-ed by name first, then still commit with `-- <paths>`.
- **Forbidden** during parallel runs: `git stash`, `git reset --hard`, `git clean -fd`.
- Before commit while parallel lanes are active, run `git status` and confirm only intended
  paths are staged.

## Acceptance check

- `build_meta` SHALL emit no machine-absolute transcript path: GIVEN a transcript under the
  invoking user's home WHEN `build_meta` runs THEN `meta["transcript_path"]` starts with
  `~/` and contains no `/Users/` (and, on Windows, no drive letter).
- Round-trip: GIVEN a stored `~/...` string WHEN `expand_transcript_path` runs THEN the
  result equals the original absolute path; GIVEN a legacy absolute string THEN it is
  returned as that path unchanged.
- Regression-first: the new test SHALL fail against unmodified `metrics.py` (red run
  recorded in Verification) before the fix lands.
- Verify: `cd taskman && uv run pytest tests/test_metrics_paths.py` exits 0 (the test needs
  no DB; today's conftest wants a reachable local Postgres at import — it is available on
  this machine; if it isn't in your worktree environment, `uv run pytest --noconftest tests/test_metrics_paths.py` is the documented fallback).

## QA contract

- Regression test written first and failing, then the fix (tdd — this is a bug fix).
- Scoped pytest run green (command above).
- Grep evidence in Verification: every consumer of the stored `transcript_path` string
  listed, each marked fixed-here / unaffected / handoff-to-lane-D.

## Toolkit

- Invoke: `skill:tdd` (bug-fix flavor — red first).

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: <d-p9: how, file:line — or "none pointed">
