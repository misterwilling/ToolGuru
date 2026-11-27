"""Find programs in the hub and open them for scanning.

Reads the hub and never writes to it: a program is opened, read and closed
without saving, and a document that was already open is left open.
"""

from __future__ import annotations

import adsk.core

from toolguru_lib import extract
from toolguru_lib.records import (
    DocumentRecord, FileRef, ObservationRecord, ScanError)

# Only Fusion designs can hold Manufacturing data.
PROGRAM_EXTENSION = 'f3d'
_SEPARATOR = ' / '


def browse(data: adsk.core.Data, folder_id: str) -> dict:
    """One level of the hub for the folder picker. An empty id lists the
    projects, each standing for its top folder."""
    if not folder_id:
        projects = data.dataProjects
        entries = []
        for i in range(projects.count):
            project = projects.item(i)
            entries.append({'id': project.rootFolder.id, 'name': project.name})
        return {'folderId': '', 'path': [], 'folders': entries, 'programs': 0}

    folder = find_folder(data, folder_id)
    folders = folder.dataFolders
    entries = []
    for i in range(folders.count):
        child = folders.item(i)
        entries.append({'id': child.id, 'name': child.name})
    return {
        'folderId': folder.id,
        'path': _path(folder),
        'folders': entries,
        'programs': len(_programs_in(folder)),
    }


def find_folder(data: adsk.core.Data, folder_id: str) -> adsk.core.DataFolder:
    # Fusion raises for an id it cannot find; it does not return nothing.
    try:
        folder = data.findFolderById(folder_id)
    except RuntimeError:
        folder = None
    if folder is None:
        raise ScanError('That folder is no longer in your hub.')
    return folder


def folder_label(folder: adsk.core.DataFolder) -> str:
    """'Project / Folder / Subfolder'."""
    return _SEPARATOR.join(entry['name'] for entry in _path(folder))


def collect_programs(folder: adsk.core.DataFolder,
                     include_subfolders: bool) -> list[FileRef]:
    """The Fusion designs in a folder, and below it when asked."""
    files = _programs_in(folder)
    if include_subfolders:
        folders = folder.dataFolders
        for i in range(folders.count):
            files.extend(collect_programs(folders.item(i), True))
    return files


def scan_file(app: adsk.core.Application, file_id: str
              ) -> tuple[DocumentRecord, list[ObservationRecord]]:
    """Open one hub file, read its CAM data and close it without saving.
    A file the user already has open is read where it is and left open."""
    try:
        data_file = app.data.findFileById(file_id)
    except RuntimeError:   # raised for an id that is not in the hub
        data_file = None
    if data_file is None:
        raise ScanError('This file is no longer in your hub.')
    doc = _open_document(app.documents, file_id)
    opened_here = doc is None
    if opened_here:
        doc = app.documents.open(data_file, True)
    try:
        return extract.scan_document(doc)
    finally:
        if opened_here:
            doc.close(False)   # never save


def _programs_in(folder: adsk.core.DataFolder) -> list[FileRef]:
    files = folder.dataFiles
    found = []
    for i in range(files.count):
        data_file = files.item(i)
        if data_file.fileExtension == PROGRAM_EXTENSION:
            found.append(FileRef(data_file.id, data_file.name,
                                 data_file.versionNumber))
    return found


def _path(folder: adsk.core.DataFolder) -> list[dict]:
    """From the project down to this folder. A project's top folder goes by
    the project's name."""
    entries = []
    while not folder.isRoot:
        entries.append({'id': folder.id, 'name': folder.name})
        folder = folder.parentFolder
    entries.append({'id': folder.id, 'name': folder.parentProject.name})
    entries.reverse()
    return entries


def _open_document(documents: adsk.core.Documents,
                   file_id: str) -> adsk.core.Document | None:
    for i in range(documents.count):
        doc = documents.item(i)
        data_file = doc.dataFile
        if data_file is not None and data_file.id == file_id:
            return doc
    return None
