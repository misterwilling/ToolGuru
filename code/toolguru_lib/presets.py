"""A tool's cutting data: the presets saved with it, and whether an operation
kept to the one it picked.

Fusion stores a tool's presets inside the tool, in the tool's own unit: an
inch tool has feeds in in/min, chip load in inches and surface speed in
ft/min; a millimetre tool has mm/min, mm and m/min. Everything here is turned
into millimetres (and m/min) so the same preset compares equal either way.
"""

from __future__ import annotations

import re

_MM_PER_INCH = 25.4
_M_PER_FOOT = 0.3048

# Preset entry -> (our name, what kind of quantity it is).
_VALUES = (
    ('n', 'spindle_rpm', 'plain'),
    ('v_f', 'feed_mm_min', 'length'),
    ('f_z', 'chip_load_mm', 'length'),
    ('v_c', 'surface_m_min', 'surface'),
    ('v_f_plunge', 'plunge_mm_min', 'length'),
    ('v_f_ramp', 'ramp_mm_min', 'length'),
    ('n_ramp', 'ramp_rpm', 'plain'),
)
# A stepover or stepdown only counts when the preset says to use it.
_STEPS = (('stepover', 'use-stepover', 'stepover_mm'),
          ('stepdown', 'use-stepdown', 'stepdown_mm'))

_RPM = re.compile(r'^\s*(\d+(?:\.\d*)?)\s*(?:rpm)?\s*$')
_FEED = re.compile(r'^\s*(\d+(?:\.\d*)?)\s*(in/min|inpm|mm/min|mmpm)\s*$')


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def find_preset(tool: dict, name: str) -> dict | None:
    """The preset of this name saved with the tool, or None."""
    presets = (tool.get('start-values') or {}).get('presets') or []
    return next((p for p in presets
                 if isinstance(p, dict) and p.get('name') == name), None)


def preset_values(preset: dict, tool_unit: str) -> dict:
    """The preset's numbers in millimetres, mm/min, m/min and rpm. A number
    the preset does not have is None."""
    inch = tool_unit == 'inches'
    scale = {'plain': 1.0,
             'length': _MM_PER_INCH if inch else 1.0,
             'surface': _M_PER_FOOT if inch else 1.0}
    values: dict = {}
    for key, name, kind in _VALUES:
        number = _number(preset.get(key))
        values[name] = None if number is None else round(number * scale[kind], 4)
    for key, switch, name in _STEPS:
        number = _number(preset.get(key)) if preset.get(switch) is True else None
        values[name] = None if number is None else round(number * scale['length'], 4)
    return values


def _typed_rpm(expression: str) -> float | None:
    match = _RPM.match(expression)
    return float(match.group(1)) if match else None


def _typed_feed_mm_min(expression: str) -> float | None:
    """A feed typed with its unit. A bare number is in the program's unit,
    which is not recorded, so it is not read."""
    match = _FEED.match(expression)
    if not match:
        return None
    feed = float(match.group(1))
    return feed * _MM_PER_INCH if match.group(2).startswith('in') else feed


def _close(used: float, wanted: float) -> bool:
    return abs(used - wanted) <= max(0.05, abs(wanted) * 0.001)


def kept_to_preset(row: dict, values: dict) -> bool | None:
    """Whether an operation ran at its preset's speed and feed.

    True when everything that can be checked matches, False when a speed or
    feed differs, None when nothing can be checked. The operation's numbers
    are used when the scan recorded them; otherwise what was typed is read,
    when it is a plain number. A feed matches the preset's cutting feed or
    its plunge feed, since drilling runs at the plunge feed.
    """
    checks: list[bool] = []

    rpm = row.get('spindle_rpm')
    if rpm is None:
        rpm = _typed_rpm(row['spindle_speed'])
    if rpm is not None and values['spindle_rpm'] is not None:
        checks.append(_close(rpm, values['spindle_rpm']))

    feed = row.get('feed_mm_min')
    if feed is None and row['strategy'] != 'drill':
        # Older scans stored a drilling operation's unused cutting feed; do
        # not judge by it.
        feed = _typed_feed_mm_min(row['feed'])
    wanted = [values[name] for name in ('feed_mm_min', 'plunge_mm_min')
              if values[name] is not None]
    if feed is not None and wanted:
        checks.append(any(_close(feed, value) for value in wanted))

    return all(checks) if checks else None
