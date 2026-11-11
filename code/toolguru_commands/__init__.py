"""Command registry and toolbar tab/panel lifecycle.

`start()` registers the add-in's tab+panel in the chosen workspace and then
starts each individual command. `stop()` reverses that, in tab-scoped order
so the lookups actually find the objects we created.

The `testRunner` command is included unconditionally; it self-gates on
`config.json: enable_tests` inside its own `start()`, registering the
"Run Tests" button only when tests are enabled. That keeps the registry
list flat (no per-command branching here) while still respecting the
production / test split.
"""

import adsk.core

from .commandPalette import entry as commandPalette
from .testRunner import entry as testRunner
from .ids import (
    WORKSPACE_ID,
    TAB_ID, TAB_NAME,
    PANEL_ID, PANEL_NAME,
)

commands = [commandPalette, testRunner]


def start():
    app = adsk.core.Application.get()
    ui = app.userInterface

    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    if workspace is None:
        # Target workspace isn't loaded yet. This happens for workspaces that
        # only register once a matching document type is opened (Drawings,
        # Electronics). Log and bail instead of crashing — user can restart
        # the add-in once the relevant workspace is active.
        return

    # Idempotent: re-use an existing tab/panel if a previous stop() didn't
    # clean up, otherwise create fresh. This keeps start() safe to re-run
    # during a hot reload.
    toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID) \
        or workspace.toolbarTabs.add(TAB_ID, TAB_NAME)
    panel = toolbar_tab.toolbarPanels.itemById(PANEL_ID) \
        or toolbar_tab.toolbarPanels.add(PANEL_ID, PANEL_NAME)

    for command in commands:
        command.start(panel)


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
        # Look up the panel through the tab we added it to — NOT through
        # workspace.toolbarPanels (which only holds tab-less top-level
        # panels and will always return None here).
        tab = workspace.toolbarTabs.itemById(TAB_ID)
        if tab:
            panel = tab.toolbarPanels.itemById(PANEL_ID)
            if panel:
                panel.deleteMe()
            tab.deleteMe()
    except:
        pass
