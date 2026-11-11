"""What each palette action does to the state and the dataset files.

No `adsk` imports: the event handler in entry.py reads Fusion and hands the
result here, so every decision is testable under pytest. `base_dir` is the
folder holding the dataset files; None means the user's home data folder.
"""

from __future__ import annotations

from pathlib import Path

from toolguru_lib.records import DocumentRecord, ObservationRecord
from toolguru_lib.store import Store, dataset_path
from toolguru_lib.tally import build_tally

from .state import AppState

RESET_WORD = 'RESET'


def _store(dataset: str, base_dir: Path | None) -> Store:
    return Store(dataset_path(dataset, base_dir))


def view(state: AppState, base_dir: Path | None = None) -> dict:
    """The full state sent to the palette after every action."""
    store = _store(state.dataset, base_dir)
    return state.serialize(store.counts(), build_tally(store.observation_rows()))


def set_dataset(state: AppState, dataset: str) -> None:
    state.begin_action()
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
    state.begin_action()
    _store('trial', base_dir).clear()
    if state.dataset == 'trial':
        state.last_scan = None
    state.notice = 'Trial data cleared.'


def reset_main(state: AppState, confirm: str, stamp: str,
               base_dir: Path | None = None) -> None:
    """Back up, then empty, the Main dataset. Needs the typed word."""
    state.begin_action()
    if confirm != RESET_WORD:
        state.error = f'Type {RESET_WORD} to reset the main data.'
        return
    backup = _store('main', base_dir).backup_and_clear(stamp)
    if state.dataset == 'main':
        state.last_scan = None
    state.notice = f'Main data reset. Backup saved as {backup.name}.'
