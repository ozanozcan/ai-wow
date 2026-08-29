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

import re
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
# docs/ is deliberately NOT here. Session reports and plan folders narrate real
# runs and name the projects those runs touched; scrubbing them would falsify
# the record rather than protect it. They are tracked and public, so that is a
# standing decision, not an oversight — revisit it, do not silently widen this
# list to make a red test green.
SCRUBBED_DIRS = ["hooks", "bin", "agents", "commands", "global", "skills", "templates",
                 "githooks"]

# The narrow form of this pattern gave a false green once already: a live
# `project-b.example` domain sat in a page template while the grep looked
# only for the hyphenated spelling. Match every separator, and none.
LEAK = re.compile(
    r"\bftm\b|\bhlc\b|project-a"
    r"|high[ ._-]?level[ ._-]?coaching"
    r"|/Users/[a-z]+",
    re.I,
)


def _scan(path):
    """[] or [relative path] — one leaked file, so callers can extend()."""
    if not path.is_file() or "__pycache__" in path.parts:
        return []
    # This file names the patterns it hunts for; it cannot scan itself.
    if path.resolve() == Path(__file__).resolve():
        return []
    try:
        text = path.read_text()
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
]

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
                             (REPO / "THIRD-PARTY.md").read_text(), re.M)
    expected = {"skills": len(skill_dirs), "subagents": len(agents),
                "third_party": len(third_party),
                "original": len(skill_dirs) - len(third_party)}

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

    seen = 0
    coverage = {}
    for name in PUBLISHED:
        raw = (REPO / name).read_text()
        coverage[name] = spans = claim_spans(raw)
        for _, _, kind, whole, token in spans:
            seen += 1
            check(f"{name}: {kind} count in {re.sub(r"\\s+", " ", whole)[:44].strip()!r}",
                  number(token), expected[kind])
    check("claim patterns actually matched something", seen > 0, True)

    # --- nothing count-shaped escapes classification ----------------------
    # A count-shaped phrase is only "checked" if it sits inside a claim match.
    # Anything else fails loudly and must be classified, never skipped.
    unclassified = []
    for name in PUBLISHED:
        raw = (REPO / name).read_text()
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
                            re.sub(r"\s+", " ", (REPO / "THIRD-PARTY.md").read_text())
                            .split("remaining skills")[-1].split("are original")[0]))
    check("THIRD-PARTY's originals + third-party == what is on disk",
          sorted(listed | set(third_party)), skill_dirs)

    # --- referenced-not-bundled claim holds -------------------------------
    check("impeccable is referenced but not bundled",
          (REPO / "skills" / "impeccable").exists(), False)
    check("impeccable's install line is still documented",
          "npx skills add pbakaus/impeccable" in (REPO / "THIRD-PARTY.md").read_text(), True)

    # --- nothing employer-specific leaked into the published repo ---------
    leaked = []
    for name in SCRUBBED_DIRS:
        for path in (REPO / name).rglob("*"):
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
