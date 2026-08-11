---
name: test-coverage
description: Find untested code paths in a project and generate test cases for them. Stack-agnostic — reads existing tests to learn the project's conventions (test runner, fixtures, factories, assertion style) before generating anything. Use when asked to improve test coverage, add tests for a new feature, when a just-built or just-changed module has no or thin tests, or when the user doubts something is tested.
---

# Test Coverage

Find untested code paths and generate tests that match the project's existing conventions.

## Step 1 — Learn the project's test conventions

Do not assume a framework. Read the project first.

1. Check `CLAUDE.md` for the test runner, test command, and any testing conventions.
2. Find the test directory — look for `tests/`, `__tests__/`, `spec/`, `test/`, or equivalent.
3. Read **2–3 existing test files** to learn:
   - Test runner and assertion style (pytest, vitest, jest, rspec, go test, …)
   - How test data is created (factories, fixtures, builders, plain constructors)
   - How DB access is handled (transaction rollback, test DB, mocks, in-memory)
   - How HTTP is tested (test client, supertest, httpx, …)
   - File naming and structure conventions
4. Check for a `conftest.py`, `setup.ts`, `jest.config`, or equivalent to find shared fixtures/helpers.
5. Note the test run command — you'll use it to verify generated tests at the end.

**Never invent fixture names, factory classes, or import paths.** Use only what you find in the project.

## Step 2 — Identify coverage gaps

### If a specific file or module is given:
Read it and list every public function, class method, route handler, or service method that has no corresponding test.

Verify with a search before flagging as untested:
```bash
grep -r "def test_\|it(\|test(\|describe(" tests/ --include="*.py" --include="*.ts" --include="*.js" | grep <function_name>
```

### If no scope is given:
Prioritize in this order:
1. **Auth and permission logic** — highest risk if untested
2. **Business logic / service layer** — the functions callers depend on
3. **Data access / query layer** — especially multi-tenant or user-scoped queries
4. **API endpoints with custom logic** — non-CRUD handlers
5. **Pure utility functions with complex branching** — easiest to test, high ROI

Skip: generated code, migrations, and trivial getters/setters.

## Step 3 — Generate tests

For each gap, write a test that:
1. Covers the happy path
2. Covers at least one failure or edge case (invalid input, unauthorized access, boundary values)
3. Uses existing fixtures, factories, and helpers — never create new infrastructure when existing ones work
4. Follows the project's file naming and placement convention exactly
5. Matches the assertion and setup style you observed in Step 1

**Generic template (adapt to the project's style):**

```
// Arrange — set up state and inputs
// Act — call the function or endpoint
// Assert — verify the outcome
// (Clean up if the project doesn't handle it automatically)
```

For pure logic (no I/O): test inputs → outputs directly; no network/DB setup needed.
For DB-touching code: use the project's DB isolation pattern (transaction rollback, test DB, etc.).
For HTTP endpoints: use the project's test client pattern found in Step 1.

**Multi-tenant / access control** — always include a test that verifies one user/tenant cannot access another's data. This is HIGH priority if the project is multi-tenant.

## Step 4 — Output

List each gap:
```
UNTESTED: <function/method/endpoint name>
File: path/to/source/file
Test file: path/to/test/file (existing or new)
Priority: HIGH | MEDIUM | LOW
  HIGH = auth/permission logic, multi-tenant isolation, data mutation
  MEDIUM = business logic, service methods
  LOW = utilities, read-only helpers
```

Then write the actual test code for the top 3 HIGH-priority gaps, or whichever the user asks for.

After writing, run the tests to confirm they pass:
```bash
# Use the test command from CLAUDE.md or discovered in Step 1
# e.g.: pytest tests/path/test_file.py -v
#       npx vitest run src/path/file.test.ts
#       go test ./...
```

If tests fail, fix them before reporting done.
