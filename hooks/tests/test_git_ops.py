#!/usr/bin/env python3
"""Tests for hooks/git-ops.py — the git-operation logger — and bin/git-timeline.

Plain `python3 hooks/tests/test_git_ops.py` — no pytest, because the
interpreter these hooks actually run under has no third-party packages.

What these pin down: an agent's Bash call is a shell line, not a git command.
`git` shows up inside quoted commit messages, grep patterns and heredocs, and a
real git call hides behind `cd x &&`, `-C dir` and `$(...)`. Counting the word
"git" is the proxy these tests exist to refuse (L40).
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "..", "git-ops.py")
TIMELINE = os.path.join(HERE, "..", "..", "bin", "git-timeline")

spec = importlib.util.spec_from_file_location("git_ops", HOOK)
git_ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(git_ops)

FAILURES = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"  — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def subs(cmd, cwd="/base"):
    return [(o["sub"], o["dir"]) for o in git_ops.parse_git_ops(cmd, cwd)]


# --- parser ------------------------------------------------------------------

print("parser")
check("plain status", subs("git status") == [("status", "/base")])
check("chained ops each count", subs("git add a && git commit -m 'x'") ==
      [("add", "/base"), ("commit", "/base")])
check("quoted git in a message is not an op",
      subs('git commit -m "fix: git push was wrong; git reset too"') == [("commit", "/base")])
check("grep pattern naming git is not an op", subs("grep -rn 'git push' docs | head") == [])
check("echo git is not an op", subs("echo git status") == [])
check("cd prefix moves the directory", subs("cd /repo/x && git log --oneline") == [("log", "/repo/x")])
check("relative cd resolves against cwd", subs("cd sub && git diff", "/base") == [("diff", "/base/sub")])
check("-C overrides the directory", subs("git -C /other status") == [("status", "/other")])
check("-C relative to the cd'd dir", subs("cd /a && git -C b fetch") == [("fetch", "/a/b")])
check("global options skipped before subcommand",
      subs("git --no-pager -c core.pager=cat log -3") == [("log", "/base")])
check("env assignment prefix", subs("GIT_EDITOR=true git rebase --continue") == [("rebase", "/base")])
check("command substitution", subs('sha=$(git rev-parse HEAD); echo "$sha"') == [("rev-parse", "/base")])
check("pipe after git", subs("git log --oneline | head -3") == [("log", "/base")])
check("newline separates commands", subs("git fetch -q\ngit status --short") ==
      [("fetch", "/base"), ("status", "/base")])
check("subshell cd does not leak", subs("(cd /x && git pull); git push") ==
      [("pull", "/x"), ("push", "/base")], str(subs("(cd /x && git pull); git push")))
check("fd-number redirection is not an arg",
      [o["argv"] for o in git_ops.parse_git_ops("git check-ignore -v x 2>/dev/null", "/b")] == ["git check-ignore -v x"],
      str([o["argv"] for o in git_ops.parse_git_ops("git check-ignore -v x 2>/dev/null", "/b")]))
check("unbalanced quotes do not raise", isinstance(subs("git commit -m \"oops"), list))
check("no git at all is fast-empty", subs("ls -la && pwd") == [])
check("path-qualified git binary", subs("/usr/bin/git status") == [("status", "/base")])
check("gitk / git-lfs words are not git", subs("gitk --all; git-lfs ls") == [])
check("heredoc body lines are not ops",
      subs("cat > f <<'EOF'\ngit push --force\nEOF\ngit status") == [("status", "/base")],
      str(subs("cat > f <<'EOF'\ngit push --force\nEOF\ngit status")))

print("categories")
check("status is read", git_ops.category("status", []) == "read")
check("push is remote", git_ops.category("push", []) == "remote")
check("commit is write", git_ops.category("commit", []) == "write")
check("bare branch listing is read", git_ops.category("branch", []) == "read")
check("branch -D is destructive", git_ops.category("branch", ["-D", "x"]) == "destructive")
check("branch -d is write", git_ops.category("branch", ["-d", "x"]) == "write")
check("stash list is read", git_ops.category("stash", ["list"]) == "read")
check("bare stash is write", git_ops.category("stash", []) == "write")
check("reset --hard is destructive", git_ops.category("reset", ["--hard"]) == "destructive")
check("push --force is destructive", git_ops.category("push", ["--force"]) == "destructive")
check("--help on a destructive command is read", git_ops.category("filter-branch", ["--help"]) == "read")
check("clean -fd is destructive", git_ops.category("clean", ["-fd"]) == "destructive")

# --- repo resolution ---------------------------------------------------------

print("repo resolution")
tmp = tempfile.mkdtemp()
main = os.path.join(tmp, "proj")
os.makedirs(main)
run = lambda *a, cwd=main: subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
run("init", "-q", "-b", "trunk")
run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init")
wt = os.path.join(main, ".claude", "worktrees", "lane-a")
run("worktree", "add", "-q", "-b", "lane-a", wt)
r = git_ops.resolve_repo(main)
check("main checkout names its repo", r["repo"] == "proj" and r["branch"] == "trunk", str(r))
r = git_ops.resolve_repo(wt)
check("worktree maps to its main repo", r["repo"] == "proj" and r["worktree"] == "lane-a"
      and r["branch"] == "lane-a", str(r))
gone = os.path.join(main, ".claude", "worktrees", "long-deleted", "sub")
r = git_ops.resolve_repo(gone)
check("deleted worktree path still maps to repo", r["repo"] == "proj" and r["worktree"] == "long-deleted", str(r))
r = git_ops.resolve_repo(os.path.join(tmp, "nowhere"))
check("non-repo dir yields a label, not a crash", r["repo"] == "(no repo)", str(r))

# --- hook end to end ---------------------------------------------------------

print("hook")
log = os.path.join(tmp, "ops.jsonl")


def fire(payload):
    env = dict(os.environ, GIT_OPS_LOG=log)
    return subprocess.run([sys.executable, HOOK], input=json.dumps(payload), env=env,
                          capture_output=True, text=True, timeout=20)


p = fire({"hook_event_name": "PostToolUse", "tool_name": "Bash", "session_id": "s1",
          "cwd": tmp, "tool_use_id": "toolu_A", "tool_input": {"command": "cd proj && git status && git log -1"},
          "tool_response": {"stdout": "ok"}})
check("hook exits 0 and prints nothing", p.returncode == 0 and p.stdout == "", p.stderr)
rows = [json.loads(l) for l in open(log)]
check("one row per git invocation", [r["sub"] for r in rows] == ["status", "log"], str(rows))
check("rows carry repo, session, ok", all(r["repo"] == "proj" and r["session"] == "s1" and r["ok"] is True
                                          and r["src"] == "hook" for r in rows), str(rows[0]))
check("row ids derive from tool_use_id", [r["id"] for r in rows] == ["toolu_A:0", "toolu_A:1"])
fire({"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "session_id": "s1", "cwd": main,
      "tool_use_id": "toolu_B", "tool_input": {"command": "git push"}, "error": "Exit code 1\nrejected",
      "is_interrupt": False, "agent_id": "ag1"})
last = json.loads(open(log).read().splitlines()[-1])
check("failure rows are ok=false with the error", last["ok"] is False and last["error"].startswith("Exit code 1")
      and last["agent"] == "ag1", str(last))
before = len(open(log).read().splitlines())
fire({"hook_event_name": "PostToolUse", "tool_name": "Bash", "session_id": "s1", "cwd": main,
      "tool_use_id": "toolu_C", "tool_input": {"command": "ls; echo 'git push'"}})
fire({"hook_event_name": "PostToolUse", "tool_name": "Edit", "session_id": "s1", "cwd": main})
p = fire("not json at all")
check("non-git, non-Bash and garbage payloads write nothing",
      len(open(log).read().splitlines()) == before and p.returncode == 0)
env = dict(os.environ, GIT_OPS_LOG=os.path.join(tmp, "no", "such", "dir", "x.jsonl"))
os.makedirs(os.path.join(tmp, "ro"))
os.chmod(os.path.join(tmp, "ro"), 0o500)
env["GIT_OPS_LOG"] = os.path.join(tmp, "ro", "x.jsonl")
p = subprocess.run([sys.executable, HOOK], input=json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                    "cwd": main, "tool_input": {"command": "git status"}}), env=env, capture_output=True, text=True)
check("unwritable log never fails the tool", p.returncode == 0, p.stderr)

# --- backfill + html ---------------------------------------------------------

print("git-timeline")
projects = os.path.join(tmp, "projects", "-x")
os.makedirs(os.path.join(projects, "sess1", "subagents"))


def entry(kind, content, ts, **extra):
    return json.dumps({"type": kind, "timestamp": ts, "sessionId": "sess1", "cwd": main,
                       "gitBranch": "trunk", "message": {"role": kind, "content": content}, **extra})


with open(os.path.join(projects, "sess1.jsonl"), "w") as fh:
    fh.write(entry("assistant", [{"type": "tool_use", "id": "toolu_A", "name": "Bash",
                                  "input": {"command": "git status"}}], "2026-09-01T10:00:00Z") + "\n")
    fh.write(entry("user", [{"type": "tool_result", "tool_use_id": "toolu_A", "content": "ok"}],
                   "2026-09-01T10:00:01Z") + "\n")
    fh.write(entry("assistant", [{"type": "tool_use", "id": "toolu_Z", "name": "Bash",
                                  "input": {"command": "git push origin trunk"}}], "2026-09-01T11:00:00Z") + "\n")
    fh.write(entry("user", [{"type": "tool_result", "tool_use_id": "toolu_Z", "is_error": True,
                             "content": "Exit code 1\n! [rejected]"}], "2026-09-01T11:00:02Z") + "\n")
    fh.write("{truncated line\n")
with open(os.path.join(projects, "sess1", "subagents", "agent-q.jsonl"), "w") as fh:
    fh.write(entry("assistant", [{"type": "tool_use", "id": "toolu_S", "name": "Bash",
                                  "input": {"command": "cd " + wt + " && git commit -qm wip"}}],
                   "2026-09-01T12:00:00Z", agentId="q") + "\n")

tl = lambda *a: subprocess.run([sys.executable, TIMELINE, *a, "--log", log, "--projects", os.path.dirname(projects)],
                               capture_output=True, text=True, timeout=60)
p = tl("backfill")
check("backfill runs", p.returncode == 0, p.stderr)
rows = [json.loads(l) for l in open(log)]
ids = [r["id"] for r in rows]
check("backfill skips ids the hook already logged", ids.count("toolu_A:0") == 1, str(ids))
z = [r for r in rows if r["id"] == "toolu_Z:0"]
check("backfilled failure is ok=false", z and z[0]["ok"] is False and z[0]["src"] == "backfill", str(z))
s = [r for r in rows if r["id"] == "toolu_S:0"]
check("subagent transcripts are read, worktree resolved", s and s[0]["agent"] == "q"
      and s[0]["repo"] == "proj" and s[0]["worktree"] == "lane-a", str(s))
n = len(rows)
tl("backfill")
check("backfill is idempotent", len(open(log).read().splitlines()) == n)

out = os.path.join(tmp, "t.html")
open(log, "a").write(json.dumps({**rows[0], "id": "evil:0", "argv": "git commit -m '</script><img src=x onerror=alert(1)>'"}) + "\n")
p = tl("html", "--out", out, "--repo", "proj")
check("html builds", p.returncode == 0 and os.path.isfile(out), p.stderr)
html = open(out).read()
check("embedded data cannot close the script tag", "</script><img" not in html)
check("default repo is baked in", '"proj"' in html)

# --- journey: commit graph + lane layout -------------------------------------

print("journey")
from importlib.machinery import SourceFileLoader
timeline = SourceFileLoader("git_timeline", TIMELINE).load_module()
jr = os.path.join(tmp, "journey")
os.makedirs(jr)
T = [1_790_000_000 + 3600 * k for k in range(10)]


def jgit(*a, t=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    if t:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"@{t} +0000"
    return subprocess.run(["git", *a], cwd=jr, env=env, capture_output=True, text=True, check=True).stdout.strip()


jgit("init", "-q", "-b", "main")
jgit("commit", "-q", "--allow-empty", "-m", "root", t=T[0])
jgit("switch", "-q", "-c", "feat")
jgit("commit", "-q", "--allow-empty", "-m", "feat 1", t=T[1])
jgit("commit", "-q", "--allow-empty", "-m", "feat 2", t=T[2])
jgit("switch", "-q", "main")
jgit("commit", "-q", "--allow-empty", "-m", "main 2", t=T[3])
jgit("merge", "-q", "--no-ff", "feat", "-m", "Merge branch 'feat'", t=T[4])
jgit("branch", "-q", "-D", "feat")                           # merged and gone: only the merge remembers it
jgit("switch", "-q", "-c", "wip")
jgit("commit", "-q", "--allow-empty", "-m", "wip 1", t=T[5])
jgit("switch", "-q", "main")
jgit("stash", "list")
graph = timeline.repo_graph(jr, prs=False)
subjects = [c[4] for c in graph["commits"]]
check("graph has every commit, newest first", subjects[0] in ("wip 1",) and set(subjects) ==
      {"root", "feat 1", "feat 2", "main 2", "Merge branch 'feat'", "wip 1"}, str(subjects))
merge = next(c for c in graph["commits"] if c[4].startswith("Merge"))
check("merge commit keeps both parents", len(merge[1]) == 2)
check("default branch detected without a remote", graph["default"] == "main", str(graph["default"]))
check("refs carry branch names", any("wip" in c[3] for c in graph["commits"]))
check("no gh call when prs=False", graph["prs"] == [])

node = subprocess.run(["which", "node"], capture_output=True, text=True).stdout.strip()
if not node:
    print("  SKIP  lane layout (no node on PATH)")
else:
    page = open(os.path.join(os.path.dirname(TIMELINE), "git-timeline.html"), encoding="utf-8").read()
    layout = page[page.index("// <journey-layout>"):page.index("// </journey-layout>")]
    iso = lambda t: __import__("datetime").datetime.fromtimestamp(t, __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    squash = {"n": 7, "title": "squashed", "head": "gone-branch", "base": "main", "state": "merged",
              "created": iso(T[6]), "merged": iso(T[8]), "closed": None, "mergeOid": None}
    fixture = dict(graph, prs=[squash])
    wts = [{"name": "lane-a", "t0": T[6] * 1000, "t1": T[7] * 1000, "n": 3, "branch": "worktree-lane-a"}]
    marks = [{"t": T[4] * 1000, "kind": "push", "branch": "main"}, {"t": T[5] * 1000, "kind": "destructive", "branch": "wip"}]
    js = layout + f"""
const J = chainsOf({json.dumps(fixture)}, {json.dumps(wts)}, {json.dumps(marks)}, {T[9] * 1000});
const {{ vis, lanes }} = packLanes(J.chains, {T[0] * 1000 - 1}, {T[9] * 1000});
console.log(JSON.stringify({{ lanes, chains: J.chains.map(c => ({{ name: c.name, kind: c.kind, n: c.commits.length,
  lane: c.lane, fork: c.fork && c.fork.s, merge: c.merge && c.merge.s, prs: c.prs.map(p => p.n),
  wts: c.wts.map(w => w.name), marks: c.marks.map(m => m.kind) }})) }}));"""
    out = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=30)
    res = json.loads(out.stdout) if out.returncode == 0 else {"chains": [], "lanes": 0}
    by = {c["name"]: c for c in res["chains"]}
    check("layout runs", out.returncode == 0, out.stderr[-300:])
    check("main is the first-parent line, lane 0", by.get("main", {}).get("kind") == "main" and by["main"]["lane"] == 0
          and by["main"]["n"] == 3, str(by.get("main")))
    f = by.get("feat", {})
    check("deleted branch is recovered from its merge subject", f.get("kind") == "merged" and f.get("n") == 2
          and f.get("fork") == "root" and f.get("merge") == "Merge branch 'feat'", str(f))
    check("open branch forks from the merge and has no merge", by.get("wip", {}).get("fork") == "Merge branch 'feat'"
          and by["wip"]["merge"] is None, str(by.get("wip")))
    check("squash-merged PR gets its own dashed lane", by.get("gone-branch", {}).get("kind") == "pr"
          and by["gone-branch"]["prs"] == [7], str(by.get("gone-branch")))
    check("unmatched worktree gets a lane named for its branch", by.get("worktree-lane-a", {}).get("wts") == ["lane-a"],
          str(by.get("worktree-lane-a")))
    check("op marks land on their branch's lane", by["main"]["marks"] == ["push"] and by["wip"]["marks"] == ["destructive"],
          str((by["main"]["marks"], by.get("wip", {}).get("marks"))))
    non_main = [c.get("lane") for c in res["chains"] if c["kind"] != "main"]
    check("every non-main chain in view gets a lane >= 1", non_main and all(isinstance(l, int) and l >= 1 for l in non_main),
          str(non_main))
    js2 = layout + """
const mk = (name, kind, t0, t1, ts) => ({ name, kind, t0, t1, commits: ts.map(t => ({ t })) });
const cs = [mk("main", "main", 0, 100, [0]), mk("idle-pr", "pr", 0, 100, []), mk("active", "branch", 40, 60, [45, 55])];
packLanes(cs, 0, 100); console.log(JSON.stringify(cs.map(c => c.lane)));"""
    out2 = subprocess.run([node, "-e", js2], capture_output=True, text=True, timeout=30)
    check("overlapping: the chain with commits in view sits nearer main than the idle one",
          out2.stdout.strip() == "[0,2,1]", out2.stdout + out2.stderr[-200:])
    check("lanes are reused once a branch has merged", res["lanes"] < len(res["chains"]) + 1, str(res["lanes"]))

os.chmod(os.path.join(tmp, "ro"), 0o700)
print(f"\n{len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
