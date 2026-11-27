"""Made-up tools and records for tests. Nothing here comes from a real program."""

from __future__ import annotations

import json
from dataclasses import replace

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
                  date_modified: int = 1_700_086_400, version: int = 3,
                  scanned_at: int | None = None,
                  scan_level: int | None = None) -> DocumentRecord:
    document = DocumentRecord(
        file_id=file_id, version=version, name=f'Program {file_id}',
        project='Project', date_created=date_created,
        date_modified=date_modified, scanned_at=scanned_at)
    return document if scan_level is None else replace(document, scan_level=scan_level)


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


# --- What the Mastercam harvester writes (see toolguru_lib/mastercam.py) ------

def make_harvest_holder(**overrides) -> dict:
    """A made-up two-step holder as Mastercam lists one: spindle end first."""
    holder = {
        'name': 'Test Chuck',
        'library_name': 'Test Holders',
        'overall_height': 3.0,
        'max_diameter': 1.75,
        'segments': [
            {'height': 2.0, 'dia_lower': 1.75, 'dia_upper': 1.75},
            {'height': 1.0, 'dia_lower': 1.0, 'dia_upper': 1.25},
        ],
    }
    holder.update(overrides)
    return holder


def make_harvest_operation(order: int = 1, *, tool: dict | None = None,
                           no_tool: bool = False, slot: int = 3,
                           seconds: float | None = 60.0, **overrides) -> dict:
    """One operation of a made-up part file: a 1/2 inch 3-flute carbide end
    mill, 1.5 in out of the holder, unless told otherwise."""
    harvested_tool = {
        'type': 'EndMill', 'name': '1/2 FLAT ENDMILL', 'number': 7, 'slot': slot,
        'is_metric': False, 'diameter': 0.5, 'corner_radius': 0,
        'flute_length': 1.25, 'shoulder_length': 1.25,
        'length_as_set_in_holder': 1.5, 'shank_diameter': 0.5,
        'shoulder_diameter': 0.5, 'tip_diameter': 0, 'flute_count': 3,
        'tip_angle': 180, 'threads': 0, 'manufacturer_code': 'EX-500',
        'material': 'CARBIDE',
    }
    harvested_tool.update(tool or {})
    operation = {
        'id': order, 'order': order, 'name': f'OP {order}', 'type': 'Contour',
        'type_name': 'Contour (2D)', 'comment': '', 'is_transform': False,
        'machine_group_id': 1, 'toolpath_group': 'Side 1', 'out_of_date': False,
        'posting': True, 'spindle_speed': 8000, 'feed_rate': 40,
        'plunge_rate': 20, 'cycle_time_seconds': seconds,
        'tool': None if no_tool else harvested_tool,
        'holder': None if no_tool else make_harvest_holder(),
        'assembly': None if no_tool else {
            'matched_by': 'slot', 'slot': harvested_tool['slot'], 'stickout': 1.5},
    }
    operation.update(overrides)
    return operation


def make_harvest_transform(order: int, seconds: float, **overrides) -> dict:
    return make_harvest_operation(
        order, no_tool=True, seconds=seconds, is_transform=True, type='4',
        type_name='Transform/Translate', **overrides)


def make_harvest_record(operations: list[dict] | None = None,
                        path: str = r'C:\Parts\Example\Bracket.mcam',
                        **overrides) -> dict:
    """One part file as the harvester records it."""
    operations = [make_harvest_operation()] if operations is None else operations
    slots = {operation['tool']['slot'] for operation in operations
             if operation.get('tool')}
    record = {
        'harvester_version': '3', 'source': 'mastercam', 'path': path,
        'file_name': path.rsplit('\\', 1)[-1],
        'harvested_at': '2026-03-01T10:00:00',
        'disk_modified': '2025-06-15T08:30:00',
        'history': {'count': 2, 'oldest': '2024-01-10T09:00:00',
                    'newest': '2025-06-15T08:30:00'},
        'machine_groups': [{'id': 1, 'name': 'Bracket',
                            'machine_name': r'C:\Machines\Example VMC.mcam-mmd',
                            'machine_description': 'Example VMC'}],
        'operations': operations,
        'tool_assemblies': [
            {'slot': slot, 'stickout': 1.5,
             'tool': {'overall_length': 1.5, 'true_physical_length': 3.0,
                      'manufacturer': 'Example Tooling'}}
            for slot in sorted(slots)],
        'status': 'ok',
    }
    record.update(overrides)
    return record
