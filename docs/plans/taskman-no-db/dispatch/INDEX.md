# Dispatch index — taskman-no-db (the spike)

Source plan: [`../plan.md`](../plan.md)
Origin brainstorm: `dotfiles-ai/docs/brainstorms/taskman-no-db.md` (verdict: pursue, shape C3)

## What we'll do

1. **Build CI from zero** — a matrix on both runners, wired to the harness tests that already
   exist but today run only from a per-clone `pre-push` hook a fresh clone does not have enabled.
2. **Write a dbless event-log store for `Task`** — append + replay, with `O_EXCL` guarding both
   id allocation and `claim`, and nothing but the standard library behind it.
3. **Prove it on Windows, not just here** — take the contested-concurrency suite green on both
   runners, fixing whatever the target platform breaks.

## What you'll have at the end

| Area | End state |
|---|---|
| Concurrency | Two processes contest one task; exactly one wins, no id ever repeats, and the log still parses. A repeatable test, not a manual run |
| Windows | That test is green on a Windows runner — the platform this effort exists for, proven rather than assumed |
| CI | Every push runs the harness tests on both platforms; a fresh clone is covered without typing `git config core.hooksPath githooks` |
| Dependencies | The store imports no third-party package, and a committed test enforces it |
| The decision | You know whether C3 is viable — or that it is not, and B is the answer, before six entities and two live boards are touched |

**In one line:** Find out whether a dbless board can be trusted under two concurrent agents on
Windows, before betting the port on it.

## Waves

- **Wave 1 (parallel, AFK):** A | B
- **Wave 2 (after wave 1, foreground):** Z

Each wave ends with a **review gate** before the next starts.

## Lanes

| Lane | Todos (in order) | PBI / Feature | Files owned | Role | Model | Review flags | AFK | Background | Decisions / Specs | Brief |
|---|---|---|---|---|---|---|---|---|---|---|
| A | ci-matrix | - / - | `.github/workflows/ci.yml` | code-edit | inherit | - | yes | yes | `-` | [01-ci-matrix.md](01-ci-matrix.md) |
| B | eventlog-store | - / - | `taskman/taskman/eventlog/**` | code-edit | fable | - | yes | yes | `-` | [02-eventlog-store.md](02-eventlog-store.md) |
| Z | windows-proof | - / - | `taskman/taskman/eventlog/**`, `docs/plans/taskman-no-db/spike-result.md` | code-edit | inherit | - | no | no | `-` | [03-windows-proof.md](03-windows-proof.md) |

`PBI / Feature` is `-` throughout: this repo is deliberately board-less, so no taskman rows exist,
no import gate runs, and no decision/requirement ids can be pointed at. The binding decisions live
in `plan.md` -> `## Decisions locked`, and each brief cites them by name.

`Model`: lane B is pinned to `fable`. Its failure mode is a concurrency race that a checklist
cannot catch and that passes on a developer machine — the "judgment a checklist cannot carry"
case. A and Z inherit.

`Review flags` are `-` throughout. No roster agent covers plain Python — `backend-reviewer` is
FastAPI-only by the `work-pc-readiness` decision, and would hand off. The wave gate still reads
every lane's `## Verification` block against its QA contract; it simply spawns no stack reviewer.

## Conflicts check

- **Same-wave (A | B):** `.github/workflows/ci.yml` vs `taskman/taskman/eventlog/**` — disjoint.
- **Cross-wave (B -> Z):** Z edits lane B's modules to fix Windows breakage. Intentional handoff,
  not an overlap — wave 1 is closed before wave 2 starts.
- **Test discovery, not enumeration:** lane A's workflow scans directories, so lane Z adds test
  files without editing lane A's file. No cross-lane edit exists.

## Cross-plan overlap — `publish-hygiene` (running in parallel)

Checked against that stem's `Files owned` on 2026-09-01. **Disjoint — parallel go is safe.**

| Their lanes own | This stem owns |
|---|---|
| `hooks/`, `bin/ai-sync`, `bin/tests/`, `skills/*/SKILL.md`, `.gitignore`, `HOW-TO-USE.human.md` | `.github/workflows/`, `taskman/taskman/eventlog/`, `docs/plans/taskman-no-db/` |

The one shared file is `docs/plans/INDEX.md` — the registry, where each stem appends its own row
by design. Not a conflict; do re-read before writing.

That stem reserved `taskman/**`, `README.md` and `HOW-TO-USE.agent.md` for this one, expecting a
storage rewrite. **This run needs none of them** — the spike amends no shipped guarantee (see
`plan.md`), so invariant I10 and `README.md:161` stay untouched until the port. That is what drops
the overlap to zero and lets both stems run concurrently rather than sequentially.

**Note:** that stem's `plan.md` calls this sibling `taskman-storage` in four places. The stem is
`taskman-no-db`. Their file, their correction to make.

**Grill checkpoint:** done 2026-09-01
**Grill write-back:** plan.md ✓ · briefs: 01-ci-matrix, 02-eventlog-store, 03-windows-proof (all
written after the grill, carrying its locked decisions) · taskman: n/a — repo is board-less, no
`.taskman.toml`, so no decision/requirement/capture ids exist
