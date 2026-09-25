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

# A git hook exports GIT_DIR (absolute, inside a worktree) to everything it runs. Inherited,
# it makes every `git` below — init, commit, branch, worktree add — act on the repo being
# pushed instead of the throwaway ones: a pre-push run from a dotfiles-ai worktree left
# that repo `core.bare = true` with test branches and commits in it. Nothing here may see
# the caller's repository.
for _var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
             "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX"):
    os.environ.pop(_var, None)

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
check("cd to a shell variable leaves the directory unknown, not the cwd",
      subs("cd $M && git commit -q -F msg") == [("commit", None)], str(subs("cd $M && git commit -q -F msg")))
check("a quoted variable path is unknown too", subs('cd "$S/mirror" && git status') == [("status", None)])
check("-C with a variable is unknown", subs('git -C "$WT" log -1') == [("log", None)])
check("a relative cd after an unknown one stays unknown", subs("cd $X && cd sub && git diff") == [("diff", None)])
check("an absolute cd resolves again", subs("cd $X; cd /repo && git status") == [("status", "/repo")])
check("backtick substitution is unknown", subs("cd `pwd`/x && git status") == [("status", None)])
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

print("commits made")
check("commit output names the sha", git_ops.made_commits("[main 351c0a9] git-ops: log it\n 9 files changed") == ["351c0a9"])
check("root commit and detached HEAD forms", git_ops.made_commits(
    "[main (root-commit) abc1234] init\n[detached HEAD 1234567f] wip") == ["abc1234", "1234567f"])
check("push/fetch brackets are not commits", git_ops.made_commits(
    " ! [rejected]        main -> main (fetch first)\n * [new branch]      x -> x") == [])

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
subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "quiet one"],
               cwd=main, check=True)
head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=main, capture_output=True, text=True).stdout.strip()
fire({"hook_event_name": "PostToolUse", "tool_name": "Bash", "session_id": "s2", "cwd": main, "tool_use_id": "toolu_Q",
      "tool_input": {"command": "git commit -q --allow-empty -m 'quiet one'"}, "tool_response": {"stdout": "", "stderr": ""}})
last = json.loads(open(log).read().splitlines()[-1])
check("a quiet commit is tied to the HEAD it made", last.get("made") and head.startswith(last["made"][0]), str(last))
fire({"hook_event_name": "PostToolUse", "tool_name": "Bash", "session_id": "s2", "cwd": main, "tool_use_id": "toolu_L",
      "tool_input": {"command": "git commit -m 'loud one'"}, "tool_response": {"stdout": "[trunk 89abcde] loud one\n", "stderr": ""}})
last = json.loads(open(log).read().splitlines()[-1])
check("a commit's printed sha is recorded", last.get("made") == ["89abcde"], str(last))
# One call, two commit-making commands, both quiet: only the last one's HEAD can be read.
subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "first"], cwd=main, check=True)
subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "second"], cwd=main, check=True)
head2 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=main, capture_output=True, text=True).stdout.strip()
fire({"hook_event_name": "PostToolUse", "tool_name": "Bash", "session_id": "s2", "cwd": main, "tool_use_id": "toolu_TWO",
      "tool_input": {"command": "git commit -q --allow-empty -m first && git commit -q --allow-empty -m second"},
      "tool_response": {"stdout": "", "stderr": ""}})
two = [json.loads(l) for l in open(log).read().splitlines() if json.loads(l)["id"].startswith("toolu_TWO:")]
check("a HEAD reading is attached only to the last commit of the call",
      [r.get("made") for r in two] == [None, [head2[:12]]], str([(r["id"], r.get("made")) for r in two]))
fire({"hook_event_name": "PostToolUse", "tool_name": "Bash", "session_id": "s2", "cwd": main, "tool_use_id": "toolu_PR",
      "tool_input": {"command": "git commit -m a && git commit -m b"},
      "tool_response": {"stdout": "[trunk 1111111] a\n[trunk 2222222] b\n", "stderr": ""}})
pr2 = [json.loads(l) for l in open(log).read().splitlines() if json.loads(l)["id"].startswith("toolu_PR:")]
check("printed shas go to their own commands, in order",
      [r.get("made") for r in pr2] == [["1111111"], ["2222222"]], str([(r["id"], r.get("made")) for r in pr2]))
fire({"hook_event_name": "PostToolUse", "tool_name": "Bash", "session_id": "s2", "cwd": main, "tool_use_id": "toolu_VAR",
      "tool_input": {"command": "cd $M && git commit -q --allow-empty -m 'var dir'"}, "tool_response": {"stdout": "", "stderr": ""}})
vr = [json.loads(l) for l in open(log).read().splitlines() if json.loads(l)["id"].startswith("toolu_VAR:")]
check("a commit in an unknown folder is not pinned to the cwd's repo or its HEAD",
      vr and vr[0]["repo"] == "(no repo)" and vr[0]["dir"] is None and "made" not in vr[0], str(vr))
fire({"hook_event_name": "PostToolUse", "tool_name": "Bash", "session_id": "s2", "cwd": main, "tool_use_id": "toolu_R",
      "tool_input": {"command": "git status"}, "tool_response": {"stdout": "", "stderr": ""}})
last = json.loads(open(log).read().splitlines()[-1])
check("a read op records no commit", "made" not in last, str(last))
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
guide = os.path.join(os.path.dirname(out), "git-timeline-guide.html")
check("the guide is written next to the page", os.path.isfile(guide) and "Reading the git timeline" in open(guide).read())
check("the page links to the guide at the top and the bottom", html.count('href="git-timeline-guide.html"') >= 2)
g_html = open(guide).read()
check("the guide links back to the page from the top, the always-visible rail, and the end",
      g_html.count('href="git-timeline.html"') >= 3 and 'class="backlink"' in g_html and 'class="toc-back"' in g_html)

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

# --- push & pull report -----------------------------------------------------

print("push & pull")
bare, a_dir, b_dir = (os.path.join(tmp, n) for n in ("remote.git", "clone-a", "clone-b"))
sg = lambda cwd, *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd,
                                    capture_output=True, text=True, check=True).stdout.strip()
subprocess.run(["git", "init", "-q", "--bare", "-b", "main", bare], check=True)
sg(tmp, "clone", "-q", bare, a_dir)
sg(a_dir, "commit", "-q", "--allow-empty", "-m", "base")
sg(a_dir, "push", "-q", "origin", "main")
sg(tmp, "clone", "-q", bare, b_dir)
sg(a_dir, "commit", "-q", "--allow-empty", "-m", "a1")
sg(a_dir, "commit", "-q", "--allow-empty", "-m", "a2")
sg(a_dir, "push", "-q", "origin", "main")                      # push carrying a1, a2
sg(b_dir, "commit", "-q", "--allow-empty", "-m", "b-only")
sg(b_dir, "push", "-q", "origin", "main:side")                 # another clone opens a branch
sg(a_dir, "fetch", "-q")                                        # a pulls side in
sg(a_dir, "reset", "-q", "--hard", "HEAD~1")
sg(a_dir, "commit", "-q", "--allow-empty", "-m", "a2-rewritten")
sg(a_dir, "push", "-q", "--force", "origin", "main")           # force push: drops a2
sg(a_dir, "switch", "-q", "-c", "feat")
sg(a_dir, "commit", "-q", "--allow-empty", "-m", "feat work")
sg(a_dir, "push", "-q", "origin", "feat")
sg(a_dir, "switch", "-q", "main")
sg(a_dir, "commit", "-q", "--allow-empty", "-m", "main m1")
sg(a_dir, "commit", "-q", "--allow-empty", "-m", "main m2")
sg(a_dir, "push", "-q", "origin", "main")
sg(a_dir, "switch", "-q", "feat")
sg(a_dir, "rebase", "-q", "main")
sg(a_dir, "push", "-q", "--force", "origin", "feat")      # rebased onto main: carries main's commits too
sg(a_dir, "switch", "-q", "main")
ev = timeline.sync_events(a_dir, "main")
rebased = [e for e in ev if e["ref"] == "origin/feat" and e["forced"]]
check("a rebased branch push counts only its own commits, not main's",
      rebased and [c[1] for c in rebased[0]["commits"]] == ["feat work"] and rebased[0]["dropped"] == 1,
      str(rebased))
ev = [e for e in ev if e["ref"] != "origin/feat" and e["commits"] and e["commits"][0][1] not in ("main m2",)]
pushes = [e for e in ev if e["how"] == "push"]
subj = lambda e: [c[1] for c in e["commits"]]
check("every push in the reflog becomes an event", len(pushes) == 3, str([(e["ref"], e["n"]) for e in ev]))
two = next((e for e in pushes if e["n"] == 2), None)
check("a push lists exactly the commits it carried", two and sorted(subj(two)) == ["a1", "a2"], str(two))
forced = next((e for e in pushes if e["forced"]), None)
check("a force push records what it dropped", forced and forced["dropped"] == 1 and subj(forced) == ["a2-rewritten"],
      str(forced))
side = next((e for e in ev if e["ref"] == "origin/side"), None)
check("a fetched new branch counts only its own commits", side and side["how"] == "fetch" and subj(side) == ["b-only"],
      str(side))
check("events are newest first", [e["t"] for e in ev] == sorted((e["t"] for e in ev), reverse=True))
check("no remote, no events", timeline.sync_events(jr, "main") == [])
iso = lambda t: __import__("datetime").datetime.fromtimestamp(t, __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
evs = [{"t": 1_000_000, "how": "push", "ref": "origin/main", "n": 2, "commits": []},
       {"t": 2_000_000, "how": "fetch", "ref": "origin/main", "n": 1, "commits": []}]
ops = [{"ts": iso(1_000_060), "sub": "push", "session": "near", "ok": True, "argv": "git push"},
       {"ts": iso(1_000_900), "sub": "push", "session": "far", "ok": True, "argv": "git push"},
       {"ts": iso(2_000_010), "sub": "push", "session": "wrong-kind", "ok": True, "argv": "git push"},
       {"ts": iso(3_000_000), "sub": "push", "session": "failer", "ok": False, "branch": "main", "argv": "git push",
        "error": "Exit code 1\n! [rejected]"}]
out = timeline.attribute(evs, ops)
by_t = {e["t"]: e for e in out}
check("a push is credited to the nearest push op within the window", by_t[1_000_000].get("session") == "near", str(by_t[1_000_000]))
check("a fetch is never credited to a push op", "session" not in by_t[2_000_000], str(by_t[2_000_000]))
check("a failed push becomes its own event", by_t.get(3_000_000, {}).get("failed") is True
      and by_t[3_000_000]["session"] == "failer", str(by_t.get(3_000_000)))

# --- which chat made / pushed which commit ------------------------------------

print("chat attribution")
iso2 = lambda t: __import__("datetime").datetime.fromtimestamp(t, __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
g = {"commits": [["aaaaaaaaaaaa", [], 1000, [], "exact one", 0], ["bbbbbbbbbbbb", [], 2000, [], "fix: the parser", 0],
                 ["cccccccccccc", [], 3000, [], "lonely", 0], ["dddddddddddd", [], 4000, [], "crowded", 0],
                 ["eeeeeeeeeeee", [], 5000, [], "Merge pull request #9", 1], ["ffffffffffff", [], 9000, [], "by hand", 0]]}
ops = [{"ts": iso2(1010), "sub": "commit", "session": "S-exact", "argv": "git commit -q -F msg", "made": ["aaaaaaa"]},
       {"ts": iso2(1005), "sub": "commit", "session": "S-decoy", "argv": "git commit -q -F msg"},
       {"ts": iso2(2100), "sub": "commit", "session": "S-msg", "argv": "git commit -m 'fix: the parser'"},
       {"ts": iso2(2001), "sub": "commit", "session": "S-near", "argv": "git commit -m 'something else'"},
       {"ts": iso2(3030), "sub": "commit", "session": "S-time", "argv": "git commit -F m"},
       {"ts": iso2(4010), "sub": "commit", "session": "S-a", "argv": "git commit -F m"},
       {"ts": iso2(4020), "sub": "commit", "session": "S-b", "argv": "git commit -F m"},
       {"ts": iso2(5001), "sub": "commit", "session": "S-gh", "argv": "git commit -F m"},
       {"ts": iso2(9001), "sub": "commit", "session": "S-failed", "argv": "git commit -F m", "ok": False}]
au = timeline.commit_authors(g, ops)
check("printed/HEAD sha beats a closer-in-time op", au.get("aaaaaaaaaaaa", {}).get("s") == "S-exact"
      and au["aaaaaaaaaaaa"]["how"] == "exact", str(au.get("aaaaaaaaaaaa")))
check("a -m message matching the subject beats the nearest op", au.get("bbbbbbbbbbbb", {}).get("s") == "S-msg"
      and au["bbbbbbbbbbbb"]["how"] == "message", str(au.get("bbbbbbbbbbbb")))
check("one chat committing nearby is credited by time", au.get("cccccccccccc", {}).get("how") == "time"
      and au["cccccccccccc"]["s"] == "S-time", str(au.get("cccccccccccc")))
check("two chats committing nearby is flagged ambiguous", au.get("dddddddddddd", {}).get("how") == "ambiguous"
      and au["dddddddddddd"]["alt"] == 1, str(au.get("dddddddddddd")))
check("a commit GitHub made is never credited to a chat", "eeeeeeeeeeee" not in au, str(au.get("eeeeeeeeeeee")))
check("a failed commit op credits nothing", "ffffffffffff" not in au, str(au.get("ffffffffffff")))
check("-qm and --message= forms are read", timeline._msg_of("git commit -qm 'a b'") == "a b"
      and timeline._msg_of("git commit --message='x y'") == "x y" and timeline._msg_of("git commit -F f") is None)

tp = os.path.join(tmp, "titles", "-p")
os.makedirs(os.path.join(tp, "s1", "subagents"))
with open(os.path.join(tp, "s1.jsonl"), "w") as fh:
    for d in ({"type": "ai-title", "aiTitle": "auto name", "sessionId": "s1"},
              {"type": "custom-title", "customTitle": "old name", "sessionId": "s1"},
              {"type": "custom-title", "customTitle": "renamed", "sessionId": "s1"}):
        fh.write(json.dumps(d) + "\n")
with open(os.path.join(tp, "s2.jsonl"), "w") as fh:
    fh.write(json.dumps({"type": "last-prompt", "lastPrompt": "fix the login bug please", "sessionId": "s2"}) + "\n")
    fh.write(json.dumps({"type": "ai-title", "aiTitle": "Fix login", "sessionId": "s2"}) + "\n")
with open(os.path.join(tp, "s1", "subagents", "agent-x.jsonl"), "w") as fh:
    fh.write(json.dumps({"type": "custom-title", "customTitle": "subagent noise", "sessionId": "s1"}) + "\n")
ti = timeline.session_titles(os.path.dirname(tp))
check("the latest custom title wins", ti.get("s1") == "renamed", str(ti))
check("an ai title beats the last prompt", ti.get("s2") == "Fix login", str(ti))

plog = os.path.join(tmp, "patch.jsonl")
git_ops.append([{"id": "t1:0", "sub": "commit", "ts": "x"}], plog)
git_ops.append([{"id": "t1:0", "patch": {"made": ["abc1234"]}}], plog)
check("a patch line merges into its row", timeline.read_log(plog) == [{"id": "t1:0", "sub": "commit", "ts": "x",
                                                                       "made": ["abc1234"]}], str(timeline.read_log(plog)))

os.chmod(os.path.join(tmp, "ro"), 0o700)
print(f"\n{len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
