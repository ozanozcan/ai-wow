#!/usr/bin/env python3
"""PostToolUse / PostToolUseFailure hook — log every git invocation an agent runs.

Agents run a lot of git, and none of it was visible after the fact except by
reading raw transcripts, which Claude Code prunes after `cleanupPeriodDays`.
This appends one JSON line per git invocation to `~/.claude/git-ops.jsonl`
(override with `GIT_OPS_LOG`); `bin/git-timeline` backfills the same file from
old transcripts and renders it as a timeline page.

Two events because a Bash call that exits non-zero fires PostToolUseFailure,
*not* PostToolUse — registering only the success event would silently drop
every failed push, which is exactly the op worth seeing.

A Bash call is a shell line, not a git command: `git` appears inside quoted
commit messages, grep patterns and heredoc bodies, and a real call hides behind
`cd x &&`, `git -C dir` and `$(...)`. So the line is tokenized with the quoting
rules the shell uses, and only a word in command position counts. One Bash call
can hold several git invocations; each gets its own row, all sharing the call's
exit status (the shell reports one status per call, not per command).

The same module is imported by bin/git-timeline, so the backfill and the live
hook classify identically. Never raises and never prints — a logger must not
fail or chatter into a tool call.
"""

import datetime
import json
import os
import re
import shlex
import subprocess
import sys

SCHEMA = 1
PUNCT = "();<>|&\n"
PREFIXES = {"env", "command", "builtin", "exec", "nohup", "time", "sudo"}
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
WORKTREE_IN_PATH = re.compile(r"^(.*?)/\.claude/worktrees/([^/]+)")

READ = {"status", "diff", "log", "show", "rev-parse", "ls-files", "ls-tree", "blame", "grep",
        "cat-file", "describe", "shortlog", "reflog", "rev-list", "merge-base", "name-rev",
        "for-each-ref", "show-ref", "symbolic-ref", "count-objects", "check-ignore",
        "whatchanged", "var", "help", "version", "range-diff", "difftool", "show-branch",
        "check-ref-format", "verify-commit", "fsck"}
REMOTE = {"fetch", "pull", "push", "clone", "ls-remote"}
# Subcommands that can create a commit. Their rows carry `made` — the shas they created — so the
# timeline can say which chat made which commit without guessing from timestamps.
CREATORS = {"commit", "merge", "cherry-pick", "revert", "pull", "am", "rebase"}
MADE = re.compile(r"^\[[^\]\n]* ([0-9a-f]{7,40})\] ", re.M)


def made_commits(text):
    """Shas git reports creating: `[main 351c0a9] subject`, `[main (root-commit) abc1234] ...`."""
    return MADE.findall(text or "")


def head_if_fresh(d, within=20):
    """HEAD of `d` when its newest reflog entry is a commit made in the last `within` seconds.

    `git commit -q` prints nothing, so this is how a quiet commit gets its sha. The
    worktree's own HEAD reflog, not the branch's: a peer committing in another
    worktree of the same repo cannot answer for this one.
    """
    try:
        p = subprocess.run(["git", "-C", d, "log", "-g", "-1", "--date=unix", "--format=%H%x1f%gd%x1f%gs", "HEAD"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3, env=_GIT_ENV)
        sha, gd, gs = p.stdout.strip().split("\x1f")
        t = int(re.search(r"@\{(\d+)\}$", gd).group(1))
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
        return None
    fresh = datetime.datetime.now(datetime.timezone.utc).timestamp() - t <= within
    return sha[:12] if fresh and gs.startswith(("commit", "merge", "cherry-pick", "revert", "pull")) else None


def _strip_heredocs(cmd):
    """Drop heredoc bodies: their lines are data, not commands."""
    out, pending = [], []
    for line in cmd.split("\n"):
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue
        out.append(line)
        pending = [m.group(2) for m in HEREDOC.finditer(line)]
    return "\n".join(out)


def _tokens(cmd):
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=PUNCT)
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        return list(lex)
    except ValueError:              # unbalanced quote — fall back to a naive split
        return _naive(cmd)


def _naive(cmd):
    return re.findall(r"[();<>|&\n]+|[^\s();<>|&]+", cmd.replace('"', " ").replace("'", " "))


def _is_punct(tok):
    return bool(tok) and all(c in PUNCT for c in tok)


def _join(base, path):
    """`path` resolved against `base`; None when the shell alone knows the answer.

    A variable or command substitution (`cd $M`, `-C "$WT"`, `` cd `pwd` ``) names a
    folder only the shell can expand. Guessing the cwd instead pinned such commits
    to the wrong repo and read the wrong HEAD. None stays None until an absolute cd.
    """
    if "$" in path or "`" in path:
        return None
    path = os.path.expanduser(path)
    if base is None:
        return os.path.normpath(path) if os.path.isabs(path) else None
    return os.path.normpath(os.path.join(base, path))


def parse_git_ops(cmd, cwd):
    """Every git invocation in shell line `cmd`, run from `cwd`, in order."""
    if "git" not in cmd:
        return []
    toks = _tokens(_strip_heredocs(cmd))
    ops, stack, cur = [], [], cwd
    i, n, at_start = 0, len(toks), True
    while i < n:
        tok = toks[i]
        if _is_punct(tok):
            if tok[0] in "<>":
                i += 2                          # redirection and its target
                continue
            for c in tok:
                if c == "(":
                    stack.append(cur)
                elif c == ")" and stack:
                    cur = stack.pop()
            at_start = True
            i += 1
            continue
        if not at_start:
            i += 1
            continue
        if ASSIGN.match(tok) or tok in PREFIXES or tok.startswith("$"):
            i += 1                              # `$(` arrives as `$` then `(`
            continue
        at_start = False
        word = tok
        i += 1
        if word in ("cd", "pushd"):
            if i < n and not _is_punct(toks[i]) and toks[i] != "-":
                cur = _join(cur, toks[i])
            continue
        if word != "git" and not word.endswith("/git"):
            continue
        d, sub, glob = cur, None, []
        while i < n and not _is_punct(toks[i]):
            t = toks[i]
            if t == "-C" and i + 1 < n:
                d = _join(d, toks[i + 1])
                glob += [t, toks[i + 1]]
                i += 2
            elif t in ("-c", "--git-dir", "--work-tree", "--namespace", "--config-env") and i + 1 < n:
                glob += [t, toks[i + 1]]
                i += 2
            elif t.startswith("-"):
                glob.append(t)
                i += 1
            else:
                sub = t
                i += 1
                break
        args = []
        while i < n and not _is_punct(toks[i]):
            if toks[i].isdigit() and i + 1 < n and toks[i + 1][0] in "<>":
                i += 1                          # the `2` of `2>/dev/null`
                continue
            args.append(toks[i])
            i += 1
        sub = sub or (glob[-1] if glob else "git")
        argv = shlex.join(["git", *glob, sub, *args])
        ops.append({"sub": sub, "args": args, "dir": d,
                    "argv": argv if len(argv) <= 500 else argv[:497] + "..."})
    return ops


def _has(args, *flags):
    return any(a in flags for a in args)


def _short(args, letter):
    return any(re.fullmatch(r"-[a-zA-Z]*" + letter + r"[a-zA-Z]*", a) for a in args)


def category(sub, args):
    """read | write | remote | destructive — the colour a row gets on the page."""
    pos = [a for a in args if not a.startswith("-")]
    first = pos[0] if pos else None
    if _has(args, "--help", "-h", "--version"):
        return "read"
    if sub == "reset" and _has(args, "--hard"):
        return "destructive"
    if sub == "push" and (_short(args, "f") or any(a.startswith("--force") for a in args)
                          or any(a.startswith("+") for a in pos)):
        return "destructive"
    if sub == "clean" and (_short(args, "f") or _has(args, "--force")):
        return "destructive"
    if sub == "branch" and (_short(args, "D") or (_has(args, "--delete") and _has(args, "--force"))):
        return "destructive"
    if sub == "stash" and first in ("drop", "clear"):
        return "destructive"
    if sub == "checkout" and ("--" in args or "." in pos):
        return "destructive"
    if sub == "restore" and not _has(args, "--staged", "-S"):
        return "destructive"
    if sub in ("filter-branch", "filter-repo"):
        return "destructive"
    if sub in REMOTE:
        return "remote"
    if sub in READ or sub.startswith("-"):
        return "read"
    if sub == "branch":
        listing = _has(args, "-a", "-r", "-v", "-vv", "-l", "--list", "--all", "--remotes",
                       "--show-current", "--contains", "--merged", "--no-merged") or \
            any(a.startswith("--format") or a.startswith("--sort") for a in args)
        changing = _has(args, "-d", "-m", "-M", "-c", "-C", "-f", "-u", "--delete", "--move",
                        "--copy", "--force", "--unset-upstream") or \
            any(a.startswith("--set-upstream-to") for a in args)
        return "write" if changing or (pos and not listing) else "read"
    if sub == "stash":
        return "read" if first in ("list", "show") else "write"
    if sub == "worktree":
        return "read" if first == "list" else "write"
    if sub == "remote":
        return "read" if first in (None, "show", "get-url") else "write"
    if sub == "tag":
        return "write" if pos and not _has(args, "-l", "--list", "--contains", "--points-at") else "read"
    if sub == "config":
        setting = _has(args, "--unset", "--unset-all", "--add", "--replace-all", "--remove-section",
                       "--rename-section") or (len(pos) >= 2 and not any(a.startswith("--get") for a in args))
        return "write" if setting else "read"
    if sub == "notes":
        return "read" if first in (None, "list", "show") else "write"
    return "write"


_REPO_CACHE = {}
_GIT_ENV = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}


def resolve_repo(d):
    """{repo, root, worktree, branch} for directory `d`, which may no longer exist.

    A worktree maps to the repo that owns it, so 'which repo' groups a lane's
    ops with its main checkout; the worktree name is kept alongside. A path that
    has since been deleted (old worktrees, mostly) is resolved through its
    nearest surviving ancestor and the `.claude/worktrees/<name>` in its path.
    """
    if d is None:
        return {"repo": "(no repo)", "root": None, "worktree": None, "branch": None}
    if d in _REPO_CACHE:
        return _REPO_CACHE[d]
    m = WORKTREE_IN_PATH.match(d)
    wt_from_path = m.group(2) if m else None
    probe = d
    while probe and not os.path.isdir(probe):
        parent = os.path.dirname(probe)
        probe = None if parent == probe else parent
    res = {"repo": "(no repo)", "root": None, "worktree": wt_from_path, "branch": None}
    if probe:
        try:
            p = subprocess.run(["git", "-C", probe, "rev-parse", "--path-format=absolute",
                                "--git-common-dir", "--show-toplevel", "--abbrev-ref", "HEAD"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=3, env=_GIT_ENV)
            lines = p.stdout.splitlines()
        except (OSError, subprocess.SubprocessError):
            lines = []
        if len(lines) >= 2:
            common, top = lines[0], lines[1]
            root = os.path.dirname(common) if os.path.basename(common) == ".git" else common
            res["root"], res["repo"] = root, os.path.basename(root)
            if probe == d or not wt_from_path:
                if os.path.normpath(top) != os.path.normpath(root):
                    res["worktree"] = os.path.basename(top)
                res["branch"] = lines[2] if len(lines) > 2 else None
        elif m and os.path.isdir(m.group(1)):
            res["root"], res["repo"] = m.group(1), os.path.basename(m.group(1))
    _REPO_CACHE[d] = res
    return res


def rows_for(command, cwd, *, rid, ts, session, agent, ok, error, src, branch_hint=None, made=None, head_made=None):
    """The log rows for one Bash call. `branch_hint` is the transcript's branch for `cwd`.

    `made`: shas git printed for the call. One per commit-making command maps in
    order; any other count cannot be split, so every such command carries them all
    (they are still this call's, so the chat is right either way). `head_made`: the
    sha read from HEAD after the call, which only the last commit-making command can own.
    """
    rows = []
    cwd_repo = resolve_repo(cwd)["repo"] if branch_hint else None
    ops = parse_git_ops(command, cwd)
    creators = [i for i, op in enumerate(ops) if op["sub"] in CREATORS]
    own = {}
    if made and len(made) == len(creators):
        own = {i: [sha] for i, sha in zip(creators, made)}
    elif made:
        own = {i: list(made) for i in creators}
    elif head_made and creators:
        own = {creators[-1]: list(head_made)}
    for i, op in enumerate(ops):
        r = resolve_repo(op["dir"])
        branch = r["branch"]
        if src == "backfill":
            # Today's branch says nothing about then; the transcript's does, for its own cwd.
            branch = branch_hint if (branch_hint and r["repo"] == cwd_repo and not r["worktree"]) else None
        rows.append({"v": SCHEMA, "id": f"{rid}:{i}", "ts": ts, "session": session, "agent": agent,
                     "repo": r["repo"], "root": r["root"], "worktree": r["worktree"], "branch": branch,
                     "dir": op["dir"], "sub": op["sub"], "cat": category(op["sub"], op["args"]),
                     "argv": op["argv"], "command": command[:1000], "ok": ok,
                     "error": (error or "")[:300] or None, "src": src})
        if i in own:
            rows[-1]["made"] = own[i]
    return rows


def log_path():
    return os.environ.get("GIT_OPS_LOG") or os.path.join(os.path.expanduser("~"), ".claude", "git-ops.jsonl")


def append(rows, path=None):
    if not rows:
        return
    import fcntl
    path = path or log_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8")
    fresh = not os.path.exists(path)
    with open(path, "ab") as fh:     # append mode: every write lands at the end, even concurrent ones
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        fh.write(data)
    if fresh:
        os.chmod(path, 0o600)       # commit messages and paths — nobody else's business


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
            return
        event = payload.get("hook_event_name")
        if event not in ("PostToolUse", "PostToolUseFailure"):
            return
        command = (payload.get("tool_input") or {}).get("command") or ""
        if "git" not in command:
            return
        ts, session = now(), payload.get("session_id")
        failed = event == "PostToolUseFailure"
        error = payload.get("error") if failed else None
        if failed and payload.get("is_interrupt"):
            error = "interrupted" + (f": {error}" if error else "")
        cwd = payload.get("cwd") or os.getcwd()
        resp = payload.get("tool_response")
        out = (resp.get("stdout", "") + "\n" + resp.get("stderr", "")) if isinstance(resp, dict) else str(resp or "")
        made = [] if failed else made_commits(out)
        head_made = None
        if not failed and not made:
            ops = [o for o in parse_git_ops(command, cwd) if o["sub"] in CREATORS]
            fresh = head_if_fresh(ops[-1]["dir"]) if ops and ops[-1]["dir"] else None
            head_made = [fresh] if fresh else None
        rows = rows_for(command, cwd,
                        rid=payload.get("tool_use_id") or f"{session}@{ts}", ts=ts, session=session,
                        agent=payload.get("agent_id"), ok=not failed,
                        error=error if isinstance(error, str) else (json.dumps(error) if error else None),
                        src="hook", made=made or None, head_made=head_made)
        append(rows)
    except Exception:
        pass                        # a logger must never fail the tool call


if __name__ == "__main__":
    main()
