"""Which tools count as the same cutter."""

import json
from decimal import Decimal

import pytest

from toolguru_lib import cutter
from toolguru_lib.records import build_observation
from toolguru_tests.factories import make_tool


class TestToMm:
    def test_inches_convert_at_25_4(self):
        assert cutter.to_mm(0.5, 'inches') == Decimal('12.700')

    def test_millimetres_pass_through(self):
        assert cutter.to_mm(6.35, 'millimeters') == Decimal('6.350')

    def test_three_sixteenths_matches_its_metric_entry(self):
        # 0.1875 in is exactly 4.7625 mm: a half-way case for 0.001 rounding.
        assert cutter.to_mm(0.1875, 'inches') == Decimal('4.763')
        assert cutter.to_mm(4.7625, 'millimeters') == Decimal('4.763')

    def test_metric_size_stored_as_inches_rounds_back(self):
        assert cutter.to_mm(0.2362205, 'inches') == Decimal('6.000')

    def test_unknown_unit_is_rejected(self):
        with pytest.raises(ValueError, match='furlongs'):
            cutter.to_mm(1.0, 'furlongs')


class TestIdentify:
    def test_normalized_fields_are_in_millimetres(self):
        fields = cutter.identify(make_tool()).fields
        assert fields['DC'] == 12.7
        assert fields['LCF'] == 31.75
        assert fields['OAL'] == 76.2
        assert fields['NOF'] == 3
        assert fields['material'] == 'carbide'

    def test_same_cutter_entered_in_inches_and_millimetres_matches(self):
        inch = make_tool()
        metric = make_tool(unit='millimeters', geometry={
            'DC': 12.7, 'LCF': 31.75, 'shoulder-length': 31.75, 'OAL': 76.2,
            'SFDM': 12.7})
        assert cutter.identify(inch).key == cutter.identify(metric).key

    def test_holder_number_description_and_stickout_do_not_change_identity(self):
        base = cutter.identify(make_tool()).key
        other = make_tool(description='renamed', holder={'description': 'Other'},
                          geometry={'LB': 2.25, 'assemblyGaugeLength': 5.5})
        other['post-process'] = {'number': 99}
        assert cutter.identify(other).key == base

    @pytest.mark.parametrize('change', [
        {'geometry': {'LCF': 0.625}},
        {'geometry': {'NOF': 4}},
        {'geometry': {'DC': 0.375}},
        {'geometry': {'RE': 0.03}},
        {'geometry': {'OAL': 4.0}},
        {'BMC': 'hss'},
        {'type': 'ball end mill'},
    ])
    def test_cutting_geometry_material_and_type_change_identity(self, change):
        assert cutter.identify(make_tool(**change)).key != cutter.identify(make_tool()).key

    def test_missing_corner_radius_equals_zero_corner_radius(self):
        without = make_tool()
        del without['geometry']['RE']
        assert cutter.identify(without).key == cutter.identify(make_tool()).key

    def test_key_is_sixteen_hex_characters(self):
        key = cutter.identify(make_tool()).key
        assert len(key) == 16
        assert set(key) <= set('0123456789abcdef')


class TestFamily:
    @pytest.mark.parametrize('tool_type, family', [
        ('flat end mill', 'milling'),
        ('chamfer mill', 'milling'),
        ('drill', 'hole making'),
        ('tap right hand', 'hole making'),
        ('thread mill', 'hole making'),
        ('probe', 'probe'),
        ('holder', 'holder'),
        ('some future mill', 'other'),
    ])
    def test_family(self, tool_type, family):
        assert cutter.family_of(tool_type) == family

    @pytest.mark.parametrize('tool_type', [
        'turning general', 'turning threading', 'waterjet', 'laser cutter'])
    def test_turning_and_jet_tools_are_out_of_scope(self, tool_type):
        assert cutter.family_of(tool_type) is None
        assert cutter.identify(make_tool(type=tool_type)) is None


class TestBuildObservation:
    def _build(self, tool: dict):
        return build_observation(
            file_id='f', setup_name='Setup1', machine='Example Mill',
            operation_name='Face', strategy='face', tool_json=json.dumps(tool),
            spindle_speed='8000', feed='40 in/min', preset='Aluminum',
            cutting_time_s=12.5)

    def test_reads_number_holder_and_description_from_the_tool(self):
        record = self._build(make_tool())
        assert record.tool_number == 7
        assert record.holder == 'Test Holder'
        assert record.description == '1/2 flat end mill'
        assert record.unit == 'inches'
        assert record.family == 'milling'
        assert json.loads(record.cutter_fields)['DC'] == 12.7

    def test_keeps_the_raw_tool_json(self):
        tool = make_tool()
        assert json.loads(self._build(tool).tool_json) == tool

    def test_tool_without_holder_or_number(self):
        tool = make_tool()
        del tool['holder']
        del tool['post-process']
        record = self._build(tool)
        assert record.holder == ''
        assert record.tool_number is None

    def test_out_of_scope_tool_produces_no_record(self):
        assert self._build(make_tool(type='turning general')) is None
