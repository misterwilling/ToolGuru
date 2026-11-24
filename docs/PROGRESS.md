# Progress
_Updated 2026-11-24._

Everything under Done is merged into `main` (pull requests 1 to 3, merged
2026-11-22) and CI is green there. `main` is the only branch.

## Done
- Milestones 0 and 1: probes, scope, scaffold, public repo, CI green on `main`.
- Milestone 2: cutter fingerprint,
  records, SQLite store with Trial and Main files, tally, Fusion extractor,
  palette actions (scan active document, clear trial, switch dataset, reset
  main with backup), Tally screen with sort and filter.
- Assembly counting: holder and stickout per observation, `build_assembly_tally`,
  `settings.json`, "Count by: Cutter / Assembly" switch. Decisions are in
  `docs/SCOPE.md` under "Rotating tool assemblies (RTA)".
- Milestone 3, folder scan:
  - `toolguru_lib/hub.py` lists projects and folders, collects the Fusion
    designs in a folder (subfolders optional), and opens one file, reads it and
    closes it without saving. A file the user already has open is left open.
  - The queue (`scan_job`, `scan_items`) lives in the dataset file
    (`toolguru_lib/store.py`), so a scan can be resumed after the palette, the
    add-in or Fusion was closed. Clearing a dataset clears its queue.
  - `actions.py`: count-then-confirm (`propose_scan`, `start_scan`), one
    program per `scan_step`, `stop_scan`, `resume_scan`, `dismiss_scan`. A
    design without Manufacturing data or without tooled operations is skipped;
    a program that raises is marked failed and the scan goes on.
  - `entry.py` turns the steps from a custom event and pushes the state to the
    palette after each program. Palette: "Scan a folder…", folder picker,
    confirmation with the count, progress bar, Stop / Resume / Dismiss, and a
    list of skipped and failed files (`webapp/src/components/ScanPanel.tsx`).
  - The summary line counts assemblies when counting by assembly.
- Checked in live Fusion on the three-program test folder: three scans of the
  folder each ended 3 scanned, 0 skipped, 0 failed, with the tally unchanged
  (3 programs, 117 operations, 24 cutters), every opened document closed and
  the active document restored. Stop before the first program, Stop during
  the last program, a double Resume, and an action sent while a program was
  open all behaved as the unit tests describe.

## In flight
- Trial acceptance gate: the owner ran it on the test folder in the palette and
  reported it good on 2026-11-21. Main may now be used.
- Main sweep, first folder (2026-11-21): 39 programs scanned and 3 skipped,
  then Fusion itself crashed while program 43 of 68 was open. Fusion's log
  shows an access violation in its own CAM loader (`Iron::Parser::Table`,
  reached from `IronDocumentEntity::loadDocumentData`) at the moment the scan
  asked the document for its CAM product. The queue had the program marked
  `opening`; Resume marked it failed and the folder finished: 63 scanned,
  4 skipped (no Manufacturing data), 1 failed.
- That crash was not reproduced. The owner opened the same version of the
  program by hand in a fresh Fusion session; its Manufacturing data loaded
  without trouble, and "Scan active document" then read it. Main now holds 64
  programs and 1856 operations. Fusion's log shows nothing that sets the
  crashing load apart from the 39 that worked: in every scan the CAM load
  starts in the same second the document opens, and the geometry-restore
  errors in the log appear on every open. Treated as a one-off Fusion crash
  unless it happens again. The exact case can no longer be repeated as it
  was: the hand session saved the program, which made a new version.
- "First used" date fix (2026-11-22, merged with milestone 3):
  `DataFile.dateCreated` is the date of the latest version, so every stored
  created date was really the last save. `extract.first_saved` now reads the
  oldest entry of `dataFile.versions`; it costs about 0.4 s per program.
  Unit tests are in `toolguru_tests/test_document_record.py`, and a live-hub
  test was added to `toolguru_fusion_tests/test_folder_scan.py`. Run
  read-only against the 64 programs in Main, it put the first save more than
  a day before the stored date for 44 of them. In-Fusion tests re-run: 22 of
  22 pass, and the live-hub test ran rather than skipped. **Still to do:**
  rescan the first Main folder so the dates already stored are refreshed.
  The test runner counts a skipped test as passed and does not list skips.

## Next step
Rescan the first Main folder for the corrected dates, then carry the Main
sweep on to further folders. Then milestone 4: dedup, similarity, cutter
detail, holding library. Later: 5 compare a program against the Hub standard
(by assembly, with the tool-number check); 6 opt-in swap to standard.

A separate Mastercam 2022 harvester is being probed outside this repo. If it
goes ahead, this add-in gains only a generic "Import scan file"; it stays
Fusion-only.

## Open questions
- Re-saving an old program today moves its "last used" to today. One program
  in Main is in that state. No rule chosen yet.
- Suppressed operations are skipped. Confirm that is the wanted rule.
- Spindle speed and feed are stored as Fusion expressions (sometimes formulas);
  resolve to numbers when the feeds/speeds view is built (milestone 4).
- Stock material per setup: only `job_groupStockMaterial` (a group) found so far.
- Which tool numbers form the per-job pool (needed for milestone 5).
- `actions.view` rebuilds the whole tally on every palette action and after
  every scanned program; revisit for speed once the Main dataset is large.
- A folder scan re-opens every design even when its version was scanned
  before. Fine for one sweep per folder; add "skip unchanged" if folders get
  rescanned often.
- Counting a folder with subfolders asks the hub once per folder (about a
  second each) and blocks Fusion while it runs. Not yet tried on a large
  project.
- Nothing has been tried yet on a design with out-of-date references or one
  that Fusion wants to upgrade on open; such a file may raise a dialog.

## Setting up on another computer
A fresh clone is missing four things that are not in the repo:
- The git hooks are off until `git config core.hooksPath .githooks` is run.
  Set `user.name` and `user.email` too; commits use a GitHub no-reply address.
- `webapp/dist/` is not committed. Run `npm install` and `npm run build` in
  `webapp/`, or the palette opens blank.
- Fusion does not know the add-in: Scripts and Add-Ins → Add-Ins → + → pick
  the cloned folder → Run. It is not set to run on startup. Fusion's own MCP
  server must be switched on; `.mcp.json` here registers it for the session.
- The scan data (`~/.toolguru/`: Trial, Main, `settings.json`) stays on the
  computer that made it. Copy the folder by hand, one way, with Fusion closed.
  Without it the add-in starts with two empty datasets.

## Working notes
- CI runs the unit tests on Python 3.12; Fusion and the development computer
  run 3.14. A module-level annotation such as `adsk.core.X | None` is
  evaluated at import on 3.12 and fails against the mocked `adsk`. Start any
  module that has one with `from __future__ import annotations`. Only CI
  catches this.
- Handlers registered from an MCP script die when that script ends. Never
  restart the add-in over MCP by calling the launcher's `stop()`/`run()`: the
  button and palette go dead. Restart it through Fusion's own object instead —
  find ToolGuru in `app.scripts`, then `stop()` and `run(False)`.
- In MCP scripts use `importlib.import_module('toolguru_commands.commandPalette.entry')`;
  `import … as` fails because the package rebinds `commandPalette` to that module.
- To drive a folder scan over MCP, call the handlers in `entry.py`
  (`_handle_browse_folder`, `_handle_count_folder`, `_handle_start_folder_scan`)
  and return; the steps run from the custom event afterwards. Poll with a
  second, read-only script.
- Fusion runs other events while `documents.open` is working: an MCP script or
  a palette click can arrive in the middle of a scan step. `state.scan_busy`
  exists for that.
- The hub tests in `toolguru_fusion_tests/test_folder_scan.py` need Fusion
  signed in and online; they list projects and open nothing.
