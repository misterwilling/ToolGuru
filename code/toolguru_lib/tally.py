"""Usage tally: collapse observations into one row per cutter, or one row per
assembly (cutter + holder + stickout).

Usage is counted from operations, never from a tool merely being present in
a program's tool list.
"""

from __future__ import annotations

import json
from collections import Counter

# Stickouts are stored to 0.001 mm; this keeps float noise out of the
# "within tolerance" comparison.
_EPSILON_MM = 1e-6


def _most_common(values: list[str]) -> str:
    """Most frequent non-empty value; ties resolve alphabetically."""
    counts = Counter(v for v in values if v)
    if not counts:
        return ''
    top = max(counts.values())
    return min(v for v, n in counts.items() if n == top)


def _summarize(group: list[dict]) -> dict:
    """The usage figures for one group of observations of the same cutter."""
    cutter_fields = json.loads(group[0]['cutter_fields'])
    times = [r['cutting_time_s'] for r in group
             if r['cutting_time_s'] is not None]
    return {
        'cutter_key': group[0]['cutter_key'],
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
    }


def build_tally(rows: list[dict]) -> list[dict]:
    """`rows` are observation rows joined with their document's dates
    (see Store.observation_rows). Returns one dict per cutter, most-used first.
    """
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row['cutter_key'], []).append(row)

    tally = [_summarize(group) for group in groups.values()]
    tally.sort(key=lambda t: (-t['operations'], t['cutter_key']))
    return tally


def _holder_keys(rows: list[dict]) -> dict[tuple[str, str], str]:
    """Decide which holders are the same holder.

    Each row names its holder by product ID and by shape; either may be
    blank. Two holders are the same when their product IDs match, and also
    when their shapes match — which covers a blank ID and an ID typed two
    different ways. Returns a key for every (product ID, shape) pair seen;
    '' means no holder at all.
    """
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    pairs = sorted({(r['holder_product_id'], r['holder_shape']) for r in rows})
    for product_id, shape in pairs:
        nodes = [name for name in (f'id:{product_id}' if product_id else '',
                                   f'shape:{shape}' if shape else '') if name]
        for node in nodes:
            parent.setdefault(node, node)
        if len(nodes) == 2:
            # The smaller name becomes the root, so the key does not depend
            # on the order rows arrive in.
            low, high = sorted(find(node) for node in nodes)
            parent[high] = low

    keys: dict[tuple[str, str], str] = {}
    for product_id, shape in pairs:
        if product_id:
            keys[(product_id, shape)] = find(f'id:{product_id}')
        elif shape:
            keys[(product_id, shape)] = find(f'shape:{shape}')
        else:
            keys[(product_id, shape)] = ''
    return keys


def _stickout_bands(group: list[dict], tolerance_mm: float) -> list[list[dict]]:
    """Split one cutter-in-one-holder group by stickout.

    Bands start at the shortest stickout and take everything within the
    tolerance of that start, so no band is ever wider than the tolerance.
    Observations with no recorded stickout form their own band.
    """
    known = sorted((r for r in group if r['stickout_mm'] is not None),
                   key=lambda r: r['stickout_mm'])
    unknown = [r for r in group if r['stickout_mm'] is None]
    bands: list[list[dict]] = []
    for row in known:
        if bands and (row['stickout_mm'] - bands[-1][0]['stickout_mm']
                      <= tolerance_mm + _EPSILON_MM):
            bands[-1].append(row)
        else:
            bands.append([row])
    if unknown:
        bands.append(unknown)
    return bands


def build_assembly_tally(rows: list[dict], tolerance_mm: float) -> list[dict]:
    """One dict per assembly: the same cutter, in the same holder, with
    stickouts within `tolerance_mm` of each other. Most-used first.

    Each row carries everything a cutter row does, plus the holder and the
    range of stickouts it covers.
    """
    holder_keys = _holder_keys(rows)
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        holder_key = holder_keys[(row['holder_product_id'], row['holder_shape'])]
        groups.setdefault((row['cutter_key'], holder_key), []).append(row)

    tally: list[dict] = []
    for (cutter_key, holder_key), group in groups.items():
        for band in _stickout_bands(group, tolerance_mm):
            stickouts = [r['stickout_mm'] for r in band
                         if r['stickout_mm'] is not None]
            start = f'{stickouts[0]:.3f}' if stickouts else 'none'
            tally.append({
                **_summarize(band),
                'assembly_key': f'{cutter_key}|{holder_key}|{start}',
                'holder': _most_common([r['holder'] for r in band]),
                'stickout_min_mm': min(stickouts) if stickouts else None,
                'stickout_max_mm': max(stickouts) if stickouts else None,
            })
    tally.sort(key=lambda t: (-t['operations'], t['assembly_key']))
    return tally
