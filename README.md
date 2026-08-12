# ai-wow

### *AI — Way of Working*

**A portable way of working with AI coding agents.** Skills, subagents, slash
commands, lifecycle hooks, and a durable task board — versioned in one repo, synced
into Claude Code and Cursor by one script, identical on every machine.

A team has a way of working: standards everyone follows, specialists you hand things
to, and checks that run whether or not anyone remembers them. Agents don't inherit
any of that by default — every conversation starts from nothing. This is that way of
working, made portable and enforced.

```bash
git clone <this-repo> ~/ai-wow
mkdir -p ~/.agents && ln -s ~/ai-wow/skills ~/.agents/skills
python3 ~/ai-wow/bin/ai-sync
python3 ~/ai-wow/bin/ai-sync status
```

> **Start here:** [`HOW-TO-USE.human.md`](HOW-TO-USE.human.md) if you're a person ·
> [`HOW-TO-USE.agent.md`](HOW-TO-USE.agent.md) if you're an agent.

---

## What's in it

| | Count | |
|---|---|---|
| **Skills** | 14 | Procedures an agent loads into its own context on demand |
| **Subagents** | 7 | Specialists with isolated context and restricted tools |
| **Slash commands** | 1 | `/diagnose` — a discipline for hard bugs |
| **Hooks** | 3 | Guarantees that fire on lifecycle events, not on the agent's judgment |
| **Board** | 1 package | `taskman` — Feature → PBI → Task, living spec, decision log |

Everything except the board runs on a bare clone: **no configuration, no API keys,
no database.**

### One optional extra

`impeccable` — the UI design skill — is referenced throughout the docs but is **not
bundled**: it is Apache-2.0 and roughly 99 files, better taken from its own source
than vendored here.

```bash
npx skills add pbakaus/impeccable
```

Nothing else depends on it. See [`THIRD-PARTY.md`](THIRD-PARTY.md).

---

## How it works

One repo is the source of truth. Portable content is **symlinked** into each editor,
so the editor's directory *is* this repo — zero drift, and edits made from inside an
editor land back here. Hook registration and MCP config use different schemas per
editor, so those are **rendered** from one neutral definition instead.

```mermaid
flowchart LR
  subgraph REPO["ai-wow — canonical"]
    direction TB
    A["skills/ · agents/ · commands/<br/>hooks/ · global/CLAUDE.md"]
    B["hooks.def.json · mcp.json"]
  end
  A -->|"symlink"| C["~/.claude"]
  A -->|"symlink"| D["~/.cursor"]
  B -->|"render"| C
  B -->|"render"| D
  C -.->|"edits write back"| A
  D -.->|"edits write back"| A
```

`ai-sync` runs `import → link → reconcile skills → render → commit`, and is
registered as a session-end hook so it happens on its own.

> [!IMPORTANT]
> `ai-sync` **will not create `~/.agents/skills`**. Without that symlink the skill
> step returns early and you get zero skills with no error. Make it before the first
> sync — it's the one step that fails silently.

> [!WARNING]
> `ai-sync` commits with `git add -A` and pushes without prompting. Keep secrets out
> of the working tree.

---

## The three mechanisms

| | Context | Fires | Use for |
|---|---|---|---|
| **Skill** | the running agent's own | when relevant | a procedure worth following |
| **Subagent** | fresh and isolated | on explicit call | a job that needs a clean slate |
| **Hook** | none — shell | every time | something that must not be skipped |

A guarantee implemented as a skill is only a suggestion. Match the mechanism to the
intent.

---

## The build loop

```mermaid
flowchart LR
  T["plan"] --> MP["/mow plan"] --> D["briefs + wave map"]
  D --> GO["/mow go"] --> R["review gate"] --> S["ship-check"] --> W["/wrap-up"]
```

Work is decomposed into per-todo briefs and a wave map, fanned out to subagents wave
by wave with a review gate between waves, then closed out through an evidence gate
that will not pass while changed files are unattributed or tasks are left in flight.

**The hard rule:** lanes in the same wave own disjoint file sets. Overlap is detected
before fan-out, not discovered afterwards.

---

## Layout

| Path | What |
|---|---|
| `skills/` | 14 skills, each `<name>/SKILL.md` |
| `agents/` | 7 subagent definitions |
| `commands/` | Slash commands |
| `hooks/` + `hooks.def.json` | Hook scripts and their neutral registration |
| `global/CLAUDE.md` | Global instructions symlinked to `~/.claude/CLAUDE.md` |
| `taskman/` | The board package — CLI, models, migrations, 142 tests |
| `docs/workflow/` | Work-loop, dispatch bridge, compact template |
| `templates/` | Bootstrap checklist for adopting the harness in a new repo |
| `bin/ai-sync` | The sync tool |
| `local.config.example.json` | Copy to `local.config.json` (gitignored) for machine paths |

Machine-specific configuration lives only in `local.config.json`, which is
gitignored. Nothing in the tracked tree points at a particular machine or project.

---

## Requirements

- **Core** — Python 3 and git. That's it.
- **Board** — Postgres (the schema uses `ARRAY` and `JSONB`; SQLite is not a
  substitute) and Python 3.12+.
- **Windows** — Developer Mode for symlinks, Git Bash, and a `python3` on PATH.
  See Appendix A of the human guide.

Run the board's tests against a throwaway database:

```bash
cd taskman
TASKMAN_TEST_DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/taskman_test" \
  uv run --group dev pytest -q
```

---

## Docs

| Doc | For |
|---|---|
| [`HOW-TO-USE.human.md`](HOW-TO-USE.human.md) | Setup, mental model, day-to-day use, Windows appendix |
| [`HOW-TO-USE.agent.md`](HOW-TO-USE.agent.md) | Invariants, decision trees, procedures with VERIFY conditions |
| [`templates/BOOTSTRAP.md`](templates/BOOTSTRAP.md) | Adopting the harness in a new repo |
| [`docs/workflow/work-loop.md`](docs/workflow/work-loop.md) | The operator's idea → board → build loop |
| [`taskman/taskman/README.md`](taskman/taskman/README.md) | The board package in depth |
| [`THIRD-PARTY.md`](THIRD-PARTY.md) | Which skills came from elsewhere, and under what terms |

---

## License

[MIT](LICENSE) for everything original to this repository — the eleven original
skills, the seven subagents, `taskman`, `ai-sync`, and the docs.

Three bundled skills come from other projects and keep their own licenses:
`tdd` and `grill-with-docs` from [mattpocock/skills](https://github.com/mattpocock/skills)
(MIT), and `playwright-cli` from
[microsoft/playwright-cli](https://github.com/microsoft/playwright-cli) (Apache-2.0).
All three are unmodified; each carries its upstream license text in its own folder.
Details in [`THIRD-PARTY.md`](THIRD-PARTY.md).
