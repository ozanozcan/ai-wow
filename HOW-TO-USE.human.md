# How to use this harness

**Audience:** a person setting this up and working with it day to day.
There is a companion document written for an agent to execute:
[`HOW-TO-USE.agent.md`](HOW-TO-USE.agent.md). Same system, different shape — that one
is numbered steps with pass/fail conditions; this one explains why the pieces are
arranged the way they are.

---

## Contents

1. [What this is](#1-what-this-is)
2. [The three mechanisms](#2-the-three-mechanisms)
3. [How config reaches your tools](#3-how-config-reaches-your-tools)
4. [Install](#4-install)
5. [Working without a board](#5-working-without-a-board)
6. [The board](#6-the-board)
7. [Orchestrating multi-step work](#7-orchestrating-multi-step-work)
8. [Session lifecycle](#8-session-lifecycle)
9. [Extending it](#9-extending-it)
10. [Appendix A — VS Code, and locked-down machines](#appendix-a--vs-code-and-locked-down-machines)
11. [Appendix B — Windows](#appendix-b--windows)
12. [Appendix C — troubleshooting](#appendix-c--troubleshooting)

---

## 1. What this is

A portable configuration layer for AI coding agents. It gives an agent a set of
**procedures** to follow, a set of **specialists** to delegate to, and a set of
**guarantees** that fire whether or not the agent remembers them — then keeps all of
that identical across two editors and every machine you work on.

Three problems it solves, in order of how much they hurt:

```mermaid
flowchart TD
  P1["Agents forget your standards <br/>every new conversation"]
  P2["Chat context dies; <br/>decisions die with it"]
  P3["Config drifts between <br/>machines and editors"]

  S1["Skills + subagents <br/>procedures that load on demand"]
  S2["taskman <br/>a board that outlives the chat"]
  S3["One repo + one sync script"]

  P1 --> S1
  P2 --> S2
  P3 --> S3
```

You can adopt these in that order. The first needs no configuration at all; the
second needs a database; the third needs one symlink and a script.

---

## 2. The three mechanisms

Almost everything here is a skill, a subagent, or a hook. Knowing which one you're
looking at explains most of its behaviour.

```mermaid
flowchart LR
  subgraph SK["SKILL"]
    SK1["loads into the <br/>running agent's context"]
    SK2["fires when relevant"]
  end
  subgraph SA["SUBAGENT"]
    SA1["own fresh context, <br/>own tool list"]
    SA2["starts cold, reports back"]
  end
  subgraph HK["HOOK"]
    HK1["shell script run <br/>by the harness"]
    HK2["fires every time"]
  end
```

The practical rule:

| You want… | Use | Because |
|---|---|---|
| A procedure followed *when it applies* | **Skill** | It's advice the agent reads; it costs nothing when unused |
| An isolated job with a clean slate | **Subagent** | Its context can't pollute yours — but spinning one up isn't free |
| Something to happen **without fail** | **Hook** | It isn't the agent's decision |

A guarantee you implement as a skill is a suggestion. A suggestion you implement as
a hook is an annoyance. Match the mechanism to the intent.

---

## 3. How config reaches your tools

One repo is the source of truth. Two delivery mechanisms, chosen per category.

```mermaid
flowchart LR
  subgraph REPO["this repo — canonical"]
    direction TB
    A["skills/ · agents/ <br/>commands/ · hooks/ <br/>global/CLAUDE.md"]
    B["hooks.def.json <br/>mcp.json"]
  end

  A -->|"symlink"| C["~/.claude"]
  A -->|"symlink"| D["~/.cursor"]
  A -->|"symlink (agents only)"| E["~/.copilot"]
  B -->|"render to <br/>Claude schema"| C
  B -->|"render to <br/>Cursor schema"| D
  B -->|"render to <br/>Copilot schema"| E

  C -.->|"your edits land here"| A
  D -.->|"your edits land here"| A
  E -.->|"agent edits land here"| A
```

**Why not symlink everything?** Skills, subagents, commands and hook *scripts* use
an identical on-disk format across Claude Code and Cursor, so a symlink means the
editor's directory *is* this repo — zero drift, and editing from inside either tool
writes straight back here. Hook *registration* and MCP config use **different
schemas** per editor, so they can't be shared as files; `ai-sync` translates one
neutral definition into each editor's dialect.

**Copilot is a third target, but a thinner one.** Its personal skill search path
already includes `~/.agents/skills` — the exact symlink below — so skills need no
extra wiring at all. Subagents get their own symlink to `~/.copilot/agents`
(Copilot's personal custom-agent directory differs from Claude's). Hooks and MCP
are rendered into Copilot's schema the same way Cursor's are. Slash commands and
per-project hooks are workspace-scoped in Copilot (`.github/prompts/`,
`.github/hooks/`), so those render into each repo listed in `managed_repos`
instead of a global symlink — see §4.

> [!NOTE]
> The hook *scripts* were written to parse Claude Code's stdin/stdout JSON shape.
> They're now registered for Copilot's matching lifecycle events too, but Copilot's
> exact runtime payload hasn't been verified against them. Hooks fail open, so a
> mismatch just makes a hook silently inert — it won't misfire — but don't treat
> `guard-destructive` as an active guardrail under Copilot until you've confirmed
> live that it actually fires.

Skills take one extra hop, and it's the hop that breaks:

```mermaid
flowchart LR
  R["repo/skills/"] -->|"symlink you create by hand"| AG["~/.agents/skills"]
  AG -->|"per-skill links <br/>ai-sync maintains"| CC["~/.claude/skills/*"]
  AG -->|"per-skill links <br/>ai-sync maintains"| CU["~/.cursor/skills/*"]
```

`ai-sync` maintains the second arrow but **not the first**. If `~/.agents/skills`
doesn't exist, the skill step returns immediately and you get zero skills with no
error message. Make that link before the first sync.

### What `ai-sync` does

```mermaid
flowchart LR
  I["import"] --> L["link"] --> S["reconcile <br/>skills"] --> R["render"] --> G["commit"]
```

- **import** — pull anything you created inside an editor into the repo
- **link** — point the editor directories at this repo
- **reconcile** — make both editors expose the same skill set
- **render** — write `hooks.def.json` and `mcp.json` into each editor's own format
- **commit** — stage everything and commit

> ⚠️ **`ai-sync` commits with `git add -A` and pushes without asking.** It is
> registered as a session-end hook, so this happens on its own. Never leave anything
> private in the working tree. On a machine that must never push to an external
> remote — a corporate laptop — set `{ "push": false }` in `local.config.json`:
> commits still happen (local history is the backup), the push is skipped.

---

## 4. Install

```bash
git clone <this-repo> ~/ai-wow
mkdir -p ~/.agents && ln -s ~/ai-wow/skills ~/.agents/skills
python3 ~/ai-wow/bin/ai-sync
python3 ~/ai-wow/bin/ai-sync status
```

`status` is the thing to trust — it reports what is actually linked rather than what
should be:

```
.claude/agents    linked
.claude/commands  linked
.claude/hooks     linked
.claude/CLAUDE.md linked
shared skills (~/.agents):  16
```

Anything `ai-sync` overwrites is copied to `.backups/<timestamp>/` first, so a wrong
first run is recoverable.

**Machine-specific settings never enter the repo.** If you want the managed-doc
render pointed at your own projects, copy `local.config.example.json` to
`local.config.json` — that filename is gitignored:

```json
{ "managed_repos": ["~/projects/my-api", "~/projects/my-web-app"] }
```

Absent or empty is a valid state. That feature simply doesn't run.

VS Code needs nothing extra — see [Appendix A](#appendix-a--vs-code-and-locked-down-machines),
which also covers machines that forbid symlinks. Windows needs three extra things:
[Appendix B](#appendix-b--windows).

### If this repo is private

`git clone` only works anonymously on a public repo. For a private one the machine has
to authenticate, and on a machine you don't fully control — a work laptop, a shared
box — *how* it authenticates matters.

**Don't sign a whole account in.** `gh auth login` stores credentials for your entire
GitHub account. Use a **fine-grained personal access token scoped to this one
repository** instead:

GitHub → Settings → Developer settings → Personal access tokens → Fine-grained →
**Only select repositories** → this repo → Repository permissions →
**Contents: Read-only** (Read and write only if you intend to push back) → set a short
expiry.

Then plain `git` is enough — no `gh` needed:

```bash
git clone https://github.com/<you>/<repo>.git ~/ai-wow
```

It prompts for a username and a password; paste the **token** as the password. The
platform credential helper caches it after that.

```mermaid
flowchart TD
  A["private repo"] --> B{"machine you<br/>fully control?"}
  B -->|yes| C["gh auth login<br/>or SSH key"]
  B -->|no| D["fine-grained token,<br/>this repo only, short expiry"]
  D --> E["revoke from GitHub<br/>to cut access instantly"]
```

The reason to prefer the token: revoking it on GitHub removes that machine's access
immediately, without touching anything else you own.

If the network blocks GitHub entirely, the repo is small enough (~2 MB) to move as an
archive — you just lose the sync path back.

---

## 5. Working without a board

Everything in this section runs on a bare clone. No database, no API key, no project
config. This is most of the value.

**Eight subagents.** Each gets its own context window and a restricted tool list.

| Subagent | Reviews or builds | Use when |
|---|---|---|
| `backend-reviewer` | reviews | A FastAPI / SQLAlchemy async diff is ready to commit |
| `classic-web-reviewer` | reviews | A template, `.html`, or non-framework `.js` diff — vanilla, jQuery, HTMX |
| `streamlit-reviewer` | reviews | A Streamlit app diff — reruns, caching, session state |
| `frontend-reviewer` | reviews | A React / Next.js diff — correctness, not looks |
| `llm-sec-review` | reviews | The diff touches prompts, tool-calling, agents or RAG |
| `ui-designer` | builds | Any visual work; it is the design authority |
| `tdd-builder` | builds | A scoped task with acceptance criteria |
| `teacher` | builds | You want to learn something over time, not get one answer |

Two invariants make this work: **reviewers never build**, and **`tdd-builder` never
commits**. If the thing that writes the code is also the thing that approves it, the
review gate means nothing.

**Sixteen skills**, in four families:

```mermaid
flowchart TD
  subgraph BUILD["build"]
    B1["tdd"]; B2["test-coverage"]; B3["adversarial-tester"]
    B4["parallel-debug"]; B5["complexity-audit"]; B6["improve-codebase-architecture"]
  end
  subgraph UI["ui"]
    U1["impeccable †"]; U2["imprint"]; U3["playwright-cli"]
  end
  subgraph ORCH["orchestration"]
    O0["bs"]; O1["mow"]; O2["grill-with-docs"]; O3["ship-check"]; O4["docs"]
  end
  subgraph CONT["continuity"]
    C1["checkpoint"]; C2["pick-up-where-i-left-off"]; C3["wrap-up"]
  end
```

**† `impeccable` is not bundled with this repo.** It is Apache-2.0 and about 99
files — the bulk of the original harness — so it is better taken fresh from its own
source than vendored here. One command adds it:

```bash
npx skills add pbakaus/impeccable
```

Everything else works without it; you lose the UI-craft handoff, and `ui-designer`
carries visual work alone. Full detail and the other three upstreams:
[`THIRD-PARTY.md`](THIRD-PARTY.md).

### Routing

Reach for the specialist rather than asking the generalist to try harder.

| The work smells like | Reach for |
|---|---|
| Building a feature, or fixing a bug | `tdd` — write the failing test first |
| A backend diff ready to commit | the stack reviewer subagent |
| Prompts, tools, agents, RAG | `llm-sec-review` **in addition to** the stack reviewer |
| A page, screen, component, mobile layout | `impeccable` † while building, `imprint` after |
| A slow endpoint or a new list query | `complexity-audit` |
| New logic with thin tests | `test-coverage`; pure logic → `adversarial-tester` |
| Two or more *unrelated* test failures | `parallel-debug` |
| A bug that isn't yielding | `/diagnose` |
| "I think it's done" | `ship-check` |

Routing is advice, not a gate. Recommend or invoke; don't block on it.

### The review pipeline

```mermaid
flowchart LR
  B["build"] --> R1["stack reviewer"]
  R1 --> R2["llm-sec-review"]
  R2 --> R3["frontend-reviewer"]
  R3 --> R4["simplify"]
  R4 --> R5["ship-check"]
```

The order is load-bearing: correctness, then security, then presentation, then
cleanup, then the gate. Polishing code that's about to be rewritten for a security
finding is wasted work.

---

## 6. The board

`taskman` is a per-project board — no web UI, nothing to deploy. A CLI that talks to
Postgres and prints tables. It exists because **chat context dies and the board
doesn't**.

Adopt it when you have work spanning more sessions than you can hold in your head.

### This repo has no board, deliberately

ai-wow ships taskman as a **tool**, and carries no board of its own — there is no
`.taskman.toml` at the root, and session reports here say `Board sync: n/a` because
that is accurate, not because someone forgot.

The reason is measured rather than assumed. With a root `.taskman.toml` present and no
reachable Postgres, `taskman wrapup gate` exits **2** — which the wrap-up skill reads as
"no session marker", the wrong diagnosis, pointing you at a command that fails the same
way. A board here would therefore break `/wrap-up` on every machine without a database,
and contradict this harness's own claim to need none. You would meet that on a locked-down
work machine first, which is exactly where it hurts.

Two consequences worth recognising when you see them:

- **The SessionStart hook stays quiet about wrap-up** in a board-less repo. It names the
  evidence gate only when it finds a `.taskman.toml` above the working directory. It still
  writes its session marker either way.
- **`taskman/.taskman.toml` exists and is not a contradiction.** It carries
  `slug = "taskman-tests"` and scopes the package's own test suite — not a board for this
  repo.

None of this stops you working: [§5](#5-working-without-a-board) is the full board-less
workflow. And if the board ever loses its database dependency, this decision is worth
revisiting — it is a judgement about today's constraints, not a rule.

### Standing one up

Four commands, once per machine. The board needs a Postgres it can reach and a role
that may create tables — it does **not** need a database of its own, because every
table is prefixed `taskman_` and sits happily beside an application's own schema.

**1. Name the project.** Put a `.taskman.toml` at the repo root:

```toml
[project]
slug = "my-service"
name = "My Service"
```

Without it taskman stops rather than guess, which is how two projects sharing one
Postgres never mix their rows.

**2. Point it at the database.** Either export `TASKMAN_DATABASE_URL`, or put it in a
`.env` beside the `.taskman.toml` — taskman walks up from the working directory to
find that file and loads the `.env` next to it.

```bash
export TASKMAN_DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/mydb"
```

The driver must be `psycopg`, not `asyncpg`. If your app already sets a `DATABASE_URL`
using `+asyncpg`, taskman rewrites it for you and reuses the same credentials.

**3. Install the CLI's dependencies:**

```bash
cd taskman && uv sync
```

**4. Create the schema:**

```bash
uv run python -m taskman init-db
```

That runs the Alembic migrations to head and registers the project. It prints
`taskman: schema ready. project 'my-service' (id=1).`

**Verify** — this should print the board's header and `(empty)`:

```bash
uv run python -m taskman board
```

If it does, the board works. From here `/mow` and `/wrap-up` can reach it.

### Shape of the data

```mermaid
flowchart TD
  F["Feature <br/>a capability"]
  R["Requirement <br/>SHALL + given/when/then"]
  P["PBI <br/>one unit of work"]
  T["Task <br/>what an agent executes"]
  D["Decision <br/>why we chose it"]
  C["Capture <br/>a session note"]

  F --> P --> T
  F -.->|"living spec"| R
  T -.-> C
  T -.-> D
```

A **Requirement** is capability-level truth — what the system must do. A **PBI's**
acceptance criteria scope one piece of work. Confusing the two produces a spec that
rots, because it was really a to-do list.

### Statuses

```mermaid
stateDiagram-v2
  direction LR
  [*] --> backlog
  backlog --> todo
  todo --> in_progress
  in_progress --> blocked
  blocked --> in_progress
  in_progress --> done
  todo --> disabled
  backlog --> disabled
  disabled --> backlog
```

`disabled` sits deliberately off the main line: *retired until explicitly
revisited*. It exists because marking something `done` that never happened is a lie
the board carries forever.

### Two rules worth learning early

**Identity is never guessed.** taskman walks up from your working directory looking
for `.taskman.toml`. No marker, no operation. That is how two projects sharing one
Postgres never mix rows.

**Tags replace, they don't append.** `task set <id> -t a,b` discards existing tags.
Read them with `task show <id>` first.

### Decision tasks

A question sharp enough to state precisely, not answered yet, with build work behind
it. It's an ordinary task tagged `kind:decision` where **the title is the question**.

```mermaid
flowchart LR
  Q["decision task <br/>title = the question"]
  B["build task"]
  B -->|"blocked-by"| Q
  Q -->|"answered → done"| U["build task <br/>recommended again"]
```

Resolving takes three commands and one file edit, and all four matter: record the
answer on the task, log *why* in the decision log, move it to `done`, then write the
locked answer into the plan. The board records that it closed; the log records why;
the plan is where the next agent reads what.

> ⚠️ Never give a decision task a dispatch-brief `source_ref`. The end-of-run sweep
> marks every task whose `source_ref` is one of the run's briefs as `done` — a
> decision task caught by it claims an answer nobody gave.

---

## 7. Orchestrating multi-step work

`mow` — Multi Agent Orchestration Workflow — is for the moment a planning session
ends with a dozen todos and neither option is good: keep building in a chat that's
already too long, or start each todo fresh and lose every decision you made.

```mermaid
flowchart TD
  T["think · grill · plan"]
  MP["/mow plan"]
  DB["dispatch/ briefs <br/>+ wave map"]
  BD[("board")]
  ML["/mow list"]
  MR["/mow ready"]
  MG["/mow go"]
  W["/wrap-up"]

  T --> MP --> DB
  MP -->|"import"| BD
  BD -->|"to-dispatch"| DB
  DB --> ML --> MR --> MG
  MG --> W --> BD
```

| Mode | Run it | It does |
|---|---|---|
| `plan` | in the chat where the decisions are still live | writes one brief per todo + the wave map, lands board rows |
| `list` | in a fresh chat | shows every active run with its full wave map |
| `ready` | before fan-out | grills the plan, one question at a time, writing each answer back |
| `go` | anywhere | fans out to subagents, wave by wave, review gate between waves |

**The hard rule:** lanes in the same wave own **disjoint file sets**.

```mermaid
flowchart TD
  subgraph W1["wave 1 — parallel"]
    L1["lane A <br/>owns api/*"]
    L2["lane B <br/>owns ui/*"]
  end
  RG["review gate"]
  subgraph W2["wave 2"]
    L3["lane C <br/>depends on A"]
  end
  L1 --> RG
  L2 --> RG
  RG --> L3
```

Two agents editing the same file in parallel is how you lose work. Overlap is
detected before fan-out, not discovered afterwards.

---

## 8. Session lifecycle

Three hooks and one skill bracket every working session.

```mermaid
sequenceDiagram
  participant You
  participant Harness
  participant Repo
  You->>Harness: open session
  Harness->>Repo: write session marker (start SHA)
  You->>Harness: work
  Harness-->>You: destructive command? ask first
  You->>Harness: /wrap-up
  Harness->>Repo: evidence gate
  Note over Harness,Repo: exits nonzero until every changed file <br/>is attributed and no task is left in_progress
  Harness->>Repo: session report + board sync
  You->>Harness: close session
  Harness->>Repo: archive transcript, ai-sync
```

The evidence gate is the part worth understanding. It compares the files changed
since the session's start SHA against what the board says you did. Unattributed
changes and tasks abandoned mid-flight both block it. You clear them by citing what
happened — which is exactly the information a future you will want.

Every hook fails open. A broken hook never blocks the agent.

---

## 9. Extending it

| Change | Edit | Then |
|---|---|---|
| A skill | `skills/<name>/SKILL.md` | `ai-sync` |
| A subagent | `agents/<name>.md` | `ai-sync` |
| A slash command | `commands/<name>.md` | `ai-sync` |
| Global instructions | `global/CLAUDE.md` | already live — it's symlinked |
| Hook wiring | `hooks.def.json` | `ai-sync` |
| An MCP server | `mcp.json` | `ai-sync` |

Because the editor directories are symlinks into this repo, editing a skill from
inside your editor edits the repo. There is no copy step and no drift.

> ⚠️ **Register hooks in exactly one place** — `hooks.def.json`. Never hand-edit the
> rendered block in `settings.json`; it gets overwritten. And never re-register a
> hook in a project's own settings: two live registrations means everything runs
> twice.

Adopting the harness in a new repo is a separate checklist:
[`templates/BOOTSTRAP.md`](templates/BOOTSTRAP.md).

---

## Appendix A — VS Code, and locked-down machines

### Does it work in VS Code?

Yes, and there is nothing extra to configure. The Claude Code VS Code extension runs
the same engine as the CLI and reads the same user directory:

```mermaid
flowchart TD
  H["~/.claude <br/>agents · commands · skills <br/>settings.json · CLAUDE.md"]
  H --> A["Claude Code CLI"]
  H --> B["VS Code extension"]
  H --> C["JetBrains extension"]
  D["~/.cursor"] --> E["Cursor"]
```

So the install is the same install. Once `ai-sync status` is clean, open any folder
in VS Code and the skills, subagents and `/diagnose` are there. There is no
VS Code-specific config file, no workspace setting, and nothing to add to
`.vscode/`.

Two things *are* different in the editor rather than the terminal:

- **The integrated terminal's shell decides whether hooks work.** Hook scripts are
  bash. On Windows, set the default profile to **Git Bash** — Command Palette →
  *Terminal: Select Default Profile* → Git Bash. With PowerShell as the default the
  hooks may not run, though nothing else is affected.
- **Per-project config still applies.** A `.claude/` directory in the opened folder
  layers on top of `~/.claude`. Keep hook registration out of it — see the warning
  in [§9](#9-extending-it).

### When the machine won't allow symlinks

This is the realistic failure on a corporate Windows build: **Developer Mode can be
disabled by group policy**, and you can't turn it on. The whole design is symlinks,
so that would normally be fatal.

It isn't. `ai-sync` probes the machine's capability once and falls back to mirroring
files:

```mermaid
flowchart TD
  S["ai-sync"] --> P{"can this machine <br/>create symlinks?"}
  P -->|yes| L["symlink mode <br/>editor dir IS the repo"]
  P -->|no| C["copy mode <br/>files mirrored into the editor"]
  L --> R1["edits in either place <br/>are the same file"]
  C --> R2["edit in the repo, <br/>re-run ai-sync to push out"]
```

The probe happens **before** anything is removed, which matters: the link step
deletes the existing directory before creating the link, so discovering the denial
afterwards would leave you with an empty `~/.claude/agents`.

You can also force it, which is worth doing if you want predictable behaviour rather
than capability-dependent behaviour:

```bash
python3 ~/ai-wow/bin/ai-sync --copy
```

…or make it permanent in `local.config.json`:

```json
{ "link_mode": "copy" }
```

`ai-sync status` always tells you which mode is active. It reads the state on disk
rather than re-probing the machine, so a one-shot `--copy` is still reported as copy
mode on later runs — the mode you *installed* with, not the mode this machine happens
to be capable of:

```
link mode: copy
.claude/agents    copied (in sync)
.claude/skills    copied (stale — re-run ai-sync)
```

`copied (stale …)` means the files were installed by `ai-sync` and have since drifted
from the repo. It is not a failed install, and re-running `ai-sync` is the fix.

**The one behavioural difference:** in symlink mode, editing a skill from inside the
editor edits the repo. In copy mode it doesn't — the editor has a copy. Edit in the
repo and re-run `ai-sync` to push changes out — which is the drift the line above
reports. Subagent and command edits made in
the editor *are* recovered, because the import step pulls them back before copying
out again; skills are not. Treat the repo as the place you edit.

### Other corporate-environment friction

| Thing | Effect | What to do |
|---|---|---|
| Extension installs blocked | No Claude Code at all | Needs IT; nothing here helps |
| Proxy / TLS inspection | Sign-in or model calls fail | Standard corporate proxy env vars |
| Antivirus scanning `bash` | Hooks slow or blocked | Skip hooks; they're optional |
| No admin rights | Can't install Python system-wide | Per-user Python install is fine |
| Roaming profile | `~/.claude` syncs across machines | Prefer copy mode; symlinks travel badly |

Only the first is a genuine blocker. Everything else has a way through.

---

## Appendix B — Windows

The harness was written on macOS. The portable parts are genuinely portable; three
things need attention.

```mermaid
flowchart TD
  D{"Developer Mode on?"}
  D -->|no| DF["symlinks fail <br/>→ empty harness"]
  D -->|yes| S{"~/.agents/skills <br/>created?"}
  S -->|no| SF["zero skills, <br/>no error message"]
  S -->|yes| P{"python3 resolves <br/>in Git Bash?"}
  P -->|no| PF["hooks silently no-op <br/>(everything else fine)"]
  P -->|yes| OK["fully working"]
```

**1. Developer Mode.** Settings → System → For developers → On. Windows blocks
symlink creation for normal users otherwise, and the entire design is symlinks.

**2. The skills link**, in PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.agents"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.agents\skills" `
         -Target "$env:USERPROFILE\ai-wow\skills"
```

**3. `python3`.** The hook scripts are bash and call `python3` by that exact name.
The python.org installer provides `python` and `py` but not `python3`. Either
install Python from the Microsoft Store — which ships a real `python3.exe` — or put
a `python3.bat` on PATH containing `@echo off` and `python %*`. Verify it from **Git
Bash**, not `cmd`; Git Bash is the shell the hooks actually run under.

Hooks are optional. Skills, subagents and commands don't touch them. If they won't
cooperate, delete the `hooks` key from `settings.json` and run `ai-sync` by hand.

---

## Appendix C — troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| No skills at all, no error | `~/.agents/skills` missing | Create it — `ai-sync` won't |
| Skills missing, subagents present | Skill farm not reconciled | Re-run `ai-sync`; `status` should show 16 |
| Symlink creation denied (corporate policy) | Developer Mode locked off | `ai-sync --copy` — Appendix A |
| Skill edit in the editor vanished | Copy mode: the editor holds a copy | Edit in the repo, re-run `ai-sync` |
| "privilege not held" on Windows | Developer Mode off | Enable it, re-run |
| Hooks never fire | `bash` or `python3` unresolvable | Appendix B step 3 |
| `status` exits 1 on managed-doc drift | `local.config.json` points at a repo that moved | Fix the path, or drop the entry |
| `taskman` refuses to run | No `.taskman.toml` in the tree | Add one at the project root |
| `taskman` can't connect | No Postgres, or no `TASKMAN_DATABASE_URL` | Start one; set the URL |
| `password authentication failed for user "taskman"` | Nothing set the URL, so the built-in default was used — it assumes a `taskman` role that your Postgres probably has no reason to have | Set `TASKMAN_DATABASE_URL` to a role that exists (section 6) |
| Board tests fail to collect, same auth error | `TASKMAN_TEST_DATABASE_URL` unset — the suite falls back to the same default | Pass a reachable URL whose role may `CREATE DATABASE` |
| Alembic "Can't locate revision" | Two taskman copies, one database, different migrations | Bring both to the same revision set |
