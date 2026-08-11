# candidate: path-tagged decision neither accepted nor waived

## Goal
Demonstrate candidate hard-floor when decision tags touch Files in scope.

## Context & decisions (only what this todo needs)
- A decision tagged path:scripts/b.py exists on the board.
- Cell is `-` — neither accepted nor waived.

## Files in scope
- scripts/b.py

## Do NOT
- Do not silently omit matching decisions.

## Acceptance check
- Preflight SHALL exit 1 listing the candidate decision.
- GIVEN path-tagged decision absent from cell WHEN preflight runs THEN exit 1 with accept/wave-off instruction.
- Verify: `pytest tests/test_mow_preflight.py -k candidate -q`

## QA contract
- `pytest tests/test_mow_preflight.py -k candidate -q`
