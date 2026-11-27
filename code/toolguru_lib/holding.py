"""The holding library: which tools the user picked, and what gets written
for each.

A picked cutter becomes one tool in the library. It is written as it was
last scanned in one of its assemblies (holder and stickout): the one the
user chose, else the usual one, else the most recently used. The tool keeps
everything it was scanned with, holder and presets included. Its tool
number is the cutter's usual number.

Pure Python. `library.py` does the writing in Fusion.
"""

from __future__ import annotations

import json

from toolguru_lib.detail import breakdown, most_used_first, usual
from toolguru_lib.tally import split_assemblies

LIBRARY_NAME = 'ToolGuru Holding'


def _scanned_key(row: dict) -> str:
    return row.get('original_cutter_key', row['cutter_key'])


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


def entry(group: list[dict], wanted: str | None, tolerance_mm: float) -> dict:
    """What is written for one cutter. `group` is all of its rows."""
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
        chosen[cutter_key] = entry(group, wanted, tolerance_mm)
    return chosen
