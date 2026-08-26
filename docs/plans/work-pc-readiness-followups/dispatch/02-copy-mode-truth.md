# copy-mode-truth: `ai-sync status` reports the mode it actually installed

**Role:** code-edit   **Wave:** 1   **AFK:** yes   **Background:** yes

**Decisions / Specs (pointers):** `-` — no taskman board in this repo. The binding decision is in [`../plan.md`](../plan.md) → `## Decisions locked`, third bullet: status reports what is **installed**, not what the machine **can do**. Two alternatives were considered and rejected there; do not re-open them.

## Goal

On a machine where symlinks work but the harness was installed with `--copy`,
`python3 bin/ai-sync status` reports copy mode and `copied (in sync)` — instead of
claiming `link mode: symlink` and printing eight `NOT linked (real dir)` lines for a
complete, correct install. The docs that quote that output verbatim are updated to match.

## Context & decisions (only what this todo needs)

- **Reproduced, both paths, before this brief was written.** With `--copy` and no config:
  `link mode: symlink` + 8× `NOT linked (real dir)`, despite every file being present and
  in sync. With `{"link_mode": "copy"}` in `local.config.json`: `link mode: copy (no
  symlink privilege)` + 8× `copied (in sync)`. Same install, same disk, two different
  verdicts.
- **Why it happens.** `do_status` prints the mode from `can_symlink()`, and
  `_dir_link_state` gates its `copied (in sync)` branch on `not can_symlink()`.
  `can_symlink()` returns False for `FORCE_COPY` — but `--copy` is a one-shot flag on the
  *install* invocation, and `status` is a *separate* invocation where `FORCE_COPY` is
  False and the config is empty. So status probes the machine's capability and reports
  that instead of the install.
- **Why it matters for the work PC.** The README quickstart tells you to run `status`
  immediately after installing, and Appendix A promises status "always tells you which
  mode is active". `--copy` is the documented path for a corporate Windows box with
  Developer Mode locked off by policy. On exactly that machine, the documented sequence
  reads as a failed install.
- **The label is wrong in the other direction too.** `copy (no symlink privilege)` is a
  claim about the machine. When copy mode was *chosen* on a machine that can symlink,
  that claim is false.
- **This is a reporting fix.** Do not change how installing works — `ensure_copy`,
  `ensure_symlink`, `reconcile_skills` and the `FORCE_COPY` install path all stay as they are.

## Files in scope

- `bin/ai-sync` — modify (status/reporting path only)
- `HOW-TO-USE.human.md` — modify (Appendix A)
- `HOW-TO-USE.agent.md` — modify (the VERIFY line that quotes the same output)

## Anchors

- `do_status()` — the `link mode:` print, around line 877
- `_dir_link_state()` — returns `linked` / `copied (in sync)` / `NOT linked (real dir)` / `missing`, around line 860
- the `LINK_FILES` loop inside `do_status` — same `not can_symlink()` gate for the single-file case
- `can_symlink()` — around line 285. **Leave its install-time behavior alone**; it is
  correct for deciding *how to install*.
- `HOW-TO-USE.human.md:596` and `HOW-TO-USE.agent.md:341` — both quote
  `link mode: copy (no symlink privilege)` verbatim

## Signatures

- Add one helper, name it as you see fit, with this contract:
  `installed_mode() -> str` — returns `"symlink"` when any managed target is a symlink
  resolving into `REPO`; `"copy"` when the managed targets are real dirs/files whose
  contents match the canonical source; and falls back to `can_symlink()`'s answer when
  nothing is installed yet (a fresh machine, every target `missing`).
- `do_status` and `_dir_link_state` read that helper instead of `can_symlink()`.
  `_dir_link_state` may take the mode as an argument rather than calling the helper per row.

## Depends on

- none

## Do NOT

- **Do NOT run `python3 bin/ai-sync` against your real `HOME`.** It relinks
  `~/.claude`, `~/.cursor` and `~/.copilot` at the repo it is run from, commits with
  `git add -A`, and pushes. Run it **only** as
  `HOME=<sandbox-dir> python3 bin/ai-sync …`, and write `{"push": false}` into
  `local.config.json` in your working copy before the first run. `local.config.json` is
  gitignored, so it will not be committed.
- **Do NOT make `--copy` write to `local.config.json`.** Explicitly rejected in the plan —
  a flag editing machine config as a side effect is its own surprise.
- Do NOT change `ensure_copy`, `ensure_symlink`, `reconcile_skills`, `do_import`, or
  `can_symlink()`'s install-time behavior. Reporting only.
- Do NOT touch `hooks/` — another lane owns it.
- Do NOT edit `README.md`; its quickstart does not quote the status output.

## Git rules

- Stage **explicit paths only** from **Files in scope** — never `git add -A` or `git add .`.
- Prefer `git commit -- bin/ai-sync HOW-TO-USE.human.md HOW-TO-USE.agent.md` over
  `git add` + `git commit`, so the index cannot pick up a peer session's staged file.
- **Forbidden:** `git stash`, `git reset --hard`, `git clean -fd`.
- Confirm `local.config.json` is **not** staged before committing.

## Acceptance check

- `ai-sync status` SHALL report the mode the harness was actually installed with, on a
  machine that is capable of symlinks either way.
- GIVEN a sandbox `HOME` where the harness was installed with `python3 bin/ai-sync --copy`
  and `local.config.json` carries **no** `link_mode`, WHEN `HOME=<sandbox> python3
  bin/ai-sync status` runs, THEN it reports copy mode and every managed target reads
  `copied (in sync)` — and **zero** lines read `NOT linked`.
- GIVEN a sandbox `HOME` installed normally (symlink mode), WHEN status runs, THEN it
  reports `link mode: symlink` and every target reads `linked` — unchanged from today.
- GIVEN a sandbox `HOME` with nothing installed at all, WHEN status runs, THEN it does not
  crash and reports the machine's capability, with targets `missing`.
- The mode label SHALL NOT claim `no symlink privilege` on a machine that has the privilege.
- **L05 check — the docs quote this output verbatim.** After changing any user-visible
  string, `grep -rn "no symlink privilege" --include="*.md" .` must return no line that
  contradicts the new output.

## QA contract

- Build **two** sandbox HOMEs under your scratch dir and run the full matrix above —
  symlink install, copy install, and empty — pasting the real status output for each.
  Recipe (adapt paths; never use the real `$HOME`):
  ```
  H=<scratch>/h-copy; mkdir -p "$H/.agents"
  echo '{ "push": false }' > local.config.json
  HOME="$H" python3 bin/ai-sync --copy
  HOME="$H" python3 bin/ai-sync status
  ```
  For the symlink case, `ln -s <worktree>/skills "$H/.agents/skills"` first — without that
  symlink the skill step returns early and you get zero skills with no error.
- `python3 -m py_compile bin/ai-sync` → exit 0.
- The `grep` for the old string across `*.md`.
- Re-run the copy-mode status **twice** and confirm it is stable, not first-run-only.

## Toolkit

- `Invoke: skill:tdd` — this is a bug fix, so capture the wrong output first (red), then
  fix. The sandbox recipe above *is* the reproduction; paste its pre-fix output.
- `Invoke: skill:simplify` only if your change lands longer than it needs to be.

Your final message MUST end with:

## Verification
- Commands run: <exact commands + pass/fail>
- Contract items: <each item → met / not-applicable + why>
- Artifacts: <paths, or "none">
- Decisions honored: <the "status reads disk" decision: how, file:line — or "none pointed">
