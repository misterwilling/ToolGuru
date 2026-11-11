# Fusion 360 React + Python Palette Architecture

This document is the architecture reference for building Fusion 360 add-ins with
React/TypeScript frontends and Python backends. It covers the full stack: entry
point, palette lifecycle, communication bridge, geometry picking, preview
geometry, joint origins, custom features, and testing.

It's a lookup, not a read-through: `AGENTS.md` holds the rules and gotchas
(cited here by ID, e.g. API-2), and this file holds the code pattern behind
each. Jump to the section the task needs.

**Sections:**

- Directory Structure
- Manifest File
- Entry Point and Module Reloading
- Event Handler Utilities
- Toolbar Registration
- Palette Lifecycle
- Python-React Communication
- Geometry Picking from Palettes
- Preview Geometry
- Joint Origins and Assembly Context
- Component Operations
- Custom Features (Timeline Entries)
- State Management
- Testing Architecture

---

## Directory Structure

```
MyAddIn/
├── MyAddIn.py                          # Entry point (bootstrap/launcher)
├── MyAddIn.manifest                    # Add-in metadata
├── config.json                         # Runtime config & feature flags
├── code/
│   ├── myaddin_entry_point.py          # Actual run()/stop() logic
│   ├── myaddin_commands/               # every package prefixed (PY-5)
│   │   ├── __init__.py                 # Command registry, toolbar setup
│   │   └── commandPalette/             # Palette command (opens React app)
│   │       ├── __init__.py
│   │       ├── entry.py                # Dispatch table, palette lifecycle
│   │       ├── state.py                # Pure Python state (no Fusion deps)
│   │       └── resources/
│   │           ├── 16x16.png
│   │           └── 32x32.png
│   ├── myaddin_lib/
│   │   ├── fusion360utils/
│   │   │   ├── __init__.py
│   │   │   ├── event_utils.py          # Event handler GC prevention
│   │   │   └── general_utils.py        # Logging, error handling
│   │   └── config_utils.py             # JSON config load/save
│   ├── myaddin_tests/                  # Python unit tests (pytest)
│   │   ├── mock_adsk.py                # Mock Fusion API modules
│   │   └── test_state.py
│   └── myaddin_fusion_tests/           # Fusion integration tests (unittest)
└── webapp/                             # React application
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx
    │   ├── api/fusionBridge.ts          # Python ↔ JS communication layer
    │   ├── types/index.ts               # TypeScript interfaces
    │   ├── hooks/                       # React hooks (state, actions)
    │   ├── components/                  # React components
    │   └── utils.ts                     # Pure logic (testable)
    └── dist/                            # Build output (palette loads this)
```

**Naming rule:** The add-in folder, `.py` entry point, and `.manifest` file
must share the exact same name (e.g. `MyAddIn/`, `MyAddIn.py`, `MyAddIn.manifest`).

---

## Manifest File

Every add-in requires a `.manifest` JSON file:

```json
{
    "autodeskProduct": "Fusion360",
    "type": "addin",
    "id": "<generate-a-new-uuid>",
    "author": "Your Name",
    "description": "Short description",
    "version": "1.0.0",
    "runOnStartup": false,
    "supportedOS": "windows|mac",
    "editEnabled": true
}
```

Generate a unique UUID per add-in: `python -c "import uuid; print(uuid.uuid4())"`.
Never reuse UUIDs across add-ins.

---

## Entry Point and Module Reloading

React palette add-ins use a two-stage launcher. `MyAddIn.py` bootstraps
`code/entry_point.py`, allowing the `code/` directory to be reloaded without
restarting Fusion.

### MyAddIn.py (launcher)

```python
import adsk.core
import importlib
import traceback
import sys
import os

_code_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'code')

# IMPORTANT: Prefix module names to avoid collisions with other add-ins.
# Generic names like 'commands' or 'entry_point' WILL collide.
_ENTRY_MODULE = 'myapp_entry_point'
_COMMANDS_MODULE = 'myapp_commands'


def run(context):
    try:
        if _code_dir not in sys.path:
            sys.path.insert(0, _code_dir)
        _reload_modules()
        ep = __import__(_ENTRY_MODULE)
        ep.run(context)
    except:
        adsk.core.Application.get().userInterface.messageBox(
            'Add-in start failed:\n{}'.format(traceback.format_exc()))


def stop(context):
    try:
        ep = __import__(_ENTRY_MODULE)
        ep.stop(context)
    except:
        adsk.core.Application.get().userInterface.messageBox(
            'Add-in stop failed:\n{}'.format(traceback.format_exc()))
    _purge_modules()


def _purge_modules():
    to_remove = [k for k in sys.modules
                 if k == _ENTRY_MODULE or k == _COMMANDS_MODULE
                 or k.startswith(_COMMANDS_MODULE + '.')]
    for k in to_remove:
        del sys.modules[k]


def _reload_modules():
    for name in [_COMMANDS_MODULE, _ENTRY_MODULE]:
        if name in sys.modules:
            try:
                importlib.reload(sys.modules[name])
            except:
                del sys.modules[name]
```

**Why two stages:** Python caches modules in `sys.modules`. Without explicit
purging, stopping and restarting the add-in reuses stale code. The
`_purge_modules()` call removes all add-in modules so the next `run()` picks
up code changes without restarting Fusion.

**Why prefixed module names:** Multiple add-ins share `sys.path`. Generic names
like `commands` or `entry_point` collide. Always prefix with your add-in name.

### code/entry_point.py

```python
from lib.fusion360utils import event_utils as futil
from lib.fusion360utils import general_utils as gutil
from commands import start as commands_start, stop as commands_stop

def run(context):
    gutil.log('Add-in starting...', force_console=True)
    commands_start()

def stop(context):
    futil.clear_handlers()
    commands_stop()
```

---

## Event Handler Utilities

Fusion silently drops event handlers that Python garbage-collects. The
`event_utils` module wraps handler registration with automatic GC prevention
and error handling.

### event_utils.py

```python
import adsk.core
import traceback
import sys

_handlers = []


def add_handler(event, callback, *, name=None, local_handlers=None):
    handler_name = name or callback.__name__
    handler_type = _get_handler_type(event)
    handler_cls = _define_handler(handler_type, callback, handler_name)
    handler = handler_cls()

    if local_handlers is not None:
        local_handlers.append(handler)
    else:
        _handlers.append(handler)

    event.add(handler)
    return handler


def clear_handlers():
    global _handlers
    _handlers = []


def _get_handler_type(event):
    module = sys.modules[event.__class__.__module__]
    add_method = getattr(type(event), 'add')
    if hasattr(add_method, '__annotations__') and 'handler' in add_method.__annotations__:
        handler_type_name = add_method.__annotations__['handler']
        if isinstance(handler_type_name, str):
            return getattr(module, handler_type_name)
        return handler_type_name
    event_type_name = type(event).__name__
    return getattr(module, event_type_name + 'Handler')


def _define_handler(handler_type, callback, name):
    class Handler(handler_type):
        def __init__(self):
            super().__init__()
        def notify(self, args):
            try:
                callback(args)
            except:
                app = adsk.core.Application.get()
                if app:
                    app.userInterface.messageBox(
                        'Handler "{}" failed:\n{}'.format(name, traceback.format_exc()))
    Handler.__name__ = f'Handler_{name}'
    return Handler
```

**Two storage modes:**
- **Global** (`_handlers`) — long-lived handlers (command registration,
  document events). Cleared in `stop()`.
- **Local** (`local_handlers`) — command-scoped handlers (execute, preview,
  validate). Cleared in `command_destroy`.

### general_utils.py

```python
import adsk.core
import traceback

try:
    from ... import config
    DEBUG = config.DEBUG
except:
    DEBUG = False


def log(message, level=adsk.core.LogLevels.InfoLogLevel, force_console=False):
    app = adsk.core.Application.get()
    if not app:
        return
    if level == adsk.core.LogLevels.ErrorLogLevel:
        app.log(str(message), level, adsk.core.LogTypes.FileLogType)
    if DEBUG or force_console:
        app.log(str(message), level, adsk.core.LogTypes.ConsoleLogType)


def handle_error(name, show_message_box=False):
    log(f'===== Error in {name} =====', adsk.core.LogLevels.ErrorLogLevel,
        force_console=True)
    log(traceback.format_exc(), adsk.core.LogLevels.ErrorLogLevel,
        force_console=True)
    if show_message_box:
        app = adsk.core.Application.get()
        if app:
            app.userInterface.messageBox(f'Error in {name}:\n{traceback.format_exc()}')
```

---

## Toolbar Registration

### commands/__init__.py

```python
import adsk.core
import traceback
from .commandPalette import entry as commandPalette

commands = [commandPalette]

ADDIN_NAME = 'MyAddIn'
COMPANY_NAME = 'MyCompany'
# Pick this based on WHERE the user will invoke the command — see the
# "Workspace IDs" section below. Do not default to FusionSolidEnvironment
# for CAM, render, simulation, or drawings add-ins.
WORKSPACE_ID = 'FusionSolidEnvironment'
TAB_ID = f'{COMPANY_NAME}_{ADDIN_NAME}_tab'
TAB_NAME = ADDIN_NAME
PANEL_ID = f'{COMPANY_NAME}_{ADDIN_NAME}_panel'
PANEL_NAME = 'Tools'


def start():
    app = adsk.core.Application.get()
    ui = app.userInterface
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    if workspace is None:
        # Workspace isn't loaded yet (e.g. Drawings before a .f2d is open).
        # Either defer registration or log and bail — don't crash.
        return

    # Idempotent: re-use the existing tab/panel if a previous stop() didn't
    # clean up, otherwise create fresh.
    toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID) or \
                  workspace.toolbarTabs.add(TAB_ID, TAB_NAME)
    panel = toolbar_tab.toolbarPanels.itemById(PANEL_ID) or \
            toolbar_tab.toolbarPanels.add(PANEL_ID, PANEL_NAME)

    for command in commands:
        command.start()


def stop():
    for command in commands:
        try:
            command.stop()
        except:
            pass
    try:
        app = adsk.core.Application.get()
        workspace = app.userInterface.workspaces.itemById(WORKSPACE_ID)
        if workspace is None:
            return
        # Look up the panel through the tab it was added to — NOT through
        # workspace.toolbarPanels, which only holds tab-less panels.
        tab = workspace.toolbarTabs.itemById(TAB_ID)
        if tab:
            panel = tab.toolbarPanels.itemById(PANEL_ID)
            if panel:
                panel.deleteMe()
            tab.deleteMe()
    except:
        pass
```

### Workspace IDs

An add-in command belongs to exactly one workspace (unless you register it in
several). Pick the workspace where the user will actually be when they want
the command — a CAM tool library belongs in **Manufacturing**, not Design; a
rendering helper belongs in **Render**, not Design. Putting a command in the
wrong workspace is a common scaffolding bug: the add-in loads cleanly and the
user never finds the button.

| ID | Workspace | Typical use | Verified |
|----|-----------|-------------|----------|
| `FusionSolidEnvironment` | Design | Solid modeling, sketches, assemblies, parameters, joints | ✅ |
| `CAMEnvironment` | Manufacturing | CAM setups, toolpaths, tool libraries, post processors, probing | ✅ |
| `FusionRenderEnvironment` | Render | Appearances, scene setup, ray-traced rendering | ✅ |
| `SimulationEnvironment` | Simulation | Static stress, modal, thermal, shape optimization | ⚠️ verify at runtime |
| `AnimationEnvironment` | Animation | Exploded views, component animation | ⚠️ verify at runtime |
| `FusionDraftingEnvironment` | Drawings | 2D drawings from 3D models | ⚠️ verify at runtime |

**✅ Verified** IDs come from Autodesk's own sample add-ins and are stable.
**⚠️ Verify at runtime** IDs are drawn from community references and Fusion
documentation but have not all been confirmed against the current version of
Fusion — always enumerate the live workspace list before hardcoding one.

### Verifying a workspace ID at runtime

Inside Fusion, open the Text Commands console (**View → Text Commands →
Python console**), switch to the workspace tab you want to target, and run:

```python
import adsk.core
app = adsk.core.Application.get()
print(app.userInterface.activeWorkspace.id)
```

To enumerate every workspace Fusion knows about right now:

```python
import adsk.core
app = adsk.core.Application.get()
for i in range(app.userInterface.workspaces.count):
    ws = app.userInterface.workspaces.item(i)
    print(ws.id, '—', ws.name)
```

Prefer this over trusting any list (including this one) when the workspace
you need isn't on the ✅ rows above.

### Workspace availability gotcha

Not every workspace exists the moment the add-in starts. Some Fusion workspaces
only register after the user opens a document of the matching type (Drawings,
for example, typically appears only after a `.f2d` document is active).
`ui.workspaces.itemById('...')` returns `None` for a workspace that doesn't
exist yet. Handle this explicitly:

```python
workspace = ui.workspaces.itemById(WORKSPACE_ID)
if workspace is None:
    gutil.log(
        f'Workspace {WORKSPACE_ID} not available yet — command will register '
        'the first time a matching document is opened.', force_console=True)
    return
```

If your add-in legitimately needs a workspace that's not always present,
listen for workspace-activation events and defer the toolbar registration
until the workspace appears, rather than crashing at `start()`.

### Choosing the workspace at scaffold time

When scaffolding a new add-in, *ask* which workspace before writing any code —
don't default to `FusionSolidEnvironment`. Phrase the question in terms of
where the user will click the button:

- "Users will run this while modeling or sketching" → Design
  (`FusionSolidEnvironment`)
- "Users will run this while setting up CAM operations, managing tools, or
  editing post processors" → Manufacturing (`CAMEnvironment`)
- "Users will run this while setting up a render" → Render
  (`FusionRenderEnvironment`)
- "Users will run this from multiple workspaces" → register the tab/panel in
  each workspace, not just one
- "I'm not sure" → ask the user to describe the workflow; don't guess

### Multi-workspace registration

If your add-in genuinely belongs in more than one workspace (for example, a
parts library that's useful in both Design and Manufacturing), iterate over
the workspace IDs and register the tab+panel in each. Use the same tab/panel
ID strings in every workspace so the user sees consistent placement:

```python
TARGET_WORKSPACES = ['FusionSolidEnvironment', 'CAMEnvironment']

def start():
    app = adsk.core.Application.get()
    ui = app.userInterface
    for ws_id in TARGET_WORKSPACES:
        workspace = ui.workspaces.itemById(ws_id)
        if workspace is None:
            continue
        toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID) or \
                      workspace.toolbarTabs.add(TAB_ID, TAB_NAME)
        panel = toolbar_tab.toolbarPanels.itemById(PANEL_ID) or \
                toolbar_tab.toolbarPanels.add(PANEL_ID, PANEL_NAME)
        for command in commands:
            command.start_in_panel(panel)
```

In `stop()`, mirror the iteration — delete the panel and tab in each
workspace, not just one.

### Known scaffolding pitfalls

1. **Hardcoding `FusionSolidEnvironment` when the add-in is CAM-related.**
   Fusion's own sample `commands/__init__.py` ships with this ID, so AI-driven
   scaffolders that mimic samples inherit the wrong default. Always ask the
   user, don't copy the sample's workspace ID.

2. **Using `workspace.toolbarPanels` to find a panel you added to a tab.**
   A panel added via `tab.toolbarPanels.add(...)` lives on that tab, not on
   `workspace.toolbarPanels` (which contains only tab-less top-level panels).
   In `stop()`, look up the panel through the same tab you added it to:

   ```python
   tab = workspace.toolbarTabs.itemById(TAB_ID)
   if tab:
       panel = tab.toolbarPanels.itemById(PANEL_ID)
       if panel:
           panel.deleteMe()
       tab.deleteMe()
   ```

3. **Duplicating `WORKSPACE_ID` / `TAB_ID` / `PANEL_ID` across files.** If
   `commands/__init__.py` creates the tab but `commands/commandPalette/entry.py`
   looks it up with a *second copy* of the ID constants, the two can drift and
   the command gets added to a nonexistent panel. Define IDs once in
   `commands/__init__.py` (or a shared `ids.py`) and import them everywhere.

4. **Not registering the panel in `start()` before adding a command to it.**
   `panel.controls.addCommand(cmd_def)` will raise if `panel` is `None` —
   which happens whenever the previous `stop()` didn't clean up and the panel
   no longer exists. Always use the `itemById(...) or add(...)` idiom so
   `start()` is idempotent.

---

## Palette Lifecycle

The palette command opens a React app inside Fusion's HTML palette.

```python
def command_created(args: adsk.core.CommandCreatedEventArgs):
    app = adsk.core.Application.get()
    ui = app.userInterface

    # Always delete and recreate to avoid stale cached HTML
    palette = ui.palettes.itemById(PALETTE_ID)
    if palette:
        palette.deleteMe()

    palette = ui.palettes.add(
        PALETTE_ID,
        PALETTE_NAME,
        _get_palette_url(),
        True,   # isVisible
        True,   # showCloseButton
        True,   # isResizable
        PALETTE_WIDTH,
        PALETTE_HEIGHT,
        True    # useNewWebBrowser — REQUIRED for window.adsk JS bridge
    )

    futil.add_handler(palette.incomingFromHTML, on_html_event)
    futil.add_handler(palette.closed, on_palette_closed)

    # Suppress command dialog — we only want the palette
    args.command.isAutoExecute = True


def _get_palette_url():
    dist_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', '..', '..', 'webapp', 'dist', 'index.html')
    dist_path = os.path.abspath(dist_path)
    return 'file:///' + dist_path.replace('\\', '/')
```

**Key points:**
- Delete and recreate the palette each time to avoid serving stale cached HTML
- The 9th parameter (`useNewWebBrowser=True`) is **required** for the `adsk`
  JS bridge to work
- `isAutoExecute = True` suppresses the empty command dialog

---

## Python-React Communication

### Architecture

```
React UI                          Python Backend
─────────────────────────────────────────────────────
sendToFusion(action, data)  ───►  on_html_event(args)
                                    args.action = action
                                    args.data = JSON string
                            ◄───  args.returnData = JSON response

onFusionPush(callback)      ◄───  palette.sendInfoToHTML(action, JSON)
```

### fusionBridge.ts

```typescript
declare const adsk: {
    fusionSendData: (action: string, data: string) => Promise<string>
} | undefined

function waitForBridge(): Promise<boolean> {
    return new Promise((resolve) => {
        if (typeof adsk !== 'undefined') { resolve(true); return }
        let attempts = 0
        const interval = setInterval(() => {
            attempts++
            if (typeof adsk !== 'undefined') {
                clearInterval(interval); resolve(true)
            } else if (attempts > 50) {
                clearInterval(interval); resolve(false)
            }
        }, 100)
    })
}

const bridgeReady = waitForBridge()

export async function sendToFusion(action: string, data?: any): Promise<any> {
    await bridgeReady
    if (typeof adsk === 'undefined') return null
    try {
        const response = await adsk.fusionSendData(action, JSON.stringify(data ?? {}))
        try { return JSON.parse(response) } catch { return response }
    } catch (err) {
        console.error(`[fusionBridge] Error in ${action}:`, err)
        return null
    }
}

export function onFusionPush(callback: (action: string, data: any) => void): void {
    (window as any).fusionJavaScriptHandler = {
        handle: (action: string, data: string) => {
            try { callback(action, JSON.parse(data)) }
            catch { callback(action, data) }
        }
    }
}
```

**Key details:**
- `adsk` is a bare global injected **after** page load — not `window.adsk`
- Poll/wait before first use (the `waitForBridge` pattern)
- Python reads `args.action` and `args.data` — NOT `args.jsonData`

### Dispatch Table Pattern

Route actions through a dispatch table instead of if/elif chains:

```python
def on_html_event(args: adsk.core.HTMLEventArgs):
    action = args.action
    data = json.loads(args.data or '{}')

    if action == 'response':
        args.returnData = '{}'
        return

    handler = handlers.get(action)
    if handler:
        result = handler(data)
        args.returnData = json.dumps(result)
    else:
        args.returnData = json.dumps({'error': f'Unknown action: {action}'})


handlers = {
    'get_state': lambda data: state.serialize(),
    'set_option': lambda data: _handle_set_option(data),
    'pick_face': lambda data: _handle_pick(data),
}
```

**The 'response' echo:** When Python calls `palette.sendInfoToHTML()`, the JS
handler's return value echoes back as `action='response'`. Always ignore it.

---

## Geometry Picking from Palettes

Palettes don't have `SelectionCommandInput`. Use `ui.selectEntity()` — a
blocking call that activates a pick cursor in the viewport.

**You cannot call `selectEntity()` inside `on_html_event`** — it blocks the
main thread while the palette is waiting for `args.returnData`. Instead, fire a
custom event, return immediately, and handle the blocking pick in the custom
event handler.

### Architecture

```
React clicks "Pick"
  → sendToFusion('pick_face', { type: 'face' })
    → on_html_event: fires custom event, returns current state
      → custom event handler: calls ui.selectEntity() (blocks)
        → user clicks geometry
          → process selection, update state
            → palette.sendInfoToHTML('state_update', new_state)
              → React receives push, re-renders
```

### Registration

```python
PICK_EVENT_ID = 'MyCompany_MyAddIn_pickEvent'
_pick_custom_event = None

def start():
    global _pick_custom_event
    app = adsk.core.Application.get()
    _pick_custom_event = app.registerCustomEvent(PICK_EVENT_ID)
    futil.add_handler(_pick_custom_event, _on_pick_event)

def stop():
    global _pick_custom_event
    app = adsk.core.Application.get()
    if _pick_custom_event:
        app.unregisterCustomEvent(PICK_EVENT_ID)
        _pick_custom_event = None
```

### Firing the pick from on_html_event

```python
def _handle_pick(data):
    pick_request = {
        'pick_type': data.get('type', 'face'),
        'prompt': data.get('prompt', 'Select geometry'),
    }
    app = adsk.core.Application.get()
    app.fireCustomEvent(PICK_EVENT_ID, json.dumps(pick_request))
    return state.serialize()  # return immediately
```

### Handling the pick

```python
def _on_pick_event(args: adsk.core.CustomEventArgs):
    pick_request = json.loads(args.additionalInfo)
    app = adsk.core.Application.get()
    ui = app.userInterface

    filter_str = _get_filter(pick_request.get('pick_type', 'face'))
    prompt = pick_request.get('prompt', 'Select geometry')

    try:
        selection = ui.selectEntity(prompt, filter_str)
        entity = selection.entity
        point = selection.point
        _process_pick(entity, point, pick_request)
    except:
        pass  # user pressed Escape

    _send_state_to_palette()


def _send_state_to_palette():
    app = adsk.core.Application.get()
    palette = app.userInterface.palettes.itemById(PALETTE_ID)
    if palette:
        palette.sendInfoToHTML('state_update', json.dumps(state.serialize()))
```

### selectEntity filter strings

| Filter | Selects |
|--------|---------|
| `'PlanarFaces'` | Flat faces only |
| `'Faces'` | All face types |
| `'LinearEdges'` | Straight edges only |
| `'Edges'` | All edge types |
| `'Vertices'` | Vertex points |
| `'Bodies'` | Solid/surface bodies |
| `'Occurrences'` | Component occurrences |
| `'JointOrigins'` | Joint origins |
| `'SketchPoints'` | Points in sketches |
| `'ConstructionPoints'` | Construction points |

Comma-separate for multiple: `'SketchPoints,ConstructionPoints,Vertices'`

### Pick Chaining (Auto-Advance)

When your workflow involves sequential picks (e.g. pick stock, then vise, then
plate), chain them synchronously within the same custom event handler:

```python
_active_pick = None

def _on_pick_event(args: adsk.core.CustomEventArgs):
    global _active_pick
    pick_request = json.loads(args.additionalInfo)
    container_type = pick_request.get('container_type', '')

    _active_pick = container_type
    _send_state_to_palette()  # show which pick is active

    try:
        selection = ui.selectEntity(f'Select {container_type}', 'Occurrences')
        _process_pick(selection.entity, container_type)
        _send_state_to_palette()

        next_type = _get_next_pick(state, container_type)
        if next_type:
            _do_chained_pick(next_type)
            return
    except:
        pass  # cancelled

    _active_pick = None
    _send_state_to_palette()
```

Key points:
- `selectEntity()` blocks, so chained picks happen sequentially
- Push state **before** each `selectEntity()` so React shows which pick is active
- Escape at any point breaks the chain
- Include `_active_pick` in the serialized state so React can highlight the
  active row

### Point Picking: worldGeometry vs geometry

```python
def get_world_point(entity, selection_point=None):
    if isinstance(entity, adsk.fusion.SketchPoint):
        return entity.worldGeometry  # MUST use worldGeometry, not geometry
    elif isinstance(entity, adsk.fusion.ConstructionPoint):
        return entity.geometry
    elif hasattr(entity, 'geometry') and isinstance(entity.geometry, adsk.core.Point3D):
        return entity.geometry
    else:
        return selection_point  # fallback to click location
```

Filter: `'SketchPoints,ConstructionPoints,JointOrigins,Vertices'`

---

## Preview Geometry

Palettes have **no auto-rollback**. Unlike command dialogs where preview
geometry is cleaned up automatically, any geometry created from a palette
persists. You must track everything and delete explicitly.

### Token-Based Tracking

```python
class PreviewState:
    def __init__(self):
        self.sketch_tokens = []
        self.feature_tokens = []
        self.appearance_cache = {}
```

After creating any sketch or feature, record its token immediately:

```python
sketch = root.sketches.add(root.xYConstructionPlane)
sketch.isVisible = False
preview.sketch_tokens.append(sketch.entityToken)

extrude = root.features.extrudeFeatures.add(ext_input)
preview.feature_tokens.append(extrude.entityToken)
```

### Deletion Order

Delete features first (in reverse creation order), then sketches:

```python
def delete_preview(design, preview):
    for token in reversed(preview.feature_tokens):
        try:
            entities = design.findEntityByToken(token)
            if entities and hasattr(entities[0], 'deleteMe'):
                entities[0].deleteMe()
        except:
            pass
    for token in preview.sketch_tokens:
        try:
            entities = design.findEntityByToken(token)
            if entities and hasattr(entities[0], 'deleteMe'):
                entities[0].deleteMe()
        except:
            pass
    preview.sketch_tokens = []
    preview.feature_tokens = []
```

### Cleanup Locations

Delete preview geometry in **all** of these:
- `stop()` — add-in shutting down
- `on_palette_closed()` — user closed the palette
- Before re-creating preview — delete old before building new
- On successful execute — preview replaced by permanent geometry

### Appearance Caching

Creating appearances from the material library is slow. Cache by color name:

```python
def get_or_create_appearance(design, color_name, cache):
    if color_name in cache:
        return cache[color_name]
    app = adsk.core.Application.get()
    for i in range(app.materialLibraries.count):
        lib = app.materialLibraries.item(i)
        lib_app = lib.appearances.itemByName(f'Plastic - Translucent Glossy ({color_name})')
        if lib_app:
            doc_app = design.appearances.addByCopy(lib_app, f'MyAddIn_{color_name}')
            cache[color_name] = doc_app
            return doc_app
    return None
```

### Refresh Pattern

When selections change, delete all indicators and recreate:

```python
def refresh_indicators(design, preview, selections):
    delete_preview(design, preview)
    for sel in selections:
        if sel is not None:
            create_indicator(design, sel, preview)
```

---

## Joint Origins and Assembly Context

### Spelling Gotcha

The Fusion API property is `jointOrgins` (missing the 'i'). Not `jointOrigins`:

```python
comp.jointOrgins.count    # CORRECT
comp.jointOrigins.count   # WRONG — AttributeError
```

### Assembly Context Proxying

Joint origins belong to components, but joints are created in the root. Proxy
JOs into the assembly context before use:

```python
def get_joint_origin(parent_occ, child_name):
    child = find_child(parent_occ, child_name)
    if child and child.component.jointOrgins.count > 0:
        jo = child.component.jointOrgins.item(0)
        return jo.createForAssemblyContext(child)  # REQUIRED
    return None
```

### Creating Joints from Joint Origins

Pass proxied `JointOrigin` objects **directly** to `joints.createInput()`:

```python
# CORRECT
joint_input = root.joints.createInput(jo1, jo2)
joint_input.setAsPlanarJointMotion(adsk.fusion.JointDirections.ZAxisJointDirection)
joint = root.joints.add(joint_input)

# WRONG — JointGeometry.createByJointOrigin() does not exist
geo1 = adsk.fusion.JointGeometry.createByJointOrigin(jo1)  # AttributeError
```

### Creating JointOrigin Objects Programmatically

`JointOrigins.createInput()` takes **one argument**: a `JointGeometry` object.

```python
geo = adsk.fusion.JointGeometry.createByPoint(component.originConstructionPoint)
jo_input = component.jointOrgins.createInput(geo)
jo = component.jointOrgins.add(jo_input)
jo.name = 'My Joint Origin'
```

### JointGeometry Creation Methods

```python
# From a point (ConstructionPoint, SketchPoint, BRepVertex)
geo = adsk.fusion.JointGeometry.createByPoint(point_entity)

# From a planar face (center)
geo = adsk.fusion.JointGeometry.createByPlanarFace(
    face, None, adsk.fusion.JointKeyPointTypes.CenterKeyPoint)

# Between two parallel planes
geo = adsk.fusion.JointGeometry.createByBetweenTwoPlanes(
    face1, face2, face1, None, adsk.fusion.JointKeyPointTypes.CenterKeyPoint)
```

### World-Space Orientation

A JointOrigin's `primaryAxisVector` returns **local-space** axes.
`createForAssemblyContext()` does NOT transform axis vectors. To get
world-space orientation, apply the occurrence transform:

```python
def get_world_jo_z(occ):
    comp = occ.component
    if comp.jointOrgins.count == 0:
        return None
    local_z = comp.jointOrgins.item(0).primaryAxisVector
    if not local_z:
        return None
    t = occ.transform
    vec = adsk.core.Vector3D.create(
        local_z.x * t.getCell(0, 0) + local_z.y * t.getCell(0, 1) + local_z.z * t.getCell(0, 2),
        local_z.x * t.getCell(1, 0) + local_z.y * t.getCell(1, 1) + local_z.z * t.getCell(1, 2),
        local_z.x * t.getCell(2, 0) + local_z.y * t.getCell(2, 1) + local_z.z * t.getCell(2, 2),
    )
    vec.normalize()
    return vec
```

| Scenario | Method |
|----------|--------|
| Creating joints between JOs | `jo.createForAssemblyContext(occ)` |
| Reading JO world-space orientation | `occ.transform` applied to local axis |
| Comparing orientations of two JOs | `occ.transform` on each, then dot product |

---

## Component Operations

### Reading Document Design Intent (Part / Assembly / Hybrid)

If your add-in only makes sense on one kind of document — it models bodies
natively *and* inserts components, or it's assembly-only, or part-only — gate on
the document's **declared design intent**, read from `design.designIntent`:

```python
def classify_design(design) -> str:
    """'part' | 'assembly' | 'hybrid' | 'unknown'."""
    try:
        intent = design.designIntent
        types = adsk.fusion.DesignIntentTypes
    except Exception:
        return 'unknown'          # not every product reports intent
    if intent == types.HybridDesignIntentType:
        return 'hybrid'
    if intent == types.PartDesignIntentType:
        return 'part'
    if intent == types.AssemblyDesignIntentType:
        return 'assembly'
    return 'unknown'
```

**Read the declared intent, do NOT infer from model composition.**
`design.designIntent` is the document's declared type — the "Part Design /
Assembly Design / Hybrid Design" setting shown in Document Settings. It is *not*
the same as looking at what the model currently contains (root bodies vs.
component occurrences). The distinction is load-bearing: a **hybrid** document
with no components inserted *yet* is still hybrid — and that empty state is
exactly when the user opens a fixture/setup wizard to start adding components. A
composition-based check (`root.bRepBodies.count > 0 and no occurrences → part`)
would wrongly reject that document. Trust the declared intent; don't reverse-
engineer it from geometry.

Gate at `command_created`, before building the palette — show a `messageBox` and
bail so the wrong document type never opens the UI:

```python
def command_created(args):
    design = adsk.fusion.Design.cast(
        app.activeDocument.products.itemByProductType('DesignProductType'))
    if not design or classify_design(design) != 'hybrid':
        ui.messageBox('This add-in only works on a hybrid document.')
        return
    _create_palette()
```

**Testing.** The `adsk` mock exposes `DesignIntentTypes` as int enums and
`MockDesign.designIntent` as a plain int, so `classify_design` is a pure unit
test — set `design.designIntent` to each type and assert the returned string
(including that a hybrid design with no occurrences still classifies as
`'hybrid'`). See §"Testing Architecture" → Layer 1.

### Inserting from Data Projects

```python
# Linked reference (preserves internal joints)
occ = root.occurrences.addByInsert(data_file, adsk.core.Matrix3D.create(), True)

# Embedded copy (no link)
occ = root.occurrences.addByInsert(data_file, adsk.core.Matrix3D.create(), False)
```

Always pass `True` (linked) unless you specifically need an embedded copy.

### Entity Attribute Tagging

```python
ATTR_GROUP = 'MyAddIn'

# Write
occurrence.attributes.add(ATTR_GROUP, 'setup_id', 'abc-123')
occurrence.attributes.add(ATTR_GROUP, 'role', 'body')

# Read
attr = entity.attributes.itemByName(ATTR_GROUP, 'setup_id')
value = attr.value if attr else None

# Search
def find_tagged(root, group, attr_name, attr_value):
    results = []
    for i in range(root.occurrences.count):
        occ = root.occurrences.item(i)
        attr = occ.attributes.itemByName(group, attr_name)
        if attr and attr.value == attr_value:
            results.append(occ)
    return results
```

### Collection Iteration

Fusion collections use index-based access, not Python iterators:

```python
# CORRECT
for i in range(root.occurrences.count):
    occ = root.occurrences.item(i)

# WRONG — most Fusion collections don't support this
for occ in root.occurrences:
```

**Exception — `URLVector`.** The CAM library URL lists
(`toolLibraries.childFolderURLs(url)` and `childAssetURLs(url)`) return a
`URLVector`, which is NOT a Fusion collection: it has no `.count` / `.item(i)`.
Use `len()` and iteration / indexing instead. (Verified live, 2026-06: a
`.count` access raises `AttributeError: 'URLVector' object has no attribute
'count'`.)

```python
folders = tl.childFolderURLs(root)   # URLVector
for url in folders:                  # iterable
    walk(url)
print(len(folders))                  # len(), not .count
```

### Single-Child Wrapper Recursion

Component references (from McMaster, GrabCAD, etc.) often insert intermediate
wrapper occurrences. Recurse through single-child wrappers transparently:

```python
def find_child_by_name(parent_occ, required_name):
    children = parent_occ.childOccurrences
    for i in range(children.count):
        child = children.item(i)
        if name_matches(child.name, required_name):
            return child
        if name_matches(child.component.name, required_name):
            return child
    if children.count == 1:
        return find_child_by_name(children.item(0), required_name)
    return None
```

---

## Custom Features (Timeline Entries)

Custom features place entries in Fusion's parametric timeline with a custom
icon. Users double-click to re-open your command in edit mode.

### Architecture

Two command definitions work together:

1. **Create command** — toolbar button. Creates geometry AND a `CustomFeature`.
2. **Edit command** — no toolbar button. Invoked when user double-clicks
   the timeline entry. Reads data from `CustomFeature` attributes.

### Registration

**Register the edit command BEFORE setting `editCommandId`.** Fusion silently
ignores `editCommandId` if the command doesn't exist yet.

```python
CUSTOM_FEATURE_ID = 'MyCompany_MyAddIn_MyFeature'
EDIT_CMD_ID = 'MyCompany_MyAddIn_EditMyFeature'

def start():
    global _custom_feature_def
    app = adsk.core.Application.get()
    ui = app.userInterface

    # 1. Create edit command FIRST
    edit_cmd_def = ui.commandDefinitions.addButtonDefinition(
        EDIT_CMD_ID, 'Edit My Feature', 'Edit', ICON_FOLDER)
    futil.add_handler(edit_cmd_def.commandCreated, on_edit_command_created)

    # 2. Register custom feature definition
    _custom_feature_def = adsk.fusion.CustomFeatureDefinition.create(
        CUSTOM_FEATURE_ID, 'My Feature', ICON_FOLDER)
    _custom_feature_def.editCommandId = EDIT_CMD_ID
```

### Creating a CustomFeature

A CustomFeature must wrap at least one feature. If your operation only creates
joints, create a hidden placeholder sketch:

```python
def create_custom_feature(design, feature_def, data):
    root = design.rootComponent
    sketch = root.sketches.add(root.xYConstructionPlane)
    sketch.name = 'Placeholder'
    sketch.isVisible = False
    sketch.sketchPoints.add(adsk.core.Point3D.create(0, 0, 0))

    cf_input = root.features.customFeatures.createInput(feature_def)
    cf_input.setStartAndEndFeatures(sketch, sketch)
    cf = root.features.customFeatures.add(cf_input)

    # Store data as attributes
    cf.attributes.add('MyAddIn', 'my_id', data['id'])
    cf.attributes.add('MyAddIn', 'config', json.dumps(data['config']))
    cf.attributes.add('MyAddIn', 'sketch_token', sketch.entityToken)

    return cf.entityToken
```

### Storing Data

- **Attributes** (recommended) — string key-value pairs, hidden from user
- **Custom parameters** (optional) — numeric values visible in Parameters dialog

### Edit Command Handler

```python
def on_edit_command_created(args: adsk.core.CommandCreatedEventArgs):
    ui = adsk.core.Application.get().userInterface
    if ui.activeSelections.count == 0:
        return
    cf = adsk.fusion.CustomFeature.cast(ui.activeSelections.item(0).entity)
    if cf is None:
        return

    # Read stored data
    my_id = cf.attributes.itemByName('MyAddIn', 'my_id')
    config = cf.attributes.itemByName('MyAddIn', 'config')

    # For palette-based edit: load state, open palette, suppress dialog
    args.command.isAutoExecute = True
```

### Edit: Delete-and-Recreate

The standard pattern: delete old custom feature and geometry, recreate with
updated values:

1. Read all needed tokens from attributes
2. Delete old joints/geometry by token
3. Delete placeholder sketch
4. Delete the custom feature itself
5. Re-resolve remaining tokens (may shift after deletions)
6. Create new geometry with updated values
7. Create new custom feature with updated attributes

### Orphan Cleanup

If a user manually deletes a custom feature from the timeline, associated
joints become orphaned. Clean up on startup:

```python
def cleanup_orphaned_joints():
    design = adsk.fusion.Design.cast(
        adsk.core.Application.get().activeProduct)
    if not design:
        return
    root = design.rootComponent
    to_delete = []
    for i in range(root.joints.count):
        joint = root.joints.item(i)
        parent_attr = joint.attributes.itemByName('MyAddIn', 'parent_feature_token')
        if parent_attr:
            entities = design.findEntityByToken(parent_attr.value)
            if not entities:
                to_delete.append(joint)
    for joint in to_delete:
        try:
            joint.deleteMe()
        except:
            pass
```

---

## State Management

### Full-State Serialization Pattern

Keep a pure Python state class with no Fusion API dependencies. Serialize the
full state on every response to React:

```python
class AppState:
    def __init__(self):
        self.selections = {}
        self.mode = 'default'
        self.config = {}

    def serialize(self) -> dict:
        return {
            'selections': self.selections,
            'mode': self.mode,
            'config': self.config,
        }
```

**Every action returns the full serialized state.** React replaces its state
entirely on each response. This is simpler than granular updates and avoids
sync bugs.

### Token Storage

Store entity tokens (strings) in state, not entity objects. Resolve with
`design.findEntityByToken(token)` when needed. Entity objects go stale between
event handler calls.

---

## Testing Architecture

Three test layers, each covering different parts of the stack. `/jgl-fusion-scaffold`
generates all of it from `templates/scaffold/`; on an existing add-in, copy
the matching files from there and adapt.

### Layer 1: Python Unit Tests (pytest)

Test pure logic by mocking the `adsk` modules. The mock layer
(`templates/scaffold/code/{{addin_prefix}}_tests/mock_adsk.py`) provides typed mock
classes for common Fusion API types — geometry, components, occurrences,
joints, BRep entities — and injects them into `sys.modules` before any
production code is imported.

The unit-test package is named `<prefix>_tests/` (e.g.
`mytool_tests/`), NOT bare `tests/`. The same prefix-or-collide rule that
applies to `commands` and `lib` applies here — see "Why prefix the test
packages too?" at the end of this section.

**Usage pattern in test files:**

```python
from myapp_tests.mock_adsk import setup_adsk_modules, MockOccurrence, MockVector3D
setup_adsk_modules()  # MUST be before any adsk imports

# Now safe to import production code
from myapp_commands.commandPalette import my_logic

class TestMyLogic:
    def test_something(self):
        occ = MockOccurrence('TestPart')
        occ.add_joint_origin('Origin1')
        result = my_logic.process(occ)
        assert result.token == occ.entityToken
```

Key points:
- `setup_adsk_modules()` must be called at **module level**, before importing
  any code that does `import adsk.core` or `import adsk.fusion`
- Mock classes implement only the methods your code calls — extend them as
  your add-in uses more of the API
- Helper methods like `MockOccurrence.add_child()` and `.add_joint_origin()`
  make it easy to build test hierarchies

Run: `python -m pytest code/<prefix>_tests/ -v`

### Layer 2: TypeScript Unit Tests (Vitest)

Extract pure logic into utility files (e.g. `utils.ts`) and test with Vitest.
Keep React components thin — business logic belongs in testable pure functions.

**Vitest configuration:** See `templates/scaffold/webapp/vite.config.ts`. Key settings:
- `base: './'` — required because palettes load via `file://` URLs
- Coverage provider: `v8` (fast, built-in)
- Coverage scoped to `.ts` files, excluding `.tsx`, `.test.ts`, and `main.tsx`

**Test scripts** in `package.json`:

```json
{
  "test": "vitest run",
  "test:watch": "vitest",
  "test:coverage": "vitest run --coverage"
}
```

**Test pattern:** Use factory helpers for test data:

```typescript
function makeMyData(overrides?: Partial<MyType>): MyType {
    return {
        id: 'test-1',
        name: 'Default',
        ...overrides,
    }
}

describe('processData', () => {
    it('transforms the name field', () => {
        const result = processData(makeMyData({ name: 'Input' }))
        expect(result.name).toBe('Expected Output')
    })
})
```

Run: `cd webapp && npm test`

### Layer 3: Fusion Integration Tests

Test real Fusion API operations (joints, attributes, geometry) using Python's
`unittest`, run against a live Fusion 360 session. These tests **cannot run
in CI** — they require a running Fusion. They CAN be triggered two ways, both
of which write the same hash-validated results file:

- **The "Run Tests" toolbar button** (manual, GUI).
- **The Fusion MCP server, headlessly** (programmatic — preferred for an
  agent). See "Triggering a run" below.

**Enabling the button:** Set `"enable_tests": true` in `config.json` (found
in the add-in's root folder). This registers a "Run Tests" button in the
add-in's toolbar panel. When you click it, the runner loads all test modules
under `code/<prefix>_fusion_tests/`, runs the full `unittest` suite against
the live Fusion API, displays a pass/fail summary in a message box, and logs
detailed results to the Text Commands console (View → Text Commands).

**Triggering a run headlessly (Fusion MCP server).** The button handler
(`_on_execute`) is a thin wrapper around a UI-free
`run_and_save()` in `<prefix>_commands/testRunner/entry.py`. Both go through
the identical `_run_tests()` + `_save_results()` core, so the
`fusion_test_results.json` they write — codebase hash and all — is
byte-for-byte the same. When the Fusion MCP server is connected, send an
`execute`/`script` that calls `run_and_save()` and prints the result:

```python
from {{addin_prefix}}_commands.testRunner.entry import run_and_save

def run(_context):
    r = run_and_save()
    print(f"run={r['tests_run']} passed={r['passed']} "
          f"failed={r['failed']} errors={r['errors']}")
    print("hash", r['codebase_hash'])
    for f in r['failures'] + r['error_details']:
        print(f['name']); print(f['traceback'])
```

This satisfies the CI hash gate exactly like a button click — there is no
second-class path. `run_and_save()` is not gated by `enable_tests` (that flag
only controls the button). **Caveat:** an MCP run executes the production
code currently resident in `sys.modules`; after editing production source,
restart the add-in (Stop → Run) before running, or you'll test stale code.
The runner re-imports the *test* files on every call, so test-file edits are
picked up without a restart. (See MCP-3 in AGENTS.md.)

The integration-test package is named `<prefix>_fusion_tests/` (e.g.
`mytool_fusion_tests/`), NOT bare `fusion_tests/`. See "Why prefix the
test packages too?" below — this is the package name that historically
collided across add-ins and produced the most confusing failure mode.

**Test fixtures** (`templates/scaffold/code/{{addin_prefix}}_fusion_tests/helpers.py`):
- `create_test_document()` — creates a temporary Fusion document with a
  component hierarchy matching your add-in's expected structure
- `close_test_document(doc)` — closes without saving
- `close_all_test_documents()` — cleanup for failed tests that left documents
  open
- `create_body_with_face(design)` — creates a simple box body for geometry
  tests

**Test class pattern:**

```python
import unittest
from myapp_fusion_tests.helpers import create_test_document, close_test_document

class TestMyFeature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc, cls.design, cls.fixtures = create_test_document()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'doc'):
            close_test_document(cls.doc)

    def test_joint_creation(self):
        root = self.design.rootComponent
        # ... test with real Fusion API ...
        self.assertEqual(root.joints.count, 1)
```

Guard `tearDownClass` with `hasattr(cls, 'doc')` — if `setUpClass` fails
partway through, `cls.doc` won't exist.

### Why prefix the test packages too?

Multiple Fusion add-ins share `sys.path` once they're loaded. Generic
package names — `commands`, `lib`, `tests`, **`fusion_tests`** — are
indistinguishable from each other across add-ins, and Python binds the
first one it finds. The integration-test stack is uniquely vulnerable
because:

- The in-Fusion test runner imports
  `<pkg>.hash_utils.compute_codebase_hash` to stamp the results file.
- If the bare-name `fusion_tests` package resolves to a different
  installed add-in's copy, the hash function walks **that** add-in's
  source tree.
- The CI-side validator (`<pkg>.hash_utils.compute_codebase_hash`)
  only sees one add-in on its `sys.path`, so it always returns the
  "right" hash.
- The two never match. CI fails with "Hash mismatch — re-run Fusion
  integration tests." Re-running doesn't help. There is no error
  message that points at the collision.

The scaffolder solves this by prefixing both test packages
(`<prefix>_tests/` and `<prefix>_fusion_tests/`) so each add-in has a
unique fully-qualified name, and by inlining the codebase-hash function
inside the test runner so it resolves paths from `__file__` rather than
through any importable package. Don't undo either of those without
restoring the equivalent guarantee.

### Hash Validation: Keeping Integration Tests Current

The core challenge: integration tests run manually inside Fusion, but CI needs
to know whether those results are still valid. The solution is a **codebase
hash** stored alongside test results.

**How it works:**

1. `hash_utils.py`
   (`templates/scaffold/code/{{addin_prefix}}_fusion_tests/hash_utils.py`) computes a
   SHA-256 hash of all `.py` files under `code/`, excluding the unit-test
   package (`<prefix>_tests/`). Both filenames and file contents are hashed,
   so renames, additions, and removals all change the hash.

2. When integration tests run inside Fusion, the test runner computes the
   hash itself (using a copy of the algorithm inlined in the testRunner
   module — see "Why prefix the test packages too?") and saves it into
   `code/<prefix>_tests/fusion_test_results.json` alongside the test
   results. The runner deliberately does NOT call
   `<prefix>_fusion_tests.hash_utils.compute_codebase_hash` for stamping;
   that path is reserved for CI's read-only validation, where there's no
   shadowing risk.

3. In CI, `test_fusion_results.py`
   (`templates/scaffold/code/{{addin_prefix}}_tests/test_fusion_results.py`)
   recomputes the hash from current source files via
   `<prefix>_fusion_tests.hash_utils` and compares it to the stored hash.
   If they don't match, CI fails with a message telling the developer to
   re-run integration tests. The two implementations (`hash_utils.py` and
   the testRunner's inlined copy) have to produce byte-identical digests for
   the same source tree — they walk the same files in the same order with
   the same SHA-256 inputs. Update both in lockstep when the algorithm
   changes.

**Results file schema** (`code/<prefix>_tests/fusion_test_results.json`):

```json
{
    "tests_run": 32,
    "passed": 32,
    "failed": 0,
    "errors": 0,
    "all_passed": true,
    "timestamp": "2026-04-06T14:30:00",
    "codebase_hash": "ca80a8a2f148...",
    "coverage": {
        "num_statements": 2861,
        "covered_lines": 579,
        "percent_covered": 20.2,
        "files": {
            "my_logic.py": { "stmts": 200, "miss": 50, "cover": 75.0 }
        }
    }
}
```

**Running integration tests:**

Integration tests cannot run in CI — they require a live Fusion 360 session —
but within a live session there are two equivalent triggers (the button and
the MCP-driven `run_and_save()`; see "Triggering a run" under Layer 3). Run
one of them before merging. The button steps:

1. Open `config.json` in the add-in's root folder. Set `"enable_tests": true`
   and save. (You only need to do this once — leave it enabled during
   development.)
2. Open Fusion 360. If the add-in is already running, stop and restart it so
   it picks up the config change. The add-in's toolbar panel (in the Fusion
   toolbar at the top of the screen, under the tab your add-in registers)
   will now show a **"Run Tests"** button alongside the normal add-in
   commands.
3. Click **"Run Tests"**. The runner will:
   - Execute the full `unittest` suite against the live Fusion API.
   - Compute a SHA-256 hash of all source files under `code/` (excluding
     unit test files).
   - Write results, coverage data, and the codebase hash to
     `code/<prefix>_tests/fusion_test_results.json`.
   - Display a pass/fail summary in a message box.
   - Log detailed results (individual test names, failures, tracebacks) to
     the Text Commands console (View → Text Commands).
4. If any tests fail, fix them and click "Run Tests" again.
5. Commit the updated `fusion_test_results.json` alongside your code changes.

The "Run Tests" button is only visible when `"enable_tests": true` in
`config.json`. There is no plain-CLI equivalent (the tests need a live Fusion
process), but the Fusion MCP server's `execute`/`script` tool calling
`run_and_save()` is the headless equivalent and writes the same artifact —
see "Triggering a run headlessly" under Layer 3.

**When to run:** You do NOT need to re-run integration tests after every edit —
that would be impractical. Hash mismatches during development are expected.
Run integration tests before pushing a final version or opening a PR. CI will
fail if the results file is missing, stale (hash mismatch), or records
failures.

**Development workflow summary:**
- Code normally. Unit tests (`pytest`, `npm test`) run locally and in CI.
- Before merging: trigger an integration run in the live session — the
  "Run Tests" button, or `run_and_save()` via the Fusion MCP server — and
  commit the updated results file.
- CI validates the hash — if source files changed since the last manual run,
  the build fails with a clear message telling you to re-run.
- CI merges unit coverage (from pytest-cov) and integration coverage (from the
  stored JSON) into a combined summary table.

### Coverage Capture (How the `coverage` Block is Produced)

The `coverage` block in `fusion_test_results.json` is populated by
`coverage.py` running inside Fusion's Python during the integration test
suite. Three load-bearing pieces:

1. **Vendored coverage package.** `coverage` ships as a local install at
   `code/lib/coverage_pkg/` (gitignored). One-time setup per developer:
   ```bash
   pip install coverage --target=code/lib/coverage_pkg
   ```
   This sidesteps the "how do I pip-install into Fusion's Python" problem
   — Fusion's bundled interpreter never gets touched. The testRunner
   prepends `code/lib/coverage_pkg/` to `sys.path` at runtime so
   `import coverage` resolves to the vendored copy.

2. **Hash exclusion.** Both `<prefix>_fusion_tests/hash_utils.py` and the
   testRunner's inlined `_compute_codebase_hash` exclude
   `code/lib/coverage_pkg/` from the walk. Without this, every coverage
   version bump would invalidate every committed `fusion_test_results.json`.

3. **Bracketed run.** The testRunner constructs
   `coverage.Coverage(data_file=…/.coverage.fusion, source=[<prod packages>],
   omit=[…testRunner, …coverage_pkg])`, calls `cov.start()` immediately
   before `runner.run(suite)`, calls `cov.stop()` + `cov.save()` in a
   `finally` block, then `cov.json_report(outfile=…/fusion_coverage.json)`
   to serialize. The serialized JSON is re-read, totals are pulled out,
   per-file entries are re-keyed by basename, and the resulting block is
   merged into the results dict before `_save_results`.

The `cov_json` is also persisted to disk at
`code/<prefix>_tests/fusion_coverage.json` (gitignored) for inspection,
but the canonical, committed copy is the `coverage` field inside
`fusion_test_results.json`.

**Coverage caveat.** `coverage.py` traces line execution from the moment
`cov.start()` is called. Production modules are imported when Fusion
loads the add-in, hours before "Run Tests" is clicked, so their top-level
`def`/`class` lines never re-execute under tracing and appear missing.
Function bodies invoked by tests are recorded correctly, which is the
signal that matters for behavioral coverage. Treat file-level
percentages as a lower bound, not a literal score.

**Skipping is graceful.** If `code/lib/coverage_pkg/` isn't installed,
`import coverage` raises `ImportError`, the testRunner logs a hint, and
the run proceeds without producing the `coverage` block. The CI merge
step handles a missing block — the Fusion column simply reports 0% for
every file.

**Reference implementations:**
- `~/Personal/FusionAddIns/SetupWizard/code/sw_commands/commandTests/entry.py`
  (the canonical reference)
- `BetterToolLib/code/bettertoollib_commands/testRunner/entry.py`
- The scaffold templates in this repo at
  `templates/scaffold/code/{{addin_prefix}}_commands/testRunner/entry.py`.

### CI Workflow

See `templates/scaffold/.github/workflows/tests.yml` for the complete workflow. It runs
two parallel jobs:

**Python job:**
1. Install pytest + pytest-cov
2. Run unit tests with coverage (`--cov-report=json` for machine-readable
   output). Integration test validation is excluded from this step.
3. Validate integration test results in a separate step: recomputes the
   codebase hash, checks it matches the stored hash in
   `fusion_test_results.json`, and verifies all tests passed. Fails the
   build if results are missing, stale, or record failures.
4. Merge unit + integration coverage into a combined summary table posted to
   the GitHub Actions job summary

**TypeScript job:**
1. `npm ci` (install dependencies)
2. `npm run test:coverage` (Vitest with v8 coverage)
3. `npm run build` (verify the webapp builds cleanly)
4. Post TypeScript coverage to job summary

The combined coverage table in the job summary shows per-file breakdown:

```
| File           | Stmts | Unit   | Fusion | Combined  |
|----------------|-------|--------|--------|-----------|
| my_logic.py    |   200 | 45.0%  | 30.0%  | **75.0%** |
| state.py       |    50 | 90.0%  |  0.0%  | **90.0%** |
| TOTAL          |   250 | 54.0%  | 24.0%  | **78.0%** |
```

This gives visibility into which code is covered by which test layer — unit
tests cover pure logic well, integration tests cover Fusion API interactions
that can't be unit-tested.
