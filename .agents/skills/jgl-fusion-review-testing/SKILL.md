---
name: jgl-fusion-review-testing
description: Audits a Fusion add-in's tests across all three layers — Python unit, TypeScript unit, and in-Fusion integration — for weak assertions, untested logic, tests that assert the implementation, mock_adsk gaps, stale integration hashes, and CI gates that can't fail, and produces a prioritized testing plan if one is warranted. Use when the user says "review tests", "/jgl-fusion-review-testing", "audit tests", "are my tests any good?", or before a refactor.
context: fork
background: false
---

# Review Testing (Fusion add-in)

Judge whether the tests catch real bugs, not how the coverage number looks.
For every test, ask: what specific, plausible bug would this catch? If the
answer is "only someone deleting the function", flag it. Report and plan
only — don't write tests.

`<prefix>` is the add-in's package prefix (the `code/*_tests/` directory).

## Evidence

1. **The tests themselves** — read what each one asserts.
2. **A run** — `python -m pytest code/<prefix>_tests/ -v`,
   `cd webapp && npm test`, and `cd webapp && npx tsc -b`; note failures.
3. **Coverage** — `python -m pytest code/<prefix>_tests/ --cov=code/
   --cov-report=term-missing` and `cd webapp && npm run test:coverage`.
   Missing tooling is `⊘ SKIPPED — <setup hint>` and a finding (`pip install
   pytest-cov`; add `"test:coverage": "vitest run --coverage"`).
4. **Integration status** — `code/<prefix>_tests/fusion_test_results.json`:
   hash validity, pass/fail counts, the `coverage` block. If the Fusion MCP
   server is live you can run the suite for ground truth via `run_and_save()`
   — confirm liveness first and restart the add-in after production edits
   (MCP-1, MCP-3; `/jgl-fusion-mcp` has the preflight).
5. **The CI gates** — see below.

## The gate inventory (do this first)

List every gate and what it runs: the PR workflow, any deploy gate, local
hooks, and the integration tests that only run inside Fusion. Fusion add-ins
legitimately gate three layers differently — Python and TypeScript unit tests
on every PR, integration tests through the CI hash check (TEST-4), and
sometimes the webapp build only at release. Then map each test file to the
gate that runs it: a file no gate runs is as bad as a missing test.

Check that each gate can fail the build: both test jobs exist and run on
every PR and push to the default branch; the Python job includes
`test_fusion_results.py` (the hash check); no `continue-on-error: true`,
`|| true`, or `exit 0` on test steps (`if: always()` on *reporting* steps is
fine); no committed `.only` / `.skip` / `xit` / `@pytest.mark.skip`; no
`paths:` filters that skip test directories.

## Pass 1 — collect everything

List every issue with file and line before deciding what matters:

- **Untested logic** — files with real business logic and no tests.
- **Weak assertions** — `assert x is not None`, `toBeDefined()`,
  `not.toBeNull()`, regex-matches-anything (TEST-2). Show what a meaningful
  assertion would be. This is the most important check.
- **Missing edges** — collection functions tested at one size only (0, 1, 2,
  N); serialize/restore pairs without a round trip — state crossing the
  Python–React boundary is a common gap.
- **Tests that assert the implementation** — expected values read off a run
  rather than derived from a requirement, one test per branch mirroring the
  code, mocks returning exactly what the code asks for. State the requirement
  without looking at the code, then ask whether the test would fail if the
  code broke it.
- **Over-mocking** — mocks below the architectural seams (TEST-5..10).
- **`mock_adsk.py` gaps** — Fusion types production code uses (including
  `isinstance` checks) that the mock doesn't provide, and methods called on
  mocks that fall through to `Mock()` defaults instead of testing behavior.
- **Bridge mocks** — components calling `sendToFusion()` whose mocked
  responses don't match what the Python side actually returns.
- **Integration gaps** — a stale or missing hash; Fusion-API code with neither
  unit nor integration coverage; common untested areas: joint
  creation/deletion, attribute round trips, preview cleanup, palette
  lifecycle, custom feature edit/delete.
- **CI gaps** from the inventory, on equal footing with missing tests.

## Pass 2 — decide

No action is needed when logic files have tests with assertions on real
values, critical paths cover their edges, core logic coverage is high, the
integration hash is current, and both test jobs run in CI on every PR and
push to main with no way to soft-fail. Say so and stop.

Otherwise, plan:

1. **Do first** — CI gaps (they make every later improvement trustworthy),
   re-running stale integration tests, tests for untested business logic,
   replacing weak assertions, extending `mock_adsk.py`.
2. **Do second** — round trips for state serialization, edge cases,
   integration tests for untested Fusion API paths.
3. **Skip for now** — gaps that aren't worth it (bootstrap, type-only,
   pure-presentation code), one line each.

Frame every item as behavior to verify, never a coverage number: "test
`build_joint_pairs()` in `code/mt_lib/joints.py` for zero, one, and several
components with matching joint origins", not "raise coverage to 85%". Name
the layer (Python unit, TypeScript unit, or Fusion integration). Pair with
`/jgl-fusion-review-code`: tests first, then refactor.

## Later passes

On a thinly tested add-in, expect 2–3 passes in a session. On a re-run, start
from what changed since the last pass (`git log`), compare coverage and
integration pass counts with last time, and say plainly when the bar above is
met rather than finding something to justify another pass.
