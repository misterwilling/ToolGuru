"""Read a Fusion document's CAM data into records.

The only module in `toolguru_lib` that touches the Fusion API. It reads and
never writes: nothing here modifies or saves a document.
"""

from __future__ import annotations

import adsk.cam
import adsk.core

from toolguru_lib.records import (
    DocumentRecord, ObservationRecord, ScanError, build_observation)

# getMachiningTime needs a feed scale (%), a rapid rate (cm/s) and a tool
# change time (s). Only the feed time is used, which does not depend on the
# rapid rate or the tool change time.
_FEED_SCALE_PERCENT = 100.0
_RAPID_CM_PER_S = 10.0
_TOOL_CHANGE_S = 0.0


def cam_product(doc: adsk.core.Document) -> adsk.cam.CAM:
    """The document's CAM product. A document that was never opened in the
    Manufacturing workspace has none, and Fusion raises instead of returning
    nothing."""
    try:
        product = doc.products.itemByProductType('CAMProductType')
    except RuntimeError:
        product = None
    cam = adsk.cam.CAM.cast(product)
    if cam is None:
        raise ScanError('This document has no Manufacturing data to scan.')
    return cam


def document_record(doc: adsk.core.Document) -> DocumentRecord:
    data_file = doc.dataFile
    if data_file is None:
        raise ScanError('Save this document to your hub before scanning it.')
    return DocumentRecord(
        file_id=data_file.id,
        version=data_file.versionNumber,
        name=data_file.name,
        project=data_file.parentProject.name,
        date_created=data_file.dateCreated,
        date_modified=data_file.dateModified,
    )


def read_observations(cam: adsk.cam.CAM, file_id: str) -> list[ObservationRecord]:
    """One record per unsuppressed operation that has an in-scope tool."""
    observations: list[ObservationRecord] = []
    setups = cam.setups
    for s in range(setups.count):
        setup = setups.item(s)
        machine = _machine_name(setup)
        operations = setup.allOperations
        for o in range(operations.count):
            operation = adsk.cam.Operation.cast(operations.item(o))
            if operation is None or operation.isSuppressed:
                continue
            tool = operation.tool
            if tool is None:
                continue
            preset = operation.toolPreset
            record = build_observation(
                file_id=file_id,
                setup_name=setup.name,
                machine=machine,
                operation_name=operation.name,
                strategy=operation.strategy,
                tool_json=tool.toJson(),
                spindle_speed=_expression(operation, 'tool_spindleSpeed'),
                feed=_expression(operation, 'tool_feedCutting'),
                preset=preset.name if preset else '',
                cutting_time_s=_cutting_time(cam, operation),
            )
            if record is not None:
                observations.append(record)
    return observations


def scan_document(doc: adsk.core.Document) -> tuple[DocumentRecord, list[ObservationRecord]]:
    document = document_record(doc)
    return document, read_observations(cam_product(doc), document.file_id)


def _machine_name(setup: adsk.cam.Setup) -> str:
    machine = setup.machine
    if machine is None:
        return ''
    return ' '.join(part for part in (machine.vendor, machine.model) if part)


def _expression(operation: adsk.cam.Operation, name: str) -> str:
    parameter = operation.parameters.itemByName(name)
    return parameter.expression if parameter else ''


def _cutting_time(cam: adsk.cam.CAM, operation: adsk.cam.Operation) -> float | None:
    """Feed time in seconds from the saved toolpath, or None when there is no
    valid toolpath or Fusion cannot calculate it. Never regenerates."""
    if not (operation.hasToolpath and operation.isToolpathValid):
        return None
    try:
        time = cam.getMachiningTime(
            operation, _FEED_SCALE_PERCENT, _RAPID_CM_PER_S, _TOOL_CHANGE_S)
    except RuntimeError:
        return None
    return time.totalFeedTime
