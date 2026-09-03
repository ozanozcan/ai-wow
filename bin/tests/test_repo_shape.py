#!/usr/bin/env python3
"""Shape tests for the published repo — inventory counts, licensing, scrub.

Plain `python3 bin/tests/test_repo_shape.py` — no pytest, matching the other
suites here, because the interpreter this harness runs under has no
third-party packages.

The drift these pin down is not "is the number 16". It is that the same number
is asserted in six independent places, in numerals and in words, and nothing
kept them honest: a predecessor run found the docs reading 14, 15 and 17 while
`ls -d skills/*/` returned 17. Counting on disk and comparing is the only
thing that scales past a human remembering every site.

Two design notes:

- Nothing here hardcodes an expected count. Adding a skill is legitimate and
  must not fail these tests; the docs disagreeing with the disk is the defect.
- The sweep FAILS LOUDLY on a count-shaped sentence it does not recognise,
  rather than skipping it. A silently unchecked claim is how this drifted in
  the first place, so a new phrasing must be classified, not ignored.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
# The docs a reader of the published repo actually meets. Plan folders and
# session reports quote historical counts on purpose and are not claims.
PUBLISHED = ["README.md", "HOW-TO-USE.human.md", "HOW-TO-USE.agent.md", "THIRD-PARTY.md"]

# Every directory whose contents ship as harness content a reader can run. The
# scrub used to cover only hooks/ and bin/, which is why a `FitnessManager`
# worked-example survived in skills/checkpoint/SKILL.md: the leak was never in
# the two directories being watched.
#
# docs/ was deliberately NOT here until 2026-09-01, on the argument that session
# reports narrate real runs and scrubbing them would falsify the record. The
# operator revisited that ahead of publishing the repo, and it does not hold: a
# reader of the published repo learns the employer codenames either way, and the
# record survives the scrub intact — every site was rewritten to say the same
# thing generically ("a real project lane", "employer codenames"), not deleted.
# What the old comment got right is the process: this list was widened by a
# decision, not to turn a red test green.
SCRUBBED_DIRS = ["hooks", "bin", "agents", "commands", "global", "skills", "templates",
                 "githooks", "docs"]

# The narrow form of this pattern gave a false green once already: a live
# `project-b.example` domain sat in a page template while the grep looked
# only for the hyphenated spelling. Match every separator, and none.
LEAK = re.compile(
    r"\bftm\b|\bhlc\b|project-a"
    r"|high[ ._-]?level[ ._-]?coaching"
    r"|/Users/[a-z]+",
    re.I,
)


def _tracked_under(dirs):
    """Every git-tracked file under `dirs`, as absolute paths.

    Tracked, not on-disk: the question this test asks is "what does publishing
    this repo expose", and an ignored file exposes nothing. Walking the working
    tree instead answers a different question and gets it wrong — adding docs/
    to SCRUBBED_DIRS made the scan reach docs/brainstorms/, which .gitignore
    keeps out of the repo entirely, and the push gate blocked on a file that
    could never leak. Everything under the original scrubbed dirs is tracked,
    which is the only reason the on-disk walk survived as long as it did.
    """
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z", "--", *dirs],
        capture_output=True, text=True, check=True,
    ).stdout
    return [REPO / rel for rel in out.split("\0") if rel]


def _headed_py(prefix):
    """Python files under `prefix` as of HEAD — what a clone sees.

    An rglob of the working tree counts untracked files a clone never gets, and
    misses tracked files deleted only in the worktree. Both were observed: the
    README's test count matched disk (186) while HEAD held 182, the gap being a
    peer's uncommitted `taskman/tests/test_metrics_paths.py`. The scrub next to
    this already uses `git ls-files` for the same reason; this matches it.
    """
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-tree", "-r", "-z", "--name-only",
         "HEAD", "--", prefix],
        capture_output=True, text=True, check=True,
    ).stdout
    return [rel for rel in out.split("\0") if rel.endswith(".py")]


def _blob(rel):
    return subprocess.run(
        ["git", "-C", str(REPO), "show", f"HEAD:{rel}"],
        capture_output=True, text=True, check=True,
    ).stdout


def _scan(path):
    """[] or [relative path] — one leaked file, so callers can extend()."""
    if not path.is_file() or "__pycache__" in path.parts:
        return []
    # This file names the patterns it hunts for; it cannot scan itself.
    if path.resolve() == Path(__file__).resolve():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    return [str(path.relative_to(REPO))] if LEAK.search(text) else []

WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}

# A claim: (kind, pattern). Group 1 is the asserted number, numeral or word.
CLAIMS = [
    ("skills",      r"\|\s*\*\*Skills\*\*\s*\|\s*(\d+)\s*\|"),
    ("skills",      r"\|\s*`skills/`\s*\|\s*(\d+)\s+skills"),
    ("skills",      r"inventory:\s*(\d+)\s+skills"),
    ("skills",      r'\{"(\d+)\s+skills listed\?"\}'),
    ("skills",      r"\*\*([A-Za-z]+)\s+skills\*\*"),
    ("skills",      r"of the\s+([a-z]+)\s+bundled skills"),
    ("subagents",   r"\|\s*\*\*Subagents\*\*\s*\|\s*(\d+)\s*\|"),
    ("subagents",   r"\|\s*`agents/`\s*\|\s*(\d+)\s+subagent definitions"),
    ("subagents",   r"inventory:.*?(\d+)\s+subagents"),
    ("subagents",   r"\*\*([A-Za-z]+)\s+subagents\.\*\*"),
    ("subagents",   r"the\s+([a-z]+)\s+subagents"),
    ("third_party", r"(?:^|\. )([A-Z][a-z]+)\s+of the\s+[a-z]+\s+bundled skills"),
    ("third_party", r"([A-Z][a-z]+)\s+bundled skills come from other projects"),
    ("original",    r"[Tt]he\s+([a-z]+)\s+remaining skills"),
    ("original",    r"the\s+([a-z]+)\s+original\s+skills"),
    ("hooks",       r"\|\s*\*\*Hooks\*\*\s*\|\s*(\d+)\s*\|"),
    ("hooks",       r"inventory:.*?(\d+)\s+hooks"),
    ("taskman_tests", r"\|\s*`taskman/`\s*\|[^|\n]*?(\d+)\+?\s+tests"),
]

# Kinds asserted as a floor ("200+ tests") rather than an exact equality.
#
# An exact test count is a claim that breaks every time someone adds a test, and
# it broke three times in three days — 142, then 135, then 210 — each time
# blocking a push over a number no reader depends on being exact. The inventory
# counts above are different: skills, subagents and hooks change rarely and
# deliberately, so an exact claim there catches a real omission.
#
# A floor keeps the signal a reader actually wants ("this package is heavily
# tested") and still fails on the case worth catching: tests disappearing. An
# understated floor is never *wrong*, only conservative, so it can be raised
# whenever someone feels like it rather than under the pressure of a red gate.
FLOOR_KINDS = {"taskman_tests"}

# Count-shaped phrases that are not inventory claims. Tested against the whole
# line the phrase sits on, so the exemption is judged in context.
EXEMPT = [
    r"\bzero skills\b",                  # the empty-farm failure mode, not a count
    r"\|\s*0 skills, no error emitted",  # the same failure mode, as a table row
    r"^#{1,6}\s+\d+(?:\.\d+)*\s",     # "### 4.1 Subagents" — a section number
]

# Sentences the sweep must find a claim (or exemption) for.
COUNT_SHAPED = re.compile(
    r"(?:\d+|\b(?:%s)\b)(?:\s+\w+){0,2}\s+(?:skills|subagents|subagent definitions)"
    % "|".join(WORDS), re.I)

FAILURES = []


def check(label, got, want):
    if got == want:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label} — got {got!r}, want {want!r}")
        FAILURES.append(label)


def number(token):
    return int(token) if token.isdigit() else WORDS.get(token.lower())


def main():
    print("published repo shape")

    # --- disk truth -------------------------------------------------------
    skill_dirs = sorted(p.name for p in (REPO / "skills").iterdir() if p.is_dir())
    missing = [n for n in skill_dirs if not (REPO / "skills" / n / "SKILL.md").is_file()]
    check("every skills/ entry has a SKILL.md", missing, [])
    agents = sorted(p.stem for p in (REPO / "agents").glob("*.md"))

    third_party = re.findall(r"^\|\s*`skills/([a-z0-9-]+)/`\s*\|",
                             (REPO / "THIRD-PARTY.md").read_text(encoding="utf-8"), re.M)
    # hooks.def.json's "hooks" array is the registration surface — one entry
    # per registered hook (a script wired to two events is two entries), which
    # is what the docs' hook counts describe. Both rotted while unguarded.
    hook_defs = json.loads((REPO / "hooks.def.json").read_text(encoding="utf-8"))["hooks"]
    taskman_tests = sum(
        len(re.findall(r"^\s*(?:async )?def test_", _blob(rel), re.M))
        for rel in _headed_py("taskman/tests"))
    expected = {"skills": len(skill_dirs), "subagents": len(agents),
                "third_party": len(third_party),
                "original": len(skill_dirs) - len(third_party),
                "hooks": len(hook_defs), "taskman_tests": taskman_tests}

    # --- every stated count agrees with the disk --------------------------
    # One pass produces both the assertions and the coverage map, so a claim
    # cannot be asserted here and considered "unchecked" there, or vice versa.
    def claim_spans(text):
        found = []
        for kind, pattern in CLAIMS:
            # Tolerate the line wrapping the docs actually use.
            for m in re.finditer(pattern.replace(" ", r"\s+"), text, re.M):
                found.append((m.start(), m.end(), kind, m.group(0), m.group(1)))
        return found

    seen = {kind: 0 for kind in expected}
    coverage = {}
    for name in PUBLISHED:
        raw = (REPO / name).read_text(encoding="utf-8")
        coverage[name] = spans = claim_spans(raw)
        for _, _, kind, whole, token in spans:
            seen[kind] += 1
            label = re.sub(r"\s+", " ", whole)[:44].strip()
            claimed = number(token)
            if kind in FLOOR_KINDS:
                check(f"{name}: {kind} floor {claimed}+ holds in {label!r}"
                      f" (actual {expected[kind]})",
                      claimed is not None and claimed <= expected[kind], True)
            else:
                check(f"{name}: {kind} count in {label!r}", claimed, expected[kind])
    for kind, n in seen.items():
        check(f"claim patterns for {kind} actually matched something", n > 0, True)

    # --- nothing count-shaped escapes classification ----------------------
    # A count-shaped phrase is only "checked" if it sits inside a claim match.
    # Anything else fails loudly and must be classified, never skipped.
    unclassified = []
    for name in PUBLISHED:
        raw = (REPO / name).read_text(encoding="utf-8")
        spans = coverage[name]
        for m in COUNT_SHAPED.finditer(raw):
            if any(s <= m.start() and m.end() <= e for s, e, *_ in spans):
                continue
            lineno = raw[:m.start()].count("\n") + 1
            line = raw.splitlines()[lineno - 1]
            if any(re.search(p, line) for p in EXEMPT):
                continue
            frag = re.sub(r"\s+", " ", m.group(0)).strip()
            unclassified.append(f"{name}:{lineno}: {frag[:60]}")
    check("no unclassified count claim", unclassified, [])

    # --- licensing surface stays truthful ---------------------------------
    for name in third_party:
        check(f"third-party skill {name}/ is present", (REPO / "skills" / name).is_dir(), True)
        check(f"third-party skill {name}/ carries its LICENSE",
              (REPO / "skills" / name / "LICENSE").is_file(), True)

    listed = set(re.findall(r"`([a-z0-9-]+)`",
                            re.sub(r"\s+", " ", (REPO / "THIRD-PARTY.md").read_text(encoding="utf-8"))
                            .split("remaining skills")[-1].split("are original")[0]))
    check("THIRD-PARTY's originals + third-party == what is on disk",
          sorted(listed | set(third_party)), skill_dirs)

    # --- referenced-not-bundled claim holds -------------------------------
    check("impeccable is referenced but not bundled",
          (REPO / "skills" / "impeccable").exists(), False)
    check("impeccable's install line is still documented",
          "npx skills add pbakaus/impeccable" in (REPO / "THIRD-PARTY.md").read_text(encoding="utf-8"), True)

    # --- every instruction names a path this repo actually has ------------
    # A shipped file that tells you to run `.venv/bin/python …` or
    # `scripts/wrapup_reconcile.py` is naming something ai-wow does not contain,
    # so the reader's first session fails on an instruction the repo gave it.
    # Both patterns shipped for months. The grep that was supposed to catch the
    # second one searched `\.venv/bin/python scripts/` — which requires
    # `scripts/` immediately after and so could only ever match the two
    # together, never a bare `.venv/bin/python`. It passed while 29 survived
    # (L40: a grep answers the pattern you typed, not the question you meant).
    # Hence a test rather than a command someone remembers to run.
    #
    # Markdown only, deliberately. A `.md` line is an instruction someone runs
    # verbatim, so naming an absent path is a defect. A shell script can *test*
    # for one first — `hooks/guard-migrations.sh` probes `[ -x .venv/bin/alembic ]`
    # with two fallbacks and a `pass`, which is correct defensive code, and the
    # first draft of this check flagged it. Scope the rule to the files where the
    # path is a promise rather than a probe.
    DEAD_PATHS = re.compile(r"\.venv/bin|scripts/wrapup_reconcile")
    dead = []
    for path in _tracked_under(["hooks", "skills"]):
        if path.suffix == ".md":
            if DEAD_PATHS.search(path.read_text(encoding="utf-8", errors="replace")):
                dead.append(str(path.relative_to(REPO)))
    check("no shipped instruction names a path this repo lacks", sorted(dead), [])

    # --- nothing employer-specific leaked into the published repo ---------
    leaked = []
    for path in _tracked_under(SCRUBBED_DIRS):
        leaked.extend(_scan(path))
    for name in PUBLISHED:
        leaked.extend(_scan(REPO / name))
    check("no employer or personal strings in published surfaces", leaked, [])

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s): " + ", ".join(FAILURES[:4])
              + (" …" if len(FAILURES) > 4 else ""))
        return 1
    print("0 failure(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
