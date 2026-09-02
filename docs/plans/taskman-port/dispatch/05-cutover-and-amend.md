# cutover-and-amend: migrate both live boards, mirror the tree, amend the guarantees

**Role:** shell   **Wave:** 3   **AFK:** no   **Background:** no

**Decisions / Specs (pointers):** `-` — board-less repo; working decisions d-p3/d-p5/**d-p10**
in `docs/plans/taskman-port/plan.md` §Decisions locked, restated below.

> Foreground lane. The orchestrator runs this with the operator watching — it writes into
> two other repos (`~/Desktop/dev`, `~/Desktop/project-b`), a second tree
> (`~/Desktop/dotfiles-ai`), and a published artifact. Nothing here is backgroundable.

## Goal

Both live boards run on committed `board/` directories through the already-on-PATH
`taskman` command; dotfiles-ai's mirrored `taskman/` is in lockstep with ai-wow's ported
one and its drift guards know every new file; I10, the README Requirements, and the
work-PC artifact say what is now true; a CI push proves the whole thing on both runners.

## Context & decisions (only what this todo needs)

- **The live `taskman` is dotfiles-ai's venv** (`~/.zshrc:24` →
  `~/Desktop/dotfiles-ai/taskman/.venv/bin`). Until the mirror step lands and that venv is
  rebuilt, users still run the Postgres CLI — which is why migration must be re-run fresh
  here (wave-2 testing wrote no live board), and why this lane is last.
- **Boards to migrate (plan d-p3, one-way):** slug `project-a` → `~/Desktop/dev/board/`; slug
  `project-b` → `~/Desktop/project-b/board/`. Credentials come from each repo's own
  `.env`/`.env.local` (the old dotenv behavior — read the file yourself; the ported CLI no
  longer loads it). Postgres data stays untouched afterwards as archive: no DROP, no
  DELETE, ever.
- **Mirror (plan d-p5):** `taskman/` is a mirrored subtree — 39 paths classified `match`
  in dotfiles-ai's `bin/tests/tree-drift.json`, a second checker at
  `taskman/taskman/mow/check_drift.py`, and **neither guard can see a one-tree-only
  directory** (measured: `eventlog/` is 7 files here, 0 there). The mirror step is
  therefore explicit: copy changed/new files, delete the removed ones there too
  (models.py, db.py, alembic/), add every new path (`eventlog/*`, `pgexport.py`, new
  tests) to `tree-drift.json` as `match` rows, then run dotfiles-ai's own drift test and
  `uv sync` its `taskman/.venv` so the console script rebuilds against the trimmed deps.
- **Guarantee amendments (locked in the spike plan: "in the change that lands the port"):**
  - `HOW-TO-USE.agent.md` I10 ("taskman requires Postgres (`ARRAY`, `JSONB`) — Never
    propose SQLite") → the new invariant: the board is a committed event log under
    `board/`; never propose a database.
  - `README.md` Requirements ("Board — Postgres (the schema uses `ARRAY` and `JSONB`...")
    → Python 3 and git, full stop.
  - The published artifact **"ai-wow on the Work PC"** still says *"a dbless replacement
    has been prototyped but not landed"* — update that sentence via the Artifact tool
    (`action: "list"` to find it, publish with its `url`), with the operator's go-ahead.
  - L05 sweep: grep ai-wow **and** dotfiles-ai for `Postgres`, `psql`, `db upgrade`,
    `init-db`, `DATABASE_URL`, `alembic` across docs/skills/templates; every hit is
    amended, justified as still-true, or listed in the report. (`skills/bs/SKILL.md` and
    `skills/grill-with-docs/SKILL.md` were taskman-prefix offenders once already —
    session report 2026-09-01, addendum 1.)
- **Smoke on real boards, from each repo's cwd:** `taskman board`, `task show` on a known
  id, one `task claim`/`release` round-trip on a throwaway task, `decision list`,
  `requirement list --feature <known>`, `wrap gate` dry paths. Compare `board` output row
  counts with the exporter's printed counts and with pre-migration `psql` counts.
- **Committing the boards:** each consuming repo commits its own `board/` (explicit paths
  only). **project-a/project-b repos may have peer sessions or auto-hooks — check
  `git status` there first** and follow the shared-checkout rules; the auto-push hazard is
  named in the spike plan (a board that travels with a repo inherits its push behavior).
- **Quiesced cutover (plan d-p10, grill Q1 — the operator's zero-loss condition):**
  1. Confirm no agent session is working project-a or project-b (`list_sessions` cwd check + ask the
     operator out loud); the freeze holds until the venv flip lands.
  2. Rehearsal export + `--verify` per board (zero diffs required) → smoke locally against
     ai-wow's tree.
  3. Mirror to dotfiles-ai, rebuild its venv — then **delete the rehearsal boards, re-export
     fresh, and run `--verify` again after that final export**. A Postgres write that landed
     mid-session is caught here; zero diffs on the *final* export is the gate that lets the
     flip stand.
  4. Smoke via the PATH command → amend docs → push ai-wow → confirm CI matrix green (both
     legs, converted suite included) → commit boards in consuming repos → lift the freeze.
- **Order matters:** the sequence above is the order — verify always runs *after* the export
  it certifies, and the final export happens after the venv rebuild, not before.

## Files in scope

- `~/Desktop/dev/board/` (new, committed there) · `~/Desktop/project-b/board/` (same)
- `~/Desktop/dotfiles-ai/taskman/**` (mirror), `~/Desktop/dotfiles-ai/bin/tests/tree-drift.json`
- `HOW-TO-USE.agent.md` (I10 row), `README.md` (Requirements), any doc/skill hit by the L05 sweep
- `artifact:ai-wow-on-the-work-pc` — the published "ai-wow on the Work PC" page, updated via its existing URL
- `docs/plans/taskman-port/` (this run's records)

## Depends on

- 03-pg-exporter, 04-cli-wiring (all of wave 2, gate passed)

## Do NOT

- No `DROP`, `DELETE`, `TRUNCATE`, or schema change against either Postgres database —
  one-way means the source stays intact (d-p3).
- Do not push dotfiles-ai or the consuming repos without the operator's explicit go-ahead
  in the moment (their push hooks and redaction gates are theirs).
- Do not edit dotfiles-ai's `taskman/` files independently — every byte comes from ai-wow's
  tree (that is what lockstep means); divergence goes through ai-wow first.
- Do not "fix" pre-existing dotfiles-ai drift beyond the taskman mirror — out of scope.
- Do not delete or rewrite the old `.env` DATABASE_URL lines in project-a/project-b — note them as
  now-unused in the report; removal is the owner's call.

## Acceptance check

- Both boards SHALL pass the zero-loss gate (d-p10): GIVEN the **final** export of each
  board (the one re-run after the venv rebuild, inside the quiesced window) WHEN
  `pgexport --verify` runs THEN it exits 0 with zero field-level diffs across every entity
  — this replaces counts+spot-checks as the blocking check; counts remain as progress
  output, and the three narrative spot-checks (a claimed task, a task with deps + tags, a
  decision with an owner task) remain as human-readable evidence in the report.
- The freeze SHALL be real: the report records when the window opened, that no project-a/project-b
  session was live during it (how checked), and that verify's timestamp postdates the final
  export's.
- The PATH command SHALL work from both repos: GIVEN a fresh shell WHEN `taskman board`
  runs from `~/Desktop/dev` and from `~/Desktop/project-b` THEN both render
  their migrated boards with no database running.
- The mirror SHALL be provably in lockstep: dotfiles-ai's `test_tree_drift` and
  `python -m taskman.mow.check_drift` both exit 0, with the new files classified.
- The board SHALL carry no absolute path: `grep -rn "/Users/" board/` in both repos → zero
  matches.
- CI SHALL be green on both legs on the port push (converted pytest suite included), links
  recorded in the action report.
- The guarantees SHALL tell the truth: the L05 grep sweep output is in the report with
  every hit dispositioned; I10's row and README Requirements read dbless.

## QA contract

- Migration evidence: `psql` count queries + exporter count output + post-replay counts,
  pasted side by side.
- Smoke transcript for each board (commands + output).
- Both drift guards' exit statuses, from dotfiles-ai's own checkout (L30: run `git -C` /
  the guard *there*, not inferred from here).
- Sweep evidence per L05, and per L47: test conditions directly, never through a pipe that
  eats the exit status.

## Toolkit

- none beyond the repo's own guards (`test_tree_drift`, `check_drift`) and `psql`.

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: <d-p3/d-p5/d-p10: how, file:line — or "none pointed">
