# Progress
_Updated 2026-11-11._

## Done
- Milestones 0 and 1: probes, scope, scaffold, public repo, CI green on `main`.
- Milestone 2 (branch `m2-trial-scan`, not yet pushed): cutter fingerprint
  (`toolguru_lib/cutter.py`), records, SQLite store with Trial and Main files,
  tally, Fusion extractor, palette actions (scan active document, clear trial,
  switch dataset, reset main with backup), Tally screen with sort and filter.
- Checks at this commit: 77 pytest, 32 Vitest, 13 in-Fusion tests, build, `npm audit` clean.
- Run through the add-in's own handlers on a real program: 63 operations → 11
  cutters, rescan identical, clear empties the dataset.

## In flight
- Owner has not yet clicked through the palette by hand. Push and pull request
  for milestone 2 wait for that and for a go-ahead.

## Next step
Milestone 3 — folder scan: pick a hub folder, count-then-confirm, one document
per custom-event tick, progress, resume, skip-and-log. Then the trial acceptance
gate on the test folder (scan, compare by eye, clear, rescan identical) before
Main is used. Later: 4 dedup/similarity/cutter detail/holding library;
5 compare a program against the Hub standard; 6 opt-in swap to standard.

## Open questions
- Suppressed operations are skipped. Confirm that is the wanted rule.
- Spindle speed and feed are stored as Fusion expressions (sometimes formulas);
  resolve to numbers when the feeds/speeds view is built (milestone 4).
- Stock material per setup: only `job_groupStockMaterial` (a group) found so far.
- Holder identity (its own tally) is not built yet; raw tool JSON is stored, so
  no rescan will be needed.

## Working notes
- Handlers registered from an MCP script die when that script ends. Restarting
  the add-in over MCP reloads modules (fine for `run_and_save()`), but its
  buttons stay dead until a manual Stop → Run in Scripts and Add-Ins.
- In MCP scripts use `importlib.import_module('toolguru_commands.commandPalette.entry')`;
  `import … as` fails because the package rebinds `commandPalette` to that module.
