## Verification
- Commands run: `test -f skills/recover/SKILL.md` pass; `grep -E '^\| R-0[1-9]|^\| R-1[0-2]'` → 12 lines pass; `grep disable-model-invocation` empty pass; `grep -i orchestrator` hits R-06 pass; `grep specs/active|specs/done` empty pass
- Contract items: YAML name recover → met; twelve codes → met; pointer ramps name diagnose/tdd/checkpoint/grill → met; gap ramps have PROTECTION → met
- Artifacts: `skills/recover/SKILL.md`
- Decisions honored: none pointed
