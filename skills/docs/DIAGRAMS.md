# Diagrams

Two lanes, because the two document shapes render differently: **markdown uses
mermaid** (GitHub renders it inline), **published pages use hand-authored SVG**
against the class tokens the house template defines. Same rules about what earns a
diagram; different mechanics.

## Contents

- [What earns a diagram](#what-earns-a-diagram) — and what doesn't
- [Complexity budget](#complexity-budget) — the caps, and what to do at the ceiling
- [Markdown lane: mermaid](#markdown-lane-mermaid)
- [Page lane: hand-authored SVG](#page-lane-hand-authored-svg)
- [The class tokens](#the-class-tokens) — the contract every figure is written against
- [Captions and accessibility](#captions-and-accessibility)

---

## What earns a diagram

A figure earns its place when it shows a reader something prose is bad at: a
topology, a flow with branches, a comparison across two axes, a state a request moves
through. If a sentence says it faster, write the sentence.

**Draw the mechanism, not its name.** A box labelled "cache" says less than the prose.
The path a request takes through it, the two stores it sits between, and the arrow
that disappears when it's removed say what words can't.

**Comparing options? Draw the difference.** Three labelled boxes with nothing
connecting them to the system is a restated list, not a comparison. Show the edge
each option adds or removes, so the reader can point at what they're choosing.

**Match complexity to the stakes.** A one-hop question is a three-box diagram. A
deploy that routes migrations through a separate credential needs both roles, both
connection paths, and the boundary they must never cross.

**Label the arrows.** An unlabelled arrow means "related somehow". `writes`,
`invalidates`, `as playbook_app · RLS enforced`, `443→8000` is information.

**One figure, one claim.** If a figure needs two sentences of caption to say what it
shows, it's two figures.

---

## Complexity budget

**Nine nodes. Twelve arrows.** Both lanes, counted before you draw. These aren't
style preferences — past roughly this size a reader stops tracing paths and starts
skimming shapes, which is the moment the figure stops earning its place.

At the ceiling you have three moves, in order of preference:

1. **Delete.** Usually two boxes are the same idea at different altitudes, or an
   arrow restates what the box labels already say. Deletion is the highest-quality
   move available and it is almost always available.
2. **Split into overview + detail.** One figure showing the four subsystems, one
   showing the inside of the subsystem the section is actually about. Each gets its
   own claim and its own caption.
3. **Stop drawing.** A dozen loosely-coupled things with no interesting topology is
   a table. A sequence with no branches is a numbered list.

Collapsing a cluster behind one box and labelling the edge into it is a legitimate
form of deletion. Shrinking the type to fit fourteen nodes is not.

---

## Markdown lane: mermaid

Fenced ```mermaid blocks. GitHub renders them; so do published markdown pages.

- `flowchart LR` for pipelines, `flowchart TD` for hierarchies, `sequenceDiagram`
  when ordering across actors is the point.
- Keep node labels to a few words. Long labels blow the layout up.
- Pad `<br/>` inside labels — `"import <br/>pull live content in"` — GitHub renders
  an unpadded `<br/>` as literal text in some contexts.
- No styling directives. Mermaid's defaults survive both themes; custom colours don't.
- The complexity budget applies here too, and mermaid hides the breach — it will
  happily lay out twenty nodes and produce something nobody reads.

---

## Page lane: hand-authored SVG

Inline `<svg>` with native shapes only — `rect`, `path`, `line`, `text`, `circle`. No
libraries, no runtime, no external images, no `<script>`, `<style>`, or
`<foreignObject>` inside the SVG.

```html
<figure>
  <div class="fig">
    <svg viewBox="0 0 1080 540" role="img" aria-label="…the claim, in words…">
      <defs>
        <marker id="ah" viewBox="0 0 10 10" refX="9" refY="5"
                markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,1 L9,5 L0,9 z" fill="context-stroke"/>
        </marker>
      </defs>
      <rect class="svg-box" x="30" y="206" width="140" height="64" rx="3"/>
      <text class="svg-t" x="100" y="236" text-anchor="middle">Phone</text>
      <text class="svg-s" x="100" y="254" text-anchor="middle">on cellular</text>
      <path class="svg-edge" d="M170,238 H205" marker-end="url(#ah)"/>
    </svg>
  </div>
  <figcaption><strong>The claim.</strong> What the reader should take away.</figcaption>
</figure>
```

- **`viewBox`, never fixed pixels.** Pick W and H for the content. The `.fig` wrapper
  scrolls horizontally on narrow screens; the SVG itself never causes page scroll.
- **Unique marker ids per figure** — `ah`, `ah2`, `ah3`. Duplicated ids on one page
  silently break arrowheads in some renderers.
- `fill="context-stroke"` on the arrowhead makes it inherit the path's colour, so a
  green edge gets a green head without a second marker definition.
- **Align to a grid.** Shared baselines and even gaps are most of what makes a
  hand-drawn diagram read as deliberate.
- Text at roughly 11–16px at drawn scale. Explanatory sentences go in the caption,
  not in the drawing.

**Connectors are where hand-authored figures fall apart.** The boxes are easy; the
lines between them are what reads as deliberate or as a tangle.

- **Orthogonal only.** `H` and `V` runs joined by an `8`-radius arc quadrant. A
  diagonal line between two axis-aligned boxes always looks like an accident:

  ```
  d="M170,238 H232 a8,8 0 0 1 8,8 V300"
  ```

- **Labels above the line, never on it.** Sit `.svg-l` 6–10px above its connector and
  mask the span behind it with a `rect` filled `var(--fig)` — the figure ground — so
  the line breaks cleanly instead of striking through the text. Paint the mask
  immediately before the label and after the path, and keep it clear of every box:
  a mask painted over a node punches a hole in it.
- **Fan the attach points.** Where several connectors meet one box edge, spread their
  endpoints ≥12px apart rather than stacking them on the midpoint. Merged tails read
  as one relationship.
- **Don't cross.** Reorder the boxes first — a crossing is nearly always a layout
  that hasn't been solved yet. If one is genuinely unavoidable, hop it: break the
  line with a small arc over the one it passes.
- **A line passing behind a box it doesn't connect to is dashed**, with its label at
  the visible end. Otherwise the reader can't tell whether the box is a stop on the
  path or scenery.

---

## The class tokens

**These class names are a public API.** Existing figures are written against them and
new ones must be. Restyle what they resolve to; never rename or drop one.

| Class | On | Means |
|---|---|---|
| `.fig` | wrapper `div` | Framed, horizontally scrollable figure container |
| `.svg-box` | `rect` | A component — the default box |
| `.svg-box-2` | `rect` | A secondary/infrastructure box, filled a step darker |
| `.svg-zone` | `rect` | A dashed boundary — a trust, billing, or ownership perimeter |
| `.svg-t` | `text` | Box title |
| `.svg-s` | `text` | Small annotation under a title |
| `.svg-l` | `text` | Edge label |
| `.svg-edge` | `path` | A neutral connection |
| `.svg-turf` | `path` | The good/chosen path — green |
| `.svg-ochre` | `path` | The conditional or deploy-time path — amber |
| `.svg-clay` | `path` | The failure or rejected path — red |
| `.svg-dash` | `path` | Modifier: dashed. Combine, e.g. `class="svg-turf svg-dash"` |
| `.t-turf` `.t-ochre` `.t-clay` | `text` | Text in the matching semantic colour |

Colour carries meaning, and only three meanings: **chosen/safe**, **conditional**,
**failure**. Everything else is neutral. Never colour a box for decoration — a reader
who learns that green means "this is the path you want" will trust it everywhere.

Do not hardcode hex values in a figure. Inline `style="stroke:var(--ochre)"` on a
`rect` is the one accepted exception, for boxes that need a semantic border colour.

---

## Captions and accessibility

Every figure carries both:

- **`aria-label` on the `<svg>`** — a full sentence describing what the picture shows,
  written for someone who will never see it. Not "architecture diagram". Describe the
  path: what connects to what, and what the colours distinguish.
- **`<figcaption>`** — states the claim in bold, then one or two sentences of
  consequence. The caption is where the argument lands; the drawing is evidence.

Write the `aria-label` first. If you can't describe the diagram in a sentence, it
isn't showing one thing yet.
