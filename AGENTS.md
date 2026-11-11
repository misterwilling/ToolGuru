# Fusion 360 Add-In Guidelines

Rules for a Fusion 360 add-in with a Python backend and a React/TypeScript
palette (pure CommandInputs add-ins are out of scope). Fusion punishes
mistakes with silent breakage rather than errors, so the Fusion rules below
are the ones to keep in mind. Rules have stable IDs so a review or plan can
cite one. Tool picks (pytest, Vitest, GitHub Actions) are defaults for a new
add-in; in an existing one, keep its tools and apply the principles.

**First run.** New add-in (no `.manifest`, no `code/`): run `/jgl-fusion-scope`,
then `/jgl-fusion-scaffold` — don't write the structure by hand. Existing
add-in: audit before changing anything. Report violations of PY-1..6 and API-*
(bare `print()`, unprefixed packages, entity objects on `self`, `for x in
collection`, handlers without `futil.add_handler()`) and fix nothing on the
first pass.

## Commands

`<prefix>` is the add-in's package prefix (e.g. `mytool`).

| Task | Command |
|---|---|
| Python unit tests | `python -m pytest code/<prefix>_tests/ -v` |
| Webapp unit tests | `cd webapp && npm test` |
| Webapp build | `cd webapp && npm run build` |
| Fusion integration tests | `run_and_save()` via the Fusion MCP server (`/jgl-fusion-mcp`), or the "Run Tests" button |

## Done means

- **DONE-1** — A change is done when the Python and webapp unit tests pass,
  `webapp/` is rebuilt if anything under `webapp/src/` changed (BUILD-1), and
  each new behavior has a test that would fail without it. If Fusion-API code
  changed, the integration tests have been re-run and the updated
  `fusion_test_results.json` is part of the change (TEST-4). Report what ran
  and what it printed; say plainly if something couldn't be run.

## Working autonomously

- **AUTO-1** — Go ahead without asking: read code, run the commands above,
  probe the Fusion API through MCP in a new scratch document, edit files the
  task needs, make a local commit when asked.
- **AUTO-2** — Ask first: pushing, deleting branches or data, adding a
  dependency, changing CI or git hooks, touching a secret value, and running
  MCP scripts that modify a document the user already had open — it's their
  model, and undo history is the only way back.
- **AUTO-3** — Do what was asked, at the scope asked. No unrequested
  features, refactors, abstractions, or error handling for cases that can't
  happen. If a better approach exists, say so in a sentence, then do the task.

## Secrets

Add-ins often hold Autodesk Platform Services secrets, AI provider keys, or
webhook URLs. A secret that reaches a chat or git history can't be taken back.

- **SEC-1** — Never commit a secret — not in source, `config.json`, the
  `.manifest`, fixtures, `.env`, commit messages, or comments. Gitignore
  `.env` and variants before any secret exists.
- **SEC-2** — Keep real secrets out of the conversation: don't ask for them,
  don't read files holding them, don't echo one you saw.
- **SEC-3** — If a real secret reaches you anyway, stop the task and help the
  user rotate it in the provider's console first; deleting the message or
  commit doesn't undo exposure. Placeholders and obviously fake fixtures
  aren't secrets.
- **SEC-4** — Code reads secrets by name (`os.environ["APS_CLIENT_SECRET"]`);
  a per-user key lives in the user's home directory, never the add-in folder;
  the repo carries a `.env.example` with names only.
- **SEC-5** — "Just hardcode it for now" doesn't change SEC-1..4.

## Python

- **PY-1** — No `print()` in add-in code; use `gutil.log(msg, force_console=True)`
  (Text Commands palette). Exception: MCP probe scripts use `print()` — it's
  the channel MCP returns (MCP-2).
- **PY-2** — Register every event handler with `futil.add_handler()`. Fusion
  garbage-collects handlers Python doesn't hold.
- **PY-3** — Command and UI IDs are global across all installed add-ins:
  `CompanyName_AddInName_commandName`.
- **PY-4** — The add-in folder, its `.py` entry point, and its `.manifest`
  share one exact name.
- **PY-5** — Prefix every top-level package under `code/` with the add-in
  name (`<prefix>_commands`, `<prefix>_lib`, `<prefix>_tests`,
  `<prefix>_fusion_tests`). A bare `commands` or `tests` binds to whichever
  add-in is first on `sys.path` — no error, just wrong code running.
- **PY-6** — Store `entity.entityToken`, never entity objects (they go stale
  between events); resolve with `design.findEntityByToken(token)`.
- **PY-7** — Iterate Fusion collections with `count` + `item(i)`, not
  `for x in collection` (API-11 is the exception).
- **PY-8** — Type hints on every signature; `snake_case` functions,
  `PascalCase` classes.

## TypeScript

- **TS-1** — All Python calls go through `sendToFusion()` and all pushes
  through `onFusionPush()` in `fusionBridge.ts` — the only bridge.
- **TS-2** — `adsk` is a bare global, not `window.adsk`; check
  `typeof adsk !== 'undefined'`.
- **TS-3** — Keep components thin; pure logic goes in utility files tested
  with Vitest.

## Fusion API gotchas

- **API-1** — The property is spelled `jointOrgins`, not `jointOrigins`.
- **API-2** — Proxy joint origins with `createForAssemblyContext(occ)` before
  creating root-level joints.
- **API-3** — Pass a `JointOrigin` straight to `joints.createInput()`, not a
  `JointGeometry`.
- **API-4** — `JointOrigins.createInput(geo)` takes one argument, a `JointGeometry`.
- **API-5** — `ui.selectEntity()` blocks the main thread: fire it from a
  custom event, never from `on_html_event`.
- **API-6** — `palette.sendInfoToHTML()` echoes back as action `'response'`;
  ignore it in the dispatch table.
- **API-7** — `palettes.add()` needs `useNewWebBrowser=True` (9th argument)
  for the JS bridge.
- **API-8** — `addByInsert(dataFile, transform, True)` inserts a linked
  reference — prefer it; `False` embeds a copy.
- **API-9** — `joints.add()` raises `RuntimeError: 3` when a joint already
  joins the same entities.
- **API-10** — Palette preview geometry has no auto-rollback: track it by
  token and delete it explicitly.
- **API-11** — CAM library URL lists (`childFolderURLs`, `childAssetURLs`)
  return a `URLVector`: use `len()` and indexing, not `.count`/`.item(i)`.
- **API-12** — Gate on `design.designIntent` (Part / Assembly / Hybrid), the
  declared intent — don't infer it from bodies or occurrences.

`ARCHITECTURE.md` has the code pattern behind each of these.

## Fusion MCP server

- **MCP-1** — Autodesk's Fusion MCP server (`http://127.0.0.1:27182/mcp`)
  drives a *running* Fusion session: run integration tests headlessly, query
  `apiDocumentation`, execute probe scripts, take screenshots. Before relying
  on it, confirm it's registered, Fusion is open with the add-in loaded, and
  the right document is open. If any check fails, tell the user what to fix
  and fall back to the GUI path; never report an MCP check as passed when it
  didn't run. `/jgl-fusion-mcp` has the preflight and the run steps.
- **MCP-2** — Probe scripts define `run(_context)`, report with `print()`,
  and let exceptions propagate so the traceback comes back.
- **MCP-3** — Fusion keeps old modules loaded: after editing production
  Python, restart the add-in (Stop → Run) before an MCP run trusts the result.

## Testing

- **TEST-1** — Plans include the test work: name which of the three layers
  (pytest, Vitest, Fusion integration) gets new or updated tests, and where.
  Point out a plan that leaves them out before it's approved.
- **TEST-2** — Assert specific values (`assert angle == 45.0`), not existence
  (`is not None`, `toBeDefined()`).
- **TEST-3** — Each test exists to catch a specific, plausible bug. Python
  unit tests use `mock_adsk.py`; call `setup_adsk_modules()` before importing
  production code.
- **TEST-4** — Integration results carry a codebase hash that CI checks. After
  changing source, re-run the integration tests (MCP or button) and commit the
  new `fusion_test_results.json`. If you change the hash algorithm, change both
  copies together (the testRunner's and `hash_utils.py`).

## Build

- **BUILD-1** — The palette loads `webapp/dist/`, not source: run
  `cd webapp && npm run build` after any `webapp/src/` change.
- **BUILD-2** — Vite needs `base: './'` — the palette loads over `file://`.

## Git

- **GIT-1** — No AI attribution in commits (no AI `Co-Authored-By`, no
  "Generated with", no 🤖). The scaffolded `commit-msg` hook rejects them.
- **GIT-2** — Commit and push are separate; push only when asked. A push to
  `main`/`master` needs a yes for that branch even when the user asked to
  push — show what's going out and offer a branch and PR. A yes holds for the
  session.
- **GIT-3** — Messages say what changed and why.
- **GIT-4** — Solo new add-ins can use `main`; shared or published add-ins
  use branches and PRs.
- **GIT-5** — Past roughly 10 changed files or 400 added lines since the last
  commit, checkpoint: commit, update `docs/PROGRESS.md`, and continue in a
  fresh session from that file and `git log`.

## Where the rest lives

- Code patterns (manifest, launcher, palette, bridge, picking, preview,
  joints, custom features, workspaces, test architecture) → `ARCHITECTURE.md`
- Testing craft, mocking, coverage, CI, pre-push hook, dependencies,
  refactoring, code structure → `PRACTICES.md`
- Skills: `/jgl-fusion-scope`, `/jgl-fusion-scaffold`, `/jgl-fusion-mcp`,
  `/jgl-fusion-check`, `/jgl-fusion-status`, `/jgl-fusion-commit`,
  `/jgl-fusion-push`, `/jgl-fusion-review-code`, `/jgl-fusion-review-testing`,
  `/jgl-fusion-setup-testing`

## Project context
_From /jgl-fusion-scope on 2026-11-11. Detail in docs/SCOPE.md._

- **What this is:** ToolGuru — scans past CAM programs, collects the tools they
  used, collapses duplicates, tallies usage and shows near-duplicates, so a
  standard tool library can be chosen from evidence.
- **Workspaces:** Manufacturing (`CAMEnvironment`).
- **Reads vs mutates:** scanned programs are read-only (open, read, close
  without saving). Writes only its own database and its own tool libraries.
- **Persistence:** SQLite files in the user's home directory, separate Trial
  and Main datasets; nothing on documents, nothing in the repo.
- **First milestone:** Trial dataset, "Scan active document", Tally screen, and
  "Clear trial data".
- **Public repo:** no machine names, program names, project names or hub ids in
  code, tests, fixtures or docs.
