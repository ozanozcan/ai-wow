#!/usr/bin/env python3
"""Generate or refresh the `## Contents` block in markdown documents.

    python3 toc.py [path ...]            # show what would change
    python3 toc.py --write [path ...]    # apply

Inserts a Contents block before the first section of any document with 2+ `##`
sections. Refreshing an existing block keeps the ` — gloss` you wrote after each
link and only fixes the links themselves.

Glosses are not generated. Write them — a bare outline is a list of headings; the
gloss is what turns it into a map. Stdlib only.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_toc import FENCE, HEADING, NOT_A_SECTION, SKIP_DIRS, slug  # noqa: E402

ENTRY = re.compile(r"^\s*-\s*\[[^\]]*\]\(#([^)]+)\)(.*)$")


def label(title):
    """Link text can't contain brackets — they'd terminate the link early."""
    return re.sub(r"\s{2,}", " ", title.replace("[", "(").replace("]", ")")).strip()


def build(path):
    """-> (new_text, note) or (None, why-not)."""
    lines = open(path, encoding="utf8", errors="replace").read().split("\n")
    if any("<!-- docs:no-toc -->" in ln for ln in lines):
        return None, "opted out"

    sections, seen, in_fence = [], {}, False
    first_section_at, contents_span = None, None
    for i, line in enumerate(lines):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        head = HEADING.match(line)
        if not head:
            continue
        level, title = len(head.group(1)), head.group(2)
        base = slug(title)
        n = seen.get(base, 0)
        seen[base] = n + 1
        anchor = base if n == 0 else f"{base}-{n}"
        if level != 2:
            continue
        if base in NOT_A_SECTION:
            end = next(
                (j for j in range(i + 1, len(lines)) if lines[j].startswith("## ")),
                len(lines),
            )
            contents_span = (i, end)
            continue
        sections.append((title, anchor))
        if first_section_at is None:
            first_section_at = i

    if len(sections) < 2:
        return None, f"{len(sections)} section(s) — nothing to table"

    kept = {}
    if contents_span:
        for line in lines[contents_span[0]: contents_span[1]]:
            m = ENTRY.match(line)
            if m:
                kept[m.group(1)] = m.group(2).rstrip()

    entries = [
        f"- [{label(title)}](#{anchor}){kept.get(anchor, '')}"
        for title, anchor in sections
    ]

    if contents_span:
        # Replace only the list itself, so a `---` rule or a note under the
        # Contents heading survives a refresh.
        start, end = contents_span
        hits = [j for j in range(start, end) if ENTRY.match(lines[j])]
        if hits:
            out = lines[: hits[0]] + entries + lines[hits[-1] + 1:]
        else:
            out = lines[: start + 1] + [""] + entries + lines[start + 1:]
        note = f"refreshed {len(entries)} entries"
    else:
        block = ["## Contents", ""] + entries + ["", "---", ""]
        out = lines[:first_section_at] + block + lines[first_section_at:]
        note = f"inserted {len(entries)} entries"

    new = "\n".join(out)
    old = "\n".join(lines)
    return (new, note) if new != old else (None, "already current")


def main(argv):
    write = "--write" in argv
    roots = [a for a in argv[1:] if a != "--write"] or ["."]
    files = []
    for root in roots:
        if os.path.isfile(root):
            files.append(root)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            files += [os.path.join(dirpath, f) for f in filenames if f.endswith(".md")]

    changed = 0
    for path in sorted(set(files)):
        floor = 120 if os.path.basename(path) == "SKILL.md" else 40
        with open(path, encoding="utf8", errors="replace") as fh:
            if sum(1 for _ in fh) < floor:
                continue
        new, note = build(path)
        if new is None:
            continue
        changed += 1
        print(f"{'wrote' if write else 'would write'}  {path}: {note}")
        if write:
            open(path, "w", encoding="utf8").write(new)

    print(f"\n{changed} file(s) {'changed' if write else 'would change'}.")
    if changed and not write:
        print("Re-run with --write to apply, then add a gloss after each link.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
