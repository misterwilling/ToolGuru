"""Assembly identity: the holder a cutter sits in and how far it sticks out.

A rotating tool assembly is cutter + holder + stickout. The cutter part is
`cutter.identify`; this module reads the other two from the same tool dict.
Which holders count as the same holder, and how close two stickouts must be,
is decided when the tally is built (see tally.build_assembly_tally) so those
rules can change without rescanning.

Pure Python: takes the dict parsed from Fusion's `Tool.toJson()`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal

from toolguru_lib.cutter import to_mm

# Holder profiles are compared to 0.01 mm: finer than any real difference
# between two holders, coarse enough to survive inch/millimetre conversion.
_SHAPE_QUANTUM = Decimal('0.01')
_SEGMENT_KEYS = ('height', 'lower-diameter', 'upper-diameter')


@dataclass(frozen=True)
class Assembly:
    holder_product_id: str    # normalized for comparison; '' when blank
    holder_shape: str         # fingerprint of the holder profile; '' when none
    holder_label: str         # what to show: description, else product ID
    stickout_mm: float | None  # Fusion's "length below holder"


def normalize_product_id(text: object) -> str:
    """Product IDs are typed by hand: ignore case and spacing differences."""
    return ' '.join(str(text or '').split()).casefold()


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _shape(holder: dict, unit: str) -> str:
    segments = holder.get('segments') or []
    if not segments:
        return ''
    profile = [
        [f'{to_mm(_number(segment.get(key)) or 0.0, unit, _SHAPE_QUANTUM):.2f}'
         for key in _SEGMENT_KEYS]
        for segment in segments]
    canonical = json.dumps(profile)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]


def describe(tool: dict) -> Assembly:
    """Holder and stickout of one tool."""
    tool_unit = str(tool.get('unit', ''))
    holder = tool.get('holder') or {}
    product_id = str(holder.get('product-id') or '').strip()
    description = str(holder.get('description') or '').strip()
    stickout = _number((tool.get('geometry') or {}).get('LB'))
    return Assembly(
        holder_product_id=normalize_product_id(product_id),
        holder_shape=_shape(holder, str(holder.get('unit') or tool_unit)),
        holder_label=description or product_id,
        stickout_mm=None if stickout is None else float(to_mm(stickout, tool_unit)),
    )
