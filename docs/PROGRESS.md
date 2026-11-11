# Progress
_Updated 2026-11-11._

## Done
- Milestones 0 and 1: probes, scope, scaffold, public repo, CI green on `main`.
- Milestone 2 (branch `m2-trial-scan`, not yet pushed): cutter fingerprint
  (`toolguru_lib/cutter.py`), records, SQLite store with Trial and Main files,
  tally, Fusion extractor, palette actions (scan active document, clear trial,
  switch dataset, reset main with backup), Tally screen with sort and filter.
  The owner has clicked through it: scan, tally and clear work.
- Assembly counting (branch `rta-assembly-view`, on top of `m2-trial-scan`, not
  yet pushed): holder product ID, holder shape and stickout stored per
  observation (`toolguru_lib/assembly.py`); older dataset files gain the
  columns on open; `build_assembly_tally`; `settings.json` beside the datasets
  (`toolguru_lib/settings.py`); "Count by: Cutter / Assembly" switch and
  stickout tolerance in the palette. Decisions are in `docs/SCOPE.md` under
  "Rotating tool assemblies (RTA)".
- Checks at this commit: 125 pytest, 46 Vitest, 16 in-Fusion tests, build.
- Read-only run on a real program: 63 operations → 11 cutters → 11 assemblies;
  one holder entered under three spellings of its product ID came out as one
  holder.

## In flight
- Owner has not yet seen the Count by switch in the palette.
- Two local branches wait for a go-ahead to push: `m2-trial-scan` first, then
  `rta-assembly-view`.

## Next step
Milestone 3 — folder scan: pick a hub folder, count-then-confirm, one document
per custom-event tick, progress, resume, skip-and-log. Then the trial acceptance
gate on the test folder (scan, compare by eye, clear, rescan identical) before
Main is used. Later: 4 dedup/similarity/cutter detail/holding library;
5 compare a program against the Hub standard (by assembly, with the tool-number
check); 6 opt-in swap to standard.

## Open questions
- Suppressed operations are skipped. Confirm that is the wanted rule.
- Spindle speed and feed are stored as Fusion expressions (sometimes formulas);
  resolve to numbers when the feeds/speeds view is built (milestone 4).
- Stock material per setup: only `job_groupStockMaterial` (a group) found so far.
- Which tool numbers form the per-job pool (needed for milestone 5).
- `actions.view` rebuilds the whole tally on every palette action; revisit for
  speed once the Main dataset is large.

## Working notes
- Handlers registered from an MCP script die when that script ends. Never
  restart the add-in over MCP by calling the launcher's `stop()`/`run()`: the
  button and palette go dead. Restart it through Fusion's own object instead —
  find ToolGuru in `app.scripts`, then `stop()` and `run(False)`. `run(False)`
  starts the add-in after the script returns, so its handlers stay alive
  (checked: `commandDefinition.execute()` then opens the palette and the page
  gets its state).
- In MCP scripts use `importlib.import_module('toolguru_commands.commandPalette.entry')`;
  `import … as` fails because the package rebinds `commandPalette` to that module.
