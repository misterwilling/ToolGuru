"""What each palette action does to the state and the dataset files.

No `adsk` imports: the event handler in entry.py reads Fusion and hands the
result here, so every decision is testable under pytest. `base_dir` is the
folder holding the dataset files; None means the user's home data folder.
"""

from __future__ import annotations

import math
import traceback
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from toolguru_lib import settings as user_settings
from toolguru_lib import store as scan_store
from toolguru_lib.records import (
    DocumentRecord, FileRef, ObservationRecord, ScanError)
from toolguru_lib.store import Store, dataset_path
from toolguru_lib.tally import build_assembly_tally, build_tally

from .state import AppState

RESET_WORD = 'RESET'
SCANNING = 'Stop the folder scan first.'
NO_OPERATIONS = 'No operations with tools.'

ScanOne = Callable[[str], tuple[DocumentRecord, list[ObservationRecord]]]


def _store(dataset: str, base_dir: Path | None) -> Store:
    return Store(dataset_path(dataset, base_dir))


def view(state: AppState, base_dir: Path | None = None) -> dict:
    """The full state sent to the palette after every action."""
    store = _store(state.dataset, base_dir)
    settings = user_settings.load(base_dir)
    rows = store.observation_rows()
    if settings.count_by == 'assembly':
        tally = build_assembly_tally(rows, settings.stickout_tolerance_mm)
    else:
        tally = build_tally(rows)
    return state.serialize(store.counts(), tally, settings, store.job())


def refuse_while_scanning(state: AppState) -> bool:
    """True, with a message, when a folder scan is running or still has a
    program open. The scan opens and closes documents and writes to the active
    dataset, so nothing else may change either underneath it."""
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


def set_dataset(state: AppState, dataset: str) -> None:
    if refuse_while_scanning(state):
        return
    state.begin_action()
    state.proposed_scan = None
    try:
        state.set_dataset(dataset)
    except ValueError as error:
        state.error = str(error)


def store_scan(state: AppState, document: DocumentRecord,
               observations: list[ObservationRecord],
               base_dir: Path | None = None) -> None:
    """Record one scanned document in the active dataset."""
    state.begin_action()
    _store(state.dataset, base_dir).replace_document(document, observations)
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


def clear_trial(state: AppState, base_dir: Path | None = None) -> None:
    """Empty the Trial dataset. Never touches Main, whichever is active."""
    if refuse_while_scanning(state):
        return
    state.begin_action()
    _store('trial', base_dir).clear()
    if state.dataset == 'trial':
        state.last_scan = None
    state.notice = 'Trial data cleared.'


def reset_main(state: AppState, confirm: str, stamp: str,
               base_dir: Path | None = None) -> None:
    """Back up, then empty, the Main dataset. Needs the typed word."""
    if refuse_while_scanning(state):
        return
    state.begin_action()
    if confirm != RESET_WORD:
        state.error = f'Type {RESET_WORD} to reset the main data.'
        return
    backup = _store('main', base_dir).backup_and_clear(stamp)
    if state.dataset == 'main':
        state.last_scan = None
    state.notice = f'Main data reset. Backup saved as {backup.name}.'


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
    """Queue the counted folder in the active dataset. True when the scan
    loop should start turning."""
    if refuse_while_scanning(state):
        return False
    state.begin_action()
    proposed = state.proposed_scan
    if proposed is None:
        state.error = 'Count a folder before starting a scan.'
        return False
    _store(state.dataset, base_dir).start_job(
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
    store = _store(state.dataset, base_dir)
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
    store = _store(state.dataset, base_dir)
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
    _store(state.dataset, base_dir).end_job()
