---
name: jgl-fusion-scaffold
description: Scaffolds a new Fusion 360 React-palette add-in by running the kit's tested scaffold.py generator from four inputs — add-in name, company, target workspace, description — then installs and builds the webapp, smoke-tests it, switches on the git hooks, and explains how to load it in Fusion. Use when the user says "/jgl-fusion-scaffold", "scaffold the add-in", or "create the add-in structure".
disable-model-invocation: true
---

# Scaffold (Fusion add-in)

Generate a new add-in with `scaffold.py`, the kit's deterministic, tested
generator. Don't write the structure by hand: hand-written scaffolds are what
produced the `sys.path` collisions (PY-5) and wrong-workspace bugs the
generator exists to prevent. Your job is to collect the inputs, run the
script, and report.

## 1. The four inputs

If `/jgl-fusion-scope` just ran, it already has these — use them rather than
asking again. Otherwise ask, one at a time:

1. **Add-in name** — PascalCase and identifier-safe (no spaces or hyphens):
   `ToolLibrary`, `StockTransfer`. It becomes the folder, launcher and
   manifest name (PY-4) and the lowercase prefix for every Python package.
2. **Company name** — identifier-safe (`Acme`, `JGL`); prefixes the global UI
   IDs (PY-3).
3. **Target workspace** — don't default this. Ask what the user clicks, then
   map it:

   | If the user says… | Workspace |
   |---|---|
   | modeling, sketching, assemblies, parameters, joints | `design` |
   | CAM, toolpaths, setups, tool library, post processor, probing | `manufacturing` |
   | appearances, rendering, scene | `render` |
   | simulation, stress, modal | `simulation` *(unverified — see ARCHITECTURE.md)* |
   | drawings, drafting, 2D | `drawings` *(unverified — see ARCHITECTURE.md)* |
   | several workspaces | ask which; `start()` gets edited to register in each |
   | not sure | describe the workflow — don't guess |

   "Workspace IDs" in `ARCHITECTURE.md` has the full table.
4. **One-line description** — goes in the manifest and the command tooltip.

## 2. Run the scaffolder

From the folder that contains `scaffold.py`:

```bash
python scaffold.py \
    --name <AddInName> \
    --company <CompanyName> \
    --workspace <friendly-name-or-id> \
    --description "<one-line>" \
    --dest <path/to/new/addin>
```

`--workspace` takes a friendly name (`design`, `manufacturing`, `render`,
`simulation`, `animation`, `drawings`) or a raw ID (`CAMEnvironment`).
Omitting `--dest` scaffolds into `./<AddInName>/`. With no flags it prompts
for each field, which suits a user still deciding.

## 3. Build the webapp and smoke-test

```bash
cd <AddInName>/webapp && npm install && npm run build && cd ..
python -m pytest code/<prefix>_tests/ -v
```

The palette loads `webapp/dist/`, so the build is required before the add-in
runs (BUILD-1). The scaffolded `test_state.py` should pass straight away; if
it doesn't, tell the user rather than papering over it.

## 4. Switch on the git hooks

The scaffold ships `.githooks/pre-push` (unit tests before a push) and
`.githooks/commit-msg` (rejects AI attribution, GIT-1). Inside the add-in
folder, run `git init` if it isn't a repo yet, then:

```bash
git config core.hooksPath .githooks
```

If `core.hooksPath` is already set to something other than `.githooks`
(Husky, lefthook, the pre-commit framework), don't repoint it — that would
switch off the hooks the repo already relies on. Show the user the lines to
add to their existing setup instead.

## 5. Mention optional integration coverage

> Optional: to get a per-file Fusion column in CI's combined coverage table,
> install coverage into the add-in once:
> `pip install coverage --target=code/lib/coverage_pkg` (gitignored, per
> developer). Tests pass and the hash gate works without it.

Point at the command; don't run it — it touches the user's local Python.

## 6. Loading it in Fusion

> In Fusion: **Scripts and Add-Ins → Add-Ins → + →** select the
> `<AddInName>/` folder **→ Run**. A **`<AddInName>`** tab appears in the
> **`<Workspace>`** workspace; its button in the **Tools** panel opens the
> palette.

If the Fusion MCP server isn't set up yet, suggest `/jgl-fusion-mcp` so the
first feature can be tested headlessly.

## If scaffold.py is missing

Ask the user to unzip the full kit. As a last-resort recovery only, the
templates under `templates/scaffold/` can be copied with the tokens
(`{{AddInName}}`, `{{addin_prefix}}`, `{{CompanyName}}`, `{{WORKSPACE_ID}}`,
`{{uuid}}`, `{{description}}`) substituted by hand — say that this isn't the
normal path.

## After scaffolding

Typical next requests: a new command (follow the dispatch-table pattern in
`entry.py`, with a pick event for geometry), a new testable module (pure
logic in `code/<prefix>_lib/`, tests in `code/<prefix>_tests/`), or a custom
feature ("Custom Features" in `ARCHITECTURE.md`). Each ships with its tests
in the same session (TEST-1, DONE-1).
