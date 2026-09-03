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

The page is **one board per repo**, not one per run. It is served from
`docs/plans/`, and every run in the repo is on it: the live ones under
`?runs=live`, the finished ones under `?runs=archive`. So the files split by
scope — the page and the marker belong to the repo, the run state to the run:

| File | Where | Written by | When |
|---|---|---|---|
| `tracker.html` | `docs/plans/` | copied from `~/.claude/skills/mow/tracker.html` | go §1, after preflight passes |
| `.board` | `docs/plans/` | `tracker_port.py`, when it answers `serve` | go §1, just before the server starts |
| `tracker.json` | `docs/plans/<stem>/dispatch/` | the orchestrator (you), via shell | at every run event (list below) |

`tracker.json` is the only per-run file and it **never moves**: a run is archived
by its own `run_status: shipped`, not by being relocated, copied or condensed.
Nothing writes a third file into `dispatch/` — the chat table is rendered from
`tracker.json` by `~/.claude/skills/mow/board_table.py` (see [The chat
board](#the-chat-board)), and the port is chosen by
`~/.claude/skills/mow/tracker_port.py` (see
[Serving](#serving-go-1-after-preflight)), whose only write is that `.board`
marker at the plans root.

All of it is disposable state — safe to delete after the stem ships, with one
consequence worth knowing: deleting a shipped run's `tracker.json` is what drops
it out of the archive view. Committing them with the plan folder is harmless.

## Serving (go §1, after preflight)

```bash
STEM=<stem>
# One stable board per repo. A second `/mow go` reuses this server instead of
# adding a port — sharing the page is the point, and `?runs=live` is where both
# runs show up. `serve` also writes docs/plans/.board, naming this repo: that
# marker is how the probe below tells our board from another project's.
mkdir -p docs/plans && cp -f ~/.claude/skills/mow/tracker.html docs/plans/tracker.html
TRACKER=$(python3 ~/.claude/skills/mow/tracker_port.py) || exit 1
PORT=${TRACKER%% *}; ACTION=${TRACKER##* }
# absolute -d: every repo's board serves a folder called docs/plans, so only the
# full path tells two projects' server processes apart at close-out
if [ "$ACTION" = serve ]; then
  python3 -m http.server "$PORT" -d "$PWD/docs/plans"   # background it
fi
# Prove the board on $PORT is this repo's before handing out the URL. Empty output
# plus a non-zero exit is the whole signal — never pipe this through `head`, which
# exits 0 on empty input and would report another project's board as healthy.
LIVE=$(python3 ~/.claude/skills/mow/tracker_port.py --owned --wait 5)
if [ "$LIVE" = "$PORT" ]; then
  # printed in every shell, so the board is always reachable by hand
  echo "tracker: http://localhost:$PORT/tracker.html            (live runs)"
  echo "         http://localhost:$PORT/tracker.html?runs=$STEM  (this run alone)"
else
  echo "warn: $PORT is not serving this repo's board (live: ${LIVE:-none}) — the board is not up"
fi
# terminal Claude Code has no pane to open it in — hand the page to the real browser
if [ -n "$TERM_PROGRAM$SSH_TTY" ] && [ "$LIVE" = "$PORT" ]; then
  if command -v open >/dev/null 2>&1; then open "http://localhost:$PORT/tracker.html"
  elif command -v start >/dev/null 2>&1; then start "http://localhost:$PORT/tracker.html"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "http://localhost:$PORT/tracker.html"
  fi
fi
```

Run the server in the background and open the URL it prints. The page polls
every 2s — no reload needed — and a bare URL lands on `?runs=live`. Record
`$PORT` into `tracker.json` as `board_port` in the same §1 write: the chat board
reads it for its link, so the table can never advertise a port this repo is not
on.

**Do not hardcode a port, and never kill by port alone.** Ownership is settled
by asking the server which repo it belongs to — a mow board answers `/.board`
with its own repo path — so another project's board is recognised and stepped
over instead of taken. The marker is load-bearing, not decoration: `docs/plans/`
looks identical from the outside whichever project it belongs to, so two repos
whose paths hash to one port would each render the other's runs under their own
bookmarked URL, with the page answering 200 the whole time. That is the same
failure the per-*run* port key was introduced to close on 2026-08-29 —
`builder-restrictions` and `product-analysis-ui` both computed 8378, `tracker.json`
answered 200 so the board looked healthy, and only a 404 on one run's own
`mockups/` gave it away — moved up a level and closed there instead. Two
concurrent runs in one repo now share a board deliberately, which is what the
**Parallel go is allowed** rule wanted all along.

The URL is stable per *repo* and worth bookmarking — on a second screen, where
animation keeps running even while the in-app browser pane is hidden (a hidden
pane freezes the animation clock). Unlike a per-run URL it outlives the run, so
the bookmark is still right next month. A hash collision with another project
costs one port, so trust the URL the block prints over a remembered one.

Stop the server at Integrate — but the board is the **repo's**, not this run's,
so stop it only when no run is still `running`, and match it by this repo's
absolute plans path (every board serves a folder named `docs/plans`; only the
full path tells two projects' processes apart). Never a bare `pkill`, which Git
Bash does not have:

```bash
# a fresh shell — the serving block's variables are long gone. Set this run's
# run_status to shipped BEFORE running this: that is what the count reads.
LEFT=$(python3 - <<'PY'
import glob, json
n = 0
for p in glob.glob("docs/plans/*/dispatch/tracker.json"):
    try:
        n += json.load(open(p)).get("run_status") == "running"
    except Exception:
        pass
print(n)
PY
) || LEFT=""
if [ -z "$LEFT" ]; then
  echo "warn: could not count live runs — leaving the board up"   # a lingering server beats a killed peer
elif [ "$LEFT" -gt 0 ]; then
  echo "board left up: $LEFT run(s) still live on it"
elif command -v pkill >/dev/null 2>&1; then
  pkill -f "http.server .* -d $PWD/docs/plans" || true
elif command -v taskkill >/dev/null 2>&1; then
  # Windows kills by PID, so confirm the listener is ours before touching it
  OWNED=$(python3 ~/.claude/skills/mow/tracker_port.py --owned)
  if [ -n "$OWNED" ]; then
    # Git Bash: netstat's local-address column gives the listener's PID
    TRACKER_PID=$(netstat -ano | grep ":$OWNED" | awk -v p=":$OWNED" '$2 ~ p"$" {print $NF; exit}')
    [ -n "$TRACKER_PID" ] && taskkill //F //PID "$TRACKER_PID" || true
  fi
else
  echo "warn: no pkill or taskkill — stop the board by hand (tracker_port.py --owned prints its port)"
fi
```

A run abandoned while still `running` holds the board up indefinitely. The page
already flags it ("board Nm behind"); setting its `run_status` is the fix, not a
harder kill.

### Views

The page takes three optional query params, all switchable live from the header.
The runs switch also rewrites the URL, so the view you are looking at is the one
you can bookmark:

| Param | Effect |
|---|---|
| `?runs=live` | **the default** — every run whose `run_status` is not `shipped`, running first. The board for "what is going on right now", and the URL to bookmark. |
| `?runs=archive` | the finished runs (`run_status: shipped`), newest first. Same files, read from where they were written; nothing was moved to get here. |
| `?runs=all` | both stacks on one page, live first. |
| `?runs=stemA,stemB` | only those runs, named. `?runs=<stem>` on its own is one run's board — the link the chat table posts. |
| `?view=compact` | the glance view for "where is this run": hubs read `W1`, `W2`, lanes keep their letters, and each lane hangs the todo it is on (`#8836 5v5 flag formation spine`) — no wave button, no detail tree. The view the chat table mirrors. |
| `?panels=tint` | colour the whole plate by wave status instead of the wave label button |

A filtered view that matches nothing still renders its header, so the switch
that walked you into an empty archive is never the one control the page drops.

The live and archive views re-read every run's `tracker.json` on each 2s poll —
that is how a run moves between them the moment its `run_status` changes — but
they only re-scan `docs/plans/` for *new* stems every 30s. A `/mow go` started
while the page is open therefore joins the board within half a minute rather
than instantly; the alternative was probing every plan folder in the repo twice
a second, most of which hold no dispatch at all.

`tracker.html` must sit in the directory being served, which is why go §1 copies
it to `docs/plans/` — one copy per repo, refreshed each run. The page also still
works when a single `dispatch/` folder is served directly and it finds a
`tracker.json` beside itself; that is the pre-refactor shape, nothing writes it
any more, and per-run copies of `tracker.html` left in old `dispatch/` folders
are dead weight you can delete.

### The chat board

The chat surface is a **markdown table**, not a widget and never an `iframe`. The
browser board on the §1 URL stays the live view; chat gets a table on every event
that changes the run's shape — fan-out, each lane reporting terminal (`done` /
`issues` / `error`), each gate verdict, close-out — and on nothing else. A todo
ticking over, an agent spawning, a pulse toggle: those are writes, not posts.

```bash
python3 ~/.claude/skills/mow/board_table.py docs/plans/<stem>/dispatch/tracker.json
```

Paste its stdout verbatim — do not hand-type a row. It prints:

| Piece | What it carries |
|---|---|
| header | title · stem · run status · active time · tokens · board URL, plus `board Nm behind` when a running board's `updated` is over four minutes old |
| one row per lane | wave (with its status and `parallel`/`sequential`), lane letter + brief + any `after`, todos as `done/total` plus the todo it is on, agents with status marks (nested reviewers as `parent › child`), lane status, active · tokens, findings as severity counts (`2C 4W 1S`) |
| a gate row per wave | the gate's status word, the wave's active · tokens, and the verdict text from `gate.detail` |
| findings block | criticals with their titles, everything else by taskman id, so no finding is dropped from chat |
| artifacts | lane + path, first 8, then `+N more` |

It derives its numbers from the same arithmetic as `tracker.html` — active time as
spans ∩ `.activity`, token rollups that never double-count — so the two surfaces
cannot disagree. Being plain text, it costs a few hundred tokens a post and stays
readable in the transcript after the server is stopped.

Why not the page itself: a widget sandbox enforces a CSP whose allowlist is
`cdnjs.cloudflare.com`, `esm.sh`, `cdn.jsdelivr.net`, `unpkg.com` and the two
Google Fonts hosts. `http://localhost:$PORT` is not on it and the request fails
silently, so a framed tracker renders as an empty white box while the server sits
there healthy. Inlining the whole renderer instead did work, and cost ~16k tokens
every post.

### Active time, and the activity trail

Durations on the board are **work, not wall clock**. A run left overnight used to
report 12h 51m; the number was honest elapsed time and useless. Two signals
replace it, both written by the hook, neither by you:

- **agent spans** — every subagent's `started`/`ended`, taken from the bounds of
  its own tool call. Overlapping lanes count once.
- **`dispatch/.activity`** — an epoch-seconds sample per tool call, at most one
  per 30s. A subagent's own tool calls fire the hook under the parent session, so
  the trail is dense while anything is running and empty while nobody is.

Active time is the **intersection**: time an agent was open *and* someone was
working. That matters because the idle hides *inside* spans — one real lane
held a single agent open for 12.7h across a night while every other agent that
day ran 4–13 minutes. Intersecting cut a 12h span to the 1h 20m actually worked.
Gaps longer than 5 minutes with no tool call at all count as idle. Hover any
duration for `active · elapsed · idle`.

Both files are disposable. Delete `.activity` and durations fall back to raw
spans; delete both and they fall back to wall clock, which is what boards written
before the hook still show.

### The board is only as live as your writes

The page polls every 2s, but **nothing changes until you write `tracker.json`**.
Elapsed times keep climbing on their own (they are computed from `started` in the
browser), which makes a stale board look busy: a lane can sit at `running` with a
ticking clock long after its agent finished. If a `running` run's `updated` is
more than four minutes old the header says **"board Nm behind"** with a red dot —
that is the page telling you the writer is lagging, not the run.

So: write at every event in the table below, and **write the lane/agent terminal
state as soon as the report lands** — before you verify its claims, not after.
Verification can take many minutes, and during it the board is lying.

## tracker.json schema (v1)

```json
{
  "schema": 1,
  "stem": "play-model",
  "title": "Play Model Wave 2",
  "run_status": "running",
  "board_port": 8362,
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

- `board_port` is the port §1 actually served the repo's board on — written
  once, at skeleton time. `board_table.py` links to it rather than recomputing,
  so the chat table cannot point at a port another project's board won on a hash
  collision. Every run in the repo carries the same value; the table appends
  `?runs=<stem>` to reach this one. Absent on a board written before the field
  existed; the table falls back to the derived home port.
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
| go §1 load done | full skeleton from INDEX: every wave/lane/todo `pending`, `run_status: running`, agents seeded empty; set run `started`; stamp each wave's `parallelism` from the INDEX map; set `board_port` to the port the serving block printed |
| wave fan-out | **post the chat board** (see above) after the write; wave + its lanes → `running`; set wave `started` (a real timestamp — `run.started` too, never a placeholder date); append each spawned agent (`running`) with its own `started` and Toolkit skills as `pending` |
| lane reports done (write **before** verifying its claims) | **post the chat board** after the write; lane agent → `done` with its `ended`; reconcile skills + artifacts from its `## Verification`; **write `dispatch/verification/<brief>`** (the four-bullet block — the wave gate reads the file, not chat); lane → `done` (or `error` if it failed); todos → per report; copy any reported `tokens` onto the agent/lane |
| wave lanes all terminal | set wave `ended`; roll up `tokens` from lanes/agents if the runtime gave them |
| review gate starts | `gate.status: running`; append reviewer agents |
| gate verdict | **post the chat board** after the write; clean → gate `done`; findings filed → gate + affected lanes `issues` with `findings[]`; critical unfixed → `error` |
| fix lane spawned | append it like any agent; re-review updates gate again |
| operator asks to toggle pulse | set `pulse: true` or `false` immediately (chat: "pulse off" / "pulse on") |
| Integrate, before close-out | **reconcile** — run `python -m taskman.mow.check_tracker docs/plans/<stem>` for the mechanical half (non-terminal statuses, missing gates, findings with no board row; `started`/`ended` gaps and unreconciled skills report without blocking), then a `general-purpose` subagent for the half it cannot see: this file against every lane's `## Verification`, the gate verdicts, and the filed findings, reporting discrepancies only (see go §3). Apply both lists, then set `run_status: shipped`; **post the close-out table** (`board_table.py`) — the last board of the run, and the one the transcript keeps after the server is stopped |

**Never transcribe a rendered value back into the field that produced it (L14).** The tracker header
renders UTC in the viewer's local zone; reading a time off the board and writing it back as a UTC
stamp put every later write hours in the future, so elapsed time computed negative and froze a running
lane at 0s. Stamp with `date -u` at the moment of the event, and where a time is genuinely unknown
**omit the field** — a missing duration announces itself, a fabricated one does not.

Every write also bumps `updated` (ISO 8601) — though a `PostToolUse` hook
(`hooks/stamp-tracker.py`) now stamps it for you on any Write/Edit of a
`dispatch/tracker.json`, so a forgotten bump no longer strands the board. Set it
yourself anyway when you can; the hook is the safety net, not the contract. Full-file
Write is fine — the file is small; do not stream partial JSON (the page tolerates
one bad poll but not many).

**Write tracker.json via shell, not the harness Edit/Write tools (L29).** The same hook
re-serializes the file after tool calls, so the harness's stale-file check races it and loses:
Edit's `old_string` stops matching after the hook reformats, and a Read→Write round-trip fails
"modified since read" because the Read itself triggered another hook pass. Write atomically from
Bash instead — heredoc to `tracker.json.tmp`, validate with `json.load`, `mv` over the target —
or mutate in one step (`python3 - <<EOF` load→edit→dump). The hook layers its stamps on top of a
shell write harmlessly.

The same hook also stamps **agent `started` / `ended`** from the spawn's own tool
call: `PreToolUse` records the spawn in `dispatch/.agent-times.json`,
`PostToolUse` pairs the return with it and merges the span into the matching
agent. A span with no agent entry to land on yet waits in that ledger and is
retried on every later tracker write, so the two can happen in any order. It
matches on the lane whose `brief` the prompt names, falling back to the
first unstamped agent whose `name` starts with the `subagent_type` — a heuristic,
unlike the `updated` stamp, so it only ever fills a field you left empty. Keep
stamping agents yourself: your value always wins, and the hook is Claude-only
(Cursor has no Task event). The ledger is disposable run state; delete it freely.

**A backgrounded lane gets only `started` from the hook — its `ended` is yours.**
An async spawn's `PostToolUse` fires when the *launch* returns, so it carries no
completion information; the hook deliberately writes no `ended` for one. Before
this was fixed, every AFK lane was stamped as finishing ~20s after spawn, which
froze that lane's clock on the board and made a live multi-minute run read as
dead — visible only while the lane was still running, because the orchestrator's
own write overwrote the bad value the moment the report landed. This is why the
write-points table says to write a lane's terminal state **as soon as the report
lands, before verifying its claims**: for background lanes nothing else will.
