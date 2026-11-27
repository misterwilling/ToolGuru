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

from toolguru_lib import holding, saved
from toolguru_lib import settings as user_settings
from toolguru_lib import similar
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
    scanned = store.observation_rows()
    merged = store.merged_cutters()
    rows = similar.apply_merges(scanned, merged)
    if settings.count_by == 'assembly':
        tally = build_assembly_tally(rows, settings.stickout_tolerance_mm)
    else:
        tally = build_tally(rows)
    library = holding.entries(
        rows, store.library_picks(), settings.stickout_tolerance_mm)
    for line in tally:
        written = library.get(line['cutter_key'])
        # Counting by assembly, only the assembly that will be written is ticked.
        line['in_library'] = written is not None and (
            'assembly_key' not in line
            or line['assembly_key'] == written['assembly_key'])
    detail = None
    if state.selected_cutter is not None:
        # A cutter that has since been merged is found under its group's line.
        shown = similar.shown_key(scanned, merged, state.selected_cutter)
        detail = build_cutter_detail(
            rows, shown, settings.stickout_tolerance_mm)
        if detail is not None:
            detail['library'] = _detail_library(
                rows, store.library_picks(), shown, library,
                settings.stickout_tolerance_mm)
    databases = saved.list_saved(base_dir) if state.databases_open else None
    similar_view = None
    if state.similar_open:
        similar_view = {
            'suggestions': similar.suggest(scanned, merged, store.not_similar()),
            'merged': similar.merged_groups(scanned, merged),
        }
    counts = store.counts()
    counts['cutters'] = len({row['cutter_key'] for row in rows})   # after merging
    return state.serialize(
        counts, tally, settings, store.job(), detail, databases, similar_view,
        len(library))


def _detail_library(rows: list[dict], picks: dict[str, str | None],
                    cutter_key: str, library: dict[str, dict],
                    tolerance_mm: float) -> dict:
    """The open cutter's place in the holding library: whether it is picked,
    the assembly chosen for it (None for "the usual one"), and the assembly
    it is, or would be, written in."""
    keys = sorted(holding.line_keys(rows, cutter_key) & picks.keys())
    written = library.get(cutter_key) or holding.entry(
        [row for row in rows if row['cutter_key'] == cutter_key], None,
        tolerance_mm)
    return {
        'picked': bool(keys),
        'choice': next((picks[key] for key in keys if picks[key] is not None), None),
        'assembly_key': written['assembly_key'],
    }


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
    state.similar_open = False
    state.notice = f'Data reset. Backup saved as {backup.name}.'


# --- Similar cutters ----------------------------------------------------------
# Cutters with the same cutting end are suggested; the user says whether they
# are one tool. Only the decision is stored.

def open_similar(state: AppState) -> None:
    state.begin_action()
    state.similar_open = True
    state.selected_cutter = None


def close_similar(state: AppState) -> None:
    state.begin_action()
    state.similar_open = False


def merge_cutters(state: AppState, cutter_keys: object,
                  base_dir: Path | None = None) -> None:
    """Treat a suggested group of cutters as one tool."""
    if refuse_while_scanning(state):
        return
    state.begin_action()
    if (not isinstance(cutter_keys, list) or len(set(cutter_keys)) < 2
            or not all(isinstance(key, str) and key for key in cutter_keys)):
        state.error = 'Pick two or more cutters to treat as the same.'
        return
    _store(base_dir).merge_cutters(cutter_keys)
    state.notice = (f'{len(set(cutter_keys))} cutters are now counted as one. '
                    'Split them again from this screen at any time.')


def split_cutters(state: AppState, cutter_key: str,
                  base_dir: Path | None = None) -> None:
    """Undo a merge: its cutters are counted apart again."""
    if refuse_while_scanning(state):
        return
    state.begin_action()
    count = _store(base_dir).split_cutters(cutter_key)
    if count == 0:
        state.error = 'That cutter is not merged with any other.'
        return
    state.selected_cutter = None
    state.notice = f'Split: {count} cutters are counted apart again.'


def not_similar(state: AppState, signature: str,
                base_dir: Path | None = None) -> None:
    """Stop suggesting one group. It comes back only if a new cutter joins it."""
    if refuse_while_scanning(state):
        return
    state.begin_action()
    if not signature:
        state.error = 'No suggestion was named.'
        return
    _store(base_dir).mark_not_similar(signature)


# --- Holding library ------------------------------------------------------------
# The user ticks cutters; "Write holding library" puts them in a tool library
# in Fusion. Only the picks are stored here; entry.py does the writing.

def pick_for_library(state: AppState, cutter_key: str, picked: bool,
                     assembly_key: str | None = None,
                     base_dir: Path | None = None) -> None:
    """Tick or untick a tally line for the holding library. `assembly_key`
    names the holder and stickout to write it in; None means the usual one."""
    if refuse_while_scanning(state):
        return
    state.begin_action()
    store = _store(base_dir)
    rows = similar.apply_merges(store.observation_rows(), store.merged_cutters())
    keys = sorted(holding.line_keys(rows, cutter_key))
    if not keys:
        state.error = 'That cutter is not in the data.'
        return
    if not picked:
        store.unpick_for_library(keys)
        return
    tolerance = user_settings.load(base_dir).stickout_tolerance_mm
    if (assembly_key is not None
            and assembly_key not in holding.assembly_keys(rows, cutter_key, tolerance)):
        state.error = 'That holder and stickout is no longer one of this cutter\'s.'
        return
    store.pick_for_library(keys, assembly_key)


def library_tools(base_dir: Path | None = None) -> list[str]:
    """The picked cutters as tool records, ready to write to Fusion."""
    store = _store(base_dir)
    rows = similar.apply_merges(store.observation_rows(), store.merged_cutters())
    tolerance = user_settings.load(base_dir).stickout_tolerance_mm
    return [entry['tool_json'] for entry in
            holding.entries(rows, store.library_picks(), tolerance).values()]


def library_written(state: AppState, asked: int, written: int) -> None:
    state.begin_action()
    if written != asked:
        state.error = (f'Fusion wrote {written} of {asked} tools to '
                       f'“{holding.LIBRARY_NAME}”. See View → Text Commands.')
        return
    tools = 'tool' if written == 1 else 'tools'
    state.notice = (f'Wrote {written} {tools} to “{holding.LIBRARY_NAME}” in '
                    'your Local tool libraries. It replaces the one written before.')


def library_failed(state: AppState, message: str) -> None:
    state.begin_action()
    state.error = message


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
    state.similar_open = False


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
