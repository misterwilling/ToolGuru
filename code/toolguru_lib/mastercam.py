"""Turn what the Mastercam harvester read from one part file into ToolGuru's
records.

The harvester is a separate Mastercam add-in. It writes one JSON record per
part file; this module reads such a record and never touches Mastercam.

Each tool is rewritten with the names Fusion uses for a tool's type and
dimensions, so the tally, the detail and the similar-cutters screen treat it
like any other. It carries `source: mastercam`, which is part of the
cutter's identity: a Mastercam cutter is never counted together with a
Fusion one, even when the geometry is the same (see cutter.identify).

These records are for ToolGuru's own use. They are NOT proven to be tools
Fusion will accept, and Fusion can crash on a tool record it does not like,
so they are never written to a Fusion tool library (see holding.py). That
is by design: Mastercam tools reach Fusion through a separate tool.

Pure Python.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import PureWindowsPath

from toolguru_lib.records import (
    DocumentRecord, ObservationRecord, build_observation)

SOURCE = 'mastercam'

_MM_PER_INCH = 25.4

# Mastercam's tool type names, as Fusion names the same tools. A type that is
# not listed keeps Mastercam's name in words and lands in the 'other' family.
_TYPES = {
    'EndMill': 'flat end mill',
    'EndMillSphere': 'ball end mill',
    'EndMillBullnose': 'bull nose end mill',
    'ChamferMill': 'chamfer mill',
    'FaceMill': 'face mill',
    'SlotMill': 'slot mill',
    'RadiusMill': 'radius mill',
    'DovetailMill': 'dovetail mill',
    'TaperedMill': 'tapered mill',
    'LollipopMill': 'lollipop mill',
    'Drill': 'drill',
    'CenterDrill': 'center drill',
    'SpotDrill': 'spot drill',
    'CounterBore': 'counter bore',
    'CounterSink': 'counter sink',
    'Reamer': 'reamer',
    'Bore': 'boring bar',
    'TapRight': 'tap right hand',
    'TapLeft': 'tap left hand',
    'ThreadMill': 'thread mill',
}

# Where Fusion keeps the angle Mastercam calls the tip angle.
_POINT_ANGLE_TYPES = {'drill', 'center drill', 'spot drill', 'counter sink'}
_TAPER_ANGLE_TYPES = {'chamfer mill', 'tapered mill', 'dovetail mill'}
_THREADED_TYPES = {'thread mill', 'tap right hand', 'tap left hand'}
# Fusion's "tip diameter" for tools that have no tip of their own.
_TIP_IS_DIAMETER = {'flat end mill', 'slot mill', 'thread mill', 'dovetail mill'}
_TIP_INSIDE_RADIUS = {'bull nose end mill', 'radius mill'}

# How exactly a transform's time must be a whole multiple of the operations
# it repeats. The real ones agree to a billionth of a second; a chance match
# this close does not happen.
_MULTIPLE_TOLERANCE = 1e-6
_MOST_COPIES = 1000


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ''


def fusion_type(mastercam_type: str) -> str:
    known = _TYPES.get(mastercam_type)
    if known:
        return known
    # 'HighFeedMill' -> 'high feed mill'
    return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', mastercam_type).lower()


def _geometry(tool: dict, tool_type: str, physical_length: float,
              stickout: float) -> dict:
    diameter = _number(tool.get('diameter'))
    flute = _number(tool.get('flute_length'))
    shoulder = _number(tool.get('shoulder_length')) or flute
    corner = _number(tool.get('corner_radius'))
    if tool_type == 'ball end mill':
        corner = diameter / 2
    tip_angle = _number(tool.get('tip_angle'))
    if tool_type in _TIP_IS_DIAMETER:
        tip = diameter
    elif tool_type in _TIP_INSIDE_RADIUS:
        tip = diameter - 2 * corner
    elif tool_type in _TAPER_ANGLE_TYPES:
        tip = _number(tool.get('tip_diameter'))
    else:
        tip = 0.0
    # Mastercam gives threads per unit of length; Fusion wants the pitch.
    threads = _number(tool.get('threads'))
    pitch = 1 / threads if tool_type in _THREADED_TYPES and threads > 0 else 0.0
    geometry = {
        'DC': diameter,
        'NOF': int(_number(tool.get('flute_count'))),
        'LCF': flute,
        'shoulder-length': shoulder,
        'OAL': max(physical_length, stickout, shoulder),
        'LB': stickout,
        'SFDM': _number(tool.get('shank_diameter')) or diameter,
        'RE': corner,
        'TA': tip_angle if tool_type in _TAPER_ANGLE_TYPES else 0,
        'TP': pitch,
        'tip-diameter': tip,
    }
    if tool_type in _POINT_ANGLE_TYPES:
        geometry['SIG'] = tip_angle
    return geometry


def _holder(holder: dict | None, unit: str) -> dict | None:
    """A Mastercam holder in Fusion's shape. Mastercam lists the profile from
    the spindle down; Fusion from the tool end up."""
    if not holder:
        return None
    segments = [
        {'height': _number(segment.get('height')),
         'lower-diameter': _number(segment.get('dia_lower')),
         'upper-diameter': _number(segment.get('dia_upper'))}
        for segment in reversed(holder.get('segments') or [])
        if isinstance(segment, dict) and _number(segment.get('height')) > 0]
    if not segments:
        return None
    return {
        'type': 'holder',
        'unit': unit,
        'description': _text(holder.get('name')),
        'product-id': '',
        'gaugeLength': sum(segment['height'] for segment in segments),
        'segments': segments,
    }


def tool_record(operation: dict, assembly: dict | None,
                part_is_metric: bool | None = None) -> dict | None:
    """One operation's tool under Fusion's names, or None when the
    operation has no tool. `assembly` is the harvester's fuller record of the
    same tool assembly, when it has one.

    Mastercam holds a tool's sizes, and an operation's feeds, in the part's
    unit, whatever unit the tool itself was defined in: a 6 mm cutter in an
    inch part is 0.2362. So the part's unit is the one that counts. A harvest
    from before it was recorded falls back to the tool's own flag."""
    tool = operation.get('tool')
    if not isinstance(tool, dict):
        return None
    metric = tool.get('is_metric') if part_is_metric is None else part_is_metric
    unit = 'millimeters' if metric else 'inches'
    tool_type = fusion_type(_text(tool.get('type')))
    held = operation.get('assembly') or {}
    stickout = _number(held.get('stickout')) or _number(
        tool.get('length_as_set_in_holder'))
    assembled = (assembly or {}).get('tool') or {}
    # Mastercam's "overall length" is only the part below the holder.
    physical = _number(assembled.get('true_physical_length')) or _number(
        assembled.get('overall_length'))
    holder = _holder(operation.get('holder'), unit)
    record = {
        'type': tool_type,
        'unit': unit,
        'source': SOURCE,
        'BMC': _text(tool.get('material')).lower() or 'unspecified',
        'description': _text(tool.get('name')),
        'vendor': _text(assembled.get('manufacturer')),
        'product-id': _text(tool.get('manufacturer_code')),
        'geometry': _geometry(tool, tool_type, physical, stickout),
        'post-process': {'number': tool.get('number')},
    }
    if holder:
        record['holder'] = holder
    return record


# --- Cutting time ---------------------------------------------------------------
# A transform operation repeats other operations as a pattern, rotation or
# mirror. It carries time but no tool, and Mastercam does not say which
# operations it repeats. Its time is given to tools only when it is an exact
# whole multiple of a set of operations just before it: then it repeats
# those, that many times. Otherwise it is counted as not credited to a tool.
#
# A ghosted operation (posting off) is not run on its own: in real programs
# it is nearly always the original that a transform repeats. So its own time
# is not counted; it gets time only from a transform that repeats it.

def _is_posted(operation: dict) -> bool:
    return operation.get('posting') is not False   # older harvests did not record it


def _fit(total: float, members: list[int], times: dict[int, float | None]) -> int:
    """How many times `total` holds the members' time, when that is an
    exact whole number; else 0."""
    if not members or any(times[i] is None for i in members):
        return 0
    one = sum(times[i] for i in members)
    if one <= 0:
        return 0
    copies = round(total / one)
    if not 1 <= copies <= _MOST_COPIES:
        return 0
    if abs(total - copies * one) > _MULTIPLE_TOLERANCE * max(1.0, total):
        return 0
    return copies


def _repeated(index: int, operations: list[dict], times: dict[int, float | None],
              earlier: dict[int, list[int]]) -> tuple[list[int], int]:
    """The operations transform `index` repeats and how many times, or
    ([], 0) when its time proves nothing. `earlier` holds what was found
    for the transforms before it."""
    transform = operations[index]
    total = times[index] or 0.0

    def same_group(other: dict) -> bool:
        return (other.get('toolpath_group') == transform.get('toolpath_group')
                and other.get('machine_group_id') == transform.get('machine_group_id'))

    tooled = [i for i in range(index)
              if isinstance(operations[i].get('tool'), dict)
              and same_group(operations[i])]
    # The operations straight before it, back to the transform before that.
    run: list[int] = []
    for i in range(index - 1, -1, -1):
        if operations[i].get('is_transform') or not same_group(operations[i]):
            break
        if isinstance(operations[i].get('tool'), dict):
            run.insert(0, i)

    def ghosted(members: list[int]) -> list[int]:
        return [i for i in members if not _is_posted(operations[i])]

    candidates = [ghosted(run), run]
    # The last few of the run, when exactly one such choice fits.
    tails = [run[-n:] for n in range(1, len(run))]
    fitting = [tail for tail in tails if _fit(total, tail, times)]
    if len(fitting) == 1:
        candidates.append(fitting[0])
    # Two transforms in a row often repeat the same operations.
    if index > 0 and operations[index - 1].get('is_transform') and same_group(
            operations[index - 1]):
        candidates.append(earlier.get(index - 1, []))
    candidates += [ghosted(tooled), tooled]
    for members in candidates:
        copies = _fit(total, members, times)
        if copies:
            return members, copies
    return [], 0


def cutting_times(operations: list[dict]) -> tuple[dict[int, float | None], float]:
    """The cutting time to count for each operation that has a tool, by its
    place in the list, and the transform time that could not be given to
    any tool. A time of None means it is not known."""
    own: dict[int, float | None] = {}
    for i, operation in enumerate(operations):
        seconds = operation.get('cycle_time_seconds')
        own[i] = _number(seconds) if isinstance(seconds, (int, float)) else None

    extra: dict[int, float] = {}
    found: dict[int, list[int]] = {}
    uncredited = 0.0
    for i, operation in enumerate(operations):
        if not operation.get('is_transform') or not own[i]:
            continue
        members, copies = _repeated(i, operations, own, found)
        found[i] = members
        if not _is_posted(operation):
            continue   # a ghosted transform is not run
        if not copies:
            uncredited += own[i]
            continue
        for member in members:
            extra[member] = extra.get(member, 0.0) + copies * own[member]

    counted: dict[int, float | None] = {}
    for i, operation in enumerate(operations):
        if not isinstance(operation.get('tool'), dict):
            continue
        if _is_posted(operation):
            counted[i] = None if own[i] is None else own[i] + extra.get(i, 0.0)
        else:
            counted[i] = extra.get(i)
    return counted, round(uncredited, 3)


# --- One part file ----------------------------------------------------------------

def _epoch(text: object) -> int | None:
    """A harvester time ('2026-01-31T14:05:00', local time) as UNIX seconds."""
    try:
        return int(datetime.fromisoformat(str(text)).timestamp())
    except (TypeError, ValueError):
        return None


def file_id(path: str) -> str:
    """A part file is known by where it is. Windows paths ignore case."""
    return f'{SOURCE}:{path.lower()}'


def document_record(record: dict, uncredited_time_s: float) -> DocumentRecord:
    path = PureWindowsPath(_text(record.get('path')))
    history = record.get('history') or {}
    read = _epoch(record.get('harvested_at'))
    saved = _epoch(record.get('disk_modified'))
    newest = _epoch(history.get('newest')) or saved or read or 0
    oldest = _epoch(history.get('oldest')) or newest
    return DocumentRecord(
        file_id=file_id(str(path)),
        version=0,
        name=path.stem,
        project=path.parent.name,
        date_created=oldest,
        date_modified=newest,
        scanned_at=read,
        uncredited_time_s=uncredited_time_s or None,
    )


def _machine(group: dict | None) -> str:
    """The machine a group of operations is programmed for. Mastercam names
    it by its machine definition file."""
    if not group:
        return ''
    name = _text(group.get('machine_name'))
    return PureWindowsPath(name).stem if name else _text(group.get('machine_description'))


def _feed_text(feed: float, unit: str) -> str:
    return f'{feed:g} {"mm/min" if unit == "millimeters" else "in/min"}'


def convert(record: dict) -> tuple[DocumentRecord, list[ObservationRecord]]:
    """One harvested part file as a document and its observations: one for
    each operation that has an in-scope tool."""
    operations = [operation for operation in record.get('operations') or []
                  if isinstance(operation, dict)]
    part_is_metric = record.get('part_is_metric')
    if not isinstance(part_is_metric, bool):
        part_is_metric = None   # an older harvest did not record it
    times, uncredited = cutting_times(operations)
    document = document_record(record, uncredited)
    machines = {group.get('id'): group for group in record.get('machine_groups') or []
                if isinstance(group, dict)}
    assemblies = {assembly.get('slot'): assembly
                  for assembly in record.get('tool_assemblies') or []
                  if isinstance(assembly, dict)}

    observations: list[ObservationRecord] = []
    for i, operation in enumerate(operations):
        slot = (operation.get('assembly') or {}).get('slot')
        tool = tool_record(operation, assemblies.get(slot), part_is_metric)
        if tool is None:
            continue
        group = machines.get(operation.get('machine_group_id'))
        rpm = _number(operation.get('spindle_speed'))
        feed = _number(operation.get('feed_rate'))
        to_mm = 1.0 if tool['unit'] == 'millimeters' else _MM_PER_INCH
        observation = build_observation(
            file_id=document.file_id,
            setup_name=_text(operation.get('toolpath_group'))
            or _text((group or {}).get('name')),
            machine=_machine(group),
            operation_name=_text(operation.get('name'))
            or _text(operation.get('comment')),
            strategy=_text(operation.get('type_name')) or _text(operation.get('type')),
            tool_json=json.dumps(tool),
            spindle_speed=f'{rpm:g}' if rpm > 0 else '',
            feed=_feed_text(feed, tool['unit']) if feed > 0 else '',
            spindle_rpm=rpm,
            feed_mm_min=feed * to_mm,
            preset='',
            cutting_time_s=times.get(i),
        )
        if observation is not None:
            observations.append(observation)
    return document, observations
