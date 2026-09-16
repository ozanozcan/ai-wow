Respond to production degradation. **Iron rule: stabilize first, learn second** — agents do not touch production unilaterally.

## Flow

1. **Human executes or explicitly approves** every stabilize action (revert, flag, rate-limit, scale). Prefer mitigation over a clever hotfix.
2. Capture evidence before it evaporates (timestamps, logs, traces, config snapshots) — write paths the operator can attach to a postmortem.
3. When rollback is the procedure, **`/recover R-11`** — names `git revert`, forbids force-push/`reset --hard`, and **stops for the operator** before revert unless AFK-no and they just approved.
4. After stabilization, run **`/fix-bug`** on the underlying defect — mitigation alone is not "done."
5. Write a short **postmortem**: timeline, root cause, and **which gate would have caught it** (test, review, ship-check, hook).
6. Record durable outcomes in the product repo's ledger (`LESSONS.md` if present, else `docs/`). This harness has no production; treat steps 1–5 as the contract when this command is installed in a product repo.
