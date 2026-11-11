---
name: jgl-fusion-check
description: Runs every check a Fusion 360 React-palette add-in has — webapp audit, type check, unit tests and build; Python audit and unit tests; and the integration-test hash gate, refreshing it through the Fusion MCP server when stale — and reports gates and drift signals with an explicit SKIPPED line for anything not installed. Use when the user says "check", "/jgl-fusion-check", "verify", or "is everything passing".
context: fork
background: false
---

# Check (Fusion add-in)

Run every check the add-in has and report each one honestly: passed, failed,
or skipped because the tool isn't there. A skip that reads like a pass is the
failure this skill exists to prevent — the user would believe an audit ran
that didn't. Read and run only; don't fix anything.

`<prefix>` is the add-in's lowercase package prefix: the directory in `code/`
matching `*_tests/`. Prefer the commands in the Commands table in `AGENTS.md`;
in an existing add-in, use what its CI runs.

## What to run

Run every line, even after one fails — the user wants the whole picture.

**Gates** (a failure blocks a push):

- **webapp audit** — `cd webapp && npm audit`.
- **webapp types** — `cd webapp && npx tsc -b`.
- **webapp tests** — `cd webapp && npm test`. No `test` script at all is
  `✗ NO TEST FRAMEWORK`, a finding — offer `/jgl-fusion-setup-testing`.
- **webapp build** — `cd webapp && npm run build`. The palette loads
  `webapp/dist/`, so a broken or stale build is what the user would see in
  Fusion (BUILD-1).
- **python audit** — `pip-audit`. Not installed is
  `⊘ SKIPPED — pip-audit not installed (install: pip install pip-audit)`.
- **python tests** — `python -m pytest code/<prefix>_tests/ -v`.
- **integration hash** — see below.

**Drift signals** (worth watching, never a failure): Python and webapp
coverage percentages, if coverage tooling is configured (COV-1..3).

A missing tool is `⊘ SKIPPED — <why> (install: <command>)` and counts as a
finding.

## The integration hash gate (TEST-4)

Read `code/<prefix>_tests/fusion_test_results.json` and compare its stored
`codebase_hash` with the current one (`compute_codebase_hash` from
`code/<prefix>_fusion_tests/hash_utils.py`). Report one of:

- **current** — hash matches and all tests passed (give the count);
- **stale** — hash mismatch: integration tests must be re-run before pushing,
  or CI rejects it;
- **missing** — integration tests have never been run.

If stale or missing, try to refresh it without leaving the chat, but confirm
the Fusion MCP server is live first (MCP-1):

1. No `fusion_mcp_*` tool in your toolset → `⊘ SKIPPED — Fusion MCP not
   connected`; point at `/jgl-fusion-mcp` or the "Run Tests" button, and stop.
2. A cheap probe (`fusion_mcp_read` `document`/`open`, or an `execute` that
   prints `app.version`) errors → `⊘ SKIPPED — Fusion not running`; ask the
   user to open Fusion and load the add-in, and stop.
3. Production source changed since the add-in last loaded → ask the user to
   restart it (Stop → Run) first, or the run tests stale code (MCP-3).

Then run the headless entry point and re-check the hash:

```python
from <prefix>_commands.testRunner.entry import run_and_save
def run(_context):
    r = run_and_save()
    print(r['tests_run'], r['passed'], r['failed'], r['errors'], r['codebase_hash'])
```

It writes the same hash-validated results file a button click would.

## Report

```
Gates — a failure here blocks the push
  ✓ webapp audit   npm audit — 0 vulnerabilities
  ✓ webapp types   tsc — clean
  ✓ webapp tests   14 passed
  ✓ webapp build   dist/ rebuilt
  ⊘ python audit   SKIPPED — pip-audit not installed (install: pip install pip-audit)
  ✗ python tests   2 failed of 31 (test_joint_utils.py:44, :61)
  ✓ integration    current — 12 passed (refreshed via MCP)

Drift signals — watch the trend, don't gate on the number
  ✓ coverage       python 78%, webapp 84%
```

Markers: `✓` passed, `✗` failed, `!` over a drift threshold, `⊘` skipped or
N/A (always with a reason). Put failing output and install commands under the
summary. Don't turn a drift signal into a failure.
