"""Pure Python state for the palette command.

No `adsk` imports here — this module is importable under pytest without
mocking. The tally itself lives in the dataset file, not in memory; this
holds only what the palette needs between events.
"""

from __future__ import annotations

from toolguru_lib.settings import Settings
from toolguru_lib.store import DATASETS


class AppState:
    def __init__(self) -> None:
        self.dataset: str = 'trial'   # the add-in always starts in Trial
        self.last_scan: dict | None = None
        self.notice: str = ''
        self.error: str = ''
        # Folder scan. The queue itself is in the dataset file; these are only
        # what the palette is showing and whether the scan loop is turning.
        self.browser: dict | None = None        # the folder picker's listing
        self.proposed_scan: dict | None = None  # counted, waiting for a yes
        self.scan_running: bool = False
        # True while one program is open and being read. Fusion handles clicks
        # while it opens a document, so an action can arrive in the middle.
        self.scan_busy: bool = False

    def begin_action(self) -> None:
        """Messages describe the latest action only."""
        self.notice = ''
        self.error = ''

    def set_dataset(self, dataset: str) -> None:
        if dataset not in DATASETS:
            raise ValueError(f'Unknown dataset: {dataset!r}')
        if dataset != self.dataset:
            self.last_scan = None
        self.dataset = dataset

    def serialize(self, counts: dict, tally: list[dict], settings: Settings,
                  job: dict | None = None) -> dict:
        """`job` is the dataset's folder scan (see Store.job), if any."""
        proposed = self.proposed_scan
        return {
            'dataset': self.dataset,
            'counts': dict(counts),
            'countBy': settings.count_by,
            'stickoutToleranceMm': settings.stickout_tolerance_mm,
            'tally': tally,
            'lastScan': dict(self.last_scan) if self.last_scan else None,
            'browser': self.browser,
            'confirmScan': ({'folder': proposed['folder'],
                             'count': len(proposed['files'])}
                            if proposed else None),
            'scan': dict(job, running=self.scan_running) if job else None,
            'notice': self.notice,
            'error': self.error,
        }


state = AppState()
