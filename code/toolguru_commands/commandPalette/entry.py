"""Palette command: opens the React palette and routes React ↔ Python events."""

import adsk.core
import json
import os
import traceback

from toolguru_lib.fusion360utils import event_utils as futil
from toolguru_lib.fusion360utils import general_utils as gutil

from ..ids import (
    CMD_ID, CMD_NAME, CMD_DESC,
    PALETTE_ID, PALETTE_NAME, PALETTE_WIDTH, PALETTE_HEIGHT,
    PICK_EVENT_ID,
)
from .state import state

_icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')
_pick_custom_event = None
_local_handlers: list = []


def start(panel: adsk.core.ToolbarPanel) -> None:
    """Register the palette command button in the supplied panel."""
    global _pick_custom_event
    app = adsk.core.Application.get()
    ui = app.userInterface

    # Drop any stale command definition from a previous load before creating.
    existing = ui.commandDefinitions.itemById(CMD_ID)
    if existing:
        existing.deleteMe()

    cmd_def = ui.commandDefinitions.addButtonDefinition(
        CMD_ID, CMD_NAME, CMD_DESC, _icons_dir)
    futil.add_handler(cmd_def.commandCreated, _on_command_created)

    # Add the command to the panel we were handed. Previous add-in authors
    # have been bitten by looking the panel up here independently — doing so
    # gives you two copies of the PANEL_ID constant that can silently drift.
    panel.controls.addCommand(cmd_def)

    # Custom event for geometry picking (selectEntity() blocks — can't be
    # called inside on_html_event because the palette is waiting on return).
    try:
        app.unregisterCustomEvent(PICK_EVENT_ID)
    except:
        pass
    _pick_custom_event = app.registerCustomEvent(PICK_EVENT_ID)
    futil.add_handler(_pick_custom_event, _on_pick_event)


def stop() -> None:
    global _pick_custom_event
    app = adsk.core.Application.get()
    ui = app.userInterface

    cmd_def = ui.commandDefinitions.itemById(CMD_ID)
    if cmd_def:
        cmd_def.deleteMe()

    palette = ui.palettes.itemById(PALETTE_ID)
    if palette:
        palette.deleteMe()

    if _pick_custom_event:
        try:
            app.unregisterCustomEvent(PICK_EVENT_ID)
        except:
            pass
        _pick_custom_event = None


def _on_command_created(args: adsk.core.CommandCreatedEventArgs) -> None:
    app = adsk.core.Application.get()
    ui = app.userInterface

    # Delete-and-recreate avoids serving stale cached HTML on reload.
    existing = ui.palettes.itemById(PALETTE_ID)
    if existing:
        existing.deleteMe()

    palette = ui.palettes.add(
        PALETTE_ID,
        PALETTE_NAME,
        _get_palette_url(),
        True,   # isVisible
        True,   # showCloseButton
        True,   # isResizable
        PALETTE_WIDTH,
        PALETTE_HEIGHT,
        True,   # useNewWebBrowser — REQUIRED for the window.adsk bridge
    )

    futil.add_handler(palette.incomingFromHTML, _on_html_event, local_handlers=_local_handlers)
    futil.add_handler(palette.closed, _on_palette_closed, local_handlers=_local_handlers)

    # Suppress the empty command dialog — we only want the palette.
    args.command.isAutoExecute = True


def _get_palette_url() -> str:
    dist_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', '..', '..', 'webapp', 'dist', 'index.html')
    dist_path = os.path.abspath(dist_path)
    return 'file:///' + dist_path.replace('\\', '/')


def _on_html_event(args: adsk.core.HTMLEventArgs) -> None:
    try:
        action = args.action
        data = json.loads(args.data or '{}')

        if action == 'response':
            # palette.sendInfoToHTML() echoes the JS return value back as
            # action='response'. Always ignore it.
            args.returnData = '{}'
            return

        handler = _handlers.get(action)
        if handler is None:
            args.returnData = json.dumps({'error': f'Unknown action: {action}'})
            return

        result = handler(data)
        args.returnData = json.dumps(result)
    except:
        gutil.log(f'_on_html_event error:\n{traceback.format_exc()}', force_console=True)
        args.returnData = json.dumps({'error': 'Internal error'})


def _on_palette_closed(args: adsk.core.UserInterfaceGeneralEventArgs) -> None:
    _local_handlers.clear()


# --- Action handlers --------------------------------------------------------
# Add new action handlers here and register them in the dispatch table below.

def _handle_get_state(data: dict) -> dict:
    return state.serialize()


def _handle_pick(data: dict) -> dict:
    pick_request = {
        'pick_type': data.get('type', 'face'),
        'prompt': data.get('prompt', 'Select geometry'),
        'slot': data.get('slot', 'default'),
    }
    app = adsk.core.Application.get()
    app.fireCustomEvent(PICK_EVENT_ID, json.dumps(pick_request))
    return state.serialize()


_handlers: dict = {
    'get_state': _handle_get_state,
    'pick': _handle_pick,
}


# --- Pick event handler -----------------------------------------------------

def _on_pick_event(args: adsk.core.CustomEventArgs) -> None:
    try:
        pick_request = json.loads(args.additionalInfo)
        app = adsk.core.Application.get()
        ui = app.userInterface

        prompt = pick_request.get('prompt', 'Select geometry')
        filter_str = _get_filter(pick_request.get('pick_type', 'face'))
        slot = pick_request.get('slot', 'default')

        try:
            selection = ui.selectEntity(prompt, filter_str)
            if selection and selection.entity is not None:
                state.set_selection(slot, selection.entity.entityToken)
        except:
            # User pressed Escape — leave state unchanged.
            pass

        _push_state_to_palette()
    except:
        gutil.log(f'_on_pick_event error:\n{traceback.format_exc()}', force_console=True)


def _get_filter(pick_type: str) -> str:
    return {
        'face': 'Faces',
        'planar_face': 'PlanarFaces',
        'edge': 'Edges',
        'linear_edge': 'LinearEdges',
        'vertex': 'Vertices',
        'body': 'Bodies',
        'occurrence': 'Occurrences',
        'joint_origin': 'JointOrigins',
    }.get(pick_type, 'Faces')


def _push_state_to_palette() -> None:
    app = adsk.core.Application.get()
    palette = app.userInterface.palettes.itemById(PALETTE_ID)
    if palette:
        palette.sendInfoToHTML('state_update', json.dumps(state.serialize()))
