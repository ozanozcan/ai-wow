# waived: candidate waved off in INDEX cell

## Goal
Demonstrate waived ids skip hydrate and citation.

## Context & decisions (only what this todo needs)
- d#3 would match Files in scope but is waved off.
- Hydrate must exclude it; citation must not require it.

## Files in scope
- scripts/c.py

## Do NOT
- Do not hydrate or citation-check waived ids.

## Acceptance check
- Preflight SHALL pass when the matching decision is `waived: d#3 (reason)`.
- GIVEN waived: d#3 (other lane owns it) WHEN preflight runs THEN no candidate error for #3.
- Verify: `pytest tests/test_mow_preflight.py -k waived -q`

## QA contract
- `pytest tests/test_mow_preflight.py -k waived -q`
