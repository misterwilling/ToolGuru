# Scope — ToolGuru
_From the /jgl-fusion-scope interview, 2026-11-11. Update as decisions change._

## What this is

A Fusion add-in that scans past CAM programs, collects every tool they used,
collapses duplicates, tallies how often each tool was used, and shows tools that
are nearly the same. The point is to choose a standard tool library from
evidence instead of memory. Once a standard library exists, the add-in checks a
new program against it and keeps a running usage count.

## Who it's for

One programmer on one Windows PC. The pain: every program carries its own copy
of its tools, so years of tooling decisions are locked inside hundreds of cloud
documents, with the same cutter entered several times under different tool
numbers and units. The repo is public and MIT-licensed, but the add-in is built
and tested for this single setup.

## Fusion shape

Add-in (persistent UI), one focused tool rather than a suite, React palette with
a Python backend.

## Workspaces

Manufacturing (`CAMEnvironment`) only.

## Reads vs mutates

**Invariant: scanned programs are read-only.** A program is opened, read, and
closed without saving. The add-in writes only:

- its own database files (see Data & persistence), and
- its own tool libraries: a regenerated "holding" library in Local, and later a
  standard library in the Hub.

A later, opt-in "swap to standard" command would edit programs. It is out of
scope until the standard library exists and must ask before every run (AUTO-2).

## API surface

- Hub data: `app.data.dataProjects`, folders, `DataFile` (dates, version, id).
- Documents: `app.documents.open(dataFile, True)`, `doc.close(False)`.
- CAM product: `doc.products.itemByProductType('CAMProductType')`, setups,
  operations, `setup.machine`, operation parameters, `cam.getMachiningTime`.
- Document tools: `cam.documentToolLibrary`, `operationsByTool`, `Tool.toJson()`.
- CAM libraries: `CAMManager.get().libraryManager.toolLibraries` —
  `urlByLocation`, `childFolderURLs` / `childAssetURLs` (URLVector, API-11),
  `toolLibraryAtURL`, `importToolLibrary`, `updateToolLibrary`, `createFolder`,
  `deleteAsset`, `deleteFolder`, `doesPathExist`.
- Custom events for the scan loop (one document per tick), following the
  pick-event pattern in `ARCHITECTURE.md`.

No joints, BRep geometry, attributes, or custom features.

## Data & persistence

SQLite files in the user's home directory, never the add-in folder and never
the repo. Two separate datasets:

- **Trial** — for small test folders; one button clears it completely,
  including its holding library.
- **Main** — the real sweep; reset makes a timestamped backup first and needs a
  typed confirmation.

Records: *Document* (hub file id, version, dates, scan status), *Observation*
(one per operation, with the tool's full raw JSON, holder, tool number,
feeds/speeds, machine, cutting time), *Cutter* (one per geometry fingerprint,
derived). Raw tool JSON is kept so the duplicate rule can change without
rescanning. Rescanning a document replaces its earlier observations.

Three levels of identity: **cutter** (geometry, unit-normalized to mm),
**assembly variant** (cutter + holder + stick-out), **usage context** (machine,
operation type, speeds/feeds, tool number).

## Cloud posture

Uses only Fusion's own signed-in hub access through the Fusion API. No Autodesk
Platform Services credentials, no other network calls, no secrets. SEC-1..5
apply if that ever changes; `.env*` is gitignored regardless.

## Dev loop

Fusion MCP server connected and proven on 2026-11-11 (Fusion 2707.0.95,
embedded Python 3.14, `sqlite3` available). Registered for this folder through
`.mcp.json`.

Three test layers:

- **pytest** — unit conversion and rounding, fingerprint, similarity, tally and
  first/last dates, rescan-replaces-not-doubles, store round trip, Trial clear
  leaves Main untouched, Main reset backs up first.
- **Vitest** — table sort/filter, time and unit formatting, cluster grouping,
  dataset badge state.
- **Fusion integration** — scratch document with a setup and operations using
  known tools; assert exact values from the extractor; write a library, read it
  back, clear it, assert it is gone.

### Verified against live Fusion (read-only probes, 2026-11-11)

- A hub document opens by script in 4–6 seconds; nothing is modified and the
  previously active document is restored after `close(False)`.
- CAM data is readable without activating the Manufacturing workspace.
- `Tool.toJson()` carries type, unit, full geometry, holder, tool number,
  presets, vendor, product id and guid.
- Tools in one program mix inch and millimetre units; fingerprints must
  normalize units.
- The same cutter can appear more than once in one program under different
  tool numbers.
- A document tool library can hold tools no operation uses; usage must be
  counted from operations (`operationsByTool`), not from presence.
- `setup.machine` gives vendor and model. Operation speed, feed and preset name
  are readable.
- `cam.getMachiningTime` works for most operations and raises for some even
  when the toolpath reports valid; those are recorded as "no time".
- `DataFile.dateCreated` / `dateModified` are UNIX epoch seconds. A copied file
  carries the copy date, not the original's.
- Library writes work in Local and Hub: create, read back, update, delete.
- A Hub library cannot be created at `hub://`; it must sit inside the hub's own
  top folder. Folders nest at least two levels below that.
- Other installed add-ins fire their document-opened handlers on every document
  the scan opens. The scan never saves, so their in-memory changes are discarded.

## First milestone

Trial dataset, "Scan active document", Tally screen, and "Clear trial data".
It is the thinnest path that touches the real pain (seeing what one program
used, deduplicated) and it puts the reset in place before any folder scan
exists.

Then: folder scan with count-then-confirm, resume and skip → trial acceptance
gate (scan, compare by eye, clear, rescan gives the identical tally, double
scan does not double counts) → Main sweep → dedup, similarity, cutter detail,
holding library → compare a program against the Hub standard.

## Workflow

Solo. Public GitHub repo, MIT license. The scaffold is the first commit on
`main`; every milestone after that is its own branch and pull request, merged
when CI is green. Commit and push are separate steps. Installs on one Windows
PC, loaded from the repo folder.

## Open questions

- **Stock material per setup** — the parameter name is not yet known. Default
  in force: material is not recorded.
- **Library organization and naming** — deferred until scan data exists.
  Default in force: none; the add-in only builds the flat holding library.
- **Pre-production Fusion build** — the development machine runs a
  pre-production build; API details may differ from the public release.
  Default in force: trust the integration tests on this machine.
- **Cloud library retirement** — Autodesk documents no date and no migration
  procedure. Default in force: do not migrate Cloud libraries; build the Hub
  standard from scan results.
