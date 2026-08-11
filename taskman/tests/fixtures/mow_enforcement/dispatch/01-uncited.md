# uncited: pointer not cited in Acceptance/Do NOT

## Goal
Demonstrate uncited-pointer-blocks-go.

## Context & decisions (only what this todo needs)
- INDEX points at a decision that this brief must not cite in Acceptance/Do NOT.
- Acceptance does not cite it — preflight must exit 1.

## Files in scope
- scripts/a.py

## Do NOT
- Do not cite the INDEX pointer id in this section (this fixture is the failure case).

## Acceptance check
- Preflight SHALL refuse fan-out for an uncited INDEX pointer.
- GIVEN INDEX cell with one decision WHEN preflight runs THEN exit 1 naming lane A.
- Verify: `pytest tests/test_mow_preflight.py -k uncited -q`

## QA contract
- `pytest tests/test_mow_preflight.py -k uncited -q`
