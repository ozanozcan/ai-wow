# Action report — Work-PC readiness

**Date:** 2026-08-19
**Project slug:** `work-pc-readiness`
**Plan:** [`plan.md`](plan.md)
**Dispatch:** [`dispatch/INDEX.md`](dispatch/INDEX.md)
**Waves:** 2 (A ‖ B, then Z) · **Lanes:** 3 · **Agent tokens:** ~163k

---

## Outcome

| Item | Status | Where it landed |
|---|---|---|
| `backend-reviewer` rewritten FastAPI-only | shipped | `agents/backend-reviewer.md` (138 → 149 lines) |
| `classic-web-reviewer` added | shipped | `agents/classic-web-reviewer.md` (123 lines) |
| `streamlit-reviewer` added | shipped | `agents/streamlit-reviewer.md` (120 lines) |
| `django-reviewer` deleted | shipped | removed from `HEAD` (was tracked, not untracked) |
| Portable mow tracker cascade | shipped, **re-targeted** | `~/Desktop/dotfiles-ai/skills/mow/{SKILL,TRACKER}.md`; synced back into ai-wow |
| Doc + inventory sweep | shipped | `HOW-TO-USE.agent.md`, `HOW-TO-USE.human.md`, `README.md`, `global/CLAUDE.md` |

Run diff: **8 markdown files**, +289 / −262 in ai-wow, plus 2 files in dotfiles-ai. No
code, no tests, no config touched.

---

## Wave results

### Wave 1 — lanes A ‖ B, backgrounded in isolated git worktrees

**Lane A — reviewer roster** (`tdd-builder`, ~94k tokens, 12m)

Delivered all four `agents/` changes. Added section `F. Security, config & output
escaping` — the one genuine gap, since FastAPI ships less secure-by-default than Django
did — covering wildcard CORS with credentials, `verify_signature=False`, `/docs` in
production, scattered `os.environ` vs `pydantic-settings`, and auth-path rate limits.
Re-lettered sections to fit (Alembic → G, LLM → H, production-readiness → I). Invoked
`simplify` per its Toolkit when the rewrite came out longer than the original; 9 findings
applied, 3 skipped with reasons, 152 → 149 lines.

The lane reported two contradictions with its own brief, both confirmed against `HEAD`
and recorded in [`plan.md`](plan.md) → `## Correction — the backend-reviewer premise was
stale`.

**Lane B — tracker portability** (`tdd-builder`, ~69k tokens, 6m)

Replaced three non-portable calls with a `command -v` cascade: kill = `pkill` →
`taskkill` → warn; open = `open` → `start` → `xdg-open` → skip; URL printed
unconditionally in every branch. Captured real red evidence by running the pre-fix lines
from `HEAD` under a Git-Bash-like PATH (`pkill: command not found` twice, close-out
exiting `127`). Narrowed the `taskkill` PID lookup with `awk` on the local-address column
so it can't hand `taskkill` the browser's PID or match port `18399`.

**Merge-back:** both worktrees committed on their own branches, merged into a disposable
integration branch, diffed against the wave-start commit and applied as one combined diff.
No conflicts. Worktrees and branches torn down after the gate.

**Gate:** both lanes' `## Verification` blocks checked against their QA contracts, and
every acceptance grep re-run independently by the orchestrator in the merged tree. Review
flags were `-` throughout — the diff is agent definitions, a skill and docs, so there was
no application code for a stack reviewer to audit.

### Wave 2 — lane Z, foreground

Docs and routing sweep. All three inventory counts (`README.md`, `HOW-TO-USE.human.md`,
`HOW-TO-USE.agent.md`) now read **eight** and agree with `ls agents/*.md`. Both subagent
tables carry eight rows. `global/CLAUDE.md`'s routing table gained file-type dispatch
signals plus the HTMX handoff row, so a mixed route+template diff routes to **both**
reviewers instead of one.

The brief cited four Django reference sites; only three existed (`HOW-TO-USE.agent.md:122`,
`:123`, `global/CLAUDE.md:59`). The human-facing routing table carries no Django — another
stale citation, same class as lane A's.

---

## Decisions locked

- **`ai-wow/skills/` is not writable in practice.** It is a mirror of
  `~/Desktop/dotfiles-ai/skills`, re-copied by a repo sync and auto-committed. Skill edits
  must be made in dotfiles-ai, which then propagates. Verified end-to-end this run.
- **Lane B's fix was ported to dotfiles-ai** with explicit operator approval, overriding
  the plan's scope boundary. Confirmed byte-identical in both repos afterwards.
- **Brief line-number citations were stale in two of three lanes.** Both lanes caught it
  by verifying against the file rather than trusting the brief. This is the single most
  useful behavior to preserve from this run.

---

## Open / deferred

Operator elected to leave these as follow-ups:

1. **The serving-block identity is unenforced.** `SKILL.md` and `TRACKER.md` must carry a
   byte-identical serving block; nothing checks it. A drift here is silent.
2. **Skills-count drift** — `HOW-TO-USE.agent.md` says "14 skills" (and a mermaid node
   asks "14 skills listed?"), `README.md` says 15, `HOW-TO-USE.human.md` says "Fifteen",
   `ls -d skills/*/` returns 17. Deliberately out of this plan's scope; it is the same
   drift class just fixed for subagents.
3. **Plain-Python diffs have no reviewer.** A consequence of the FastAPI-only decision:
   `backend-reviewer` hands off when the stack doesn't match, but no sibling owns plain
   Python. A CLI script or data pipeline falls through the gate.
4. **`ai-wow` is `ahead 1` and unpushed.** The work PC clones GitHub, so nothing reaches
   it until a push. Left to the operator.
5. **`hooks/stamp-tracker.py` mis-times backgrounded agents.** Its `PostToolUse` pairing
   fires when the *launch* returns, not when the agent finishes, so every AFK lane gets an
   `ended` ~20s after spawn. Visible only on a still-running lane, where it freezes the
   board's clock and makes a live run look dead. Fix belongs in dotfiles-ai.
6. **`.claude/worktrees/` is not gitignored.** The auto-sync committed two worktree
   gitlinks mid-run; they were removed from the index during Integrate. The next
   worktree-isolated run will recreate them.

---

## Verify

| Check | Result |
|---|---|
| `grep -riE "django\|flask" agents/` | 0 hits |
| `ls agents/*.md` vs stated counts | 8 = 8 = 8 = 8 |
| Security greps in `backend-reviewer` | 3 (≥3 required) |
| Seam named in both directions | 6 and 6 (≥1 required) |
| Out-of-scope Django sites intact | 9 files still present |
| `bash -n` on all three cascade blocks | 3/3 parse |
| Serving snippets byte-identical | yes, both repos |
| Platform branching (`uname`/`OSTYPE`/`MSYS`) | 0 |
| Tracker serve → curl → stop | `200` then connection refused |
| `python3 bin/ai-sync status` | exit 0 |
| Agent roster reload | `classic-web-reviewer` + `streamlit-reviewer` live, `django-reviewer` gone |

**P3 post-build protocol:** this repo has no `docs/agents/protocols.md`, so the default
applied. `/verify`, `test-coverage` and the adversarial batch are **n/a** — the entire run
diff is markdown with no executable surface. The repo's `taskman/tests` suite was not run:
nothing in the diff touches Python, `pytest` is not installed in the active interpreter,
and there is no venv at the repo root. Recorded as n/a rather than skipped silently.

**Ship-check:** run against `plan.md` + the shipped diff. **No Critical findings.**
Layer 1: 4 (all record-accuracy, corrected in `plan.md`) · Layer 2: 2 (both deferred
above) · Layer 3: 3 (two deferred above; the third — new agents needing a session restart
— proved wrong, the roster reloaded live).

**Finding triage:** every Layer 1 finding was **(b) convention/record** and fixed in
`plan.md` this run. Items 1–3 in Open/deferred are **(a) mechanizable** with an
operator-approved deferral. Items 4–6 are **(c) one-off**.

**Board sync:** n/a — this repo has no root `.taskman.toml`, so no Feature/Task rows exist.
