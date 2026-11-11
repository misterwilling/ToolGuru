"""Load and save the add-in's config.json file.

Thin wrapper around json + the filesystem — kept in `lib` so every part of
the add-in reaches for the same loader rather than re-implementing it.
"""

from __future__ import annotations

import json
import os


_CONFIG_FILENAME = 'config.json'


def _config_path() -> str:
    # config.json lives at the add-in root, two directories up from this
    # file (<AddInRoot>/code/<prefix>_lib/config_utils.py).
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, '..', '..', _CONFIG_FILENAME))


def load_config() -> dict:
    path = _config_path()
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(config: dict) -> None:
    path = _config_path()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
        f.write('\n')
