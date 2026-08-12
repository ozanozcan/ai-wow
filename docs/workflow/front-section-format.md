# Workflow-doc front sections — format

**Status:** contract (d#848 · workflow-parity plan) · **Audience:** ai-sync doc renderer + operators editing cores/fronts

The canonical, project-agnostic **cores** of the shared workflow docs live in this
directory (`work-loop.md`, `mow-compact-template.md`, `taskman-dispatch-bridge.md`).
Each consuming repo gets a **rendered managed copy** in its own `docs/workflow/`.
This file defines the shape of that rendered copy and of the per-project front
files it is assembled from.

## The contract

A rendered copy is exactly three parts, concatenated in order, each part
separated from the next by a single blank line:

1. **Managed header** — a single HTML-comment line. It MUST begin with
   `<!-- ai-sync managed copy` and MUST name the canonical core path. Canonical
   wording (the renderer may append provenance such as a content hash after the
   `Front:` field, but the line stays a single HTML comment):

   ```text
   <!-- ai-sync managed copy — do not hand-edit; edits fail the drift gate. Core: ~/ai-wow/docs/workflow/<doc>.md · Front: ~/ai-wow/docs/workflow/fronts/<slug>/<doc>.md -->
   ```

   When the doc has no front file, the `Front:` field reads `none`.

2. **Front section** — the **verbatim** contents of
   `~/ai-wow/docs/workflow/fronts/<slug>/<doc>.md`, where `<slug>` is the
   repo's `.taskman.toml` project slug and `<doc>.md` matches the core filename.
   If that file does not exist, this part is omitted entirely (header is then
   followed directly by the body). All project-specific content lives here:
   the `**Project:** <slug> · **As of:** <date>` line, and any stack-specific
   rules or links (e.g. demo's field/play persistence-contract rule).

3. **Canonical body** — the core file, **byte-identical** across every repo's
   rendered copy. The renderer copies it verbatim; it never substitutes,
   trims, or reflows. The body begins with the doc's H1, so the front section
   renders as a short project banner above the title.

**Drift gate:** re-render and byte-compare the whole file. Any difference —
hand-edit, stale core, stale front — fails the gate (req #435). To change a
rendered copy, edit the core (shared change) or the repo's front file
(project-specific change) in ai-wow and re-render; never edit the copy.

## Front-file conventions

- Plain markdown, no frontmatter, no H1 (the body owns the title).
- First line SHOULD be `**Project:** <slug> · **As of:** <date>` — the date is
  static text, updated when the front file is edited.
- Subsequent paragraphs hold project-specific rules, one paragraph each,
  worded exactly as they should appear in the rendered doc.
- Keep fronts minimal: anything true for every repo belongs in the core.
  Prefer identical commands across repos (the taskman package is shared);
  a per-repo command variant is a front-file paragraph only as a last resort.

## Current layout

```text
~/ai-wow/docs/workflow/
  work-loop.md                  # core
  mow-compact-template.md       # core (no project-specific content; fronts optional)
  taskman-dispatch-bridge.md    # core (no project-specific content; fronts optional)
  front-section-format.md       # this contract
  fronts/
    demo/work-loop.md            # Project/As-of line + field/play contract rule
    web-app/work-loop.md            # Project/As-of line
```
