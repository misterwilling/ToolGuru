"""Palette command: opens the React palette and routes React ↔ Python events."""

from __future__ import annotations

import adsk.core
import datetime
import json
import os
import traceback

from toolguru_lib import extract, hub
from toolguru_lib.records import ScanError
from toolguru_lib.fusion360utils import event_utils as futil
from toolguru_lib.fusion360utils import general_utils as gutil

from ..ids import (
    CMD_ID, CMD_NAME, CMD_DESC,
    PALETTE_ID, PALETTE_NAME, PALETTE_WIDTH, PALETTE_HEIGHT,
    SCAN_EVENT_ID,
)
from . import actions
from .state import state

_icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')
_local_handlers: list = []
_scan_event: adsk.core.CustomEvent | None = None
_step_queued = False   # a scan step is waiting in Fusion's event queue


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

    global _scan_event, _step_queued
    app.unregisterCustomEvent(SCAN_EVENT_ID)   # left by a load that never stopped
    _scan_event = app.registerCustomEvent(SCAN_EVENT_ID)
    futil.add_handler(_scan_event, _on_scan_step)
    _step_queued = False


def stop() -> None:
    global _scan_event, _step_queued
    app = adsk.core.Application.get()
    ui = app.userInterface

    # The queue is in the dataset file; the scan can be resumed after a restart.
    state.scan_running = False
    _step_queued = False
    if _scan_event:
        app.unregisterCustomEvent(SCAN_EVENT_ID)
        _scan_event = None

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
    if actions.refuse_while_scanning(state):
        return
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


# --- Folder scan --------------------------------------------------------------

def _handle_browse_folder(data: dict) -> None:
    try:
        listing = hub.browse(adsk.core.Application.get().data,
                             str(data.get('folderId', '')))
    except ScanError as error:
        actions.scan_failed(state, str(error))
        return
    actions.show_folder(state, listing)


def _handle_close_folder_picker(data: dict) -> None:
    actions.close_folder_picker(state)


def _handle_count_folder(data: dict) -> None:
    try:
        folder = hub.find_folder(adsk.core.Application.get().data,
                                 str(data.get('folderId', '')))
    except ScanError as error:
        actions.scan_failed(state, str(error))
        return
    files = hub.collect_programs(folder, bool(data.get('includeSubfolders')))
    actions.propose_scan(state, hub.folder_label(folder), files)


def _handle_start_folder_scan(data: dict) -> None:
    if actions.start_scan(state):
        _queue_scan_step()


def _handle_stop_scan(data: dict) -> None:
    actions.stop_scan(state)


def _handle_resume_scan(data: dict) -> None:
    if actions.resume_scan(state):
        _queue_scan_step()


def _handle_dismiss_scan(data: dict) -> None:
    actions.dismiss_scan(state)


def _queue_scan_step() -> None:
    """Ask Fusion to run one scan step once it is idle. Never queues a second
    step while one is waiting, so Stop then Resume cannot start two loops."""
    global _step_queued
    if not _step_queued:
        _step_queued = True
        adsk.core.Application.get().fireCustomEvent(SCAN_EVENT_ID, '')


def _on_scan_step(args: adsk.core.CustomEventArgs) -> None:
    """Scan one program, show the progress, and queue the next step. Errors
    are logged, never shown in a message box: the scan runs unattended."""
    global _step_queued
    _step_queued = False
    try:
        app = adsk.core.Application.get()
        more = actions.scan_step(
            state, lambda file_id: hub.scan_file(app, file_id),
            log=lambda text: gutil.log(text, force_console=True))
        _push_state()
        if more:
            _queue_scan_step()
    except:
        state.scan_running = False
        gutil.log(f'_on_scan_step error:\n{traceback.format_exc()}',
                  force_console=True)


def _push_state() -> None:
    """Send the current view to the palette, if it is open."""
    palette = adsk.core.Application.get().userInterface.palettes.itemById(PALETTE_ID)
    if palette and palette.isVisible:
        palette.sendInfoToHTML('state', json.dumps(actions.view(state)))


_handlers: dict = {
    'get_state': _handle_get_state,
    'set_dataset': _handle_set_dataset,
    'set_count_by': _handle_set_count_by,
    'set_stickout_tolerance': _handle_set_stickout_tolerance,
    'scan_active': _handle_scan_active,
    'clear_trial': _handle_clear_trial,
    'reset_main': _handle_reset_main,
    'browse_folder': _handle_browse_folder,
    'close_folder_picker': _handle_close_folder_picker,
    'count_folder': _handle_count_folder,
    'start_folder_scan': _handle_start_folder_scan,
    'stop_scan': _handle_stop_scan,
    'resume_scan': _handle_resume_scan,
    'dismiss_scan': _handle_dismiss_scan,
}
