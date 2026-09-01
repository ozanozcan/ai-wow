# taskman-no-db — a board with no database

**Stem:** `taskman-no-db`
**Created:** 2026-09-01
**Origin brainstorm:** `dotfiles-ai/docs/brainstorms/taskman-no-db.md` (verdict: pursue, shape C3, 2026-08-12)
**Sibling stem:** `publish-hygiene` (running in parallel — owns `hooks/`, `bin/ai-sync`, `.gitignore`, `HOW-TO-USE.human.md`)

## Goal

The board runs with no database server and no database file — plain text in git, readable
by an agent with no CLI and no runtime. Distribution is the driver: `git clone` instead of
"install Python, install Postgres, run migrations".


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

## Decisions locked

- **Dbless — shape C3 (append-only event log), not B (SQLite).** (operator, 2026-09-01)
  Reopened B vs C3 and closed it on C3.

  The weak form of the argument — "SQLite is another database" — does not carry on its own:
  `sqlite3` is Python stdlib, so there is nothing to install and no server to run, and the
  adoption barrier this whole effort exists to remove does not apply to it.

  What decides it, in order of weight:
  1. **An agent with no CLI and no runtime can read a text log.** SQLite is opaque without a
     client. This is the capability that keeps working if a restricted machine turns out to
     restrict more than expected, and B cannot buy it at any price.
  2. **No migration tree.** C3 deletes the alembic surface outright — 9 revisions,
     `db upgrade`, revision stamping, `warn_if_behind`. B keeps every bit of it.
  3. **Reviewable in a PR, mergeable as text.** A SQLite file in git is a binary blob:
     undiffable, unreviewable, unresolvable on conflict.

  **B is retained as the documented fallback** if the spike shows id allocation or `claim`
  cannot be made trustworthy without a transaction. Fallback, not plan.

- **The board is committed, in the consuming repo, at a top-level `board/`.** (operator, 2026-09-01)
  Not gitignored, not a sibling store. Every argument that beat B — reviewable in a PR,
  union-mergeable, readable by a CLI-less agent — is an argument about *git*. Gitignoring the
  board or moving it outside the repo pays C3's full implementation cost and keeps none of its
  winnings, at which point B was the better buy. Committed is the only option under which the
  shape decision above still holds.

  Two consequences this creates, named rather than discovered:
  - **Auto-push hazard.** A board that travels with a repo inherits that repo's push behaviour.
    `bin/ai-sync` auto-commits its managed categories, and a board in a repo with an auto-push
    hook publishes work notes on a timer. This is the risk `ai-sync-push-guard` was raised for.
  - **Path relativization is load-bearing, not hygiene.** A committed board carrying absolute
    paths is wrong on every machine but the one that wrote it.

- **Concurrency: `O_EXCL` lockfile, proven by a cross-platform CI matrix.** (operator, 2026-09-01)

  What `claim` depends on today is a **compare-and-swap**: `UPDATE ... WHERE claimed_by IS NULL`
  plus `rowcount` is a test-and-set in one statement (`taskman/taskman/cli.py:740`), and its
  atomicity is the database's entirely. Invariant I3 (same-wave lanes own disjoint file sets)
  leans on that being trustworthy. C3 must rebuild it from nothing.

  - **Primitive: `O_EXCL` lockfile** (`open(path, "x")`) — atomic on both POSIX and Windows, no
    third-party dependency, and it guards id allocation and `claim` with one mechanism.
    **Rejected: `fcntl.flock`** — the origin brainstorm's lead option, and POSIX-only. It does
    not exist on Windows Python, and Git Bash does not change that (still native Windows
    CPython). It is non-portable in precisely the environment this work exists to serve.
  - **Watch `O_APPEND`.** It is not atomic on Windows the way it is on POSIX under `PIPE_BUF`,
    so "just append, the log is the total order" can interleave under concurrent writers on the
    target platform. The spike must not assume it.
  - **Acceptance is a repeatable concurrent test**, not a manual run: two processes, N contested
    attempts on one task, exactly one winner, no id collision, log parses cleanly afterwards.
  - **Proof runs on Windows**, via a CI matrix rather than a borrowed laptop. A POSIX-only green
    means nothing here; the precedent is already burned into this repo, where a `HOME=` sandbox
    did nothing on Windows because `Path.home()` reads `USERPROFILE` there. A guard is proven by
    firing it in the environment it exists for.

  **Consequence — CI does not exist yet.** There is no `.github/workflows` and no CI config of
  any kind in this repo, though `origin` is a GitHub remote. This decision creates that
  infrastructure from zero. It is worth more than this stem: the repo's test scripts currently
  run only from a per-clone `pre-push` hook that a fresh clone does not have enabled.

- **This run is the spike, not the port.** (operator, 2026-09-01) `Task` entity only, behind the
  existing CLI, proving replay + `O_EXCL` id allocation + `O_EXCL` claim under two concurrent
  processes. No other entity is ported, and the two live boards are not migrated.

  The right-size test settles it: "prove a dbless store works **and also** port six entities
  **and also** migrate two live boards **and also** build CI from zero" is three plans wearing
  one stem. And the ordering is not arbitrary — if `claim` and ids cannot be made trustworthy
  without a transaction, every other line of the port is wasted work, and the answer is the
  documented fallback to B.

  Provisional lanes: **A** CI matrix (both runners, wired to the tests that already exist) ->
  **B** event-log store for `Task` -> **Z** the contested-concurrency suite green on both
  runners. A comes first because under the cross-platform decision above, "proven on Windows"
  *is* the CI matrix; without it lane Z has no way to meet its acceptance.

- **The spike amends no shipped guarantee.** Invariant I10 (`HOW-TO-USE.agent.md:56`) and
  `README.md:161` stay exactly as they are. The origin brainstorm says to amend I10 "in the same
  change" — that means the change that *lands* the port, not the spike that proves it possible.
  Amending a shipped guarantee on the strength of a spike is how a repo starts lying about
  itself, which is what the sibling stem is next door fixing.

  **Consequence: cross-plan overlap with `publish-hygiene` is zero.** This run needs neither
  `README.md`, nor `HOW-TO-USE.agent.md`, nor `HOW-TO-USE.human.md` — the file that stem flagged
  as the likely genuine collision. The two stems can run fully in parallel rather than sequentially.

- **Absolute paths must be relativized at write time.** Measured, not assumed:
  `AgentSession.transcript_path` stores `str(transcript)` verbatim (`taskman/taskman/metrics.py:250`)
  with no relativization, unlike `source_ref`, whose relative format is locked at
  `taskman/taskman/models.py:36`. An absolute path from one machine is meaningless on another,
  so this is a portability defect before it is a privacy one — and a text board commits it.


## Living-spec requirements (drafted)

No board in this repo, so these live here rather than in taskman. Lift them into brief
`## Acceptance check` sections at plan time.

- **Exclusive claim** — The system SHALL grant a task claim to at most one agent, with no
  database present.
  *Scenario:* `contested claim` | GIVEN task #N is unclaimed | WHEN two processes claim it
  concurrently | THEN exactly one exits 0 and the other exits non-zero naming the existing claimant.

- **Collision-free ids** — The system SHALL never issue the same entity id twice.
  *Scenario:* `concurrent creates` | GIVEN an empty board | WHEN two processes each add N tasks
  concurrently | THEN 2N distinct ids exist and the log parses cleanly.

- **Cross-platform proof** — The concurrency suite SHALL run on both POSIX and Windows.
  *Scenario:* `matrix` | GIVEN a push to the default branch | WHEN CI runs | THEN the claim and
  id tests execute on both runners, and a failure on either blocks.

## Not yet specified

*Sharpness test: can you state the question precisely now — **not** answer it now? Sharp -> a `kind:decision` board row. Not sharp -> a line here.*

- **Sharp, but unbookable — this repo has no board.** Each of these is precisely stateable now
  and would be a `kind:decision` row if a board existed; they are recorded here so they are not
  lost, and they belong to the **port** run, not the spike:
  - What is the event record shape, and how does replay handle an event version it does not
    recognise?
  - Compaction policy for the log — never, on demand, or at a size threshold?
  - How do the two existing Postgres boards migrate, and is the migration one-way?
- **Still fog.** Personal board or squad board. The origin brainstorm defers this behind
  distribution, and a squad board would reopen shape A.

## Out of scope

*Scope, not sharpness. Never graduates — returns only if this plan's goal is redrawn, and then as a fresh stem.*

- **The single self-contained board page** — split out as its own stem `board-single-page` by
  the origin brainstorm; orthogonal to storage and independently valuable.
- **Squad-shared Postgres (shape A)** — does not serve the distribution thesis at all, and puts
  IT lead time on the critical path.
- **Board-less working (shape E)** — rejected in the origin brainstorm: it forfeits the
  token/usage analysis, which is already built and is the capability most likely to land with
  the intended audience.
