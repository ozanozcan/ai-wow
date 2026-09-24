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

os.chmod(os.path.join(tmp, "ro"), 0o700)
print(f"\n{len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
