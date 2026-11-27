"""The holding library: which tools the user picked, and what gets written
for each.

A picked cutter becomes one tool in the library. It is written as it was
last scanned in one of its assemblies (holder and stickout): the one the
user chose, else the usual one, else the most recently used. The tool keeps
everything it was scanned with, holder included. Its tool number is the
cutter's usual number.

Its cutting data is gathered from every scan of the cutter, and of the
cutters merged with it: each preset found on the tool anywhere, used or
not. Where a name has different numbers in different programs, the most
recently saved program's version is the one written.

Only a tool that Fusion itself wrote is ever written back to Fusion. A tool
read from another CAM system (see mastercam.py) is ToolGuru's own rewriting
of it, and Fusion can crash on a tool record it does not like. So a cutter
seen only in such programs cannot be picked, and a line merged from both
kinds is written from its Fusion scans alone.

Pure Python. `library.py` does the writing in Fusion.
"""

from __future__ import annotations

import json
import uuid

from toolguru_lib.detail import breakdown, most_used_first, usual
from toolguru_lib.tally import split_assemblies

LIBRARY_NAME = 'ToolGuru Holding'

_MM_PER_INCH = 25.4
_M_PER_FOOT = 0.3048
# A preset's numbers are in its tool's unit. Feeds per minute, per tooth and
# per revolution, and the stepover and stepdown, are lengths; the surface
# speed is feet or metres per minute. Speeds in rpm and angles are not.
_LENGTH_PREFIXES = ('v_f', 'f_')
_LENGTH_KEYS = ('stepover', 'stepdown')
_SURFACE_KEY = 'v_c'


def _scanned_key(row: dict) -> str:
    return row.get('original_cutter_key', row['cutter_key'])


def _from_fusion(row: dict) -> bool:
    """True when the row's tool was scanned in Fusion, not read elsewhere."""
    scanned = row.get('original_cutter_fields', row['cutter_fields'])
    return not json.loads(scanned).get('source')


def writable(rows: list[dict]) -> set[str]:
    """The tally lines that can be written to a Fusion library: those with
    at least one Fusion scan behind them. `rows` have merges applied."""
    return {row['cutter_key'] for row in rows if _from_fusion(row)}


def line_keys(rows: list[dict], cutter_key: str) -> set[str]:
    """Every scanned cutter that one tally line stands for: more than one
    after a merge. `rows` have merges applied (see similar.apply_merges)."""
    return {_scanned_key(row) for row in rows if row['cutter_key'] == cutter_key}


def assembly_keys(rows: list[dict], cutter_key: str,
                  tolerance_mm: float) -> list[str]:
    group = [row for row in rows if row['cutter_key'] == cutter_key]
    return [assembly['assembly_key']
            for assembly, _, _ in split_assemblies(group, tolerance_mm)]


def _last_used(band: list[dict]) -> int:
    return max(row['date_modified'] for row in band)


def _choose(group: list[dict], wanted: str | None,
            tolerance_mm: float) -> tuple[dict, list[dict]]:
    """The assembly a cutter is written in, with its rows: the one asked
    for when it still exists, else the usual one, else the one used most
    recently."""
    assemblies = [(assembly, band)
                  for assembly, _, band in split_assemblies(group, tolerance_mm)]
    assemblies.sort(key=lambda item: (*most_used_first(item[0]),
                                      item[0]['assembly_key']))
    for assembly, band in assemblies:
        if assembly['assembly_key'] == wanted:
            return assembly, band
    usual_one = usual([assembly for assembly, _ in assemblies])
    if usual_one is not None:
        return next(item for item in assemblies if item[0] is usual_one)
    return max(assemblies, key=lambda item: _last_used(item[1]))


def _in_unit(preset: dict, from_unit: str, to_unit: str) -> dict:
    """The preset with its numbers turned from one tool unit ('inches' or
    'millimeters') into the other. Typed expressions are left as they are:
    they name their own units."""
    if from_unit == to_unit:
        return preset
    to_inch = to_unit == 'inches'
    length = 1 / _MM_PER_INCH if to_inch else _MM_PER_INCH
    surface = 1 / _M_PER_FOOT if to_inch else _M_PER_FOOT
    converted = {}
    for name, value in preset.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            converted[name] = value
        elif name == _SURFACE_KEY:
            converted[name] = value * surface
        elif name.startswith(_LENGTH_PREFIXES) or name in _LENGTH_KEYS:
            converted[name] = value * length
        else:
            converted[name] = value
    return converted


def gathered_presets(group: list[dict], own: list[dict], unit: str) -> list[dict]:
    """Every preset found on the cutter in any scan, one per name, in the
    unit of the tool being written. `own` are the presets already on that
    tool; they keep their place and the others follow by name. For each
    name, the version from the most recently saved program is taken.
    """
    latest: dict[str, tuple[tuple, dict]] = {}
    for row in group:
        found = (json.loads(row['tool_json']).get('start-values') or {}).get('presets')
        when = (row['date_modified'], row.get('id', 0))
        for preset in found or []:
            if not isinstance(preset, dict) or not isinstance(preset.get('name'), str):
                continue
            held = latest.get(preset['name'])
            if held is None or when > held[0]:
                latest[preset['name']] = (when, _in_unit(preset, row['unit'], unit))
    names = [preset['name'] for preset in own
             if isinstance(preset, dict) and preset.get('name') in latest]
    names += sorted(set(latest) - set(names))
    gathered, used_ids = [], set()
    for name in dict.fromkeys(names):
        preset = latest[name][1]
        if preset.get('guid') in used_ids:
            # Two presets must not share an id inside one tool.
            preset = dict(preset, guid=str(uuid.uuid4()))
        used_ids.add(preset.get('guid'))
        gathered.append(preset)
    return gathered


def entry(group: list[dict], wanted: str | None,
          tolerance_mm: float) -> dict | None:
    """What is written for one cutter. `group` is all of its rows. None
    when it has no Fusion scan to write from."""
    group = [row for row in group if _from_fusion(row)]
    if not group:
        return None
    assembly, band = _choose(group, wanted, tolerance_mm)
    shown = group[0]['cutter_key']
    # After a merge, prefer a scan of the cutter that names the line.
    source = max(band, key=lambda row: (_scanned_key(row) == shown,
                                        row['date_modified'], row.get('id', 0)))
    tool = json.loads(source['tool_json'])
    usual_number = usual(breakdown(group, 'tool_number'))
    number = usual_number['value'] if usual_number else source['tool_number']
    if number is not None:
        tool['post-process'] = dict(tool.get('post-process') or {}, number=number)
    start_values = tool.get('start-values') or {}
    presets = gathered_presets(
        group, start_values.get('presets') or [], source['unit'])
    if presets:
        tool['start-values'] = dict(start_values, presets=presets)
    return {'cutter_key': shown, 'assembly_key': assembly['assembly_key'],
            'tool_json': json.dumps(tool)}


def entries(rows: list[dict], picks: dict[str, str | None],
            tolerance_mm: float) -> dict[str, dict]:
    """The tools to write, by tally line. `picks` maps a scanned cutter's
    key to the assembly chosen for it, or None for the usual one. A line is
    picked when any cutter it stands for is; a pick for a cutter that is no
    longer in the data is ignored."""
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row['cutter_key'], []).append(row)
    chosen: dict[str, dict] = {}
    for cutter_key, group in groups.items():
        picked = sorted({_scanned_key(row) for row in group} & picks.keys())
        if not picked:
            continue
        wanted = next((picks[key] for key in picked if picks[key] is not None), None)
        written = entry(group, wanted, tolerance_mm)
        if written is not None:
            chosen[cutter_key] = written
    return chosen
