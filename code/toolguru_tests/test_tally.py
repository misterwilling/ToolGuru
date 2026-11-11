"""The usage tally: one row per cutter, counted from operations."""

from dataclasses import asdict

from toolguru_lib.tally import build_assembly_tally, build_tally
from toolguru_tests.factories import make_holder, make_observation, make_tool


def _row(file_id: str = 'a', *, created: int = 100, modified: int = 200, **kwargs) -> dict:
    row = asdict(make_observation(file_id, **kwargs))
    row['date_created'] = created
    row['date_modified'] = modified
    return row


def test_no_observations_gives_no_rows():
    assert build_tally([]) == []


def test_single_observation():
    tally = build_tally([_row(cutting_time_s=42.0)])
    assert len(tally) == 1
    row = tally[0]
    assert row['tool_type'] == 'flat end mill'
    assert row['family'] == 'milling'
    assert row['description'] == '1/2 flat end mill'
    assert row['diameter_mm'] == 12.7
    assert row['flutes'] == 3
    assert row['programs'] == 1
    assert row['operations'] == 1
    assert row['time_s'] == 42.0
    assert row['operations_without_time'] == 0
    assert (row['first_used'], row['last_used']) == (100, 200)
    assert row['tool_numbers'] == [7]
    assert row['machines'] == ['Example Mill']
    assert row['units'] == ['inches']


def test_programs_and_operations_are_counted_separately():
    rows = [_row('a'), _row('a'), _row('a'), _row('b')]
    row = build_tally(rows)[0]
    assert row['programs'] == 2
    assert row['operations'] == 4


def test_time_sums_known_times_and_counts_the_unknown():
    rows = [_row(cutting_time_s=10.5), _row(cutting_time_s=None),
            _row(cutting_time_s=4.5), _row(cutting_time_s=None)]
    row = build_tally(rows)[0]
    assert row['time_s'] == 15.0
    assert row['operations_without_time'] == 2


def test_first_and_last_used_span_all_programs():
    rows = [_row('a', created=500, modified=900),
            _row('b', created=300, modified=400),
            _row('c', created=700, modified=1200)]
    row = build_tally(rows)[0]
    assert (row['first_used'], row['last_used']) == (300, 1200)


def test_same_cutter_under_different_numbers_units_and_machines_is_one_row():
    renumbered = make_tool(description='half inch EM')
    renumbered['post-process'] = {'number': 344}
    metric = make_tool(unit='millimeters', geometry={
        'DC': 12.7, 'LCF': 31.75, 'shoulder-length': 31.75, 'OAL': 76.2, 'SFDM': 12.7})
    rows = [_row('a'), _row('a', tool=renumbered),
            _row('b', tool=metric, machine='Other Mill')]
    tally = build_tally(rows)
    assert len(tally) == 1
    assert tally[0]['tool_numbers'] == [7, 344]
    assert tally[0]['machines'] == ['Example Mill', 'Other Mill']
    assert tally[0]['units'] == ['inches', 'millimeters']


def test_description_is_the_most_common_one():
    odd = make_tool(description='odd name')
    rows = [_row(), _row(tool=odd), _row()]
    assert build_tally(rows)[0]['description'] == '1/2 flat end mill'


def test_different_cutters_are_separate_rows_most_used_first():
    drill = make_tool(type='drill', description='drill')
    rows = [_row(tool=drill), _row(), _row()]
    tally = build_tally(rows)
    assert [(r['tool_type'], r['operations']) for r in tally] == [
        ('flat end mill', 2), ('drill', 1)]


# --- Counting by assembly: cutter + holder + stickout ------------------------

OTHER_SEGMENTS = [{'height': 4.0, 'lower-diameter': 2.0, 'upper-diameter': 2.0}]


def _held(file_id: str = 'a', *, stickout_in: float = 1.5, **holder) -> dict:
    """An observation of the default cutter with the given holder and stickout."""
    tool = make_tool(geometry={'LB': stickout_in}, holder=make_holder(**holder))
    return _row(file_id, tool=tool)


def test_assembly_tally_of_nothing_is_empty():
    assert build_assembly_tally([], 0.5) == []


def test_assembly_row_adds_holder_and_stickout_to_the_cutter_figures():
    rows = [_held('a'), _held('b')]
    tally = build_assembly_tally(rows, 0.5)
    assert len(tally) == 1
    row = tally[0]
    assert row['holder'] == 'Test Holder'
    assert (row['stickout_min_mm'], row['stickout_max_mm']) == (38.1, 38.1)
    assert (row['programs'], row['operations']) == (2, 2)
    assert row['cutter_key'] == build_tally(rows)[0]['cutter_key']
    assert row['assembly_key'].startswith(row['cutter_key'] + '|id:th-100|38.100')


def test_same_cutter_in_a_different_holder_is_a_different_assembly():
    other = {'product-id': 'TH-200', 'description': 'Other Holder',
             'segments': OTHER_SEGMENTS}
    rows = [_held(), _held(), _held(**other)]
    assert len(build_tally(rows)) == 1
    assert [(t['holder'], t['operations']) for t in build_assembly_tally(rows, 0.5)] == [
        ('Test Holder', 2), ('Other Holder', 1)]


def test_same_product_id_is_the_same_holder_even_if_the_shape_differs():
    rows = [_held(), _held(segments=OTHER_SEGMENTS)]
    assert [t['operations'] for t in build_assembly_tally(rows, 0.5)] == [2]


def test_blank_product_id_matches_a_named_holder_of_the_same_shape():
    rows = [_held(), _held(**{'product-id': ''})]
    assert [t['operations'] for t in build_assembly_tally(rows, 0.5)] == [2]


def test_product_id_typed_two_ways_is_one_holder_when_the_shape_matches():
    rows = [_held(), _held(**{'product-id': 'TH 100 (4.00)'})]
    assert [t['operations'] for t in build_assembly_tally(rows, 0.5)] == [2]


def test_blank_product_id_and_a_different_shape_is_a_different_holder():
    rows = [_held(), _held(**{'product-id': '', 'segments': OTHER_SEGMENTS})]
    assert [t['operations'] for t in build_assembly_tally(rows, 0.5)] == [1, 1]


def test_holders_are_matched_the_same_way_whatever_order_rows_arrive_in():
    rows = [_held(**{'product-id': ''}), _held(**{'product-id': 'TH 100 (4.00)'}), _held()]
    forward = build_assembly_tally(rows, 0.5)
    backward = build_assembly_tally(rows[::-1], 0.5)
    assert [t['assembly_key'] for t in forward] == [t['assembly_key'] for t in backward]
    assert [t['operations'] for t in forward] == [3]


def test_tools_without_a_holder_are_grouped_together():
    bare = make_tool()
    del bare['holder']
    rows = [_row(tool=bare), _row(tool=bare), _held()]
    tally = build_assembly_tally(rows, 0.5)
    assert [(t['holder'], t['operations']) for t in tally] == [('', 2), ('Test Holder', 1)]


def test_stickout_within_tolerance_is_one_assembly_showing_the_range():
    rows = [_held(stickout_in=1.5), _held(stickout_in=1.51)]   # 38.1 and 38.354 mm
    tally = build_assembly_tally(rows, 0.5)
    assert len(tally) == 1
    assert (tally[0]['stickout_min_mm'], tally[0]['stickout_max_mm']) == (38.1, 38.354)


def test_stickout_outside_tolerance_is_two_assemblies():
    rows = [_held(stickout_in=1.5), _held(stickout_in=1.6), _held(stickout_in=1.6)]
    tally = build_assembly_tally(rows, 0.5)
    assert [(t['stickout_min_mm'], t['operations']) for t in tally] == [
        (40.64, 2), (38.1, 1)]


def test_stickout_exactly_at_the_tolerance_still_matches():
    metric = [_row(tool=make_tool(unit='millimeters', geometry={'LB': lb}))
              for lb in (40.0, 40.5)]
    assert len(build_assembly_tally(metric, 0.5)) == 1


def test_zero_tolerance_needs_an_exact_stickout():
    rows = [_held(stickout_in=1.5), _held(stickout_in=1.5), _held(stickout_in=1.5001)]
    assert [t['operations'] for t in build_assembly_tally(rows, 0)] == [2, 1]


def test_a_run_of_close_stickouts_never_becomes_one_wide_assembly():
    # 40.0, 40.4, 40.8: each is within 0.5 of its neighbour, but 40.8 is not
    # within 0.5 of 40.0.
    rows = [_row(tool=make_tool(unit='millimeters', geometry={'LB': lb}))
            for lb in (40.8, 40.0, 40.4)]
    tally = build_assembly_tally(rows, 0.5)
    assert sorted((t['stickout_min_mm'], t['stickout_max_mm']) for t in tally) == [
        (40.0, 40.4), (40.8, 40.8)]


def test_unknown_stickout_is_its_own_assembly():
    unknown = make_tool()
    del unknown['geometry']['LB']
    rows = [_held(), _row(tool=unknown), _row(tool=unknown)]
    tally = build_assembly_tally(rows, 0.5)
    assert [(t['stickout_min_mm'], t['stickout_max_mm'], t['operations']) for t in tally] == [
        (None, None, 2), (38.1, 38.1, 1)]


def test_different_cutters_in_the_same_holder_stay_separate():
    rows = [_held(), _row(tool=make_tool(type='ball end mill'))]
    assert len(build_assembly_tally(rows, 0.5)) == 2


def test_counting_by_cutter_ignores_holder_and_stickout():
    rows = [_held(), _held(stickout_in=3.0),
            _held(**{'product-id': 'TH-200', 'segments': OTHER_SEGMENTS})]
    assert [t['operations'] for t in build_tally(rows)] == [3]
