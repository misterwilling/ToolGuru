"""What each palette action does to the state and the data file.

No `adsk` imports: the event handler in entry.py reads Fusion and hands the
result here, so every decision is testable under pytest. `base_dir` is the
folder holding the data file; None means the user's home data folder.
"""

from __future__ import annotations

import math
import traceback
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from toolguru_lib import saved
from toolguru_lib import settings as user_settings
from toolguru_lib import store as scan_store
from toolguru_lib.detail import build_cutter_detail
from toolguru_lib.records import (
    DocumentRecord, FileRef, ObservationRecord, ScanError)
from toolguru_lib.store import Store, data_path
from toolguru_lib.tally import build_assembly_tally, build_tally

from .state import AppState

RESET_WORD = 'RESET'
SCANNING = 'Stop the folder scan first.'
NO_OPERATIONS = 'No operations with tools.'

ScanOne = Callable[[str], tuple[DocumentRecord, list[ObservationRecord]]]


def _store(base_dir: Path | None) -> Store:
    return Store(data_path(base_dir))


def view(state: AppState, base_dir: Path | None = None) -> dict:
    """The full state sent to the palette after every action."""
    store = _store(base_dir)
    settings = user_settings.load(base_dir)
    rows = store.observation_rows()
    if settings.count_by == 'assembly':
        tally = build_assembly_tally(rows, settings.stickout_tolerance_mm)
    else:
        tally = build_tally(rows)
    detail = None
    if state.selected_cutter is not None:
        detail = build_cutter_detail(
            rows, state.selected_cutter, settings.stickout_tolerance_mm)
    databases = saved.list_saved(base_dir) if state.databases_open else None
    return state.serialize(
        store.counts(), tally, settings, store.job(), detail, databases)


def refuse_while_scanning(state: AppState) -> bool:
    """True, with a message, when a folder scan is running or still has a
    program open. The scan opens and closes documents and writes to the data
    file, so nothing else may change either underneath it."""
    scanning = state.scan_running or state.scan_busy
    if scanning:
        state.begin_action()
        state.error = SCANNING
    return scanning


def set_count_by(state: AppState, count_by: str,
                 base_dir: Path | None = None) -> None:
    """Count by cutter, or by assembly (cutter + holder + stickout). Only the
    view changes; the stored scans are the same either way."""
    state.begin_action()
    if count_by not in user_settings.COUNT_BY:
        state.error = f'Unknown way to count: {count_by!r}'
        return
    user_settings.save(
        replace(user_settings.load(base_dir), count_by=count_by), base_dir)


def set_display_unit(state: AppState, unit: str,
                     base_dir: Path | None = None) -> None:
    """Show lengths in inches or in millimetres. Only the display changes;
    everything is stored in millimetres."""
    state.begin_action()
    if unit not in user_settings.DISPLAY_UNITS:
        state.error = f'Unknown unit: {unit!r}'
        return
    user_settings.save(
        replace(user_settings.load(base_dir), display_unit=unit), base_dir)


def set_description_width(state: AppState, width_px: object,
                          base_dir: Path | None = None) -> None:
    """Remember how wide the user dragged the tally's description column."""
    state.begin_action()
    if (isinstance(width_px, bool) or not isinstance(width_px, (int, float))
            or not math.isfinite(width_px) or width_px < 1):
        state.error = 'The column width must be a number of pixels, one or more.'
        return
    user_settings.save(
        replace(user_settings.load(base_dir),
                description_width_px=round(width_px)), base_dir)


def set_stickout_tolerance(state: AppState, tolerance_mm: object,
                           base_dir: Path | None = None) -> None:
    """How close two stickouts must be to count as the same assembly."""
    state.begin_action()
    if (isinstance(tolerance_mm, bool)
            or not isinstance(tolerance_mm, (int, float))
            or not math.isfinite(tolerance_mm) or tolerance_mm < 0):
        state.error = 'Stickout tolerance must be a number, zero or more.'
        return
    user_settings.save(
        replace(user_settings.load(base_dir),
                stickout_tolerance_mm=round(float(tolerance_mm), 3)),
        base_dir)


def show_cutter(state: AppState, cutter_key: str) -> None:
    """Open one cutter's detail. It stays open, and follows the data, until
    it is closed or the data is reset."""
    state.begin_action()
    state.selected_cutter = cutter_key


def close_cutter(state: AppState) -> None:
    state.begin_action()
    state.selected_cutter = None


def store_scan(state: AppState, document: DocumentRecord,
               observations: list[ObservationRecord],
               base_dir: Path | None = None) -> None:
    """Record one scanned document."""
    state.begin_action()
    _store(base_dir).replace_document(document, observations)
    state.last_scan = {
        'name': document.name,
        'operations': len(observations),
        'cutters': len({o.cutter_key for o in observations}),
        'operationsWithoutTime': sum(
            1 for o in observations if o.cutting_time_s is None),
    }


def scan_failed(state: AppState, message: str) -> None:
    state.begin_action()
    state.error = message


def reset_data(state: AppState, confirm: str, stamp: str,
               base_dir: Path | None = None) -> None:
    """Back up, then empty, the scan data. Needs the typed word."""
    if refuse_while_scanning(state):
        return
    state.begin_action()
    if confirm != RESET_WORD:
        state.error = f'Type {RESET_WORD} to reset the data.'
        return
    backup = _store(base_dir).backup_and_clear(stamp)
    state.last_scan = None
    state.selected_cutter = None
    state.notice = f'Data reset. Backup saved as {backup.name}.'


# --- Saved databases ----------------------------------------------------------
# Named copies of the data: save what is on screen, load one in its place, or
# add one to it.

LOAD_MODES = ('replace', 'add')


def _programs(count: int) -> str:
    return f'{count} program' if count == 1 else f'{count} programs'


def open_databases(state: AppState) -> None:
    state.begin_action()
    state.databases_open = True


def close_databases(state: AppState) -> None:
    state.begin_action()
    state.databases_open = False


def save_database(state: AppState, name: str, replace: bool,
                  base_dir: Path | None = None) -> None:
    """Save the data on screen under a name. An existing database of that
    name is only replaced when `replace` is set."""
    if refuse_while_scanning(state):
        return
    state.begin_action()
    try:
        entry = saved.save(name, replace, base_dir)
    except saved.SavedError as error:
        state.error = str(error)
        return
    state.notice = (f"Saved as “{entry['name']}”: "
                    f"{_programs(entry['counts']['documents'])}.")


def load_database(state: AppState, name: str, mode: str, stamp: str,
                  base_dir: Path | None = None) -> None:
    """Load a saved database: in place of the data on screen ('replace',
    which backs that data up first) or merged into it ('add')."""
    if refuse_while_scanning(state):
        return
    state.begin_action()
    if mode not in LOAD_MODES:
        state.error = f'Unknown way to load: {mode!r}'
        return
    try:
        if mode == 'replace':
            backup = saved.load_replacing(name, stamp, base_dir)
            state.notice = f'Loaded “{name}”.' + (
                f' What was on screen is kept as {backup.name}.' if backup else '')
        else:
            result = saved.load_adding(name, base_dir)
            state.notice = (
                f"Merged “{name}”: {_programs(result['added'])} added, "
                f"{result['updated']} updated to a later version, "
                f"{result['kept']} already here.")
    except saved.SavedError as error:
        state.error = str(error)
        return
    state.last_scan = None
    state.selected_cutter = None
    state.databases_open = False


# --- Folder scan --------------------------------------------------------------
# Pick a folder, count it, confirm, then one program per step. entry.py turns
# the steps from a custom event so Fusion stays responsive between programs.

def show_folder(state: AppState, listing: dict) -> None:
    """Show one level of the hub in the folder picker."""
    state.begin_action()
    state.browser = listing
    state.proposed_scan = None


def close_folder_picker(state: AppState) -> None:
    state.begin_action()
    state.browser = None
    state.proposed_scan = None


def propose_scan(state: AppState, folder: str, files: list[FileRef]) -> None:
    """A folder has been counted. Nothing is scanned until `start_scan`."""
    if refuse_while_scanning(state):
        return
    state.begin_action()
    state.proposed_scan = None
    if not files:
        state.error = f'No Fusion designs in “{folder}”.'
        return
    state.proposed_scan = {'folder': folder, 'files': list(files)}


def start_scan(state: AppState, base_dir: Path | None = None) -> bool:
    """Queue the counted folder. True when the scan
    loop should start turning."""
    if refuse_while_scanning(state):
        return False
    state.begin_action()
    proposed = state.proposed_scan
    if proposed is None:
        state.error = 'Count a folder before starting a scan.'
        return False
    _store(base_dir).start_job(
        proposed['folder'], proposed['files'])
    state.proposed_scan = None
    state.browser = None
    state.last_scan = None
    state.scan_running = True
    return True


def scan_step(state: AppState, scan_one: ScanOne,
              base_dir: Path | None = None,
              log: Callable[[str], None] = lambda text: None) -> bool:
    """Scan the next waiting program. True when another step should follow.

    `scan_one` takes a hub file id and returns what `extract.scan_document`
    returns. One program that cannot be read never stops the sweep: it is
    marked skipped (not a program) or failed (an error, with its traceback
    sent to `log`) and the scan moves on.
    """
    if not state.scan_running or state.scan_busy:
        # Not running, or a step arrived while a program is still open: the
        # step that has it open carries on from there.
        return False
    store = _store(base_dir)
    waiting = store.next_pending()
    if waiting is not None:
        position, file = waiting
        store.mark_item(position, scan_store.OPENING)
        state.scan_busy = True
        try:
            try:
                document, observations = scan_one(file.file_id)
            finally:
                state.scan_busy = False
        except ScanError as error:
            store.mark_item(position, scan_store.SKIPPED, str(error))
        except Exception as error:
            log(f'Could not scan "{file.name}":\n{traceback.format_exc()}')
            store.mark_item(position, scan_store.FAILED,
                            f'{type(error).__name__}: {error}'[:300])
        else:
            if observations:
                store.replace_document(document, observations)
                store.mark_item(position, scan_store.SCANNED)
            else:
                # Not a program. Drop any earlier scan of it so the tally
                # matches the file as it is now.
                store.remove_document(file.file_id)
                store.mark_item(position, scan_store.SKIPPED, NO_OPERATIONS)
    if store.next_pending() is not None:
        return state.scan_running   # False when stopped while it was open
    state.scan_running = False
    state.begin_action()
    job = store.job() or {'scanned': 0, 'skipped': 0, 'failed': 0}
    state.notice = (
        f"Folder scan finished: {job['scanned']} scanned, "
        f"{job['skipped']} skipped, {job['failed']} failed.")
    return False


def stop_scan(state: AppState) -> None:
    """Pause after the program being read now. The queue is kept."""
    state.begin_action()
    if state.scan_running:
        state.scan_running = False
        state.notice = 'Folder scan paused.'


def resume_scan(state: AppState, base_dir: Path | None = None) -> bool:
    """Carry on with a paused or interrupted folder scan. True when the scan
    loop should start turning."""
    state.begin_action()
    if state.scan_running:
        return False
    store = _store(base_dir)
    if not state.scan_busy:   # a program open right now is not a lost one
        store.fail_interrupted()
    if store.next_pending() is None:
        state.error = 'There is no folder scan to resume.'
        return False
    state.scan_running = True
    return True


def dismiss_scan(state: AppState, base_dir: Path | None = None) -> None:
    """Forget the folder scan's queue and log. What was scanned stays."""
    if refuse_while_scanning(state):
        return
    state.begin_action()
    _store(base_dir).end_job()
