# Progress
_Updated 2026-11-11._

## Done
- Milestone 0: live-Fusion probes (findings in `docs/SCOPE.md`, "Verified against live Fusion").
- Milestone 1: scoped, scaffolded, public repo created, CI green on `main`.
- Codebase hash made identical on Windows and Linux (both copies, with tests).
- vite 8 / vitest 5 in place; `npm audit` reports 0 findings.

## In flight
- Nothing. Branch `m2-trial-scan` exists locally with only this file.

## Next step
Milestone 2 — trial loop for a single document, on `m2-trial-scan`, merged by pull request:
1. `toolguru_lib/` pure modules: unit normalization + cutter fingerprint, SQLite
   store with separate Trial and Main files in the user's home directory, tally.
2. Extractor: active document → observations (one per operation, raw tool JSON kept).
3. Palette: dataset badge, "Scan active document", Tally table, "Clear trial data".
4. Tests in all three layers (see `docs/SCOPE.md`, "Dev loop"); integration tests
   build a scratch document with known tools. Re-run in Fusion, commit the results file.

Later milestones: 3 folder scan (count-then-confirm, resume, skip) and the trial
acceptance gate; 4 dedup, similarity, cutter detail, holding library; 5 compare
a program against the Hub standard; 6 opt-in swap to standard.

## Open questions
- Parameter name for a setup's stock material (not found yet).
- The scaffolded pick event and `state.py` selections are unused by this add-in;
  remove them when the palette is rewritten in milestone 2.
- After editing the test runner itself, restart the add-in (or reload that one
  module) before `run_and_save()`, or the stamped hash comes from old code.
