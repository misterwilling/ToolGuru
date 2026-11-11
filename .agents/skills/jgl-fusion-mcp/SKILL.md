---
name: jgl-fusion-mcp
description: Registers the Autodesk Fusion MCP server and proves it's live — registered, Fusion running with the add-in loaded, the right document open — before any MCP-dependent work such as headless integration tests, API probing, or viewport screenshots. Use when the user says "set up the Fusion MCP", "/jgl-fusion-mcp", "is the MCP connected?", or "why can't you run the Fusion tests", or when a Fusion MCP tool call fails.
---

# Fusion MCP — connect and verify the live-Fusion loop

Autodesk's Fusion MCP server is a bridge into a *running* Fusion session.
With it, an agent can run the integration suite headlessly, probe the API,
read the active document, and screenshot the viewport. It only answers when
Fusion is open, the add-in is loaded, and (for document work) a document is
open — so this skill checks each of those in order and tells the user exactly
what to fix (MCP-1 in `AGENTS.md`).

## Preflight — stop at the first failure

Each check gates the next. If one fails, report it plainly and fall back to
the GUI path (the "Run Tests" button, the Text Commands console); never treat
an unreachable server as a pass.

### 1. Registered?

Look for a `fusion_mcp_*` tool (`fusion_mcp_read`, `fusion_mcp_execute`). If
none is present, tell the user:

> The Fusion MCP server isn't connected. Register it, restart your AI tool so
> the tools load, and make sure Fusion is open. In Claude Code:
> ```bash
> claude mcp add --transport http fusion http://127.0.0.1:27182/mcp
> ```
> Other tools: add an HTTP MCP server at `http://127.0.0.1:27182/mcp`.

### 2. Fusion running and answering?

A registered server still errors when Fusion is closed. Run a cheap probe —
`fusion_mcp_read` with `document` / `open`, or:

```python
def run(_context):
    import adsk.core
    print(adsk.core.Application.get().version)
```

Probe scripts report with `print()` (that's what MCP returns) and let
exceptions propagate so the traceback comes back (MCP-2). If the probe errors:

> The Fusion MCP server is registered but not responding — open Fusion 360
> and load the add-in (Scripts and Add-Ins → Run), then try again.

### 3. The right document open?

The probe also shows whether a document is open. Confirm the kind the work
needs — a Manufacturing document for CAM work, a Design document for modeling
and joints. If it's missing or wrong, ask the user to open one. Prefer a new
scratch document for experiments; ask before running scripts that change a
document the user already had open (AUTO-2).

## After the preflight

Report what you confirmed — registered ✓, Fusion live (version X) ✓,
document ✓ — then proceed:

1. **Headless integration tests** — call the testRunner's `run_and_save()`
   through `execute`; it writes the same hash-validated
   `fusion_test_results.json` as the "Run Tests" button, so it satisfies the
   CI hash gate (TEST-4).
2. **API experiments** — probe scripts, `apiDocumentation` queries, and
   `screenshot` to check a result visually.
3. **Live document work** — `execute` runs against the active document.

Fusion keeps modules loaded: after editing production Python, restart the add-in
(Stop → Run) before trusting an MCP run, or it executes the old code (MCP-3).
Output can also pick up tracebacks from other loaded add-ins' event handlers;
if a response looks corrupted, retry or disable the noisy add-in.
