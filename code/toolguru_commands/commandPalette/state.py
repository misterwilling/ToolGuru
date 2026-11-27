"""Pure Python state for the palette command.

No `adsk` imports here — this module is importable under pytest without
mocking. The tally itself lives in the data file, not in memory; this
holds only what the palette needs between events.
"""

from __future__ import annotations

from toolguru_lib.settings import Settings


class AppState:
    def __init__(self) -> None:
        self.last_scan: dict | None = None
        self.selected_cutter: str | None = None   # the cutter whose detail is open
        self.databases_open: bool = False         # the saved-databases panel is showing
        self.similar_open: bool = False           # the similar-cutters screen is showing
        self.notice: str = ''
        self.error: str = ''
        # Folder scan. The queue itself is in the data file; these are only
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

    def serialize(self, counts: dict, tally: list[dict], settings: Settings,
                  job: dict | None = None, detail: dict | None = None,
                  databases: list[dict] | None = None,
                  similar: dict | None = None,
                  library_count: int = 0, unchanged: int = 0,
                  uncredited_time_s: float = 0.0) -> dict:
        """`job` is the folder scan under way (see Store.job), if any.
        `detail` is the open cutter's detail (see detail.build_cutter_detail).
        `databases` is the list of saved databases while its panel is open.
        `similar` is the similar-cutters screen's content while it is open.
        `library_count` is how many cutters are picked for the holding library.
        `unchanged` is how many of the counted folder's programs a scan would skip.
        `uncredited_time_s` is cutting time that could not be given to any tool."""
        proposed = self.proposed_scan
        return {
            'counts': dict(counts),
            'countBy': settings.count_by,
            'stickoutToleranceMm': settings.stickout_tolerance_mm,
            'displayUnit': settings.display_unit,
            'descriptionWidthPx': settings.description_width_px,
            'tally': tally,
            'detail': detail,
            'databases': databases,
            'similar': similar,
            'libraryCount': library_count,
            'uncreditedTimeS': uncredited_time_s,
            'lastScan': dict(self.last_scan) if self.last_scan else None,
            'browser': self.browser,
            'confirmScan': ({'folder': proposed['folder'],
                             'count': len(proposed['files']),
                             'unchanged': unchanged}
                            if proposed else None),
            'scan': dict(job, running=self.scan_running) if job else None,
            'notice': self.notice,
            'error': self.error,
        }


state = AppState()
