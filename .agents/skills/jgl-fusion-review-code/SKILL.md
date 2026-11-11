---
name: jgl-fusion-review-code
description: Reviews a Fusion add-in's whole codebase for structural problems and Fusion API misuse — duplication, multi-responsibility files, dead code, logic tangled into event handlers or components, type gaps, dependency health, stored entity objects, collection iteration, unregistered handlers — and produces a prioritized refactor plan if one is warranted. Use when the user says "review code", "/jgl-fusion-review-code", "anything need refactoring?", or "look over the code".
context: fork
background: false
---

# Review Code (Fusion add-in)

Review the add-in's structure and Fusion API usage and, if it's warranted,
plan refactors. Report and plan only — don't change code.

`<prefix>` is the add-in's package prefix (the `code/*_tests/` directory).

## Evidence

When a tool isn't configured, report it as `⊘ SKIPPED — <tool> not
configured (<setup hint>)` rather than leaving it out — a silent skip looks
like a clean result.

1. **The code** — `code/` (Python) and `webapp/src/` (TypeScript).
2. **Static analysis** — `cd webapp && npx tsc -b`, and the webapp's `lint`
   script if it has one.
3. **Coverage** — `python -m pytest code/<prefix>_tests/ --cov=code/
   --cov-report=term-missing` (needs `pytest-cov`) and
   `cd webapp && npm run test:coverage`. Low coverage on logic-heavy files
   often means logic is welded to event handlers or components.
4. **Dependencies** — `cd webapp && npm audit`, and `pip-audit` (not
   installed → `⊘ SKIPPED — pip install pip-audit`; never claim a clean audit
   that didn't run).

## Pass 1 — collect everything

Write down every issue you find, with file, line range, and your confidence,
before deciding what matters. Don't filter yet — a finding dropped here can't
be weighed later.

**Structure (both languages)**
- Files carrying more than one responsibility (name them), and the reverse —
  one concept fragmented across many tiny files (STRUCT-1..3).
- Logic duplicated in three or more places (DUP-1).
- Dead code: unused exports, commented-out blocks, unreachable branches.
- Security: hardcoded secrets, missing validation at system boundaries — put
  these at the top regardless of anything else (SEC-1).

**TypeScript**
- `any`, unsafe casts, untyped public functions.
- Business logic inside React components instead of utility files (TS-3);
  calls that bypass `fusionBridge.ts` (TS-1).

**Python**
- Missing type hints or bare `dict`/`list` (PY-8).
- Business logic inside event handlers (`on_html_event`, `command_created`,
  custom events) instead of pure, testable modules.

**Fusion API misuse** — each of these breaks silently in Fusion:
- Entity objects stored on `self` or in state instead of `entityToken` (PY-6).
- `for x in collection` instead of `count` + `item(i)` (PY-7; API-11 is the
  exception).
- Handlers registered without `futil.add_handler()` (PY-2).
- Bare `print()` in add-in code (PY-1).
- Command/UI IDs without the `CompanyName_AddInName_` prefix (PY-3).
- Unprefixed top-level packages under `code/` (PY-5).

## Pass 2 — decide

Separate **findings** (a concrete defect with a concrete fix) from **drift
signals** (file length, coverage percentage — readings that mean little on
their own). A drift signal becomes a finding only when it points at something
in the list above: "`entry.py` is 900 lines" is a signal; "`entry.py` holds
the dispatch table, the pick logic and the preview cleanup" is a finding.

A refactor is warranted if any of these hold: Fusion API misuse; logic
duplicated 3+ times; business logic that can't be unit tested; a file with
more than one responsibility; one concept fragmented across many tiny files;
moderate or worse audit findings; `any` in core TypeScript logic. Otherwise
say no refactor is needed, give the drift readings in a line, and stop.

Leave out formatting nits and speculative improvements. Code without
meaningful tests (real assertions on computed values) isn't a refactor
candidate yet — mark it "tests first" and point at
`/jgl-fusion-review-testing`.

## Plan

1. **Do first** — high value, low risk: Fusion API misuse, duplicated logic,
   audit findings.
2. **Do second** — pull tangled logic into pure modules, split
   multi-responsibility files, replace `any`, add type hints.
3. **Skip for now** — real but not worth it yet, one line on why.

Each item: file path, what's wrong, the concrete fix ("move lines 45–120 of
`code/mt_commands/commandPalette/entry.py` into
`code/mt_commands/commandPalette/pick_logic.py`"). Close with a separate
**Drift** block of the readings, so nobody mistakes a reading for a task.
