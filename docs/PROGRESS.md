# Progress
_Updated 2026-11-26._

Everything under Done is merged into `main` (pull requests 1 to 3, merged
2026-11-22) and CI is green there. The work under In flight dated
2026-11-26 is committed on the branch `m4-cutter-detail`, which has not been
pushed.

## Done
- Milestones 0 and 1: probes, scope, scaffold, public repo, CI green on `main`.
- Milestone 2: cutter fingerprint,
  records, SQLite store, tally, Fusion extractor, palette actions (scan
  active document, reset with backup), Tally screen with sort and filter.
- Assembly counting: holder and stickout per observation, `build_assembly_tally`,
  `settings.json`, "Count by: Cutter / Assembly" switch. Decisions are in
  `docs/SCOPE.md` under "Rotating tool assemblies (RTA)".
- Milestone 3, folder scan:
  - `toolguru_lib/hub.py` lists projects and folders, collects the Fusion
    designs in a folder (subfolders optional), and opens one file, reads it and
    closes it without saving. A file the user already has open is left open.
  - The queue (`scan_job`, `scan_items`) lives in the data file
    (`toolguru_lib/store.py`), so a scan can be resumed after the palette, the
    add-in or Fusion was closed. Resetting the data clears the queue.
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
- Acceptance check: the owner ran it on the test folder in the palette and
  reported it good on 2026-11-21.
- The sweep, first folder (2026-11-21): 39 programs scanned and 3 skipped,
  then Fusion itself crashed while program 43 of 68 was open. Fusion's log
  shows an access violation in its own CAM loader (`Iron::Parser::Table`,
  reached from `IronDocumentEntity::loadDocumentData`) at the moment the scan
  asked the document for its CAM product. The queue had the program marked
  `opening`; Resume marked it failed and the folder finished: 63 scanned,
  4 skipped (no Manufacturing data), 1 failed.
- That crash was not reproduced. The owner opened the same version of the
  program by hand in a fresh Fusion session; its Manufacturing data loaded
  without trouble, and "Scan active document" then read it. The data now holds
  64 programs and 1856 operations. Fusion's log shows nothing that sets the
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
  read-only against the 64 scanned programs, it put the first save more than
  a day before the stored date for 44 of them. In-Fusion tests re-run: 22 of
  22 pass, and the live-hub test ran rather than skipped.
  The test runner counts a skipped test as passed and does not list skips.
- The data was reset and the first folder rescanned on 2026-11-26: 64 scanned,
  4 skipped (no Manufacturing data), 0 failed. Programs, operations (1856),
  cutters (141) and cutting time match the backup taken by the reset; "first
  used" moved earlier by more than a day for 44 programs, as predicted. The
  program that crashed Fusion in the first sweep scanned normally.
- Milestone 4, slice 1, cutter detail (branch `m4-cutter-detail`): clicking a
  tally row opens that cutter's detail.
  - Layout: the owner found the first one cluttered, chose parts of three
    drawn layouts, then picked "version D" of five combinations
    (2026-11-26). Top line: Fusion's picture, the name, and four figures
    (programs, operations, cutting time, last used). Then the geometry
    beside the usual setup (tool number, holder and stickout, machine, each
    with its program count). Then every program in one table, with whatever
    differs from the usual setup marked. It fits the palette's 760 px width.
  - The usual value is the one most programs used, operations breaking a
    tie. When the top two are level there is no usual one and nothing is
    marked: a cutter given a fresh tool number in every program has no odd
    one out. The usual holder and stickout are those of the usual assembly;
    a stickout counts as usual from that assembly's shortest stickout up to
    the tolerance above it, whatever holder it is in.
  - `toolguru_lib/detail.py` builds it from the same rows as the tally
    (`tally.split_assemblies` now hands out each assembly's rows);
    `actions.show_cutter` / `close_cutter` keep the selection in `AppState`;
    `webapp/src/components/CutterDetail.tsx` shows it.
  - Names used and operation types were in the first layout and are not in
    this one; nothing computes them now.
  - Unit tests: `toolguru_tests/test_detail.py` (each rule was also broken
    on purpose to see a test fail), `TestCutterDetail` in `test_state.py`,
    and the detail helpers in `webapp/src/utils.test.ts`. Looked at in a
    browser with made-up data, dark and light, at 760 px.
  - In-Fusion tests re-run on 2026-11-26 after restarting the add-in: 26 of
    26 pass (22 earlier, 4 new for the theme and tool pictures; none of the
    4 skipped), and `fusion_test_results.json` carries the new hash.
  - Checked read-only against the real data (141 cutters, 555 program rows): every
    detail builds, its figures agree with the tally row, and program,
    assembly and setup operations each add up. Inside Fusion the whole view
    with the busiest cutter's detail (49 programs) takes 0.03 s and is 73 KB.
    Every cutter has a usual tool number; 3 have no usual holder and
    stickout; 120 program rows have something marked.
  - **Still to do:** the owner has not yet looked at it in the palette on
    real data. Whether Fusion's pictures load in the palette (a `file://`
    page showing a `file://` image from the install folder) is only proven
    in a browser preview.
- Palette look (same branch), asked for by the owner on
  2026-11-26 before any more Fusion work:
  - Dark mode. Every colour in `webapp/src/styles/index.css` is a variable
    with a light and a dark value. `entry._view` adds Fusion's theme
    (`toolguru_lib/theme.py`, from `activeUserInterfaceTheme`) to every
    answer and push; `App.tsx` puts it on `<html data-theme>`. Before Fusion
    has answered, the device's setting is used. A theme change in Fusion
    reaches an open palette at its next action; no theme event was found.
  - Display unit. `settings.display_unit` ('in' by default, or 'mm'), set
    with "Show lengths in". A tool entered in the other unit shows that unit
    too, in brackets: `0.197 in (5.00 mm)`. Inches show three decimal
    places and millimetres two (owner's choice); stored values and the
    cutter fingerprint keep 0.001 mm, so two cutters that differ by less
    than the display shows can look alike in the tally.
  - Aligned lengths. In a table a length is split in two columns: the shown
    unit, and beside it the bracketed other unit (`utils.ts` `LengthParts`).
    Every shown value then lines up whether or not its row has an other
    unit. Used for the tally's diameter and stickout and the detail's
    geometry; the second column appears only when some row needs it. Flutes
    moved out of the diameter cell into a sortable column of its own.
  - Tool type filter. The tally's drop-down keeps "All families" and the
    families, and adds each milling and hole making tool type as a choice
    (`utils.ts` `typesByFamily`). Only types found by the scans are
    listed, not every type Fusion offers. A choice that the data no longer
    has (after a rescan or a reset) falls back to all.
  - Description column. It starts 240 px wide whatever the descriptions
    hold; a longer one is cut with "…" and shows in full on hover. A handle
    on its heading drags it between 80 and 1000 px (`utils.ts`
    `draggedWidth`). It is the only resizable column. The width is
    remembered: when a drag ends the palette sends it once
    (`set_description_width`) and it is kept as `description_width_px` in
    `settings.json`. The palette owns the limits and clamps whatever it is
    given; Python only stores a whole number of pixels, one or more.
  - In-Fusion tests re-run after this last Python change (2026-11-26): 26 of
    26 pass and `fusion_test_results.json` carries the current hash.
  - Its own look. The owner chose Verdana with a violet
    accent from three looks shown as pictures (the others: Bahnschrift with
    teal; Segoe UI with Consolas figures). Verdana ships with Windows and
    macOS, so nothing is downloaded or bundled. The header is a TOOLGURU
    wordmark over an accent rule; list rows are tinted alternately. All in
    `webapp/src/styles/index.css`.
  - Quieter lengths. The other unit has no brackets: it
    sits in its own column after a wider gap, in the muted colour, and in
    one piece of text the two are set apart by an em space
    (`utils.ts` `UNIT_GAP`). The shown diameter is bold. The tally's
    Programs and Operations headings are "PGMs" and "OPs", with the full
    word on hover.
  - Units in the headings. In the tally a length column
    names its unit once, in its heading, and its rows are bare figures:
    "Dia(in)" and, when some tool needs it, "Dia(mm)" beside it; the same
    for stickout when counting by assembly. The headings follow the "Show
    lengths in" switch. Elsewhere (the detail, labels, the tolerance text)
    a length still carries its unit.
  - Header and counts. The header holds the wordmark
    alone. The counts of programs, operations and cutters (assemblies when
    counting by assembly) sit on their own line under it, each with a small
    icon drawn in `webapp/src/components/Stats.tsx`: no icon library.
  - The add-in's icon. A guru seated in meditation, with
    a topknot and a beard, holding a tall end mill upright in each hand, on
    a rounded square in the app's violet. The owner turned down a first
    design (three end mills as tally bars) and directed this one through
    several rounds; lettering was tried and dropped. The end mills are
    drawn after the one in Fusion's own tool library (gunmetal, a band of
    light, a dark outline, S-shaped flutes) but are original drawings, not
    copies of Autodesk's picture. The drawings are
    `docs/icon/toolguru.svg` and, drawn more boldly for 16 and 32 pixels,
    `docs/icon/toolguru-small.svg`. The PNG
    files in `commandPalette/resources/` were made from them by a browser
    (canvas export), since no image tool is installed; the `@2x` files are
    for high-density screens. The same drawing is shown beside the name in
    the palette header (`App.tsx` imports `docs/icon/toolguru.svg`, so there
    is one copy). Fusion keeps a button's old icon in memory, see
    `docs/SCOPE.md`: after replacing the PNG files, Fusion itself has to be
    restarted once before the toolbar shows them.
  - Tool pictures. The API has no picture of a tool (`Tool` offers
    `toJson`, `parameters`, `presets`, `toolBlockGeometry` only). Fusion's own
    tool library ships one PNG per tool type under its install folder;
    `toolguru_lib/tool_pictures.py` finds them and the palette shows them
    from there. They are never copied into this repo. Form mills and probes
    have none. The to-scale profile in Fusion's library is drawn live by
    Fusion and cannot be captured.
  - New in-Fusion tests in `toolguru_fusion_tests/test_palette_look.py`
    (theme values, picture files): pass, see above. Fusion reports 21
    picture files and a dark theme on this machine.

- One data file (2026-11-26, same branch). The app was
  built with a second, throwaway set of data for testing beside the real
  one, a switch between them, and a one-click clear. With the scan trusted,
  the owner had it removed: there is one data file, `toolguru.sqlite`, and
  one "Reset data" button that backs up first and needs the typed word. The
  owner's existing data file was renamed to the new name by hand and the
  test file deleted; the app carries no code to migrate either. After the
  rename the add-in reads the same 64 programs, 1856 operations and 141
  cutters. In-Fusion tests re-run: 26 of 26 pass on the new hash.

- Saved databases (2026-11-26, same branch). A
  "Databases…" button opens a panel: save what is on screen under a typed
  name, and load a saved one from a list. The owner chose a list inside
  ToolGuru over a file dialog, and to be asked on every load whether to
  replace or add.
  - A saved database is a copy of the data file in a `saved` folder beside
    it (`toolguru_lib/saved.py`), without any folder-scan queue. Names must
    be valid Windows file names; a name already saved is only overwritten
    when the palette says "Replace".
  - Load, replace: the data on screen is backed up first by the same code as
    "Reset data" (`toolguru-backup-<stamp>.sqlite`), then the saved copy
    takes its place. Empty data is not backed up.
  - Load, merge ("Merge" in the palette): `Store.merge_from`. Programs only in the saved copy are
    added. A program in both keeps the scan already on screen unless the
    saved copy holds a later version of the program. The data has no "when
    was this scanned" stamp, so the program's version number decides.
  - Neither works while a folder scan runs. The saved list is only read
    while the panel is open.
  - Tests: `toolguru_tests/test_saved.py` (39) and five in `utils.test.ts`.
    No Fusion API is involved, so there is no new in-Fusion test; the
    existing 26 were re-run on the new hash and pass.

- Speeds and feeds as numbers (2026-11-26, same branch).
  Milestone 4, slice 2.
  - Probe, in a scratch program: a CAM parameter's `value.value` is the
    number Fusion works the expression out to, formula or not.
    `tool_spindleSpeed` comes in rpm and `tool_feedCutting` in mm/min,
    whatever unit was typed (40 in/min reads 1016). A value never set reads
    0. Other parameters do not share one unit (`tool_feedPerTooth` is in cm),
    so nothing else is taken from them.
  - A drilling operation has `tool_feedCutting` greyed out (`isEnabled` is
    False); its feed is `tool_feedPlunge`. `extract._feed_parameter` picks
    accordingly, and the stored feed expression is now that parameter's.
  - Stored beside the expressions as `spindle_rpm` and `feed_mm_min`; 0 is
    stored as nothing. An older data file gains the two columns empty, and
    they fill when a program is scanned again.
  - The cutter detail shows, under the geometry, the range and the most
    used value of each (`detail._speeds`), the feed in in/min or mm/min by
    the unit switch, and says how many operations have none recorded.
  - Tests: `test_detail.py`, `test_store.py`, `utils.test.ts`, and a new
    in-Fusion class `TestReadSpeeds`. In-Fusion: 30 of 30 pass.
  - Not yet seen on a real program: the owner's data was scanned before
    this, so every cutter shows "None recorded" until a rescan.

- Cutting data (2026-11-26, same branch). The owner asked
  for the cutting data that comes with a tool, and for customized data.
  - No scan change was needed: `Tool.toJson()` already carries every preset
    under `start-values.presets`, and each operation's preset name was
    already stored. Presets are in the tool's own unit (inch tool: in/min,
    inches, ft/min; millimetre tool: mm/min, mm, m/min);
    `toolguru_lib/presets.py` turns them into mm, mm/min and m/min.
  - The cutter detail lists the presets operations picked (the owner's
    choice: not the unused ones), one line per distinct set of numbers,
    with programs, operations and how many operations ran at a different
    speed or feed ("Changed"). Columns chosen by the owner: rpm, feed,
    surface speed, chip load, plunge, ramp, ramp rpm, stepover, stepdown.
    No coolant.
  - "Changed" uses the scanned numbers when present. For older scans it
    reads what was typed when that is a plain number with a unit; formulas
    are "not checked" until a rescan. An older drilling operation's feed is
    not judged (the stored one was the unused cutting feed). The Programs
    table has a "Cutting data" column, marked where an operation changed.
  - There is no "own or Fusion sample" label. One was tried from the
    preset's description text, and it called the owner's own presets
    samples, because a copied preset keeps the sample text.
  - Tests: `toolguru_tests/test_presets.py`, `utils.test.ts`. In-Fusion: 30
    of 30 pass on the new hash.

- Similar cutters (2026-11-26, same branch). Milestone
  4, slice 3. The owner's choices: suggest cutters with the same cutting
  end; "treat as same" merges them into one line everywhere; the merged
  line shows the most used cutter; suggestions get their own screen.
  - Rule (`toolguru_lib/similar.py`): same type, diameter, flute count,
    corner radius, angles and thread pitch. Lengths, shaft and tip diameter
    and material may differ. No weighted distance and no tolerance settings.
    The owner's data gives 16 groups covering 37 of 141 cutters.
  - Only decisions are stored, in two new tables of the data file:
    `merged_cutters` (cutter key, group) and `not_similar` (a signature of
    the exact set of cutters, so the question returns when a new cutter
    joins). Observations are never altered. `similar.apply_merges` rewrites
    the rows on their way to the tally and the detail, so a merged line's
    key and geometry are its most used cutter's and can change as usage
    does. Reset clears the decisions; a saved database carries them;
    merging one database into another does not bring its decisions along.
  - Palette: a "Similar…" button opens the screen (suggestions with "Treat
    as same" and "Not the same", then the merged groups with "Split"). A
    merged tally line carries an "N merged" tag, the cutter count in the
    header follows the merges, and the detail has a "Merged from" table.
  - Tests: `toolguru_tests/test_similar.py`, `utils.test.ts`. In-Fusion: 30
    of 30 pass on the new hash.

## Next step
Milestone 4, one slice at a time on `m4-cutter-detail`:
1. Cutter detail — built, see In flight.
2. Feeds and speeds as numbers — built, see In flight. Needs a rescan to
   fill.
3. Similar tools — built, see In flight.
4. Holding library: write the collapsed cutters to a Local tool library;
   resetting the data removes it.

The sweep can carry on to further folders at any time. Later: 5 compare
a program against the Hub standard (by assembly, with the tool-number
check); 6 opt-in swap to standard.

A separate Mastercam 2022 harvester is being probed outside this repo. If it
goes ahead, this add-in gains only a generic "Import scan file"; it stays
Fusion-only.

## Open questions
- Re-saving an old program today moves its "last used" to today. One scanned
  program is in that state. No rule chosen yet.
- Suppressed operations are skipped. Confirm that is the wanted rule.
- Spindle speed and feed are stored as Fusion expressions (sometimes formulas);
  resolve to numbers when the feeds/speeds view is built (milestone 4,
  slice 2).
- Stock material per setup: only `job_groupStockMaterial` (a group) found so far.
- Which tool numbers form the per-job pool (needed for milestone 5).
- `actions.view` rebuilds the whole tally on every palette action and after
  every scanned program; revisit for speed once the data is large.
- A folder scan re-opens every design even when its version was scanned
  before. Fine for one sweep per folder; add "skip unchanged" if folders get
  rescanned often.
- Counting a folder with subfolders asks the hub once per folder (about a
  second each) and blocks Fusion while it runs. Not yet tried on a large
  project.
- Nothing has been tried yet on a design with out-of-date references or one
  that Fusion wants to upgrade on open; such a file may raise a dialog.

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
