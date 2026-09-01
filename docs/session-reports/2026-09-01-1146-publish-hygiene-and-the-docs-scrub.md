---
date: 2026-09-01 11:46
branch: master
slug: publish-hygiene
project: none
session_id: none — no .taskman.toml in this repo
start_sha: f866c1f
---

# Session report — scrub `docs/`, fix what a fresh clone cannot follow, ship it

## What was done

The session opened as a status question — *"where are we, I want to go public and pull to my
work PC tonight"* — and turned into a publish-readiness pass plus a full mow run.

1. **Scrubbed `docs/` and widened the gate to cover it.** 17 leak sites across 10 tracked files —
   nine absolute home paths and six employer codenames, plus three verification greps that quoted
   the codenames verbatim. Every site was rewritten to say the same thing generically rather than
   deleted, so the record survives. `SCRUBBED_DIRS` gained `docs`, and the standing comment saying
   it was deliberately excluded was replaced with the reasoning for the change, not edited away.

2. **Found and fixed a defect in that very widening.** The scan walked the working tree, so adding
   `docs/` made it reach `docs/brainstorms/` — gitignored, unpublishable — and the push gate
   blocked on a file that could never leak. It scans git-tracked files now. The flaw was invisible
   before because every other scrubbed directory is fully tracked.

3. **Wrote the missing board bootstrap.** `README.md` stated Postgres as a requirement while
   nothing documented how to stand a board up. Rehearsed end to end on a venv-less clone first —
   `uv sync` → `init-db` → board renders, suite 135/135 — then wrote it. **This first version was
   wrong; see Lessons.**

4. **Planned, grilled and ran `publish-hygiene`** — five lanes, three waves, shipped. Full detail
   in [`../plans/publish-hygiene/action-report.md`](../plans/publish-hygiene/action-report.md).

5. **Corrected two claims already published earlier the same day**, and one on the README's most
   read section. All three below.

## Files changed

`f866c1f..HEAD` carries **23 commits**, spanning this session *and* the sibling `taskman-no-db`
stem that ran in the same checkout — one branch, two sessions, so the range is not separable by
range alone. This session's are the `publish-hygiene` wave commits, the scrub, the bootstrap, the
README correction, and the gitignore/untracking pass.

| Area | What |
|---|---|
| `docs/` (10 files) | employer codenames and home paths removed |
| `bin/tests/test_repo_shape.py` | `docs` added to `SCRUBBED_DIRS`; scan switched to tracked files; new dead-path check |
| `HOW-TO-USE.human.md` | board bootstrap added, then corrected; board-less posture; drift sample; the exit-2 correction |
| `hooks/session-start-marker.py` + new `hooks/tests/test_session_start_marker.py` | gate named only when a board exists, marker still unconditional |
| `bin/ai-sync` + its suite | `copied (stale — re-run ai-sync)` for a drifted copy install |
| `skills/{wrap-up,grill-with-docs,bs,mow,checkpoint}/SKILL.md` | 29 venv prefixes removed; dead references repointed; roster claim hedged |
| `.gitignore` | `.claude/worktrees/` |
| `README.md` | the `git add -A` warning corrected |

## Wrap-up gate

**Ran at close, exit 2 — board-less path.** `taskman wrapup gate` reports
`no .taskman.toml above cwd` and exits 2, which the skill's table defines as "no session marker".
Neither condition applies; it is the misdiagnosis recorded in Open threads. With no root
`.taskman.toml`, wrap-up takes its documented board-less route: **lessons + session report only**,
no board sync, no retroactive sweep, no forward capture — there is no board to write to.

**Earlier in the session it was also blocked, deliberately.** Two of three conditions red: the evidence gate exits 2 (the
misdiagnosis recorded below, not real unattributed work), and this session is **not the sole
writer** — a second session worked the same checkout all day and `work-pc-readiness/action-report.md`
still holds its uncommitted lines. Attributing files this session does not own is exactly what that
condition prevents. Operator runs `/wrap-up`.

## Taskman sync

**n/a — no board exists to sync to.** No root `.taskman.toml`. Made an explicit, documented decision this session rather than
left as an absence.

## Lessons

**One pattern, five times: a check passed because it checked the easy case.** Worth recording as a
pattern rather than five separate slips, because no individual instance looked careless.

1. **A grep that could not match what it claimed to verify.** The acceptance said "no repo-root
   `.venv/` path survives"; the grep searched `\.venv/bin/python scripts/`, which requires
   `scripts/` immediately after and so only ever matched the combination. It passed while **29**
   bare `.venv/bin/python` lines survived. Found by ship-check, not by review. (L40)
2. **A bootstrap verified against the one case where its bug cannot show.** The documented steps
   told the reader to put a `.taskman.toml` at *their* repo root, then ran `init-db` from *this*
   repo's taskman directory — registering `taskman-tests`, not their project. It was rehearsed
   against taskman's own test project, so it printed success. Re-verified against a scratch project
   afterwards, where it failed and then passed.
3. **An exit code read through a pipe.** `EXIT=$?` after `| tail` returns tail's status. That
   produced a confident "the gate exits 0 board-less" which was published in a guide and used as
   the argument for a decision. It exits **2**. The same session applied this rule correctly to a
   different measurement an hour later, which is what makes it worth writing down. (L18)
4. **A count of a proxy rather than the thing.** `grep -c "add -A"` over a sibling repo matched the
   comment reading *"never `git add -A`"* and nearly produced a false report that a safety fix had
   not been ported. (L15/L40 again)
5. **A comparison blind to untracked files.** `git diff HEAD` cannot see a new file, so a
   merge-back safety check reported the integration branch and the working tree as differing when
   the only difference was a newly created test. Fail-closed caught it; a byte-comparison resolved
   it.

**The corollary worth keeping:** every one of these was caught by something that *ran*, never by
re-reading. Ship-check found (1). Running the bootstrap against a different project found (2).
The wrap-up safety check found (3). The pattern is not "be more careful" — it is "make the check
execute against the case you have not tried."

**A guard is proven by making it fire.** Applied four times this session and it paid every time —
the widened scrub, the gitignore rule (proven with two real lane worktrees live on disk), the
dead-path check, and the hook's marker guard. The dead-path check found a file manual analysis had
missed on its first run, and flagged a false positive on its second, which is how it got scoped
correctly. (L33)

### Routed this pass

Two new rules logged and **routed the same pass** into `global/CLAUDE.md` on the path the runtime
loads (`~/.claude/CLAUDE.md` → the dotfiles checkout), ledger row and routed edit committed together
in `217b6ce`:

- **L45 → `claude-md`** — `git commit -- <paths>` reads the working tree and ignores the index, so it
  discards a staged deletion and re-commits the file. Written in *beside* the command it caveats, in
  the Shared checkouts section, rather than in a separate list — anyone reaching for that command
  needs the caveat in the same breath.
- **L46 → `claude-md`** — running a procedure against the one input where its defect cannot appear is
  not verification. Names the shape shared by five separate misses this session.

**Deliberately not logged:** the grep-counted-a-comment miss and the exit-code-through-a-pipe miss
are recurrences of **L40** and **L18**, both already routed into `global/CLAUDE.md` and therefore
already loading. The retired `seen ×3` gate is what bumping used to feed; with routing on first
sighting, a recurrence of a loaded rule needs no row. Recorded here instead.

No `BACKLOG` or `PRUNE` signal from the ledger.

## Decisions

- **`docs/` is scrubbed and gated.** The prior standing decision — that scrubbing would falsify the
  record — does not survive publication: a reader learns the codenames either way, and the record
  survives a generic rewrite intact.
- **ai-wow stays board-less**, because a tracked `.taskman.toml` hands every cloner this repo's
  project identity pointed at their database, and because the README's "needs no database" claim
  would be undercut by making this repo's own workflow require one. Revisit if the board loses its
  database dependency.
- **`django-reviewer` stays out.** Django is not widely used at the operator's company. The fix was
  to make the references honest, not to ship the agent.
- **One way to invoke taskman: the console script on PATH.** Better than a relative venv prefix
  because project identity is resolved by walking up from the working directory — the CLI must run
  from the reader's project, and a relative prefix fights that.
- **Two stems, sequenced.** The storage refactor was split out rather than bundled: its shape was
  undecided, so its briefs would have failed the thin-brief gate, and both stems wanted the same
  two files.

## Open threads / not finished

1. **The repo is still private.** Going public is the operator's call and the one step nobody took.
2. **`/wrap-up` has not run** — blocked on sole-writer, above.
3. **`taskman wrapup gate` returns exit 2 for two unrelated conditions** — no board, and an
   unreachable database — while the wrap-up skill's table defines 2 as "no session marker". Advice
   that fits neither. Lives in `taskman/**`.
4. **`installed_mode()` can misreport an unmanaged directory as a stale copy** where nothing is
   installed and symlinks are unavailable. Bounded; the remedial advice stays correct.
5. **The scrub gate cannot read binaries.** A screenshot at the repo root turned out to hold another
   project's task ids, source filenames and review findings — invisible to a text scan even if
   committed. It was never tracked and has been removed. A rule forbidding tracked image files
   would close this with no false positives, since this repo ships none.
6. **Two sessions share this checkout, so either one's push publishes the other's commits.** This
   session's final push carried three commits from the sibling stem. Harmless while private;
   a different proposition once public.
7. **Disposable run state accumulates in `git status`** — `.activity`, `.agent-times.json`,
   `tracker.html`, `.board`. Same class as `.claude/worktrees/`, which was gitignored this session.
8. **`skills/mow/TRACKER.md` still names a reviewer this repo does not ship**, in a worked example.
   Reads as illustration rather than a roster claim.

## Post-report — same session, operator-directed

Five more things landed after the report above was first written, at the operator's direction.

- **The README was wrong about `ai-sync`.** Its `[!WARNING]` told every reader the tool commits with
  `git add -A`; `bin/ai-sync:865` says *"Path-scoped, never `git add -A`"* in its own comment, and
  `do_commit()` stages and commits by name. Stale since `ac7abe9`. The false half was the frightening
  half, on the most-read section of a repo about to go public. Corrected in `57b310c`; the accurate
  half (pushes without prompting, `{"push": false}` disables) was re-checked against the code and kept.
- **The stray screenshot was not what I said it was.** I twice reported it "checked clean of leak
  strings" — a text grep over a PNG, which establishes nothing. Looking at it showed another project's
  feature and task ids, source filenames, review findings in prose, and a personal browser tab. Never
  tracked, absent from all history, moved to the Trash. **The scrub gate cannot read binaries**, so it
  was never a backstop here.
- **Generated board files gitignored** — `docs/plans/tracker.html` and `.board`, anchored with a
  leading slash so the pattern could not swallow `skills/mow/tracker.html`, the template every board
  is copied from.
- **Run-state trails untracked** — `**/dispatch/.activity` and `**/dispatch/.agent-times.json`, after
  two mechanical errors worth keeping: a gitignore pattern containing a slash is anchored to the repo
  root and never matched the nested paths, and `git commit -- <paths>` re-committed the files it was
  meant to remove (L45). Cost recorded rather than discovered later: an archived run rendered from a
  fresh clone now falls back to wall clock for active time.
- **Push access verified before going public** — personal repo, not an org, not a fork; exactly one
  collaborator with write (the owner); no deploy keys; the new CI workflow's token is
  `contents: read` and it triggers on `pull_request`, not `pull_request_target`. Public grants read,
  never write.

**Observed, not acted on:** two sessions sharing one checkout means either one's push publishes the
other's commits. It happened in both directions this session — this session's push carried three of
the sibling stem's commits, and the sibling's later push carried five of this one's.

## Next steps

- Operator: flip visibility, then `/wrap-up`, then clone at work and run the four-test check.
- The board is optional there: two PATH lines plus `taskman init-db` from the project root.
- Resume pointer: [`../plans/publish-hygiene/action-report.md`](../plans/publish-hygiene/action-report.md)
  · [`../plans/publish-hygiene/plan.md`](../plans/publish-hygiene/plan.md) · this report.
