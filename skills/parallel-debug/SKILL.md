---
name: parallel-debug
description: Debug 2+ unrelated failures in parallel — one subagent per independent problem (different test files, subsystems, or bugs). Auto-invoke from tdd-builder / mow lanes when pytest shows multiple failures with different root causes. Not for failures that share one cause or exploratory "what's broken?" sessions.
---

# Parallel Debug

When **multiple unrelated failures** exist, investigating them one-by-one in a single chat wastes time and pollutes context. Dispatch **one focused subagent per independent problem domain** and run them concurrently.

**Not for:** building features, executing plans, or related failures that share one root cause. For those use **`/diagnose`** (single bug) or **`/mow`** (multi-todo plans).

## When to use

- 2+ test files failing for **different** reasons
- Multiple subsystems broken **independently**
- Each fix can happen without context from the others
- No shared files between investigations (same wave = disjoint file ownership)
- **Auto (mow / tdd-builder):** pytest (or the lane's test command) returns **>1 unrelated** failures mid-build

## When NOT to use

- Failures might share one root cause — investigate together first with **`/diagnose`**
- You don't know what's broken yet (exploratory) — use **`/diagnose`** first
- Failures are related (fixing one may fix others)
- Agents would edit the same files

## Pattern

### 1. Group by independent domain

Example after a refactor:

- `workouts/tests/test_buddy.py` — 500 on set save
- `custom_users/tests/test_auth.py` — rate limit assertion
- `recommendations/tests/test_engine.py` — empty queryset

Three domains → three parallel agents.

### 2. One focused prompt per agent

Each prompt: the failing test output, the suspected files, "fix only this failure; do not touch other domains; end with what you changed + how you verified."

### 3. Fan out concurrently

Launch all domain agents in **one** message (parallel Task/Agent calls). Wait for all. Merge results; re-run the full failing set to confirm green.

### 4. Report

Summarize per domain: root cause, files touched, verify command. If two agents touched the same file, stop and reconcile before committing anything (orchestrator owns git).
