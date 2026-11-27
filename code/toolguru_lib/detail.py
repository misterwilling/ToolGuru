"""Everything known about one cutter: its geometry, its usual setup, and
which programs used it differently.

The usual setup is whatever most programs did: the tool number, the assembly
(holder and stickout) and the machine each used in the most programs. Every
program is then compared against it, so the odd ones stand out. Where the
top two are level there is no usual one, and nothing is marked as different:
a cutter that got a fresh tool number in every program has no usual number.

Built from the same observation rows as the tally, so the two always agree.
"""

from __future__ import annotations

import json
from collections import Counter

from toolguru_lib import presets as cutting_data
from toolguru_lib import similar
from toolguru_lib.tally import split_assemblies, summarize

# Stickouts are stored to 0.001 mm; this keeps float noise out of the
# "within tolerance" comparison.
_EPSILON_MM = 1e-6

_ASSEMBLY_FIELDS = ('assembly_key', 'holder', 'stickout_min_mm',
                    'stickout_max_mm', 'programs', 'operations', 'time_s')


def _most_used_first(entry: dict) -> tuple:
    return (-entry['programs'], -entry['operations'])


def _breakdown(group: list[dict], field: str) -> list[dict]:
    """How widely each value of `field` was used: the value used in the most
    programs first. Blank values are left out."""
    seen: dict = {}
    for row in group:
        value = row[field]
        if value is None or value == '':
            continue
        entry = seen.setdefault(value, {'files': set(), 'operations': 0})
        entry['files'].add(row['file_id'])
        entry['operations'] += 1
    breakdown = [{'value': value, 'programs': len(entry['files']),
                  'operations': entry['operations']}
                 for value, entry in seen.items()]
    breakdown.sort(key=lambda b: (*_most_used_first(b), b['value']))
    return breakdown


def _usual(entries: list[dict]) -> dict | None:
    """The first of `entries` (already most-used first), or None when there
    are none or the top two were used equally."""
    if not entries:
        return None
    if len(entries) > 1 and _most_used_first(entries[0]) == _most_used_first(entries[1]):
        return None
    return entries[0]


def _same_stickout(assembly: dict, usual: dict, tolerance_mm: float) -> bool:
    """True when `assembly` sits at the usual assembly's stickout, whatever
    holder it is in. The usual stickout runs from the usual assembly's
    shortest stickout up to the tolerance above it."""
    if assembly is usual:
        return True
    low, start = assembly['stickout_min_mm'], usual['stickout_min_mm']
    if low is None or start is None:
        return low is None and start is None
    return (low >= start - _EPSILON_MM
            and assembly['stickout_max_mm'] <= start + tolerance_mm + _EPSILON_MM)


def _marked(values: list, usual: dict | None) -> list[dict]:
    """Each value with whether it is the usual one. With no usual one,
    nothing differs from it."""
    return [{'value': value, 'usual': usual is None or value == usual['value']}
            for value in values]


def _spread(group: list[dict], field: str) -> dict | None:
    """The lowest, highest and most often used value of a speed or feed, with
    the number of operations that have one. None when none has. Where the
    top two values were used equally often there is no most-used one."""
    values = [row[field] for row in group if row.get(field) is not None]
    if not values:
        return None
    ranked = Counter(values).most_common(2)
    clear = len(ranked) == 1 or ranked[0][1] > ranked[1][1]
    return {'min': min(values), 'max': max(values),
            'most_used': ranked[0][0] if clear else None,
            'operations': len(values)}


def _speeds(group: list[dict]) -> dict:
    """The spindle speeds (rpm) and feeds (mm/min) the cutter was run at.
    Operations scanned before these were recorded, or with neither set, are
    counted apart."""
    return {
        'spindle_rpm': _spread(group, 'spindle_rpm'),
        'feed_mm_min': _spread(group, 'feed_mm_min'),
        'operations_without': sum(
            1 for row in group
            if row.get('spindle_rpm') is None and row.get('feed_mm_min') is None),
    }


def _read_presets(group: list[dict]) -> list[tuple[dict, bool | None] | None]:
    """For each row, the preset its operation picked: its numbers, and
    whether the operation kept to them (None when that cannot be checked).
    None for a row whose preset is not with its tool."""
    read = []
    for row in group:
        tool = json.loads(row['tool_json'])
        preset = cutting_data.find_preset(tool, row['preset'])
        if preset is None:
            read.append(None)
            continue
        values = cutting_data.preset_values(preset, row['unit'])
        read.append((values, cutting_data.kept_to_preset(row, values)))
    return read


def _presets(group: list[dict], read: list) -> list[dict]:
    """The cutting data in use: one entry per preset that an operation
    picked, most used first. A preset of the same name with different
    numbers is a different entry. Presets no operation picked are left out.

    `changed` counts the operations that ran at a different speed or feed
    than the preset, `unchecked` those where that cannot be told.
    """
    entries: dict[tuple, dict] = {}
    for row, found in zip(group, read):
        if found is None:
            continue
        values, kept = found
        key = (row['preset'], *values.values())
        entry = entries.setdefault(key, {
            'name': row['preset'], **values, 'files': set(), 'operations': 0, 'changed': 0,
            'unchecked': 0})
        entry['files'].add(row['file_id'])
        entry['operations'] += 1
        entry['changed'] += kept is False
        entry['unchecked'] += kept is None
    listed = []
    for key, entry in entries.items():
        entry['programs'] = len(entry.pop('files'))
        listed.append((key, entry))
    listed.sort(key=lambda item: (*_most_used_first(item[1]),
                                  tuple(str(part) for part in item[0])))
    return [entry for _, entry in listed]


def _programs(group: list[dict], assemblies: list[tuple[dict, str, list[dict]]],
              usual_number: dict | None, usual_machine: dict | None,
              usual_assembly: dict | None, tolerance_mm: float,
              read: list) -> list[dict]:
    """One entry per program that used the cutter, latest saved first, with
    everything that differs from the usual setup marked `usual: False`.

    A program that used the cutter more than one way lists each: every tool
    number and machine, and one `setups` line per assembly. `presets` names
    the cutting data the program picked, each marked `changed` when one of
    its operations ran at a different speed or feed.
    """
    kept_by_row = {id(row): found for row, found in zip(group, read)}
    usual_holder = next((holder_key for assembly, holder_key, _ in assemblies
                         if assembly is usual_assembly), None)
    by_file: dict[str, list[dict]] = {}
    for row in group:
        by_file.setdefault(row['file_id'], []).append(row)

    programs = []
    for file_id, rows in by_file.items():
        mine = {id(row) for row in rows}
        setups = []
        for assembly, holder_key, band in assemblies:
            used = [row for row in band if id(row) in mine]
            if not used:
                continue
            stickouts = [row['stickout_mm'] for row in used
                         if row['stickout_mm'] is not None]
            setups.append({
                'holder': assembly['holder'],
                'holder_usual': (usual_assembly is None
                                 or holder_key == usual_holder),
                'stickout_min_mm': min(stickouts) if stickouts else None,
                'stickout_max_mm': max(stickouts) if stickouts else None,
                'stickout_usual': (usual_assembly is None or _same_stickout(
                    assembly, usual_assembly, tolerance_mm)),
                'operations': len(used),
            })
        setups.sort(key=lambda s: -s['operations'])   # stable: usual order kept
        times = [row['cutting_time_s'] for row in rows
                 if row['cutting_time_s'] is not None]
        programs.append({
            'file_id': file_id,
            'name': rows[0]['document_name'],
            'last_saved': rows[0]['date_modified'],
            'operations': len(rows),
            'time_s': round(sum(times), 3),
            'tool_numbers': _marked(
                sorted({row['tool_number'] for row in rows
                        if row['tool_number'] is not None}), usual_number),
            'machines': _marked(
                sorted({row['machine'] for row in rows if row['machine']}),
                usual_machine),
            'setups': setups,
            'presets': _program_presets(rows, kept_by_row),
        })
    programs.sort(key=lambda p: (-p['last_saved'], p['name'], p['file_id']))
    return programs


def _program_presets(rows: list[dict], kept_by_row: dict) -> list[dict]:
    changed: dict[str, bool] = {}
    for row in rows:
        found = kept_by_row[id(row)]
        if found is None:
            continue
        changed[row['preset']] = changed.get(row['preset'], False) or found[1] is False
    return [{'name': name, 'changed': changed[name]} for name in sorted(changed)]


def build_cutter_detail(rows: list[dict], cutter_key: str,
                        tolerance_mm: float) -> dict | None:
    """`rows` are observation rows (see Store.observation_rows). Returns None
    when no observation has this cutter.

    The result carries the cutter's tally figures, its full geometry in
    millimetres, the speeds and feeds it ran at, how widely each tool number, assembly and machine was used,
    which of each is the usual one (None when the top two are level), and
    the programs compared against that usual setup. `tolerance_mm` is the
    stickout tolerance that groups the assemblies.
    """
    group = [row for row in rows if row['cutter_key'] == cutter_key]
    if not group:
        return None
    assemblies = split_assemblies(group, tolerance_mm)
    assemblies.sort(key=lambda a: (*_most_used_first(a[0]), a[0]['assembly_key']))
    numbers = _breakdown(group, 'tool_number')
    machines = _breakdown(group, 'machine')
    usual_number, usual_machine = _usual(numbers), _usual(machines)
    usual_assembly = _usual([assembly for assembly, _, _ in assemblies])
    read = _read_presets(group)
    return {
        **summarize(group),
        'fields': json.loads(group[0]['cutter_fields']),
        'variants': similar.variants(group),
        'speeds': _speeds(group),
        'presets': _presets(group, read),
        'tool_number_use': numbers,
        'machine_use': machines,
        'assemblies': [{field: assembly[field] for field in _ASSEMBLY_FIELDS}
                       for assembly, _, _ in assemblies],
        'usual': {
            'tool_number': usual_number['value'] if usual_number else None,
            'machine': usual_machine['value'] if usual_machine else None,
            'assembly_key': (usual_assembly['assembly_key']
                             if usual_assembly else None),
        },
        'program_list': _programs(
            group, assemblies, usual_number, usual_machine, usual_assembly,
            tolerance_mm, read),
    }
