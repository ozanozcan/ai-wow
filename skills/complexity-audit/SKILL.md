---
name: complexity-audit
description: Audit backend code for performance problems — N+1 ORM queries, O(n²) loops, missing DB indexes, and unnecessary data materialization. Stack-agnostic; ORM-specific fix patterns come from CLAUDE.md or the prompt. Use when a page or endpoint is slow, when building or reviewing new list/query endpoints, or when asked about query performance, N+1s, or complexity.
---

# Complexity Audit

Find performance bottlenecks in the codebase. Focus on database query patterns and algorithmic complexity.

## Step 0 — Establish the stack

Before scanning, determine the ORM and query style in use:
1. Check `CLAUDE.md` for stack information.
2. If not there, look at `pyproject.toml`, `package.json`, or a representative model/schema file.
3. Note the ORM — the N+1 fix pattern varies:
   - **SQLAlchemy async (2.0):** `selectinload` (collections), `joinedload` (to-one) in the query options
   - **Django ORM:** `select_related` (FK/to-one), `prefetch_related` (M2M/reverse FK)
   - **Prisma (Node):** `include` in the query
   - **ActiveRecord (Rails):** `includes`, `preload`, `eager_load`
   - **Other:** identify the eager-load mechanism from the project's existing code

## Step 1 — Establish scope

If the user specifies files, scan those. Otherwise:
1. Check `git diff --name-only HEAD~1` for recently changed files.
2. Fall back to scanning all service/repository/query/view files — look for patterns like `services/`, `repositories/`, `queries/`, `views/`, `resolvers/`, or equivalent for the stack.

## Step 2 — N+1 Query Detection

Flag any loop that issues a DB query on each iteration. The pattern is universal; the fix is ORM-specific.

**The anti-pattern (stack-agnostic):**
```
for record in collection:
    access record.related_thing   # hits DB each iteration — N queries instead of 1
```

**Signs to look for:**
- A loop over a queryset/result-set, followed by attribute access on a relationship that wasn't eagerly loaded
- A function called inside a loop that issues its own query
- Serialization/rendering code that triggers lazy loading per item (`.all()`, `.load()`, property access on unloaded relations)
- Nested loops where the inner loop issues a query per outer-loop item

For each finding, state the fix using the project's actual ORM vocabulary (established in Step 0).

## Step 3 — O(n²) Algorithm Detection

Flag nested loops over the same or related data:

```
# O(n²) — nested iteration over same collection
for a in items:
    for b in items:
        if similar(a, b): ...

# Hidden O(n²) — query per loop iteration
for record in records:
    related = db.query(...).filter(id=record.id)  # should be one query upfront
```

Also flag:
- Sorting a result set in application code when the DB `ORDER BY` would do it
- Building lookup dicts inside loops instead of once upfront
- Repeated filtered queries inside loops where a single query + in-memory grouping suffices

## Step 4 — Missing DB Indexes

Check model/schema files for columns that are:
- Used in frequent `WHERE` / `filter` clauses but not indexed
- Used in `ORDER BY` without an index
- Foreign key columns on the "many" side of a relationship (some ORMs don't auto-index these)
- Composite filter patterns that would benefit from a composite index

Flag any hot-path filter on a non-PK, non-auto-indexed column.

## Step 5 — Unnecessary Data Materialization

Flag cases where data is pulled into memory when a leaner operation would work:

```
# Loading all rows to count them
records = db.query(Model).all()
count = len(records)          # use .count() / COUNT(*)

# Loading full objects to get IDs
ids = [r.id for r in db.query(Model).all()]   # use .values_list / scalar subquery

# Unbounded fetch in a list endpoint
results = db.query(Model).all()   # missing LIMIT/pagination
```

## Output format

For each finding:

```
[HIGH|MEDIUM|LOW] <short title>
File: path/to/file, line N (function: func_name)
Problem: <what the query/algorithm does>
Fix: <specific ORM change or algorithm improvement, using the project's ORM vocabulary>
Estimated impact: <e.g. "reduces N+1 queries to 1 per request">
```

End with:
- Total findings by severity
- Top 3 highest-impact fixes (the ones to do first)
