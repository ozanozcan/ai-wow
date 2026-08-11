# Third-party content

Most of this repository is original work under the MIT license in
[`LICENSE`](LICENSE). Three of the fourteen bundled skills are not — they were
installed from other projects and are redistributed here under their own terms.

| Skill | Upstream | License | Full text |
|---|---|---|---|
| `skills/tdd/` | [mattpocock/skills](https://github.com/mattpocock/skills) | MIT — © 2026 Matt Pocock | [`skills/tdd/LICENSE`](skills/tdd/LICENSE) |
| `skills/grill-with-docs/` | [mattpocock/skills](https://github.com/mattpocock/skills) | MIT — © 2026 Matt Pocock | [`skills/grill-with-docs/LICENSE`](skills/grill-with-docs/LICENSE) |
| `skills/playwright-cli/` | [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli) | Apache-2.0 — © Microsoft Corporation | [`skills/playwright-cli/LICENSE`](skills/playwright-cli/LICENSE) |

**None of these three has been modified.** They are byte-identical to what the
`skills` CLI installed, so there are no changes to declare under Apache-2.0 §4(b).
`microsoft/playwright-cli` ships no `NOTICE` file, so there is nothing to propagate.

Exact upstream commits are recorded in [`skills.lock.json`](skills.lock.json)
(`skillFolderHash` per skill).

## Not bundled

**`impeccable`** ([pbakaus/impeccable](https://github.com/pbakaus/impeccable),
Apache-2.0) is referenced throughout the docs as the UI design skill, but is
deliberately **not** vendored here — at ~99 files it would have been the bulk of
this repository, and it is better taken fresh from its own source. Install it
alongside the others:

```bash
npx skills add pbakaus/impeccable
```

Everything else works without it. What you lose: the `impeccable` routing rows in
the design workflow, and the `ui-designer` subagent's visual-craft companion — that
agent still functions, it simply won't have `impeccable` to hand off to.

## Restoring the full skill set

`skills.lock.json` records every skill that came from an upstream, so a fresh clone
can reproduce the original set:

```bash
npx skills add mattpocock/skills          # tdd, grill-with-docs (already bundled)
npx skills add microsoft/playwright-cli   # playwright-cli       (already bundled)
npx skills add pbakaus/impeccable         # impeccable           (not bundled)
```

The eleven remaining skills — `adversarial-tester`, `checkpoint`,
`complexity-audit`, `imprint`, `improve-codebase-architecture`, `mow`,
`parallel-debug`, `pick-up-where-i-left-off`, `ship-check`, `test-coverage`,
`wrap-up` — are original to this repository and covered by [`LICENSE`](LICENSE).
