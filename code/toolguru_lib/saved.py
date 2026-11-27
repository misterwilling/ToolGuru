"""Saved databases: named copies of the scan data, kept in a folder beside it.

Saving copies the data file under a name the user types. Loading either
puts a saved copy in place of the data, after backing the data up, or adds
its programs to the data. Nothing here touches Fusion.
"""

from __future__ import annotations

import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from toolguru_lib.store import Store, data_dir, data_path

SAVED_FOLDER = 'saved'
MAX_NAME_LENGTH = 60

# Characters and names Windows will not take in a file name.
_FORBIDDEN = set('<>:"/\\|?*')
_RESERVED = {'con', 'prn', 'aux', 'nul',
             *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}


class SavedError(Exception):
    """A saved database cannot be written or read. The message is written
    for the user."""


def saved_dir(base_dir: Path | None = None) -> Path:
    return (base_dir or data_dir()) / SAVED_FOLDER


def clean_name(name: str) -> str:
    """The name as it will be used: trimmed, and fit to be a file name."""
    name = name.strip()
    if not name:
        raise SavedError('Give the database a name.')
    if len(name) > MAX_NAME_LENGTH:
        raise SavedError(f'Use a name of {MAX_NAME_LENGTH} characters or fewer.')
    if any(ch in _FORBIDDEN or ord(ch) < 32 for ch in name):
        raise SavedError('A name cannot contain any of < > : " / \\ | ? *')
    if name.endswith('.') or name.lower() in _RESERVED:
        raise SavedError('Windows does not allow that name. Choose another.')
    return name


def _existing(name: str, base_dir: Path | None) -> Path | None:
    """The saved file with this name, whatever case it was typed in."""
    folder = saved_dir(base_dir)
    if not folder.is_dir():
        return None
    for path in folder.glob('*.sqlite'):
        if path.stem.lower() == name.lower():
            return path
    return None


def _counts(path: Path) -> dict | None:
    """What a saved file holds, read without changing it. None when it cannot
    be read as a ToolGuru database."""
    try:
        with closing(sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True)) as conn:
            programs = conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
            operations, cutters = conn.execute(
                'SELECT COUNT(*), COUNT(DISTINCT cutter_key) FROM observations'
            ).fetchone()
    except sqlite3.Error:
        return None
    return {'documents': programs, 'observations': operations, 'cutters': cutters}


def list_saved(base_dir: Path | None = None) -> list[dict]:
    """Every saved database, the most recently saved first."""
    folder = saved_dir(base_dir)
    if not folder.is_dir():
        return []
    saved = [{'name': path.stem,
              'saved_at': int(path.stat().st_mtime),
              'counts': _counts(path)}
             for path in folder.glob('*.sqlite')]
    saved.sort(key=lambda entry: (-entry['saved_at'], entry['name'].lower()))
    return saved


def save(name: str, replace: bool = False, base_dir: Path | None = None) -> dict:
    """Save the scan data under `name`. An existing database of that name is
    left alone unless `replace` is set. Returns what was saved."""
    name = clean_name(name)
    data = Store(data_path(base_dir))
    counts = data.counts()
    if counts['documents'] == 0:
        raise SavedError('There is nothing to save yet. Scan a program first.')
    existing = _existing(name, base_dir)
    if existing is not None and not replace:
        raise SavedError(f'“{existing.stem}” is already saved. Choose another name, '
                         'or replace it.')
    folder = saved_dir(base_dir)
    folder.mkdir(parents=True, exist_ok=True)
    if existing is not None:
        existing.unlink()
    target = folder / f'{name}.sqlite'
    shutil.copyfile(data.path, target)
    Store(target).end_job()   # a saved database holds scans, not a half-run folder scan
    return {'name': name, 'counts': counts}


def _saved_file(name: str, base_dir: Path | None) -> Path:
    existing = _existing(name.strip(), base_dir)
    if existing is None:
        raise SavedError(f'“{name}” is no longer among the saved databases.')
    if _counts(existing) is None:
        raise SavedError(f'“{existing.stem}” cannot be read as a ToolGuru database.')
    return existing


def load_replacing(name: str, stamp: str, base_dir: Path | None = None) -> Path | None:
    """Put the saved database in place of the scan data. Data that holds any
    program is backed up first; returns the backup, or None when there was
    nothing to back up."""
    source = _saved_file(name, base_dir)
    data = Store(data_path(base_dir))
    backup = data.backup_and_clear(stamp) if data.counts()['documents'] else None
    shutil.copyfile(source, data.path)
    Store(data.path)   # bring a file from an older ToolGuru up to date
    return backup


def load_adding(name: str, base_dir: Path | None = None) -> dict[str, int]:
    """Add the saved database's programs to the scan data (see
    Store.merge_from). Returns how many were added, updated and kept."""
    source = _saved_file(name, base_dir)
    Store(source)             # bring a file from an older ToolGuru up to date
    return Store(data_path(base_dir)).merge_from(source)
