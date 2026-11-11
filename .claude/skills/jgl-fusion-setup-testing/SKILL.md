---
name: jgl-fusion-setup-testing
description: Wires the CI-runnable test layers into an existing Fusion add-in that lacks them — pytest with mock_adsk for Python, Vitest for the webapp, the CI workflow, and a pre-push hook — and explains the in-Fusion integration layer. Use when the user says "set up testing" or "/jgl-fusion-setup-testing", or when /jgl-fusion-check reports a missing test framework.
disable-model-invocation: true
---

# Setup Testing (Fusion add-in)

Bootstrap the test infrastructure on a Fusion add-in that's missing it.
This is the **brownfield helper** — use it on an existing add-in that
wasn't built with `/jgl-fusion-scaffold` and so doesn't have the three
layers wired up.

For a **new** add-in, use `/jgl-fusion-scaffold` instead — it already
produces all three layers, so this skill would have nothing to do.

## What "three layers" means here

Fusion add-ins need three separate test layers, each gated differently:

1. **Python unit tests** (pytest) — pure logic in
   `code/<prefix>_tests/`, mocks `adsk.*` modules. Runs in CI on every
   PR. Fast.
2. **TypeScript unit tests** (Vitest) — pure logic extracted out of
   React components. Runs in CI on every PR. Fast.
3. **Fusion integration tests** (unittest) — real Fusion API
   operations in `code/<prefix>_fusion_tests/`. Runs *inside Fusion 360
   itself*, not in CI. CI validates a hash of the source tree against
   the last in-Fusion run to make sure integration tests aren't stale.

This skill wires up layers 1 and 2. Layer 3 cannot be added by a script —
it requires running Fusion and clicking "Run Tests."

## 1. Identify the prefix

Find the add-in's lowercase prefix by listing `code/`. It's the
directory matching `*_tests/` or `*_commands/`. Example: in
`code/mytool_tests/`, the prefix is `mytool`.

If `code/` doesn't exist or has no prefixed directories, stop and ask the
user. Either the add-in hasn't been scaffolded yet (use
`/jgl-fusion-scaffold`) or its packages are unprefixed — a finding worth
surfacing on its own, because bare names collide on `sys.path` (PY-5).

## 2. Check what's already there

Before installing anything, show the user a checklist of what's already in
place: `code/<prefix>_tests/` with `mock_adsk.py` and passing `test_*.py`
files; `pytest` and `pytest-cov` installed and listed in
`requirements-dev.txt`; and in `webapp/`, Vitest in `devDependencies`,
`test` / `test:coverage` scripts, test config in `vite.config.ts`, and any
`*.test.ts`. Install only what's missing.

## 3. Install Python deps

If `pytest` or `pytest-cov` is missing:

```bash
pip install pytest pytest-cov
# also add to requirements-dev.txt if the project uses one:
echo "pytest" >> requirements-dev.txt
echo "pytest-cov" >> requirements-dev.txt
```

## 4. Set up Python unit-test scaffolding

If `code/<prefix>_tests/` is missing:

```bash
mkdir -p code/<prefix>_tests
touch code/<prefix>_tests/__init__.py
```

Copy `mock_adsk.py` from `templates/scaffold/code/{{addin_prefix}}_tests/mock_adsk.py`,
substituting `{{addin_prefix}}` with the project's actual prefix. This
is the mock layer that lets unit tests import production code without
loading Fusion itself.

Write a **real** starter unit test — not `assert True`. Pick a small
piece of pure logic that already exists (a calculation, a parser, a
state-management function) and assert on a specific computed value.
Cover sizes 0/1/N where it applies.

Example shape:

```python
# code/<prefix>_tests/test_<thing>.py
from <prefix>_tests.mock_adsk import setup_adsk_modules
setup_adsk_modules()

from <prefix>_lib.calculations import compute_offset

def test_compute_offset_zero():
    assert compute_offset(0.0, 0.0) == 0.0

def test_compute_offset_handles_negative():
    assert compute_offset(-5.0, 2.0) == -3.0
```

## 5. Set up Vitest in webapp/

If `webapp/` exists but `vitest` isn't installed:

```bash
cd webapp
npm install -D vitest jsdom @vitest/coverage-v8
```

Add to `webapp/vite.config.ts` (or create `webapp/vitest.config.ts`):

```ts
/// <reference types="vitest" />
import { defineConfig } from 'vite';

export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.*', 'src/main.tsx'],
    },
  },
});
```

Add scripts to `webapp/package.json`:

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage"
  }
}
```

Write a **real** TypeScript starter test on a pure utility:

```ts
// webapp/src/utils.test.ts
import { describe, it, expect } from 'vitest';
import { someUtility } from './utils';

describe('someUtility', () => {
  it('handles the canonical case', () => {
    expect(someUtility(42)).toBe(/* the real expected value */);
  });
  it('handles zero', () => {
    expect(someUtility(0)).toBe(/* the real expected value */);
  });
});
```

## 6. Wire CI

If `.github/workflows/tests.yml` doesn't exist, copy the template from
`templates/scaffold/.github/workflows/tests.yml`, adjusting the prefix
substitutions. If a workflow already exists, **don't overwrite it** —
report what changes you'd make and let the user decide.

The CI workflow has two jobs: Python (pytest + pytest-cov + hash
validation) and TypeScript (Vitest + build). See ARCHITECTURE.md for
the full structure and `templates/scaffold/.github/workflows/tests.yml`
for the canonical version.

## 7. Add a pre-push hook

CI catching a red suite *after* the push is too late. Add a
version-controlled pre-push hook that runs the same fast gate locally and
blocks the push on failure. Write `.githooks/pre-push` (substituting the
real prefix for `<prefix>`):

```bash
#!/usr/bin/env bash
#
# pre-push hook — run the CI-runnable test layers before a push.
# Mirrors CI's fast gate: Python unit tests + webapp unit tests. It does
# NOT run Fusion integration tests (they need Fusion 360) or the
# integration-hash check (test_fusion_results.py) — a stale hash is a
# legitimate state, so that gate stays in CI and /jgl-fusion-push's warning.
#
# Emergency bypass (people, not agents):  git push --no-verify
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

echo "pre-push: pytest + webapp tests …"

if ! python -m pytest code/<prefix>_tests/ -q \
    --ignore=code/<prefix>_tests/test_fusion_results.py; then
  echo "pre-push: ✗ Python unit tests failed — push aborted." >&2
  exit 1
fi

if [ -d webapp ]; then
  if ! ( cd webapp && npm test ); then
    echo "pre-push: ✗ webapp unit tests failed — push aborted." >&2
    exit 1
  fi
fi

echo "pre-push: ✓ tests passed."
```

Then make it executable and activate the version-controlled hooks path
(once per clone — tell the user to re-run the `config` line on any other
clone):

```bash
chmod +x .githooks/pre-push
git config core.hooksPath .githooks
```

If `.githooks/pre-push` already exists, **don't overwrite it** — report
what you'd change and let the user decide.

If `core.hooksPath` is already set to something other than `.githooks`
(Husky, lefthook, the pre-commit framework), don't repoint it — that would
switch off the hooks the repo already relies on. Show the user the lines to
add to their existing setup instead.

## 8. Verify

Run both unit-test suites once to confirm everything works:

```bash
python -m pytest code/<prefix>_tests/ -v
cd webapp && npm test
```

If anything fails, fix it in the same session rather than leaving the add-in
half-configured.

## 9. Tell the user about layer 3

Integration tests run inside Fusion, so no script can add them. If the Fusion
MCP server is connected (`/jgl-fusion-mcp`), `run_and_save()` can run them
headlessly; otherwise point the user at the in-Fusion workflow:

> "Layer 3 (Fusion integration tests) is set up next:
>
> 1. In `config.json`, set `enable_tests: true`.
> 2. Load the add-in in Fusion.
> 3. Click the 'Run Tests' button in the add-in's toolbar (it'll
>    appear once `enable_tests: true`).
> 4. Commit the resulting `code/<prefix>_tests/fusion_test_results.json`
>    alongside your code.
>
> CI will start requiring this file once it exists. Re-run 'Run Tests'
> in Fusion any time you change source files — `/jgl-fusion-status`
> will warn you when the hash is stale."

## 10. Report

```
✓ pytest + pytest-cov installed; added to requirements-dev.txt
✓ code/mytool_tests/mock_adsk.py copied from template
✓ code/mytool_tests/test_offset.py written (2 tests, both passing)
✓ Vitest + @vitest/coverage-v8 + jsdom installed in webapp/
✓ webapp/vite.config.ts updated with test config
✓ webapp/package.json scripts added: test, test:watch, test:coverage
✓ webapp/src/utils.test.ts written (2 tests, both passing)
⊘ CI workflow exists; suggested changes shown above (not applied)
✓ .githooks/pre-push written + chmod +x; core.hooksPath set to .githooks
⊘ Integration tests (layer 3) require running Fusion — see above

Next: run /jgl-fusion-check to confirm everything's wired correctly.
```
