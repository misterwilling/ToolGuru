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


def _programs(group: list[dict], assemblies: list[tuple[dict, str, list[dict]]],
              usual_number: dict | None, usual_machine: dict | None,
              usual_assembly: dict | None, tolerance_mm: float) -> list[dict]:
    """One entry per program that used the cutter, latest saved first, with
    everything that differs from the usual setup marked `usual: False`.

    A program that used the cutter more than one way lists each: every tool
    number and machine, and one `setups` line per assembly.
    """
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
        })
    programs.sort(key=lambda p: (-p['last_saved'], p['name'], p['file_id']))
    return programs


def build_cutter_detail(rows: list[dict], cutter_key: str,
                        tolerance_mm: float) -> dict | None:
    """`rows` are observation rows (see Store.observation_rows). Returns None
    when no observation has this cutter.

    The result carries the cutter's tally figures, its full geometry in
    millimetres, how widely each tool number, assembly and machine was used,
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
    return {
        **summarize(group),
        'fields': json.loads(group[0]['cutter_fields']),
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
            tolerance_mm),
    }
