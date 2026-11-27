"""A tool's cutting data, and whether an operation kept to it."""

from dataclasses import asdict

from toolguru_lib import presets
from toolguru_lib.detail import build_cutter_detail
from toolguru_tests.factories import make_observation, make_tool


def make_preset(name: str = 'Aluminum - Roughing', **overrides) -> dict:
    """An inch tool's preset as Fusion stores it: 8000 rpm, 40 in/min."""
    preset = {
        'name': name, 'description': '', 'n': 8000, 'v_f': 40.0, 'f_z': 0.002,
        'v_c': 1000.0, 'v_f_plunge': 10.0, 'v_f_ramp': 20.0, 'n_ramp': 7000,
        'stepover': 0.1, 'use-stepover': True,
        'stepdown': 0.5, 'use-stepdown': False,
        'tool-coolant': 'flood',
    }
    preset.update(overrides)
    return preset


def tool_with(*tool_presets: dict, **overrides) -> dict:
    return make_tool(**{'start-values': {'presets': list(tool_presets)}}, **overrides)


def _row(file_id: str = 'a', *, preset: str = 'Aluminum - Roughing',
         tool: dict | None = None, strategy: str = 'adaptive', **kwargs) -> dict:
    row = asdict(make_observation(file_id, tool=tool or tool_with(make_preset()), **kwargs))
    row.update(preset=preset, strategy=strategy, document_name=f'Program {file_id}',
               date_created=100, date_modified=200)
    return row


def _detail(rows: list[dict]) -> dict:
    return build_cutter_detail(rows, rows[0]['cutter_key'], 0.5)


INCH_VALUES = {
    'spindle_rpm': 8000.0, 'feed_mm_min': 1016.0, 'chip_load_mm': 0.0508,
    'surface_m_min': 304.8, 'plunge_mm_min': 254.0, 'ramp_mm_min': 508.0,
    'ramp_rpm': 7000.0, 'stepover_mm': 2.54, 'stepdown_mm': None,
}
METRIC_PRESET = dict(v_f=1016.0, f_z=0.0508, v_c=304.8, v_f_plunge=254.0,
                     v_f_ramp=508.0, stepover=2.54)


class TestPresetValues:
    def test_an_inch_preset_is_turned_into_millimetres_and_metres(self):
        assert presets.preset_values(make_preset(), 'inches') == INCH_VALUES

    def test_a_millimetre_preset_is_kept_as_it_is(self):
        preset = make_preset(**METRIC_PRESET)
        assert presets.preset_values(preset, 'millimeters') == INCH_VALUES

    def test_a_stepdown_the_preset_does_not_use_is_left_out(self):
        values = presets.preset_values(make_preset(), 'inches')
        assert values['stepdown_mm'] is None   # use-stepdown is off

    def test_a_number_the_preset_lacks_is_none(self):
        preset = make_preset()
        del preset['f_z']
        assert presets.preset_values(preset, 'inches')['chip_load_mm'] is None

    def test_the_preset_is_found_by_name(self):
        tool = tool_with(make_preset('One', n=1000), make_preset('Two', n=2000))
        assert presets.find_preset(tool, 'Two')['n'] == 2000
        assert presets.find_preset(tool, 'Three') is None
        assert presets.find_preset(make_tool(), 'One') is None


class TestKeptToPreset:
    """`make_observation` types '8000' and '40 in/min' unless told otherwise."""

    def _kept(self, **changes) -> bool | None:
        row = _row(**{k: v for k, v in changes.items()
                      if k in ('spindle_rpm', 'feed_mm_min', 'strategy')})
        row.update({k: v for k, v in changes.items()
                    if k in ('spindle_speed', 'feed')})
        return presets.kept_to_preset(row, INCH_VALUES)

    def test_an_operation_at_the_presets_numbers_kept_to_it(self):
        assert self._kept() is True

    def test_a_different_speed_is_a_change(self):
        assert self._kept(spindle_rpm=10000.0) is False

    def test_a_different_feed_is_a_change(self):
        assert self._kept(feed_mm_min=500.0) is False

    def test_a_drill_at_the_presets_plunge_feed_kept_to_it(self):
        assert self._kept(feed_mm_min=254.0) is True

    def test_rounding_in_the_last_place_is_not_a_change(self):
        assert self._kept(spindle_rpm=8000.004, feed_mm_min=1016.3) is True

    def test_an_older_scan_is_judged_by_the_numbers_that_were_typed(self):
        old = {'spindle_rpm': None, 'feed_mm_min': None}
        assert self._kept(**old) is True
        assert self._kept(**old, spindle_speed='9000 rpm') is False
        assert self._kept(**old, feed='1016 mm/min') is True
        assert self._kept(**old, feed='30in/min') is False

    def test_an_older_scan_with_formulas_cannot_be_checked(self):
        assert self._kept(
            spindle_rpm=None, feed_mm_min=None,
            spindle_speed='tool_surfaceSpeed/(tool_diameter * Math.PI)',
            feed='tool_feedPerTooth * tool_spindleSpeed * tool_numberOfFlutes') is None

    def test_a_feed_typed_without_a_unit_is_not_judged(self):
        assert self._kept(spindle_rpm=None, feed_mm_min=None, feed='999') is True

    def test_an_older_drilling_scan_is_not_judged_by_its_unused_cutting_feed(self):
        assert self._kept(spindle_rpm=None, feed_mm_min=None, strategy='drill',
                          feed='99inpm') is True


class TestDetailPresets:
    def test_a_preset_in_use_is_listed_with_its_numbers_and_use(self):
        rows = [_row('a'), _row('a'), _row('b')]
        assert _detail(rows)['presets'] == [{
            'name': 'Aluminum - Roughing', **INCH_VALUES,
            'programs': 2, 'operations': 3, 'changed': 0, 'unchecked': 0}]

    def test_presets_no_operation_picked_are_left_out(self):
        tool = tool_with(make_preset(), make_preset('Steel - Roughing', n=3000))
        assert [p['name'] for p in _detail([_row(tool=tool)])['presets']] == [
            'Aluminum - Roughing']

    def test_the_same_name_with_different_numbers_is_listed_twice_most_used_first(self):
        edited = tool_with(make_preset(n=9000))
        rows = [_row('a', spindle_rpm=9000.0, tool=edited), _row('b'), _row('c')]
        listed = _detail(rows)['presets']
        assert [(p['spindle_rpm'], p['programs']) for p in listed] == [
            (8000.0, 2), (9000.0, 1)]

    def test_the_same_preset_in_inches_and_millimetres_is_one_line(self):
        metric = tool_with(
            make_preset(**METRIC_PRESET), unit='millimeters',
            geometry={'DC': 12.7, 'LCF': 31.75, 'shoulder-length': 31.75,
                      'OAL': 76.2, 'SFDM': 12.7, 'LB': 38.1,
                      'assemblyGaugeLength': 101.6})
        rows = [_row('a'), _row('b', tool=metric)]
        assert rows[0]['cutter_key'] == rows[1]['cutter_key']
        assert [(p['programs'], p['operations'])
                for p in _detail(rows)['presets']] == [(2, 2)]

    def test_changed_and_unchecked_operations_are_counted(self):
        formula = _row('c', spindle_rpm=None, feed_mm_min=None)
        formula.update(spindle_speed='tool_surfaceSpeed/1', feed='tool_feedPerTooth*1')
        rows = [_row('a'), _row('b', spindle_rpm=12000.0), formula]
        preset = _detail(rows)['presets'][0]
        assert (preset['operations'], preset['changed'], preset['unchecked']) == (3, 1, 1)

    def test_a_program_names_its_presets_and_marks_the_changed_one(self):
        tool = tool_with(make_preset(), make_preset('Finish'))
        rows = [_row('a', tool=tool),
                _row('a', tool=tool, preset='Finish', feed_mm_min=300.0),
                _row('b', tool=tool)]
        programs = {p['file_id']: p['presets'] for p in _detail(rows)['program_list']}
        assert programs == {
            'a': [{'name': 'Aluminum - Roughing', 'changed': False},
                  {'name': 'Finish', 'changed': True}],
            'b': [{'name': 'Aluminum - Roughing', 'changed': False}],
        }

    def test_an_operation_whose_preset_is_not_with_the_tool_is_left_out(self):
        detail = _detail([_row('a', preset='Gone')])
        assert detail['presets'] == []
        assert detail['program_list'][0]['presets'] == []
