"""SQLite storage for scan results.

Two datasets, each its own file in the user's home directory and never in
the add-in folder: 'trial' for small test scans (cleared with one call) and
'main' for the real sweep (reset only after a backup copy is written).
"""

from __future__ import annotations

import shutil
import sqlite3
from contextlib import closing
from dataclasses import astuple, fields
from pathlib import Path

from toolguru_lib.records import DocumentRecord, ObservationRecord

DATASETS = ('trial', 'main')

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
    spindle_speed TEXT NOT NULL,
    feed TEXT NOT NULL,
    preset TEXT NOT NULL,
    cutting_time_s REAL,
    cutter_fields TEXT NOT NULL,
    tool_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS observations_by_cutter ON observations(cutter_key);
"""


def data_dir() -> Path:
    return Path.home() / '.toolguru'


def dataset_path(dataset: str, base_dir: Path | None = None) -> Path:
    if dataset not in DATASETS:
        raise ValueError(f'Unknown dataset: {dataset!r}')
    return (base_dir or data_dir()) / f'{dataset}.sqlite'


class Store:
    """One dataset file. Opens a connection per call so no file handle is held
    between palette events."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(_SCHEMA)

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

    def counts(self) -> dict[str, int]:
        with closing(self._connect()) as conn:
            documents = conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
            observations, cutters = conn.execute(
                'SELECT COUNT(*), COUNT(DISTINCT cutter_key) FROM observations'
            ).fetchone()
        return {'documents': documents, 'observations': observations,
                'cutters': cutters}

    def observation_rows(self) -> list[dict]:
        """Every observation joined with its document's dates."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                'SELECT o.*, d.date_created, d.date_modified '
                'FROM observations o JOIN documents d USING (file_id) '
                'ORDER BY o.id').fetchall()
        return [dict(row) for row in rows]

    def clear(self) -> None:
        """Remove everything; the dataset is as it was on first run."""
        with closing(self._connect()) as conn, conn:
            conn.execute('DELETE FROM observations')
            conn.execute('DELETE FROM documents')

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
