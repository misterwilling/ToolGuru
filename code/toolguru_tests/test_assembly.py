"""Holder and stickout: the parts of an assembly beyond the cutter."""

from toolguru_lib import assembly
from toolguru_tests.factories import make_holder, make_tool

# The default test holder (inches) written out in millimetres.
METRIC_SEGMENTS = [
    {'height': 25.4, 'lower-diameter': 25.4, 'upper-diameter': 31.75},
    {'height': 50.8, 'lower-diameter': 44.45, 'upper-diameter': 44.45},
]


def test_reads_product_id_label_and_stickout():
    held = assembly.describe(make_tool())
    assert held.holder_product_id == 'th-100'
    assert held.holder_label == 'Test Holder'
    assert held.stickout_mm == 38.1   # LB 1.5 in
    assert len(held.holder_shape) == 16


def test_product_id_ignores_case_and_spacing():
    assert assembly.normalize_product_id('  TH 100 /  Long X 4.00 ') == 'th 100 / long x 4.00'
    tidy = assembly.describe(make_tool(holder=make_holder(**{'product-id': 'th-100'})))
    messy = assembly.describe(make_tool(holder=make_holder(**{'product-id': ' TH-100  '})))
    assert tidy.holder_product_id == messy.holder_product_id == 'th-100'


def test_same_holder_in_inches_and_millimetres_has_one_shape():
    inch = assembly.describe(make_tool())
    metric = assembly.describe(make_tool(
        holder=make_holder(unit='millimeters', segments=METRIC_SEGMENTS)))
    assert inch.holder_shape == metric.holder_shape


def test_shape_ignores_name_vendor_and_product_id():
    renamed = make_holder(description='Renamed', vendor='Other', **{'product-id': ''})
    assert (assembly.describe(make_tool(holder=renamed)).holder_shape
            == assembly.describe(make_tool()).holder_shape)


def test_a_different_profile_is_a_different_shape():
    longer = make_holder(segments=[
        {'height': 1.0, 'lower-diameter': 1.0, 'upper-diameter': 1.25},
        {'height': 3.0, 'lower-diameter': 1.75, 'upper-diameter': 1.75}])
    assert (assembly.describe(make_tool(holder=longer)).holder_shape
            != assembly.describe(make_tool()).holder_shape)


def test_shape_differences_under_a_hundredth_of_a_millimetre_are_ignored():
    nudged = make_holder(segments=[
        {'height': 1.0001, 'lower-diameter': 1.0, 'upper-diameter': 1.25},
        {'height': 2.0, 'lower-diameter': 1.75, 'upper-diameter': 1.75}])
    assert (assembly.describe(make_tool(holder=nudged)).holder_shape
            == assembly.describe(make_tool()).holder_shape)


def test_holder_unit_defaults_to_the_tool_unit():
    holder = make_holder()
    del holder['unit']
    assert (assembly.describe(make_tool(holder=holder)).holder_shape
            == assembly.describe(make_tool()).holder_shape)


def test_label_falls_back_to_the_product_id():
    held = assembly.describe(make_tool(holder=make_holder(description='')))
    assert held.holder_label == 'TH-100'


def test_tool_with_no_holder():
    tool = make_tool()
    del tool['holder']
    held = assembly.describe(tool)
    assert (held.holder_product_id, held.holder_shape, held.holder_label) == ('', '', '')
    assert held.stickout_mm == 38.1


def test_stickout_is_converted_from_the_tool_unit():
    metric = make_tool(unit='millimeters', geometry={'LB': 38.1},
                       holder=make_holder(unit='millimeters', segments=METRIC_SEGMENTS))
    assert assembly.describe(metric).stickout_mm == 38.1


def test_missing_stickout_is_unknown_not_zero():
    tool = make_tool()
    del tool['geometry']['LB']
    assert assembly.describe(tool).stickout_mm is None
