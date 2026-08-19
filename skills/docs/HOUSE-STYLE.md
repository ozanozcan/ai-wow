# House style

How a document is structured, how it sounds, and the specific habits that make
writing read as machine-generated. Read before writing; run the last section over
the draft before shipping.

## Contents

- [Structure](#structure) — the skeleton every document shares
- [Voice](#voice) — what to sound like
- [Tables, lists, prose](#tables-lists-prose) — picking the right container
- [Naming and files](#naming-and-files) — where documents live
- [The tells](#the-tells) — the checklist that catches machine-written prose

---

## Structure

**Opening.** Three short paragraphs, no heading: what it is, what it isn't, why it
exists. The "what it isn't" line does more work than the other two — it's what stops
a reader building the wrong model in the first thirty seconds.

**Contents.** Per the TOC contract in [`SKILL.md`](SKILL.md). Not optional.

**Body.** Sections ordered by the reader's path. Each section opens with its claim in
the first sentence, then supports it. If a section's first sentence could be deleted
without loss, it was throat-clearing — the second sentence was the claim.

**Sources.** Last section, always. Files, decision ids, dashboards, the spike that
produced a number. A fact you could not verify is marked as unverified or cut. This
section is why the document is still trusted in six months.

Section headings are **never numbered**. The TOC gives position. Numbers rot the
moment something is inserted, and they make every heading look like a chapter in a
manual nobody wrote.

Length is not a virtue. A four-section document that answers the question beats a
twelve-section one that surveys the territory.

---

## Voice

Write like someone who has done the thing and is telling a colleague how it went.

**Lead with the claim.** "Render's pre-deploy command runs inside the service's own
environment" — then explain why that matters. Not "There are a few considerations
around where migrations run."

**Be concrete.** A path, a command, a number, a role name, a decision id. `#875`
beats "a previous decision". `~$7/month` beats "inexpensive". If you can't be
concrete, say why: "the console doesn't publish this — read it off the plan selector".

**Say what breaks.** Every procedure has a failure mode, and the failure mode is the
part worth writing down. A document with no failure modes in it was written by
someone who hasn't done the thing.

**Admit uncertainty in the first person.** "I couldn't verify this — the console
changed since the spike" is more useful than a confident sentence that turns out to
be wrong. Hedging *everything* is the opposite failure: state plainly what you know.

**Vary the rhythm.** Long sentence, then a short one. Some sections run three
paragraphs; some are two lines and a table. Uniform paragraph length across a whole
document is the single loudest signal that nobody read it back.

**Second person for instructions, first person for judgement.** "Create the smallest
Postgres and run one query." / "I'd use a separate job — pre-deploy quietly hands the
owner credential back to the service."

---

## Tables, lists, prose

| Container | Use when | Don't use when |
|---|---|---|
| **Prose** | There's an argument, a cause, or a tradeoff | You're listing parallel facts |
| **Table** | Three or more things share the same attributes | The rows have nothing in common but existing |
| **Bullets** | Genuinely unordered, short, parallel | Each bullet is a paragraph — that's prose with dashes |
| **Numbered list** | The order is load-bearing | You just want bullets that look organised |
| **Figure** | Topology, branching flow, or a two-axis comparison | It restates a table |
| **Callout** | A trap that costs real money or time | Emphasis for its own sake — three per document, tops |

Code blocks are runnable as written, or marked as an excerpt. A block a reader pastes
and watches fail costs more trust than the block saved.

---

## Naming and files

```
docs/
  <area>/
    INDEX.md                  ← every directory gets one; it's the entry point
    <subject>.human.md        ← rationale, tradeoffs, why
    <subject>.agent.md        ← imperative steps, VERIFY / STOP / DECISION markers
```

Stems are kebab-case and are **reused** across the lifecycle — a brainstorm at
`docs/brainstorms/offline-mode.md` becomes `docs/plans/offline-mode/`, so lineage is
greppable. Add the row to the directory's `INDEX.md` in the same commit that creates
the file; an index that lags is worse than no index.

---

## The tells

Run this over the draft. Each item is a habit that makes prose read as
machine-written — not because the sentence is bad, but because the *pattern* repeats.

**Sentence-level**

- [ ] **The antithesis reflex** — "not X, but Y" / "It's not about A — it's about B".
      Fine once in a document. Three times is a signature. Rewrite two of them as
      plain statements.
- [ ] **Rule of three everywhere.** Triads in every list, every caption, every
      summary. Real things come in twos, fours, and sevens. Count yours.
- [ ] **Em-dash density.** More than one per paragraph, sustained, reads as machine
      cadence. Some become commas, some become full stops, some become nothing.
- [ ] **The aphoristic closer** — "An alert nobody has ever seen fire is not an
      alert." Earns its place once. Six of them and the document sounds like a
      LinkedIn carousel. **One per document.**
- [ ] **Bolded lead-in on every paragraph.** When everything is emphasised, the
      emphasis stops meaning anything. Reserve it for the paragraphs that carry a
      decision.
- [ ] **Symmetric captions** — "Two stores, two readers, zero overlap." Pleasing, and
      obviously constructed. Let a caption be an ordinary sentence.
- [ ] **Restating the heading** in the first sentence of the section.
- [ ] **Hedge words as filler** — "importantly", "it's worth noting", "essentially",
      "simply", "just", "robust", "seamless", "leverage", "ensure", "delve".
- [ ] **Uniform sentence length.** Read three consecutive paragraphs aloud. If they
      breathe identically, break one.

**Document-level**

- [ ] **Every section the same size and shape** — intro paragraph, figure, table,
      callout, repeat. Real documents are lumpy. The hard part gets four paragraphs;
      the obvious part gets one line.
- [ ] **Over-explaining the easy step, under-explaining the hard one.** Where did you
      actually get stuck? That's where the words go.
- [ ] **No first person, no uncertainty, no evidence of having tried it.** Add the
      line about what you ran and what came back.
- [ ] **Decorative section numbering, eyebrows, and badges** that carry no
      information. If removing it loses nothing, remove it.
- [ ] **Grid of cards where a list would do.** A card grid is a layout reflex; ask
      whether the items are really parallel enough to deserve equal boxes.

**Visual** — the published-page equivalents of the above live in
[`templates/page.template.html`](templates/page.template.html) and in the repo's
`ui-registry.md`. The same principle applies: hierarchy should come from the content's
actual importance, not from applying every component in the library once.
