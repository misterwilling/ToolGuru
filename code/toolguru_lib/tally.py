"""Usage tally: collapse observations into one row per cutter.

Usage is counted from operations, never from a tool merely being present in
a program's tool list.
"""

from __future__ import annotations

import json
from collections import Counter


def _most_common(values: list[str]) -> str:
    """Most frequent non-empty value; ties resolve alphabetically."""
    counts = Counter(v for v in values if v)
    if not counts:
        return ''
    top = max(counts.values())
    return min(v for v, n in counts.items() if n == top)


def build_tally(rows: list[dict]) -> list[dict]:
    """`rows` are observation rows joined with their document's dates
    (see Store.observation_rows). Returns one dict per cutter, most-used first.
    """
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row['cutter_key'], []).append(row)

    tally: list[dict] = []
    for key, group in groups.items():
        cutter_fields = json.loads(group[0]['cutter_fields'])
        times = [r['cutting_time_s'] for r in group
                 if r['cutting_time_s'] is not None]
        tally.append({
            'cutter_key': key,
            'tool_type': group[0]['tool_type'],
            'family': group[0]['family'],
            'description': _most_common([r['description'] for r in group]),
            'diameter_mm': cutter_fields.get('DC'),
            'flutes': cutter_fields.get('NOF'),
            'programs': len({r['file_id'] for r in group}),
            'operations': len(group),
            'time_s': round(sum(times), 3),
            'operations_without_time': len(group) - len(times),
            'first_used': min(r['date_created'] for r in group),
            'last_used': max(r['date_modified'] for r in group),
            'tool_numbers': sorted({r['tool_number'] for r in group
                                    if r['tool_number'] is not None}),
            'machines': sorted({r['machine'] for r in group if r['machine']}),
            'units': sorted({r['unit'] for r in group if r['unit']}),
        })
    tally.sort(key=lambda t: (-t['operations'], t['cutter_key']))
    return tally
