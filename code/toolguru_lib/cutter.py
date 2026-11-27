"""Cutter identity: which tools count as "the same tool".

Two tools are the same cutter when their type, cutter material and cutting
geometry match after converting lengths to millimetres. Holder, stick-out,
tool number, description and feeds/speeds are deliberately left out — those
describe an assembly or a use, not the cutter.

A tool read from another CAM system names it in `source`, and that is part
of its identity: such a cutter is never the same cutter as a Fusion one,
whatever its geometry. The user can still merge the two by hand.

Pure Python: takes the dict parsed from Fusion's `Tool.toJson()`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

_MM_PER_INCH = Decimal('25.4')
_QUANTUM = Decimal('0.001')
_UNIT_FACTORS = {'millimeters': Decimal(1), 'inches': _MM_PER_INCH}

# Fusion geometry keys that define the cutter. Lengths are unit-converted;
# angles and counts are not.
_LENGTH_KEYS = ('DC', 'LCF', 'shoulder-length', 'OAL', 'SFDM', 'RE', 'TP',
                'tip-diameter')
_ANGLE_KEYS = ('TA', 'SIG')
_COUNT_KEYS = ('NOF',)

_FAMILY_BY_TYPE = {
    'flat end mill': 'milling',
    'ball end mill': 'milling',
    'bull nose end mill': 'milling',
    'chamfer mill': 'milling',
    'face mill': 'milling',
    'slot mill': 'milling',
    'radius mill': 'milling',
    'dovetail mill': 'milling',
    'tapered mill': 'milling',
    'lollipop mill': 'milling',
    'form mill': 'milling',
    'drill': 'hole making',
    'center drill': 'hole making',
    'spot drill': 'hole making',
    'counter bore': 'hole making',
    'counter sink': 'hole making',
    'reamer': 'hole making',
    'boring bar': 'hole making',
    'tap right hand': 'hole making',
    'tap left hand': 'hole making',
    'thread mill': 'hole making',
    'probe': 'probe',
    'holder': 'holder',
}
_EXCLUDED_TYPES = {'waterjet', 'laser cutter', 'plasma cutter'}
_EXCLUDED_PREFIXES = ('turning',)


@dataclass(frozen=True)
class Cutter:
    key: str
    tool_type: str
    family: str
    fields: dict


def family_of(tool_type: str) -> str | None:
    """Family a tool type belongs to, or None when the type is out of scope
    (turning and jet/laser/plasma cutting). Unknown types are kept as 'other'
    so nothing disappears silently."""
    if tool_type in _EXCLUDED_TYPES or tool_type.startswith(_EXCLUDED_PREFIXES):
        return None
    return _FAMILY_BY_TYPE.get(tool_type, 'other')


def to_mm(value: float, unit: str, quantum: Decimal = _QUANTUM) -> Decimal:
    """Convert a length to millimetres, rounded half-up to `quantum`
    (0.001 mm unless told otherwise).

    Decimal arithmetic keeps 0.1875 in and 4.7625 mm on the same side of the
    rounding boundary, which binary floats do not guarantee.
    """
    if unit not in _UNIT_FACTORS:
        raise ValueError(f'Unknown tool unit: {unit!r}')
    exact = Decimal(repr(float(value))) * _UNIT_FACTORS[unit]
    return exact.quantize(quantum, rounding=ROUND_HALF_UP)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def identify(tool: dict) -> Cutter | None:
    """Fingerprint a tool. Returns None for out-of-scope tool types."""
    tool_type = str(tool.get('type', ''))
    family = family_of(tool_type)
    if family is None:
        return None

    unit = str(tool.get('unit', ''))
    geometry = tool.get('geometry') or {}
    normalized: dict[str, Decimal] = {}
    for key in _LENGTH_KEYS:
        number = _number(geometry.get(key))
        if number:
            normalized[key] = to_mm(number, unit)
    for key in _ANGLE_KEYS:
        number = _number(geometry.get(key))
        if number:
            normalized[key] = Decimal(repr(number)).quantize(
                _QUANTUM, rounding=ROUND_HALF_UP)
    for key in _COUNT_KEYS:
        number = _number(geometry.get(key))
        if number:
            normalized[key] = Decimal(int(number))

    material = str(tool.get('BMC') or '')
    source = str(tool.get('source') or '')
    identity = {'type': tool_type, 'material': material,
                **{k: f'{v:.3f}' for k, v in normalized.items()}}
    if source:
        # Left out for a Fusion tool, so the keys of cutters scanned before
        # other sources existed stay what they were.
        identity['source'] = source
    canonical = json.dumps(identity, sort_keys=True)
    key = hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]

    fields: dict = {k: float(v) for k, v in normalized.items()}
    if 'NOF' in fields:
        fields['NOF'] = int(fields['NOF'])
    fields['material'] = material
    if source:
        fields['source'] = source
    return Cutter(key=key, tool_type=tool_type, family=family, fields=fields)
