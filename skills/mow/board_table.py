#!/usr/bin/env python3
"""Render a mow board as a markdown table for chat.

The browser board stays the live surface; chat gets a table posted at wave
boundaries. This is not a hand-typed card — it reads `tracker.json`, and it
ports the page's own arithmetic (`tracker.html`) so the two surfaces cannot
disagree on a number:

  - **active time**, not wall clock: agent spans intersected with the
    `.activity` trail, 5-minute gaps counted as idle, an open span ceilinged
    one staleness window past the last write.
  - **token rollup** without double counting: a lane prefers its own figure
    over the sum of its agents, a wave its own over the sum of its lanes.

The board URL comes from `board_port` in the file — the port `/mow go` actually
served on — falling back to `tracker_port.derive()` for a board written before
that field existed. It links straight to this run (`?runs=<stem>`) on the repo's
one shared board, so the table lands on the run it describes rather than on the
whole live view. Run it from the repo root the tracker was served from.

    python3 board_table.py docs/plans/<stem>/dispatch/tracker.json
"""

import json
import os
import sys
import time
from urllib.parse import quote
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

import tracker_port

IDLE_GAP_MS = 300_000       # 5 min with no tool call at all = idle
SAMPLE_MS = 30_000          # the hook's sampling interval — a sample covers it
STALE_AFTER_MS = 240_000    # a running board this far behind is flagged
TITLE_CAP = 34
ARTIFACT_CAP = 8
AGENT_CAP = 24
AGENTS_SHOWN = 4

MARK = {"pending": "○", "running": "●", "done": "✓", "issues": "⚠",
        "error": "✗", "shipped": "✓"}
SEV = {"critical": "C", "warning": "W", "suggestion": "S"}


def st(v):
    v = (v or "pending").lower()
    return v if v in MARK else "pending"


def tag(status):
    s = st(status)
    return f"{MARK[s]} {s}"


def esc(text):
    return str(text or "").replace("|", "\\|").replace("\n", " ").strip()


def clip(text, cap=TITLE_CAP):
    text = esc(text)
    return text if len(text) <= cap else text[: cap - 1].rstrip() + "…"


# ---------- numbers, ported from tracker.html ----------

def parse_tokens(t):
    if t is None or t == "":
        return None
    if isinstance(t, bool):
        return None
    if isinstance(t, (int, float)):
        return t
    if isinstance(t, str):
        try:
            return float(t)
        except ValueError:
            return None
    if isinstance(t, dict):
        if isinstance(t.get("total"), (int, float)):
            return t["total"]
        a = (t.get("input") or t.get("in") or 0) + (t.get("output") or t.get("out") or 0)
        return a or None
    return None


def _to_fixed(value, digits):
    """`Number.prototype.toFixed` — rounds half *away from zero* on the double.
    Python's own formatting rounds half to even (12.5 -> "12"), so the page and
    the table would disagree on every exact half."""
    return str(Decimal(value).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def _drop_trailing_zero(text):
    r"""The page's `.replace(/\.0$/, "")` — a trailing `.0`, never a trailing digit.
    `.rstrip("0")` here turned 80464 into `8k tok` and 100000 into `1k tok`."""
    return text[:-2] if text.endswith(".0") else text


def fmt_tokens(n):
    if n is None:
        return None
    a = abs(n)
    if a >= 1e6:
        return _drop_trailing_zero(_to_fixed(n / 1e6, 0 if a >= 1e7 else 1)) + "M tok"
    if a >= 1000:
        return _drop_trailing_zero(_to_fixed(n / 1000, 0 if a >= 10000 else 1)) + "k tok"
    return f"{_to_fixed(n, 0)} tok"


def fmt_dur(ms):
    if ms is None or ms < 0:
        return None
    s = round(ms / 1000)
    if s < 60:
        return f"{s}s"
    m, r = divmod(s, 60)
    if m < 60:
        return f"{m}m {r}s" if r else f"{m}m"
    h, m2 = divmod(m, 60)
    return f"{h}h {m2}m" if m2 else f"{h}h"


def parse_iso(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp() * 1000
    except ValueError:
        return None


def activity_windows(path):
    try:
        with open(path, encoding="utf-8") as fh:
            samples = sorted(float(x) * 1000 for x in fh.read().split() if x.strip())
    except (OSError, ValueError):
        return []
    out = []
    for t in samples:
        if t <= 0:
            continue
        if out and t - out[-1][1] <= IDLE_GAP_MS:
            out[-1][1] = t + SAMPLE_MS
        else:
            out.append([t, t + SAMPLE_MS])
    return out


def merge_spans(spans):
    out = []
    for sp in sorted(spans):
        if out and sp[0] <= out[-1][1]:
            out[-1][1] = max(out[-1][1], sp[1])
        else:
            out.append(list(sp))
    return out


def intersect_ms(a, b):
    i = j = 0
    total = 0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if hi > lo:
            total += hi - lo
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return total


def agents_under(scope):
    """Every agent under a run, a wave or a lane — nested agents included."""
    if isinstance(scope, dict) and scope.get("waves") is not None:
        lanes = [l for w in scope["waves"] or [] for l in (w or {}).get("lanes") or []]
    elif isinstance(scope, dict) and scope.get("lanes") is not None:
        lanes = scope["lanes"] or []
    else:
        lanes = [scope]

    def walk(agents):
        for a in agents or []:
            if isinstance(a, dict):
                yield a
                yield from walk(a.get("agents"))

    return [a for l in lanes for a in walk((l or {}).get("agents"))]


def span_of(agent, ceil_ms):
    t0 = parse_iso(agent.get("started"))
    if t0 is None:
        return None
    t1 = parse_iso(agent.get("ended"))
    if t1 is None:
        t1 = ceil_ms if st(agent.get("status")) == "running" else None
    return [t0, t1] if t1 is not None and t1 >= t0 else None


def active_ms(scope, ceil_ms, activity):
    spans = [s for s in (span_of(a, ceil_ms) for a in agents_under(scope)) if s]
    if not spans:
        return None
    merged = merge_spans(spans)
    if activity:
        return intersect_ms(merged, activity)
    return sum(s[1] - s[0] for s in merged)


def lane_tokens(lane):
    direct = parse_tokens(lane.get("tokens"))
    if direct is not None:
        return direct
    vals = [parse_tokens(a.get("tokens")) for a in agents_under(lane)]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def wave_tokens(wave):
    direct = parse_tokens(wave.get("tokens"))
    if direct is not None:
        return direct
    vals = [lane_tokens(l) for l in wave.get("lanes") or []]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def run_tokens(board):
    direct = parse_tokens(board.get("tokens"))
    if direct is not None:
        return direct
    vals = [wave_tokens(w) for w in board.get("waves") or []]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def stats(ms, tokens):
    parts = [p for p in (fmt_dur(ms), fmt_tokens(tokens)) if p]
    return " · ".join(parts) if parts else "—"


# ---------- cells ----------

def todos_cell(lane):
    todos = lane.get("todos") or []
    if not todos:
        return "—"
    done = sum(1 for t in todos if st(t.get("status")) in ("done", "issues"))
    running = next((t for t in todos if st(t.get("status")) == "running"), None)
    focus = running or next((t for t in todos if st(t.get("status")) == "pending"), None)
    count = f"{done}/{len(todos)}"
    if focus is None:
        return count
    label = " ".join(p for p in (esc(focus.get("id")), clip(focus.get("title"))) if p)
    return f"{count} · {label}" if label else count


def agents_cell(lane):
    def render(agents):
        out = []
        for a in agents or []:
            if not isinstance(a, dict):
                continue
            cell = f"{clip(a.get('name') or 'agent', AGENT_CAP)} {MARK[st(a.get('status'))]}"
            kids = render(a.get("agents"))
            out.append(f"{cell} › {kids}" if kids else cell)
        tail = len(out) - AGENTS_SHOWN
        return " · ".join(out[:AGENTS_SHOWN]) + (f" · +{tail}" if tail > 0 else "")

    return render(lane.get("agents")) or "—"


def findings_cell(lane):
    """Counts by severity — a real lane files ten of these, and ten titles in one
    cell is not a table any more. Titles go under the table, ids all of them."""
    findings = lane.get("findings") or []
    if not findings:
        return "—"
    counts = {}
    for f in findings:
        counts[SEV.get((f.get("severity") or "").lower(), "·")] = \
            counts.get(SEV.get((f.get("severity") or "").lower(), "·"), 0) + 1
    return " ".join(f"{counts[k]}{k}" for k in ("C", "W", "S", "·") if k in counts)


def findings_block(board):
    """Criticals carry their title; everything else carries its task id, which is
    what makes it findable on the taskman board. Nothing is silently dropped."""
    lines = []
    for wave in board.get("waves") or []:
        for lane in wave.get("lanes") or []:
            findings = lane.get("findings") or []
            if not findings:
                continue
            crit = [f for f in findings if (f.get("severity") or "").lower() == "critical"]
            rest = [f for f in findings if f not in crit]
            parts = [f"C {esc(f.get('task'))} {clip(f.get('title'), 44)}".strip() for f in crit]
            if rest:
                ids = " ".join(esc(f.get("task")) for f in rest if f.get("task"))
                sev = "/".join(
                    f"{sum(1 for f in rest if (f.get('severity') or '').lower() == name)}{letter}"
                    for name, letter in (("warning", "W"), ("suggestion", "S"))
                    if any((f.get("severity") or "").lower() == name for f in rest)
                )
                parts.append(f"{sev or f'{len(rest)}·'}: {ids}".strip())
            lines.append(f"- **{esc(lane.get('lane'))}** — " + " · ".join(parts))
    return lines


def lane_label(lane):
    bits = esc(lane.get("lane") or "?")
    brief = esc(lane.get("brief"))
    if brief:
        bits += f" `{brief}`"
    after = lane.get("after") or []
    if after:
        bits += f" (after {', '.join(esc(x) for x in after)})"
    return bits


def build(path):
    with open(path, encoding="utf-8") as fh:
        board = json.load(fh)
    activity = activity_windows(os.path.join(os.path.dirname(os.path.abspath(path)), ".activity"))
    updated = parse_iso(board.get("updated"))
    now = time.time() * 1000
    ceil_ms = min(now, updated + STALE_AFTER_MS) if updated is not None else now

    lines = []
    head = [f"**{esc(board.get('title') or board.get('stem') or 'mow run')}**"]
    if board.get("stem"):
        head.append(f"`{esc(board['stem'])}`")
    head.append(tag(board.get("run_status")))
    run_dur = fmt_dur(active_ms(board, ceil_ms, activity))
    run_tok = fmt_tokens(run_tokens(board))
    head.append(" · ".join(p for p in (f"{run_dur} active" if run_dur else None, run_tok) if p) or "—")
    # one board per repo, so the stem is what narrows the page to this run
    port = board.get("board_port") or tracker_port.derive()
    stem = board.get("stem") or ""
    view = f"?runs={quote(stem)}" if stem else "?runs=live"
    head.append(f"[board](http://localhost:{port}/tracker.html{view})")
    lines.append(" · ".join(head))
    if updated is not None and st(board.get("run_status")) == "running" and now - updated > STALE_AFTER_MS:
        lines.append("")
        lines.append(f"> ⚠ board {fmt_dur(now - updated)} behind — `tracker.json` has not been written since "
                     f"{datetime.fromtimestamp(updated / 1000, timezone.utc).strftime('%H:%M UTC')}.")
    lines.append("")
    if not (board.get("waves") or []):
        lines.append("_no waves on the board yet._")
        return "\n".join(lines) + "\n"
    lines.append("| Wave | Lane | Todos | Agents | Status | Active | Findings |")
    lines.append("|---|---|---|---|---|---|---|")

    for wave in board.get("waves") or []:
        lanes = wave.get("lanes") or []
        shape = wave.get("parallelism") or ("parallel" if len(lanes) > 1 else "sequential")
        wave_cell = f"**W{esc(wave.get('wave'))}** {MARK[st(wave.get('status'))]} · {shape}"
        wave_total = stats(active_ms(wave, ceil_ms, activity), wave_tokens(wave))
        first = True
        for lane in lanes:
            lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
                wave_cell if first else "",
                lane_label(lane),
                todos_cell(lane),
                agents_cell(lane),
                tag(lane.get("status")),
                stats(active_ms(lane, ceil_ms, activity), lane_tokens(lane)),
                findings_cell(lane),
            ))
            first = False
        gate = wave.get("gate") or {}
        lines.append("| {} | _gate_ | — | — | {} | {} | {} |".format(
            wave_cell if first else "",
            tag(gate.get("status")),
            wave_total,
            clip(gate.get("detail"), 64) or "—",
        ))

    artifacts = [
        (esc(lane.get("lane")), esc(art.get("label") or art.get("path")), esc(art.get("path")))
        for wave in board.get("waves") or []
        for lane in wave.get("lanes") or []
        for agent in agents_under(lane)
        for art in agent.get("artifacts") or []
    ]
    block = findings_block(board)
    if block:
        lines.append("")
        lines.append("**Findings** (criticals titled; the rest by task id — all on the taskman board)")
        lines.extend(block)

    if artifacts:
        shown = artifacts[:ARTIFACT_CAP]
        tail = len(artifacts) - len(shown)
        lines.append("")
        lines.append("**Artifacts** — " + " · ".join(
            f"{lane} `{path or label}`" for lane, label, path in shown)
            + (f" · +{tail} more" if tail > 0 else ""))
    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    sys.stdout.write(build(sys.argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
