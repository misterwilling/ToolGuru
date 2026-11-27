"""Made-up tools and records for tests. Nothing here comes from a real program."""

from __future__ import annotations

import json

from toolguru_lib.records import (
    DocumentRecord, ObservationRecord, build_observation)


def make_holder(**overrides) -> dict:
    """A made-up two-step holder, in the shape Fusion stores one."""
    holder = {
        'type': 'holder',
        'unit': 'inches',
        'description': 'Test Holder',
        'product-id': 'TH-100',
        'vendor': 'Example Tooling',
        'gaugeLength': 3.0,
        'segments': [
            {'height': 1.0, 'lower-diameter': 1.0, 'upper-diameter': 1.25},
            {'height': 2.0, 'lower-diameter': 1.75, 'upper-diameter': 1.75},
        ],
    }
    holder.update(overrides)
    return holder


def make_tool(**overrides) -> dict:
    """A 1/2 inch 3-flute carbide flat end mill, in Fusion's Tool.toJson() shape."""
    geometry = {
        'DC': 0.5, 'NOF': 3, 'LCF': 1.25, 'shoulder-length': 1.25, 'OAL': 3.0,
        'SFDM': 0.5, 'RE': 0, 'TA': 0, 'TP': 0, 'tip-diameter': 0,
        'LB': 1.5, 'assemblyGaugeLength': 4.0, 'CSP': False, 'HAND': True,
    }
    geometry.update(overrides.pop('geometry', {}))
    tool = {
        'type': 'flat end mill',
        'unit': 'inches',
        'BMC': 'carbide',
        'description': '1/2 flat end mill',
        'geometry': geometry,
        'holder': make_holder(),
        'post-process': {'number': 7},
        'vendor': 'Example Tooling',
        'product-id': 'EX-500',
    }
    tool.update(overrides)
    return tool


def make_document(file_id: str = 'file-1', *, date_created: int = 1_700_000_000,
                  date_modified: int = 1_700_086_400) -> DocumentRecord:
    return DocumentRecord(
        file_id=file_id, version=3, name=f'Program {file_id}', project='Project',
        date_created=date_created, date_modified=date_modified)


def make_observation(file_id: str = 'file-1', *, tool: dict | None = None,
                     machine: str = 'Example Mill', operation_name: str = 'Op',
                     cutting_time_s: float | None = 60.0,
                     spindle_rpm: float | None = 8000.0,
                     feed_mm_min: float | None = 1016.0) -> ObservationRecord:
    record = build_observation(
        file_id=file_id, setup_name='Setup1', machine=machine,
        operation_name=operation_name, strategy='adaptive',
        tool_json=json.dumps(tool or make_tool()),
        spindle_speed='8000', feed='40 in/min', preset='Aluminum',
        cutting_time_s=cutting_time_s,
        spindle_rpm=spindle_rpm, feed_mm_min=feed_mm_min)
    assert record is not None
    return record
