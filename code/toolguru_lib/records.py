"""The two kinds of record a scan produces. Pure data, no Fusion types."""

from __future__ import annotations

import json
from dataclasses import dataclass

from toolguru_lib import assembly, cutter


# What a scan records. Raise it when a scan starts recording something new,
# so programs scanned before are read again even though they have not changed.
#   1: tools, holders, expressions and cutting time
#   2: spindle speed and feed as numbers
SCAN_LEVEL = 2


class ScanError(Exception):
    """A document cannot be scanned. The message is written for the user."""


@dataclass(frozen=True)
class FileRef:
    """A hub file waiting to be scanned. `version` is its latest version in
    the hub; 0 when that is not known."""
    file_id: str
    name: str
    version: int = 0


@dataclass(frozen=True)
class DocumentRecord:
    file_id: str
    version: int
    name: str
    project: str
    date_created: int   # UNIX epoch seconds
    date_modified: int  # UNIX epoch seconds
    scanned_at: int | None = None   # when it was read; None for older scans
    scan_level: int = SCAN_LEVEL    # what that scan recorded
    # Cutting time in the program that could not be given to any tool: a
    # Mastercam transform whose repeated operations are not known.
    uncredited_time_s: float | None = None


@dataclass(frozen=True)
class ObservationRecord:
    """One operation's use of one tool."""
    file_id: str
    setup_name: str
    machine: str
    operation_name: str
    strategy: str
    cutter_key: str
    tool_type: str
    family: str
    description: str
    unit: str
    tool_number: int | None
    holder: str
    holder_product_id: str    # normalized; see assembly.describe
    holder_shape: str
    stickout_mm: float | None
    spindle_speed: str        # as typed in the program: a number or a formula
    feed: str
    spindle_rpm: float | None   # what Fusion worked it out to; None when not set
    feed_mm_min: float | None
    preset: str
    cutting_time_s: float | None
    cutter_fields: str  # JSON of the normalized cutter geometry
    tool_json: str      # raw Tool.toJson(), kept so rules can change later


def _set_number(value: float | None) -> float | None:
    """A speed or feed as stored. Zero is what Fusion holds for one that was
    never set, so it is stored as nothing rather than as a speed of zero."""
    if value is None or value <= 0:
        return None
    return round(value, 3)


def build_observation(*, file_id: str, setup_name: str, machine: str,
                      operation_name: str, strategy: str, tool_json: str,
                      spindle_speed: str, feed: str, preset: str,
                      cutting_time_s: float | None,
                      spindle_rpm: float | None = None,
                      feed_mm_min: float | None = None) -> ObservationRecord | None:
    """Turn what was read from one operation into a record.

    Returns None when the tool's type is out of scope (see cutter.family_of).
    """
    tool = json.loads(tool_json)
    identity = cutter.identify(tool)
    if identity is None:
        return None
    number = (tool.get('post-process') or {}).get('number')
    held = assembly.describe(tool)
    return ObservationRecord(
        file_id=file_id,
        setup_name=setup_name,
        machine=machine,
        operation_name=operation_name,
        strategy=strategy,
        cutter_key=identity.key,
        tool_type=identity.tool_type,
        family=identity.family,
        description=str(tool.get('description') or ''),
        unit=str(tool.get('unit') or ''),
        tool_number=number if isinstance(number, int) else None,
        holder=held.holder_label,
        holder_product_id=held.holder_product_id,
        holder_shape=held.holder_shape,
        stickout_mm=held.stickout_mm,
        spindle_speed=spindle_speed,
        feed=feed,
        spindle_rpm=_set_number(spindle_rpm),
        feed_mm_min=_set_number(feed_mm_min),
        preset=preset,
        cutting_time_s=cutting_time_s,
        cutter_fields=json.dumps(identity.fields, sort_keys=True),
        tool_json=tool_json,
    )
