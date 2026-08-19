#!/usr/bin/env python3
"""Check that every markdown document carries a working table of contents.

    python3 check_toc.py [path ...]      # files or directories; defaults to cwd

Reports three failures:
  MISSING   a document with 2+ `##` sections and no `## Contents` block
  BROKEN    a link whose anchor matches no heading (in this file or the file it names)
  PARTIAL   a `##` section the Contents block never links to

Exits 1 if anything is reported. Stdlib only.
Opt a file out with an HTML comment anywhere in it: <!-- docs:no-toc -->
"""

import os
import re
import sys

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
# Headings that structure the document rather than sit inside it.
NOT_A_SECTION = {"contents", "table of contents"}
FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
INLINE_MD = re.compile(r"[`*_~]|\[|\]|<[^>]+>")


def slug(text):
    """GitHub's heading-anchor rules: strip inline markup and punctuation, hyphenate."""
    text = INLINE_MD.sub("", text)
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return text.strip().lower().replace(" ", "-")


def parse(path):
    """-> (anchors, sections, toc_targets, opted_out) for one markdown file."""
    anchors, sections, toc, seen = set(), [], set(), {}
    in_contents = False
    in_fence = False
    opted_out = False

    for line in open(path, encoding="utf8", errors="replace"):
        if "<!-- docs:no-toc -->" in line:
            opted_out = True
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        head = HEADING.match(line)
        if head:
            level, title = len(head.group(1)), head.group(2)
            base = slug(title)
            n = seen.get(base, 0)
            seen[base] = n + 1
            anchors.add(base if n == 0 else f"{base}-{n}")
            if level == 2:
                in_contents = base in NOT_A_SECTION
                if not in_contents:
                    sections.append((title, base))
            continue

        if in_contents:
            toc.update(LINK.findall(line))

    return anchors, sections, toc, opted_out


def main(argv):
    roots = argv[1:] or ["."]
    files = []
    for root in roots:
        if os.path.isfile(root):
            files.append(root)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            files += [
                os.path.join(dirpath, f) for f in filenames if f.endswith(".md")
            ]

    parsed = {os.path.realpath(f): parse(f) for f in sorted(set(files))}
    problems = []

    for path in sorted(files, key=os.path.realpath):
        real = os.path.realpath(path)
        anchors, sections, toc, opted_out = parsed[real]
        if opted_out:
            continue
        # A skill's reference/ tree is context an agent loads, not a document a
        # person opens. Out of scope for this standard.
        parts = set(path.replace("\\", "/").split("/"))
        if parts & {"reference", "references"}:
            continue
        # Nothing that fits on one screen needs a map. Short SKILL.md files are
        # read whole by an agent, so they get a longer rope.
        if not toc:
            floor = 120 if os.path.basename(path) == "SKILL.md" else 40
            with open(path, encoding="utf8", errors="replace") as fh:
                if sum(1 for _ in fh) < floor:
                    continue

        if len(sections) >= 2 and not toc:
            problems.append((path, "MISSING", f"{len(sections)} sections, no Contents block"))
            continue

        for target in sorted(toc):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            file_part, _, anchor = target.partition("#")
            if file_part:
                other = os.path.realpath(os.path.join(os.path.dirname(path), file_part))
                if not os.path.exists(other):
                    problems.append((path, "BROKEN", f"{target} — no such file"))
                    continue
                if anchor:
                    if other not in parsed:
                        parsed[other] = parse(other)
                    if anchor not in parsed[other][0]:
                        problems.append((path, "BROKEN", f"{target} — no such heading there"))
            elif anchor and anchor not in anchors:
                problems.append((path, "BROKEN", f"#{anchor} — no heading with that anchor"))

        if toc:
            linked = {t.partition("#")[2] for t in toc}
            for title, anchor in sections:
                if anchor not in linked and title.strip().lower() not in NOT_A_SECTION:
                    problems.append((path, "PARTIAL", f"'{title}' is not in the Contents"))

    for path, kind, detail in problems:
        print(f"{kind:8} {path}: {detail}")

    checked = len(files)
    if problems:
        print(f"\n{len(problems)} problem(s) across {checked} file(s).")
        return 1
    print(f"{checked} file(s) checked, every table of contents resolves.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
