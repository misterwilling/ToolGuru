"""Palette command: opens the React palette and routes React ↔ Python events."""

import adsk.core
import datetime
import json
import os
import traceback

from toolguru_lib import extract
from toolguru_lib.fusion360utils import event_utils as futil
from toolguru_lib.fusion360utils import general_utils as gutil

from ..ids import (
    CMD_ID, CMD_NAME, CMD_DESC,
    PALETTE_ID, PALETTE_NAME, PALETTE_WIDTH, PALETTE_HEIGHT,
)
from . import actions
from .state import state

_icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')
_local_handlers: list = []


def start(panel: adsk.core.ToolbarPanel) -> None:
    """Register the palette command button in the supplied panel."""
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


def stop() -> None:
    app = adsk.core.Application.get()
    ui = app.userInterface

    cmd_def = ui.commandDefinitions.itemById(CMD_ID)
    if cmd_def:
        cmd_def.deleteMe()

    palette = ui.palettes.itemById(PALETTE_ID)
    if palette:
        palette.deleteMe()


def _on_command_created(args: adsk.core.CommandCreatedEventArgs) -> None:
    app = adsk.core.Application.get()
    ui = app.userInterface

    # Delete-and-recreate avoids serving stale cached HTML on reload.
    existing = ui.palettes.itemById(PALETTE_ID)
    if existing:
        existing.deleteMe()

    # A freshly opened palette should not show a message from an earlier one.
    state.begin_action()

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

        handler(data)
        args.returnData = json.dumps(actions.view(state))
    except:
        gutil.log(f'_on_html_event error:\n{traceback.format_exc()}', force_console=True)
        args.returnData = json.dumps({'error': 'Internal error'})


def _on_palette_closed(args: adsk.core.UserInterfaceGeneralEventArgs) -> None:
    _local_handlers.clear()


# --- Action handlers --------------------------------------------------------
# Each handler changes state through actions.py; the caller then returns the
# full view. Only the Fusion reads live here.

def _handle_get_state(data: dict) -> None:
    pass


def _handle_set_dataset(data: dict) -> None:
    actions.set_dataset(state, str(data.get('dataset', '')))


def _handle_set_count_by(data: dict) -> None:
    actions.set_count_by(state, str(data.get('countBy', '')))


def _handle_set_stickout_tolerance(data: dict) -> None:
    actions.set_stickout_tolerance(state, data.get('toleranceMm'))


def _handle_scan_active(data: dict) -> None:
    doc = adsk.core.Application.get().activeDocument
    if doc is None:
        actions.scan_failed(state, 'Open a document to scan.')
        return
    try:
        document, observations = extract.scan_document(doc)
    except extract.ScanError as error:
        actions.scan_failed(state, str(error))
        return
    actions.store_scan(state, document, observations)


def _handle_clear_trial(data: dict) -> None:
    actions.clear_trial(state)


def _handle_reset_main(data: dict) -> None:
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    actions.reset_main(state, str(data.get('confirm', '')), stamp)


_handlers: dict = {
    'get_state': _handle_get_state,
    'set_dataset': _handle_set_dataset,
    'set_count_by': _handle_set_count_by,
    'set_stickout_tolerance': _handle_set_stickout_tolerance,
    'scan_active': _handle_scan_active,
    'clear_trial': _handle_clear_trial,
    'reset_main': _handle_reset_main,
}
