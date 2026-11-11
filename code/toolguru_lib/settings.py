"""The user's ToolGuru settings: one small JSON file beside the datasets in
the home data folder. It belongs to neither dataset, so clearing Trial or
resetting Main leaves it alone.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from toolguru_lib.store import data_dir

COUNT_BY = ('cutter', 'assembly')


@dataclass(frozen=True)
class Settings:
    # 'cutter': same cutter geometry is one tool. 'assembly': a different
    # holder or stickout makes a different tool (rotating tool assemblies).
    count_by: str = 'cutter'
    # Stickouts this close together count as the same assembly.
    stickout_tolerance_mm: float = 0.5


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
            'stickout_tolerance_mm', defaults.stickout_tolerance_mm))


def save(settings: Settings, base_dir: Path | None = None) -> None:
    path = settings_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2) + '\n',
                    encoding='utf-8')
