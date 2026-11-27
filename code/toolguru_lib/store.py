"""SQLite storage for scan results.

One file in the user's home directory, never in the add-in folder. It is
emptied only by a reset, which writes a backup copy first.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import closing
from dataclasses import astuple, fields
from pathlib import Path

from toolguru_lib import assembly
from toolguru_lib.records import DocumentRecord, FileRef, ObservationRecord

DATA_FILE = 'toolguru.sqlite'

_DOCUMENT_COLUMNS = [f.name for f in fields(DocumentRecord)]
_OBSERVATION_COLUMNS = [f.name for f in fields(ObservationRecord)]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    file_id TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    project TEXT NOT NULL,
    date_created INTEGER NOT NULL,
    date_modified INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY,
    file_id TEXT NOT NULL REFERENCES documents(file_id) ON DELETE CASCADE,
    setup_name TEXT NOT NULL,
    machine TEXT NOT NULL,
    operation_name TEXT NOT NULL,
    strategy TEXT NOT NULL,
    cutter_key TEXT NOT NULL,
    tool_type TEXT NOT NULL,
    family TEXT NOT NULL,
    description TEXT NOT NULL,
    unit TEXT NOT NULL,
    tool_number INTEGER,
    holder TEXT NOT NULL,
    holder_product_id TEXT NOT NULL DEFAULT '',
    holder_shape TEXT NOT NULL DEFAULT '',
    stickout_mm REAL,
    spindle_speed TEXT NOT NULL,
    feed TEXT NOT NULL,
    preset TEXT NOT NULL,
    cutting_time_s REAL,
    cutter_fields TEXT NOT NULL,
    tool_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS observations_by_cutter ON observations(cutter_key);
CREATE TABLE IF NOT EXISTS scan_job (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    folder TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scan_items (
    position INTEGER PRIMARY KEY,
    file_id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    message TEXT NOT NULL DEFAULT ''
);
"""

# A folder scan's items. 'opening' is set just before Fusion opens the file, so
# a file that takes Fusion down is still marked when the add-in comes back.
PENDING, OPENING, SCANNED, SKIPPED, FAILED = (
    'pending', 'opening', 'scanned', 'skipped', 'failed')
INTERRUPTED = ('The scan stopped while this program was open. '
               'Scan it on its own to check it.')

# Columns added after data files already existed. An older file gains them on
# open and they are filled from each row's stored tool JSON.
_ADDED_COLUMNS = {
    'holder_product_id': "TEXT NOT NULL DEFAULT ''",
    'holder_shape': "TEXT NOT NULL DEFAULT ''",
    'stickout_mm': 'REAL',
}


def _upgrade(conn: sqlite3.Connection) -> None:
    present = {row['name'] for row in
               conn.execute('PRAGMA table_info(observations)')}
    missing = [name for name in _ADDED_COLUMNS if name not in present]
    if not missing:
        return
    for name in missing:
        conn.execute(
            f'ALTER TABLE observations ADD COLUMN {name} {_ADDED_COLUMNS[name]}')
    for row in conn.execute('SELECT id, tool_json FROM observations').fetchall():
        held = assembly.describe(json.loads(row['tool_json']))
        conn.execute(
            'UPDATE observations SET holder_product_id = ?, holder_shape = ?, '
            'stickout_mm = ? WHERE id = ?',
            (held.holder_product_id, held.holder_shape, held.stickout_mm,
             row['id']))


def data_dir() -> Path:
    return Path.home() / '.toolguru'


def data_path(base_dir: Path | None = None) -> Path:
    return (base_dir or data_dir()) / DATA_FILE


class Store:
    """The data file. Opens a connection per call so no file handle is held
    between palette events."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(_SCHEMA)
            _upgrade(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    def replace_document(self, document: DocumentRecord,
                         observations: list[ObservationRecord]) -> None:
        """Store a scan of one document, replacing any earlier scan of it so
        rescanning never doubles the counts."""
        doc_sql = 'INSERT INTO documents ({}) VALUES ({})'.format(
            ', '.join(_DOCUMENT_COLUMNS), ', '.join('?' * len(_DOCUMENT_COLUMNS)))
        obs_sql = 'INSERT INTO observations ({}) VALUES ({})'.format(
            ', '.join(_OBSERVATION_COLUMNS),
            ', '.join('?' * len(_OBSERVATION_COLUMNS)))
        with closing(self._connect()) as conn, conn:
            conn.execute('DELETE FROM documents WHERE file_id = ?',
                         (document.file_id,))
            conn.execute(doc_sql, astuple(document))
            conn.executemany(obs_sql, [astuple(o) for o in observations])

    def remove_document(self, file_id: str) -> None:
        """Forget one document and its observations."""
        with closing(self._connect()) as conn, conn:
            conn.execute('DELETE FROM documents WHERE file_id = ?', (file_id,))

    def counts(self) -> dict[str, int]:
        with closing(self._connect()) as conn:
            documents = conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
            observations, cutters = conn.execute(
                'SELECT COUNT(*), COUNT(DISTINCT cutter_key) FROM observations'
            ).fetchone()
        return {'documents': documents, 'observations': observations,
                'cutters': cutters}

    def observation_rows(self) -> list[dict]:
        """Every observation joined with its document's name and dates."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                'SELECT o.*, d.name AS document_name, d.date_created, '
                'd.date_modified '
                'FROM observations o JOIN documents d USING (file_id) '
                'ORDER BY o.id').fetchall()
        return [dict(row) for row in rows]

    def clear(self) -> None:
        """Remove everything; the file is as it was on first run."""
        with closing(self._connect()) as conn, conn:
            conn.execute('DELETE FROM observations')
            conn.execute('DELETE FROM documents')
            conn.execute('DELETE FROM scan_items')
            conn.execute('DELETE FROM scan_job')

    def backup_and_clear(self, stamp: str) -> Path:
        """Copy the file to `<name>-backup-<stamp>.sqlite`, then clear.
        The copy is written and verified before anything is removed."""
        backup = self.path.with_name(f'{self.path.stem}-backup-{stamp}.sqlite')
        if backup.exists():
            raise FileExistsError(f'Backup already exists: {backup.name}')
        shutil.copy2(self.path, backup)
        if backup.stat().st_size != self.path.stat().st_size:
            raise OSError(f'Backup is incomplete: {backup.name}')
        self.clear()
        return backup

    # --- Folder scan queue --------------------------------------------------
    # One folder scan at a time. It is kept in the file so a scan
    # can carry on after the palette, the add-in or Fusion was closed.

    def start_job(self, folder: str, files: list[FileRef]) -> None:
        """Queue a folder's files, replacing any earlier queue."""
        with closing(self._connect()) as conn, conn:
            conn.execute('DELETE FROM scan_items')
            conn.execute('DELETE FROM scan_job')
            conn.execute('INSERT INTO scan_job (id, folder) VALUES (1, ?)',
                         (folder,))
            conn.executemany(
                'INSERT INTO scan_items (position, file_id, name) VALUES (?, ?, ?)',
                [(i, f.file_id, f.name) for i, f in enumerate(files)])

    def job(self) -> dict | None:
        """Progress of the folder scan, or None when there is none. A file left
        'opening' counts as pending until `fail_interrupted` settles it."""
        with closing(self._connect()) as conn:
            job = conn.execute('SELECT folder FROM scan_job').fetchone()
            if job is None:
                return None
            by_status = dict(conn.execute(
                'SELECT status, COUNT(*) FROM scan_items GROUP BY status'))
            problems = conn.execute(
                'SELECT name, status, message FROM scan_items '
                'WHERE status IN (?, ?) ORDER BY position',
                (SKIPPED, FAILED)).fetchall()
        return {
            'folder': job['folder'],
            'total': sum(by_status.values()),
            'pending': by_status.get(PENDING, 0) + by_status.get(OPENING, 0),
            'scanned': by_status.get(SCANNED, 0),
            'skipped': by_status.get(SKIPPED, 0),
            'failed': by_status.get(FAILED, 0),
            'problems': [dict(row) for row in problems],
        }

    def next_pending(self) -> tuple[int, FileRef] | None:
        """The first file still waiting, with its place in the queue."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                'SELECT position, file_id, name FROM scan_items '
                'WHERE status = ? ORDER BY position LIMIT 1',
                (PENDING,)).fetchone()
        if row is None:
            return None
        return row['position'], FileRef(row['file_id'], row['name'])

    def mark_item(self, position: int, status: str, message: str = '') -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                'UPDATE scan_items SET status = ?, message = ? WHERE position = ?',
                (status, message, position))

    def fail_interrupted(self) -> int:
        """Mark files left 'opening' by a scan that never came back as failed,
        so resuming does not open the same file again. Returns how many."""
        with closing(self._connect()) as conn, conn:
            return conn.execute(
                'UPDATE scan_items SET status = ?, message = ? WHERE status = ?',
                (FAILED, INTERRUPTED, OPENING)).rowcount

    def end_job(self) -> None:
        """Forget the folder scan. Scanned data stays."""
        with closing(self._connect()) as conn, conn:
            conn.execute('DELETE FROM scan_items')
            conn.execute('DELETE FROM scan_job')
