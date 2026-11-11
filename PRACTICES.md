# Practices

Engineering practice for a Fusion add-in that doesn't need to be in front of
the agent on every turn. `AGENTS.md` holds the rules agents get wrong without
being told (Python, API, MCP, testing gates); this file is the lookup for
writing tests, wiring CI, adding a dependency, or planning a refactor.

Contents: Code structure · Testing craft · Coverage · CI and the pre-push
hook · Dependencies · Refactoring · Code quality

## Code structure

- **STRUCT-1** — Optimize for cohesion, not line count: everything one concept
  needs in one place, named after the concept.
- **STRUCT-2** — One concept per file, where a concept can be a whole feature.
  One-function-per-file scatters a feature for humans and agents alike.
- **STRUCT-3** — ~500 lines is a soft ceiling. Multiple responsibilities is the
  smell, not length.
- **STRUCT-4** — One clear responsibility per function. Predictable named
  exports, no hidden global state, no clever metaprogramming.
- **STRUCT-5** — Explicit return types (TypeScript) and type hints (Python) on
  public functions. Discriminated unions (TS) or enums/string literals (Python)
  over boolean flags for multi-state values.
- **DUP-1** — Two identical blocks is usually fine; three is borderline; four
  or more, extract.
- **DUP-2** — Centralize shared constants, regexes, and magic strings.
- **DUP-3** — Three similar lines beat a premature abstraction. Never extract a
  helper for one caller.

## Testing craft

`AGENTS.md` carries TEST-1..4 (plans include tests, real assertions, every test
catches a bug, the integration hash). The rest:

- **TEST-5** — Test behavior, not implementation: names describe what the
  system does ("pairs joint origins by name"), and a refactor shouldn't break
  them.
- **TEST-6** — Cover sizes 0, 1, 2, and N for anything that takes a
  collection. Round-trip every serialize/restore pair — state crosses the
  Python–React boundary as JSON, so this is where add-ins break.
- **TEST-7** — Mock at architectural seams. Python unit tests mock the Fusion
  API through `mock_adsk.py`; TypeScript tests mock `fusionBridge.ts` for
  components that call Python. Pure utilities need no mocks. If you're mocking
  more than you're testing, step back.
- **TEST-8** — Integration tests (`code/<prefix>_fusion_tests/`) use
  `unittest.TestCase` with `setUpClass`/`tearDownClass` to create and clean up
  temp documents. They need a live Fusion session, so they never run in CI —
  CI checks their committed results instead (TEST-4).
- **TEST-9** — The in-Fusion test runner inlines its own codebase-hash
  function instead of importing `<prefix>_fusion_tests.hash_utils`, because
  another add-in's bare `fusion_tests` package can shadow the import. Keep the
  two copies identical.
- **TEST-10** — Correctly untested: framework glue that only forwards
  arguments, type-only files, pure-presentation components, bootstrap files.
  No snapshot tests for computed values.

## Coverage

- **COV-1** — Coverage finds untested code; it can't tell whether tested code
  is tested well. Judge test quality by reading the tests ("what could break,
  and would this catch it?"), then type checking, then coverage.
- **COV-2** — No hard coverage thresholds that fail the build — they reward
  filler tests. Core logic (calculations, transforms, state) should be high;
  bridge glue and UI can be lower.
- **COV-3** — Integration coverage is a lower bound: production modules load
  when Fusion starts, long before "Run Tests", so `def`/`class` lines look
  missed. Function bodies are recorded correctly. The coverage package lives in
  gitignored `code/lib/coverage_pkg/` (`pip install coverage
  --target=code/lib/coverage_pkg`) and is excluded from the codebase hash.

Tools: `pytest-cov` with `--cov-report=term-missing --cov-report=json`;
`@vitest/coverage-v8` with `text` and `text-summary` reporters. CI merges the
Fusion coverage block with pytest-cov per file (`ARCHITECTURE.md`, "Coverage
Capture").

## CI and the pre-push hook

- **CI-1** — GitHub Actions with two jobs. Python: install pytest + pytest-cov →
  unit tests with coverage → validate the integration-results hash → job
  summary. TypeScript: `npm ci` → `npm run test:coverage` → `npm run build` →
  job summary. Keep coverage artifacts ~14 days.
- **CI-2** — The hash check is what keeps integration tests honest: if source
  changed since the last in-Fusion run, CI fails until the developer re-runs
  them and commits fresh results.
- **CI-3** — A version-controlled pre-push hook at `.githooks/pre-push`,
  activated once per clone with `git config core.hooksPath .githooks`, runs the
  CI-runnable layers only: pytest (with `--ignore` on `test_fusion_results.py`)
  and `cd webapp && npm test`. No coverage, no integration tests.
- **CI-4** — The hash check stays out of the pre-push hook: a stale hash is a
  normal state between edits and the in-Fusion re-run. `/jgl-fusion-push` warns
  about it instead.
- **CI-5** — If the repo already sets `core.hooksPath` elsewhere (Husky,
  lefthook, pre-commit), add the checks there rather than repointing it.
- **CI-6** — `--no-verify` is a human's emergency exit, not a routine way past
  a red suite.

## Dependencies

- **DEP-1** — Python dependencies stay minimal: add-ins run in Fusion's
  embedded Python, and every install is friction for users. Pin runtime deps in
  `requirements.txt`; dev deps (pytest, pytest-cov) in `requirements-dev.txt`.
- **DEP-2** — Webapp: prefer maintained packages, and don't add one for a few
  lines of code.
- **DEP-3** — Run `npm audit` after adding or upgrading packages and fix
  findings before committing.
- **DEP-4** — Pin major versions in `package.json`.

## Refactoring

- **REF-1** — Refactoring untested code is high-risk; add tests first.
- **REF-2** — A refactor keeps behavior: existing tests pass without
  modification. Run them after each step, not just at the end.
- **REF-3** — No speculative future-proofing.
- **REF-4** — No backwards-compatibility shims; delete what's unused.

## Code quality

- **QUAL-1** — Static analysis and tests together; neither alone is enough.
- **QUAL-2** — Explicit over compact: no nested ternaries or clever one-liners.
- **QUAL-3** — Delete dead code; don't comment it out.
- **QUAL-4** — Validate only at system boundaries (user input, external APIs,
  Fusion API responses); no handling for cases that can't happen.
