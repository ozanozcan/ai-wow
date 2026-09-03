---
date: 2026-09-02 23:03
branch: master
slug: work-pc-brief-and-ai-sync-utf8
project: none — ai-wow is deliberately board-less (no .taskman.toml)
session_id: 06f0a637-6238-479f-9636-62e4ace908c6
start_sha: 2e92a79aa3be
---

# Session report — the work-PC readiness brief, then closing the encoding gap it surfaced

Two halves. First a readiness question about pulling this repo to a Windows work PC under
VS Code + Copilot, answered by auditing the current code rather than the write-ups. That
audit named `bin/ai-sync`'s bare `read_text()` calls as the highest-value open item; the
second half closed them.

## What was done

- **Audited work-PC readiness against the code, not the reports.** Read `bin/ai-sync`,
  `hooks.def.json`, `.github/workflows/ci.yml` and Appendices A–C of `HOW-TO-USE.human.md`,
  and re-checked every claimed landmine against the tree as it actually stood. Ran all 11
  database-free suites (green) to establish a baseline.
- **Published two artifacts** — an English install runbook and a Turkish translation of it —
  each carrying the `ai-sync` pipeline diagram, the post-install fileset, the ordered
  commands, and the landmine table.
- **Fixed the encoding defect and guarded it.** 13 text I/O sites in `bin/ai-sync` now name
  `encoding="utf-8"`; a new two-layer suite pins it; `githooks/pre-push` registers that
  suite. Pushed as `7ec9cea`, `8d03b60..7ec9cea`.

## Files changed

Only `7ec9cea` belongs to this session. `git show --stat 7ec9cea`:

| Path | Change |
|---|---|
| `bin/ai-sync` | 13 sites: 9 `read_text()` + 4 `write_text()` now name `encoding="utf-8"` |
| `bin/tests/test_ai_sync_encoding.py` | new — 233 lines, behavioural + AST layers |
| `githooks/pre-push` | +1 line registering the new suite |

**Not this session's.** `2e92a79..HEAD` also contains `63dafe3`, `f1d0b9c` and `8d03b60`,
and the tree still carries `docs/plans/INDEX.md`, `docs/plans/work-pc-readiness/action-report.md`,
`docs/plans/taskman-port/` and `templates/copilot-instructions.template.md`. All of that is
peer-session work from the ~11 hours this session sat idle mid-question. Left untouched and
deliberately not attributed here.

## Wrap-up gate

**Not run — unavailable, not skipped.** No `.taskman.toml` anywhere up the tree and no
`scripts/wrapup_reconcile.py` in this repo, so the deterministic gate cannot execute. Per the
skill's preconditions this took the board-less path: lessons + session report only.

Evidence came from git instead: session marker `start_sha=2e92a79aa3be`, per-commit diffstats,
a red-then-green test transcript, and the pre-push gate's own output on the real push.

## Taskman sync

**None — no board exists in this repo, by decision.** No Feature/PBI/Task/Requirement rows to
create or move. The open items below are recorded here rather than booked.

## Lessons

**None logged.** One candidate was considered and declined.

The behavioural half of the new test **passed against unfixed code** on first run. The fixture
was built with `json.dumps(...)`, whose default `ensure_ascii=True` escaped the non-ASCII to
`ğ` — so the file contained no non-ASCII bytes and the test exercised nothing. That is
exactly **L46** (*running the real procedure against the one input where its defect cannot
appear is not verification*), already routed to `claude-md`.

Declined to bump it, on the precedent set on 2026-09-01 for L40: a routed rule recurring means
its destination is not working, and here it did work — the pass-against-broken-code was caught
in the same turn, before anything was reported verified. The durable fix also landed as a
committed assertion (`fixture X really carries non-ASCII bytes`) rather than as a rule someone
has to remember, which the skill itself rates as strictly better.

Ledger state: 92 lines, one unrouted rule (L22), no BACKLOG or PRUNE signal.

## Decisions

- **`write_text` was fixed alongside `read_text`, though only the reads were asked for.** Lines
  618/622 and 793/795 are read-then-write pairs; fixing one half leaves a round-trip whose ends
  disagree about the encoding. Stated at the time rather than folded in silently.
- **No exception handling changed.** On POSIX these call sites already raised on a non-UTF-8
  byte, so naming UTF-8 makes Windows behave the way the development platform already did. It
  is not a new failure mode, and widening the `except` tuples would have been scope creep with a
  real downside: `load_json` falling back to `{}` for `~/.claude.json` precedes a `write_json`
  that would then overwrite it.
- **Two test layers, because neither alone is worth much.** The bug only manifests where the
  locale encoding is not UTF-8, so a behavioural test alone is green before and after on macOS
  and proves nothing. It is pinned to an ASCII locale in a subprocess so it fires here; the AST
  layer then covers all 13 sites including those needing a whole rendered repo, and is what
  stays true as the file grows.
- **`subprocess.run(text=True)` in `git()` left alone.** Same defect class, deliberately out of
  scope and flagged in the commit message rather than folded in. Lower risk: `core.quotepath`
  escapes non-ASCII in porcelain output by default.
- **The readiness answer was published as artifacts, not left in scrollback.** It is a runbook to
  be read on the other machine, where this terminal's history will not exist.

## Open threads / not finished

1. **`git()` calls `subprocess.run(text=True)` with no `encoding`** — `bin/ai-sync:834`. Same
   class as what was just fixed; noted in `7ec9cea`'s message.
2. **`hooks/peer-session-{guard,notice}.py` carry 4 bare `read_text()`** reading JSON markers —
   lines 73/90 and 122/131. Outside this session's scope, still open.
3. **`~/Desktop/dotfiles-ai/bin/ai-sync` has the identical defect** — 8 bare reads, 3 bare
   writes, 0 with an encoding. The same asymmetry as the separator bug on 2026-09-01, where the
   published tree was fixed first and the private one carried the bug longer. That tree's own
   `test_tree_drift` guard will now see `bin/ai-sync` as drifted.
4. **`README.md`'s post-clone check block names four suites** and not the new encoding one —
   which is the most relevant of the set for a Windows box. Left alone to keep the diff surgical;
   offered to the operator.
5. **Whether VS Code's Copilot reads `~/.copilot/agents` is still unverified.** The README asserts
   it; that path is also the Copilot CLI's. Confirm a subagent actually appears before relying on
   the roster.
6. **`global/CLAUDE.md` still reaches only `~/.claude/CLAUDE.md`.** A peer session appears to be
   addressing this — `templates/copilot-instructions.template.md` is untracked in the tree — but
   it is not this session's to land or describe.

## Next steps

- Decide item 3: the same fix is owed in `dotfiles-ai`, and until it lands that tree's drift
  guard will refuse a push naming `bin/ai-sync`.
- Items 1 and 2 are both one-line changes and could ride together.
- **No checkpoint created.** This repo has no `docs/checkpoints/` and no board, so the skill's
  leftover-bundling path cannot run; the open threads above are the handoff. Flagged as a
  deviation rather than silently skipped.
- **Resume pointer:** this report ·
  [`bin/tests/test_ai_sync_encoding.py`](../../bin/tests/test_ai_sync_encoding.py) ·
  `git show 7ec9cea` · `~/Desktop/dotfiles-ai/bin/ai-sync` for item 3.

---

## Addendum — 2026-09-03, same thread

The open-thread list above is left as written: it was accurate when the report was
filed. This records what has since closed, because that list is where a resume pointer
sends the next session and four of its six items are now done.

### The encoding work finished, and it was bigger than the list said

Items 1 and 2 are **closed** by `b40a1db` (this tree) and `810ad25` (dotfiles-ai).

They were framed as two spots — one `subprocess.run(text=True)` and four bare
`read_text()`. Widening the guard's AST layer from `bin/ai-sync` alone to the whole
Python surface (`bin/ai-sync` plus `hooks/*.py`), and teaching it that subprocess in
text mode decodes with the locale encoding too, found **nine**:

| File | Sites |
|---|---|
| `bin/ai-sync` | `subprocess.run(text=True)` |
| `hooks/peer-session-guard.py` | `read_text` ×2, **`write_text`**, `subprocess.run` |
| `hooks/peer-session-notice.py` | `read_text` ×2, `subprocess.run` |
| `hooks/session-start-marker.py` | **`subprocess.run`** |

The two in bold appeared in neither open thread. They were found by the scan, not by
anyone reading the code — the same argument `.github/workflows/ci.yml` already makes
about discovering test files rather than enumerating them, applied to call sites.
Two anti-vacuity checks landed with it: one fails if the `hooks/*.py` glob stops
matching, one if the code stops decoding text at all.

### The two trees are now locked, not merely both fixed

`bin/tests/test_ai_sync_encoding.py` and the three hooks are `match` in dotfiles-ai's
`tree-drift.json`, and were verified byte-identical **origin to origin** after both
pushes. Parity is enforced by that guard now rather than remembered. Item 3 closed
with it (`31db64f`); that tree reports 0 bare reads on its own origin.

### Item 4 closed by someone else, better than it was offered

`README.md`'s post-clone block no longer enumerates four suites — it says
`bash githooks/pre-push`, which runs all ten and names the UTF-8 property in prose.
An enumeration that would have gone stale was replaced by the gate itself.

### Still open

5. **`~/.copilot/agents` remains unverified for VS Code's Copilot.** Unchanged. Nothing
   in this thread tested it; the README's claim still rests on documentation, and that
   path is also the Copilot CLI's.
6. **`global/CLAUDE.md` still reaches only `~/.claude/CLAUDE.md`** — `LINK_FILES` has
   exactly one entry. `templates/copilot-instructions.template.md` is now *tracked*,
   so the gap has a documented manual answer, but nothing wires it: a Copilot user
   still gets skills and subagents without the standards unless they copy it by hand.

### Verify

Both remotes were re-checked by cloning at `origin/master` and running each tree's own
suite from inside the clone, so `REPO` resolved to the probe rather than the live
checkout — the flaw that invalidated an earlier attempt at this same check.

| Check | Result |
|---|---|
| ai-wow origin: bare `read_text()` in `bin/ai-sync` + `hooks/*.py` | 0 |
| dotfiles-ai origin: same | 0 |
| Text-mode subprocess sites naming an encoding, both origins | all 4 |
| `test_ai_sync_encoding.py` verdict, both origins | 0 failure(s) |
| Full db-free suite | 13/13 ai-wow · 11/11 dotfiles-ai (incl. `test_tree_drift`) |
| `match` files, origin vs origin | 4/4 byte-identical |
