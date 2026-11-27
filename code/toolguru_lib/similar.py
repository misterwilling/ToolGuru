"""Similar cutters: finding tools that are probably one tool entered slightly
differently, and treating a chosen group of them as the same.

Two cutters are suggested as similar when they have the same cutting end:
type, diameter, flute count, corner radius, angles and thread pitch. What
may differ is the rest: flute, shoulder and overall length, shaft and tip
diameter, and material.

Nothing merges on its own. The user's decisions are kept in the data file
(see Store.merged_cutters); the scanned observations are never altered.
Merging is applied to the rows on their way to the tally and the detail.
"""

from __future__ import annotations

import hashlib
import json

# The fields that make the cutting end. Cutters that differ in any of these
# are never suggested together.
SAME_END_FIELDS = ('DC', 'NOF', 'RE', 'TA', 'SIG', 'TP')

# The order differing fields are listed in.
_FIELD_ORDER = ('DC', 'NOF', 'LCF', 'shoulder-length', 'OAL', 'SFDM', 'RE',
                'tip-diameter', 'TP', 'TA', 'SIG', 'material')


def _cutters(rows: list[dict]) -> dict[str, dict]:
    """Each cutter in `rows` with its usage, by its own key (the one it was
    scanned with, even after merging)."""
    cutters: dict[str, dict] = {}
    for row in rows:
        key = row.get('original_cutter_key', row['cutter_key'])
        cutter = cutters.get(key)
        if cutter is None:
            fields = row.get('original_cutter_fields', row['cutter_fields'])
            cutter = cutters[key] = {
                'cutter_key': key, 'tool_type': row['tool_type'],
                'fields': json.loads(fields), 'fields_json': fields,
                'descriptions': {}, 'files': set(), 'operations': 0,
                'time_s': 0.0}
        cutter['files'].add(row['file_id'])
        cutter['operations'] += 1
        cutter['time_s'] += row['cutting_time_s'] or 0.0
        described = cutter['descriptions']
        described[row['description']] = described.get(row['description'], 0) + 1
    return cutters


def _most_used_first(cutter: dict) -> tuple:
    return (-len(cutter['files']), -cutter['operations'], cutter['cutter_key'])


def _member(cutter: dict) -> dict:
    described = cutter['descriptions']
    return {
        'cutter_key': cutter['cutter_key'],
        'description': min(described, key=lambda d: (-described[d], d)),
        'fields': cutter['fields'],
        'programs': len(cutter['files']),
        'operations': cutter['operations'],
        'time_s': round(cutter['time_s'], 3),
    }


def _differing(members: list[dict]) -> list[str]:
    """The fields that are not the same in every member, in a fixed order."""
    names = {name for member in members for name in member['fields']}
    differing = [name for name in names
                 if len({json.dumps(member['fields'].get(name))
                         for member in members}) > 1]
    order = {name: index for index, name in enumerate(_FIELD_ORDER)}
    return sorted(differing, key=lambda name: (order.get(name, len(order)), name))


def signature(cutter_keys: list[str]) -> str:
    """A short name for one exact set of cutters, to remember a "not the
    same" answer by. A set that gains a cutter has a new signature, so the
    question comes back."""
    joined = '|'.join(sorted(cutter_keys))
    return hashlib.sha1(joined.encode('utf-8')).hexdigest()[:16]


def suggest(rows: list[dict], merged: dict[str, str],
            dismissed: set[str]) -> list[dict]:
    """Groups of cutters with the same cutting end that have not been dealt
    with: not all merged into one already, and not answered "not the same".
    The group with the most operations comes first; in a group, the most
    used cutter. `merged` maps a cutter key to its merge group.
    """
    buckets: dict[tuple, list[dict]] = {}
    for cutter in _cutters(rows).values():
        end = (cutter['tool_type'],
               *(json.dumps(cutter['fields'].get(name)) for name in SAME_END_FIELDS))
        buckets.setdefault(end, []).append(cutter)

    suggestions = []
    for bucket in buckets.values():
        if len(bucket) < 2:
            continue
        keys = [cutter['cutter_key'] for cutter in bucket]
        if len({merged.get(key, key) for key in keys}) == 1:
            continue   # already one tool
        name = signature(keys)
        if name in dismissed:
            continue
        bucket.sort(key=_most_used_first)
        members = [dict(_member(cutter), merged=cutter['cutter_key'] in merged)
                   for cutter in bucket]
        suggestions.append({
            'signature': name,
            'tool_type': bucket[0]['tool_type'],
            'differs': _differing(members),
            'members': members,
        })
    suggestions.sort(key=lambda s: (-sum(m['operations'] for m in s['members']),
                                    s['signature']))
    return suggestions


def merged_groups(rows: list[dict], merged: dict[str, str]) -> list[dict]:
    """The groups being treated as one tool, for the list they can be split
    from. A group with fewer than two of its cutters still in the data is
    left out: there is nothing to see merged."""
    cutters = _cutters(rows)
    by_group: dict[str, list[dict]] = {}
    for key, group in merged.items():
        if key in cutters:
            by_group.setdefault(group, []).append(cutters[key])
    groups = []
    for bucket in by_group.values():
        if len(bucket) < 2:
            continue
        bucket.sort(key=_most_used_first)
        members = [_member(cutter) for cutter in bucket]
        groups.append({'cutter_key': members[0]['cutter_key'],
                       'tool_type': bucket[0]['tool_type'],
                       'differs': _differing(members),
                       'members': members})
    groups.sort(key=lambda g: (-sum(m['operations'] for m in g['members']),
                               g['cutter_key']))
    return groups


def apply_merges(rows: list[dict], merged: dict[str, str]) -> list[dict]:
    """The rows with every merged cutter counted as its group's most used
    one: that cutter's key and geometry stand for the whole group. A changed
    row remembers what it was scanned as in `original_cutter_key` and
    `original_cutter_fields`. Rows of unmerged cutters are passed through.
    """
    if not merged:
        return rows
    cutters = _cutters(rows)
    stand_in: dict[str, dict] = {}
    for key, group in merged.items():
        cutter = cutters.get(key)
        if cutter is None:
            continue
        best = stand_in.get(group)
        if best is None or _most_used_first(cutter) < _most_used_first(best):
            stand_in[group] = cutter
    result = []
    for row in rows:
        group = merged.get(row['cutter_key'])
        if group is None:
            result.append(row)
            continue
        shown = stand_in[group]
        result.append(dict(
            row, cutter_key=shown['cutter_key'], cutter_fields=shown['fields_json'],
            original_cutter_key=row['cutter_key'],
            original_cutter_fields=row['cutter_fields']))
    return result


def shown_key(rows: list[dict], merged: dict[str, str], cutter_key: str) -> str:
    """The key a cutter is listed under once merges are applied."""
    for row in apply_merges([row for row in rows
                             if merged.get(row['cutter_key']) is not None
                             and merged.get(row['cutter_key']) == merged.get(cutter_key)],
                            merged):
        return row['cutter_key']
    return cutter_key


def variants(group: list[dict]) -> dict | None:
    """What one tally line was merged from: each scanned cutter with its own
    usage, most used first, and the fields they differ in. None for a cutter
    that is not a merge."""
    cutters = sorted(_cutters(group).values(), key=_most_used_first)
    if len(cutters) < 2:
        return None
    members = [_member(cutter) for cutter in cutters]
    return {'differs': _differing(members), 'members': members}
