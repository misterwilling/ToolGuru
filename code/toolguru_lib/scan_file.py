"""Read a scan file: tools read from programs by something other than
ToolGuru's own scan of Fusion documents.

A scan file holds one JSON record per line, one per program. A program that
was read more than once has several lines; the last one counts. Today the
only writer is the Mastercam harvester (see mastercam.py).

Pure Python.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from toolguru_lib import mastercam
from toolguru_lib.records import DocumentRecord, ObservationRecord, ScanError

# What the harvester writes for a file it opened and read.
_READ = 'ok'


@dataclass
class ScanFile:
    """What a scan file holds. `programs` are the files that were read, with
    their observations; one with none is a file without tooled operations.
    `not_read` counts files the writer could not read (not opened, saved by
    a newer version, and so on)."""
    programs: list[tuple[DocumentRecord, list[ObservationRecord]]] = field(
        default_factory=list)
    not_read: int = 0


def read(path: Path) -> ScanFile:
    """Raises ScanError, with a message for the user, when the file cannot
    be read or holds nothing ToolGuru understands."""
    try:
        text = path.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeDecodeError) as error:
        raise ScanError(f'Could not read “{path.name}”: {error}') from error

    latest: dict[str, dict] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if (isinstance(record, dict) and record.get('source') == mastercam.SOURCE
                and isinstance(record.get('path'), str)):
            latest[mastercam.file_id(record['path'])] = record
    if not latest:
        raise ScanError(
            f'“{path.name}” is not a scan file ToolGuru can read. Pick the '
            'harvest.jsonl written by the Mastercam harvester.')

    found = ScanFile()
    for record in latest.values():
        if record.get('status') == _READ:
            found.programs.append(mastercam.convert(record))
        else:
            found.not_read += 1
    return found
