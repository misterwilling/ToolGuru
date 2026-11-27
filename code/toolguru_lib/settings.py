"""The user's ToolGuru settings: one small JSON file beside the data file in
the home data folder. It is not part of the scan data, so a reset leaves
it alone.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from toolguru_lib.store import data_dir

COUNT_BY = ('cutter', 'assembly')
DISPLAY_UNITS = ('in', 'mm')


@dataclass(frozen=True)
class Settings:
    # 'cutter': same cutter geometry is one tool. 'assembly': a different
    # holder or stickout makes a different tool (rotating tool assemblies).
    count_by: str = 'cutter'
    # Stickouts this close together count as the same assembly.
    stickout_tolerance_mm: float = 0.5
    # The unit lengths are shown in. A tool entered in the other unit shows
    # that one too, in brackets. Everything is stored in millimetres.
    display_unit: str = 'in'
    # How wide the tally's description column is, in pixels. The palette
    # sets the limits; this only remembers where the user left it.
    description_width_px: int = 240


def settings_path(base_dir: Path | None = None) -> Path:
    return (base_dir or data_dir()) / 'settings.json'


def load(base_dir: Path | None = None) -> Settings:
    path = settings_path(base_dir)
    if not path.exists():
        return Settings()
    saved = json.loads(path.read_text(encoding='utf-8'))
    defaults = Settings()
    return Settings(
        count_by=saved.get('count_by', defaults.count_by),
        stickout_tolerance_mm=saved.get(
            'stickout_tolerance_mm', defaults.stickout_tolerance_mm),
        display_unit=saved.get('display_unit', defaults.display_unit),
        description_width_px=saved.get(
            'description_width_px', defaults.description_width_px))


def save(settings: Settings, base_dir: Path | None = None) -> None:
    path = settings_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2) + '\n',
                    encoding='utf-8')
