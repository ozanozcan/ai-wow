# mow live tracker — go-mode contract

The tracker is a live visual of a `/mow go` run, drawn as a left-to-right flow.
`mow go` is a green traffic light — the start signal — feeding the first wave.
Each wave sits on its own plate: the wave number in the top-left corner with its
start time beneath, its shape and cost beside it (`A ‖ B → C · 12m 30s · 125k tok`),
and the wave label as a status-coloured button in the top-right. The hub **forks**
into every lane that starts with it; a lane declaring `after` **joins** from the
lanes it waits on; the last stage rejoins at the review gate, which hands the run
to the next wave's hub. Under each lane hangs its detail — todos (chained circles =
sequential), subagents in calling order with what they spent, the skills and tools
each invoked, and artifacts as file icons with a colour-coded extension badge.

Status colors: green done · yellow passed-with-issues · red failed · gray queued —
and anything **in progress carries a rotating shine ring** (white/grey with blue
accents, 16s clockwise) on a neon-white fill whose glow heartbeats in a lub-dub
cycle. With `pulse: false` the ring only turns; nothing shines. Skill and tool
frames spin their chain-link ring while running. Single typeface: Onest (embedded).
Agent, skill, and tool circles carry kind icons (robot / wand / wrench) in neutral
ink. Letters on colored fills are neutral ink — never a hue-on-hue tint.

Two files, both living in `docs/plans/<stem>/dispatch/`:

| File | Written by | When |
|---|---|---|
| `tracker.html` | copied once from `~/.claude/skills/mow/tracker.html` | go §1, after preflight passes |
| `tracker.json` | the orchestrator (you), via Write/Edit | at every run event (list below) |

Both are disposable run state — safe to delete after the stem ships. Committing
them with the plan folder is harmless.

## Serving (go §1, after preflight)

```bash
# one stable port per repo, so two projects' runs never land on each other
PORT=$(python3 -c "import hashlib,os;print(8300+int(hashlib.md5(os.getcwd().encode()).hexdigest(),16)%80)")
# clear this repo's own stale tracker from an earlier run (matches only that server)
pkill -f "http.server $PORT" || true
python3 -m http.server $PORT -d docs/plans/<stem>/dispatch
echo "tracker: http://localhost:$PORT/tracker.html"
```

Run it in the background and open the URL it prints. The page polls
`tracker.json` every 2s — no reload needed.

**Do not hardcode a port and do not skip the kill.** A server left behind by an
earlier run keeps serving *that* run's dispatch folder: the board loads, looks
live, and shows another run's data. Deriving the port from the repo path means
FTM and HLC can run at once, and each project's URL stays the same every run —
worth bookmarking on a second screen, where animation keeps running even while
the in-app browser pane is hidden (a hidden pane freezes the animation clock).

Stop the server at Integrate: `pkill -f "http.server $PORT"`.

## tracker.json schema (v1)

```json
{
  "schema": 1,
  "stem": "play-model",
  "title": "Play Model Wave 2",
  "run_status": "running",
  "pulse": true,
  "started": "2026-08-14T12:00:00Z",
  "updated": "2026-08-14T12:07:30Z",
  "waves": [
    {
      "wave": 1,
      "status": "running",
      "parallelism": "parallel",
      "started": "2026-08-14T12:01:00Z",
      "ended": null,
      "tokens": 48200,
      "gate": { "status": "pending" },
      "lanes": [
        {
          "lane": "A",
          "brief": "01-task-3074.md",
          "role": "code-edit",
          "afk": true,
          "status": "running",
          "started": "2026-08-14T12:01:05Z",
          "tokens": 26100,
          "todos": [
            { "id": "#3074", "title": "Add rest timer model", "status": "done" },
            { "id": "#3075", "title": "Wire timer endpoint", "status": "running" }
          ],
          "agents": [
            {
              "name": "tdd-builder",
              "status": "running",
              "started": "2026-08-14T12:01:10Z",
              "tokens": 18400,
              "detail": "worktree: .claude/worktrees/…",
              "skills": [
                { "name": "tdd", "status": "done" },
                { "name": "test-coverage", "status": "pending" }
              ],
              "tools": [
                { "name": "pytest workouts/", "status": "done" }
              ],
              "artifacts": [
                { "label": "timer_test.py", "path": "workouts/tests/timer_test.py" }
              ]
            }
          ],
          "findings": [
            { "task": "#3101", "severity": "warning", "title": "N+1 on timer list" }
          ]
        },
        {
          "lane": "C",
          "brief": "03-task-3077.md",
          "role": "code-edit",
          "afk": true,
          "status": "pending",
          "after": ["A", "B"],
          "todos": [
            { "id": "#3077", "title": "Wire the two halves together", "status": "pending" }
          ],
          "agents": []
        }
      ]
    }
  ]
}
```

**Status vocabulary** (waves, gates, lanes, todos, agents, skills — same five):
`pending` · `running` · `done` · `issues` (passed with issues) · `error` (failed).
`run_status` additionally allows `shipped` (rendered as done).

Field notes:

- `lane` letters follow the **A→Z rule** (SKILL.md plan §3): lettered in wave
  order from `A`, and the final lane of the run is always `Z` (e.g. 6 lanes =
  A B C D E Z). A single-lane run is just `A`. Hard cap 26 lanes (A–Y + Z).
- `agents` is an **ordered array = calling order**. Append on spawn, never reorder.
  Reviewer subagents from the wave gate go on the lane they reviewed (or the first
  lane) with `name` like `django-reviewer`.
- `skills` under an agent = skills that agent invoked, in order, as far as the
  orchestrator knows them: at spawn seed from the brief's `## Toolkit` as
  `pending`; on lane completion reconcile from the lane's `## Verification` block
  (invoked → `done`, never invoked → drop or leave `pending`).
- `tools` (optional, per agent) = **important** tool calls only — the test run, the
  migration dry-run, the deploy command — not every Read/Edit. Same
  `{name, status, detail}` shape as skills; rendered smaller.
- `artifacts` = files the lane reported creating (Verification "Artifacts:" line,
  mockups, reports). `label` short, `path` full (shown on hover).
- `findings` mirror **taskman review-finding tasks** — a lane goes `issues` only
  when its findings are filed on the board (mow go §2b.3); put the task id in
  `task`. No board row → not a tracked finding.
- `pulse` (optional, default `true`) = in-progress **heartbeat** on the shine
  ring, bloom, and running disc. Spin stays 16s clockwise either way. The
  operator toggles this by chatting with the orchestrator ("pulse off", "turn
  the heartbeat back on") — flip the flag immediately; do not wait for a run
  event. The page applies the class without remounting nodes.
- `detail` (agents/skills/todos) is optional hover text. v2 will hang taskman
  decisions/tags here.
- `after` (optional, per lane) = the lanes this one waits on, e.g.
  `"after": ["A", "B"]`. This is what draws the flow: a wave hub **forks** into
  every lane with no `after`, those lanes **join** into the lanes that name
  them, and the last stage rejoins at the gate. A wave can mix both shapes —
  `A ‖ B` running together and then `C` after both is one wave, rendered
  `A ‖ B → C`. Name only real dependencies; a cycle is ignored.
- `parallelism` (optional, per wave) = `"parallel"` or `"sequential"`. The
  fallback when **no** lane in the wave declares `after`: `parallel` forks every
  lane off the hub at once, `sequential` chains them one after another. Omit
  both and the page infers it: two or more lanes → parallel, one → sequential.
  Sequential todos *inside* a lane are a different axis — they render as a
  chained row of circles under the lane, on parallel and sequential waves alike.
- `started` / `ended` (optional ISO 8601, per **wave, lane or agent**) =
  wall-clock bounds. Anything with `started` and no `ended` shows a live
  duration that ticks, so a running subagent's elapsed time climbs on the board.
  Waves and lanes render it under the circle, agents beside the name, both as
  `duration · tokens`. Stamp an agent's `started` when you spawn it and its
  `ended` when its report lands. Omit rather than guess.
- `tokens` (optional, per wave, lane, or agent) = a number (total) or
  `{ "input": N, "output": N, "total": N }` / `{ "in": N, "out": N }`. Totals
  roll up without double-counting: a lane prefers its own figure over the sum
  of its agents, and a wave prefers its own over the sum of its lanes. Unknown
  stays an em dash — never invent a count. Record usage when the runtime
  reports it (Claude Code / Cursor agent totals); skip the field when it
  doesn't.

## Write points (the event → write table)

| Event | Write |
|---|---|
| go §1 load done | full skeleton from INDEX: every wave/lane/todo `pending`, `run_status: running`, agents seeded empty; set run `started`; stamp each wave's `parallelism` from the INDEX map |
| wave fan-out | wave + its lanes → `running`; set wave `started`; append each spawned agent (`running`) with its own `started` and Toolkit skills as `pending` |
| lane reports done | lane agent → `done` with its `ended`; reconcile skills + artifacts from its `## Verification`; lane → `done` (or `error` if it failed); todos → per report; copy any reported `tokens` onto the agent/lane |
| wave lanes all terminal | set wave `ended`; roll up `tokens` from lanes/agents if the runtime gave them |
| review gate starts | `gate.status: running`; append reviewer agents |
| gate verdict | clean → gate `done`; findings filed → gate + affected lanes `issues` with `findings[]`; critical unfixed → `error` |
| fix lane spawned | append it like any agent; re-review updates gate again |
| operator asks to toggle pulse | set `pulse: true` or `false` immediately (chat: "pulse off" / "pulse on") |
| Integrate, before close-out | **reconcile** — a `general-purpose` subagent diffs this file against every lane's `## Verification`, the gate verdicts, and the filed findings, and reports discrepancies only (see go §3). Apply its list, then set `run_status: shipped` |

Every write also bumps `updated` (ISO 8601). Full-file Write is fine — the file is
small; do not stream partial JSON (the page tolerates one bad poll but not many).
