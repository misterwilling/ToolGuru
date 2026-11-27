"""The detail of one cutter: its usual setup and the programs that differ."""

from dataclasses import asdict

from toolguru_lib.detail import build_cutter_detail
from toolguru_lib.tally import build_tally
from toolguru_tests.factories import make_holder, make_observation, make_tool

DRILL = make_tool(type='drill', description='Drill')
OTHER_HOLDER = make_holder(**{
    'product-id': 'TH-200', 'description': 'Other Holder',
    'segments': [{'height': 4.0, 'lower-diameter': 2.0, 'upper-diameter': 2.0}]})


def _row(file_id: str = 'a', *, created: int = 100, modified: int = 200,
         number: int | None = 7, **kwargs) -> dict:
    tool = dict(kwargs.pop('tool', None) or make_tool())
    tool['post-process'] = {'number': number}
    row = asdict(make_observation(file_id, tool=tool, **kwargs))
    row['document_name'] = f'Program {file_id}'
    row['date_created'] = created
    row['date_modified'] = modified
    return row


def _detail(rows: list[dict], tolerance_mm: float = 0.5) -> dict:
    return build_cutter_detail(rows, rows[0]['cutter_key'], tolerance_mm)


def _program(detail: dict, file_id: str) -> dict:
    return next(p for p in detail['program_list'] if p['file_id'] == file_id)


def test_a_cutter_that_is_not_in_the_data_has_no_detail():
    assert build_cutter_detail([_row()], 'no-such-cutter', 0.5) is None
    assert build_cutter_detail([], 'anything', 0.5) is None


def test_detail_repeats_the_tally_row_and_adds_the_full_geometry():
    rows = [_row('a', cutting_time_s=30.0), _row('b', cutting_time_s=12.0)]
    detail = _detail(rows)
    tally_row = build_tally(rows)[0]
    assert {name: detail[name] for name in tally_row} == tally_row
    assert detail['fields'] == {
        'DC': 12.7, 'LCF': 31.75, 'NOF': 3, 'OAL': 76.2, 'SFDM': 12.7,
        'material': 'carbide', 'shoulder-length': 31.75}


def test_only_the_asked_cutter_is_counted():
    rows = [_row('a'), _row('a', tool=DRILL), _row('b', tool=DRILL)]
    detail = _detail(rows)
    assert (detail['tool_type'], detail['programs'], detail['operations']) == (
        'flat end mill', 1, 1)
    assert [p['name'] for p in detail['program_list']] == ['Program a']


def test_a_cutter_used_one_way_has_nothing_marked():
    detail = _detail([_row('a'), _row('b')])
    assert detail['usual'] == {
        'tool_number': 7, 'machine': 'Example Mill',
        'assembly_key': detail['assemblies'][0]['assembly_key']}
    for program in detail['program_list']:
        assert program['tool_numbers'] == [{'value': 7, 'usual': True}]
        assert program['machines'] == [{'value': 'Example Mill', 'usual': True}]
        assert [(s['holder'], s['holder_usual'], s['stickout_usual'])
                for s in program['setups']] == [('Test Holder', True, True)]


# --- Tool numbers ------------------------------------------------------------

def test_the_usual_tool_number_is_the_one_most_programs_used():
    rows = [_row('a', number=12), _row('b', number=12),
            _row('c', number=3), _row('c', number=3), _row('c', number=3)]
    detail = _detail(rows)
    assert detail['tool_number_use'] == [
        {'value': 12, 'programs': 2, 'operations': 2},
        {'value': 3, 'programs': 1, 'operations': 3}]
    assert _program(detail, 'a')['tool_numbers'] == [{'value': 12, 'usual': True}]
    assert _program(detail, 'c')['tool_numbers'] == [{'value': 3, 'usual': False}]


def test_a_program_using_two_numbers_lists_both_and_marks_the_odd_one():
    rows = [_row('a', number=12), _row('a', number=40), _row('b', number=12)]
    detail = _detail(rows)
    assert [(use['value'], use['programs']) for use in detail['tool_number_use']] == [
        (12, 2), (40, 1)]
    assert _program(detail, 'a')['tool_numbers'] == [
        {'value': 12, 'usual': True}, {'value': 40, 'usual': False}]


def test_a_tie_between_numbers_goes_to_the_one_with_more_operations():
    rows = [_row('a', number=5), _row('b', number=9), _row('b', number=9)]
    detail = _detail(rows)
    assert [use['value'] for use in detail['tool_number_use']] == [9, 5]
    assert _program(detail, 'a')['tool_numbers'] == [{'value': 5, 'usual': False}]


def test_numbers_used_equally_have_no_usual_one_and_none_is_marked():
    # A fresh tool number in every program: none of them is the odd one.
    rows = [_row('a', number=20), _row('b', number=21), _row('c', number=22)]
    detail = _detail(rows)
    assert detail['usual']['tool_number'] is None
    assert sorted(n['value'] for p in detail['program_list']
                  for n in p['tool_numbers']) == [20, 21, 22]
    assert all(n['usual'] for p in detail['program_list']
               for n in p['tool_numbers'])


def test_a_number_that_leads_by_operations_alone_is_still_the_usual_one():
    rows = [_row('a', number=5), _row('b', number=9), _row('b', number=9)]
    assert _detail(rows)['usual']['tool_number'] == 9


def test_a_program_without_a_tool_number_lists_none_and_marks_nothing():
    rows = [_row('a', number=None), _row('b', number=5)]
    detail = _detail(rows)
    assert detail['tool_number_use'] == [
        {'value': 5, 'programs': 1, 'operations': 1}]
    assert _program(detail, 'a')['tool_numbers'] == []
    assert detail['operations'] == 2


# --- Machines ----------------------------------------------------------------

def test_the_usual_machine_is_the_one_most_programs_used():
    rows = [_row('a'), _row('b'), _row('c', machine='Other Mill'),
            _row('d', machine='')]
    detail = _detail(rows)
    assert detail['machine_use'] == [
        {'value': 'Example Mill', 'programs': 2, 'operations': 2},
        {'value': 'Other Mill', 'programs': 1, 'operations': 1}]
    assert _program(detail, 'a')['machines'] == [
        {'value': 'Example Mill', 'usual': True}]
    assert _program(detail, 'c')['machines'] == [
        {'value': 'Other Mill', 'usual': False}]
    assert _program(detail, 'd')['machines'] == []


def test_machines_used_equally_have_no_usual_one_and_none_is_marked():
    rows = [_row('a'), _row('b', machine='Other Mill')]
    detail = _detail(rows)
    assert detail['usual']['machine'] is None
    assert _program(detail, 'b')['machines'] == [
        {'value': 'Other Mill', 'usual': True}]


def test_a_cutter_with_no_machine_set_anywhere_has_no_usual_machine():
    detail = _detail([_row('a', machine=''), _row('b', machine='')])
    assert (detail['machine_use'], detail['usual']['machine']) == ([], None)


# --- Holder and stickout -----------------------------------------------------

def test_assemblies_are_listed_with_the_most_programs_first():
    long_reach = make_tool(geometry={'LB': 2.5})
    rows = [_row('a'), _row('b'),
            _row('c', tool=long_reach), _row('c', tool=long_reach),
            _row('c', tool=long_reach), _row('d', tool=make_tool(holder=OTHER_HOLDER))]
    detail = _detail(rows)
    assert [(a['holder'], a['stickout_min_mm'], a['stickout_max_mm'],
             a['programs'], a['operations']) for a in detail['assemblies']] == [
        ('Test Holder', 38.1, 38.1, 2, 2),
        ('Test Holder', 63.5, 63.5, 1, 3),
        ('Other Holder', 38.1, 38.1, 1, 1)]
    assert set(detail['assemblies'][0]) == {
        'assembly_key', 'holder', 'stickout_min_mm', 'stickout_max_mm',
        'programs', 'operations', 'time_s'}


def test_the_usual_assembly_is_the_one_most_programs_used():
    rows = [_row('a'), _row('b'), _row('c', tool=make_tool(holder=OTHER_HOLDER))]
    detail = _detail(rows)
    assert detail['usual']['assembly_key'] == detail['assemblies'][0]['assembly_key']
    assert detail['assemblies'][0]['holder'] == 'Test Holder'


def test_assemblies_used_equally_have_no_usual_one_and_none_is_marked():
    odd = make_tool(holder=OTHER_HOLDER, geometry={'LB': 2.5})
    detail = _detail([_row('a'), _row('b', tool=odd)])
    assert detail['usual']['assembly_key'] is None
    assert [(s['holder_usual'], s['stickout_usual'])
            for p in detail['program_list'] for s in p['setups']] == [
        (True, True), (True, True)]


def test_a_different_holder_at_the_usual_stickout_marks_only_the_holder():
    rows = [_row('a'), _row('b'), _row('c', tool=make_tool(holder=OTHER_HOLDER))]
    setups = _program(_detail(rows), 'c')['setups']
    assert setups == [{
        'holder': 'Other Holder', 'holder_usual': False,
        'stickout_min_mm': 38.1, 'stickout_max_mm': 38.1, 'stickout_usual': True,
        'operations': 1}]


def test_the_usual_holder_at_a_different_stickout_marks_only_the_stickout():
    rows = [_row('a'), _row('b'), _row('c', tool=make_tool(geometry={'LB': 2.5}))]
    setups = _program(_detail(rows), 'c')['setups']
    assert [(s['holder'], s['holder_usual'], s['stickout_min_mm'], s['stickout_usual'])
            for s in setups] == [('Test Holder', True, 63.5, False)]


def test_a_different_holder_and_stickout_marks_both():
    odd = make_tool(holder=OTHER_HOLDER, geometry={'LB': 2.5})
    rows = [_row('a'), _row('b'), _row('c', tool=odd)]
    setups = _program(_detail(rows), 'c')['setups']
    assert [(s['holder_usual'], s['stickout_usual']) for s in setups] == [(False, False)]


def test_a_stickout_within_the_tolerance_of_the_usual_one_is_not_marked():
    close = make_tool(holder=OTHER_HOLDER, geometry={'LB': 1.51})   # 0.254 mm longer
    rows = [_row('a'), _row('b'), _row('c', tool=close)]
    assert _program(_detail(rows, 0.5), 'c')['setups'][0]['stickout_usual'] is True
    assert _program(_detail(rows, 0.1), 'c')['setups'][0]['stickout_usual'] is False


def test_a_stickout_shorter_than_the_usual_one_is_marked():
    short = make_tool(holder=OTHER_HOLDER, geometry={'LB': 1.49})
    rows = [_row('a'), _row('b'), _row('c', tool=short)]
    assert _program(_detail(rows, 0.5), 'c')['setups'][0]['stickout_usual'] is False


def test_the_stickout_tolerance_decides_how_assemblies_are_grouped():
    rows = [_row('a'), _row('b', tool=make_tool(geometry={'LB': 1.51}))]
    assert len(_detail(rows, 0.5)['assemblies']) == 1
    assert len(_detail(rows, 0.0)['assemblies']) == 2


def test_a_program_using_two_setups_lists_both_with_its_own_stickouts():
    long_reach = make_tool(geometry={'LB': 2.5})
    rows = [_row('a'), _row('b'), _row('c'), _row('c', tool=long_reach),
            _row('c', tool=long_reach)]
    setups = _program(_detail(rows), 'c')['setups']
    assert [(s['stickout_min_mm'], s['stickout_usual'], s['operations'])
            for s in setups] == [(63.5, False, 2), (38.1, True, 1)]


def test_a_setups_stickout_range_is_the_programs_own_not_the_assemblys():
    rows = [_row('a'), _row('b', tool=make_tool(geometry={'LB': 1.51}))]
    detail = _detail(rows, 0.5)
    assert (detail['assemblies'][0]['stickout_min_mm'],
            detail['assemblies'][0]['stickout_max_mm']) == (38.1, 38.354)
    setup = _program(detail, 'b')['setups'][0]
    assert (setup['stickout_min_mm'], setup['stickout_max_mm']) == (38.354, 38.354)
    assert setup['stickout_usual'] is True


def test_tools_without_a_recorded_stickout_match_each_other_only():
    no_reach = make_tool(geometry={'LB': None})
    rows = [_row('a', tool=no_reach), _row('b', tool=no_reach), _row('c')]
    detail = _detail(rows)
    assert _program(detail, 'a')['setups'][0]['stickout_usual'] is True
    assert _program(detail, 'a')['setups'][0]['stickout_min_mm'] is None
    assert _program(detail, 'c')['setups'][0]['stickout_usual'] is False


# --- Programs ----------------------------------------------------------------

def test_programs_are_listed_latest_first_with_their_own_figures():
    rows = [_row('old', modified=200, cutting_time_s=10.0),
            _row('new', modified=900, cutting_time_s=4.0, number=9),
            _row('new', modified=900, cutting_time_s=None, number=9)]
    detail = _detail(rows)
    assert [(p['file_id'], p['name'], p['last_saved'], p['operations'], p['time_s'])
            for p in detail['program_list']] == [
        ('new', 'Program new', 900, 2, 4.0),
        ('old', 'Program old', 200, 1, 10.0)]


# --- Speeds and feeds ---------------------------------------------------------

def test_speeds_give_the_range_and_the_value_most_operations_used():
    rows = [_row('a', spindle_rpm=8000.0, feed_mm_min=1016.0),
            _row('a', spindle_rpm=8000.0, feed_mm_min=1016.0),
            _row('b', spindle_rpm=12000.0, feed_mm_min=1524.0),
            _row('c', spindle_rpm=6000.0, feed_mm_min=508.0)]
    assert _detail(rows)['speeds'] == {
        'spindle_rpm': {'min': 6000.0, 'max': 12000.0, 'most_used': 8000.0,
                        'operations': 4},
        'feed_mm_min': {'min': 508.0, 'max': 1524.0, 'most_used': 1016.0,
                        'operations': 4},
        'operations_without': 0,
    }


def test_values_used_equally_often_have_no_most_used_one():
    rows = [_row('a', spindle_rpm=8000.0), _row('b', spindle_rpm=9000.0)]
    assert _detail(rows)['speeds']['spindle_rpm'] == {
        'min': 8000.0, 'max': 9000.0, 'most_used': None, 'operations': 2}


def test_operations_without_numbers_are_counted_and_left_out_of_the_range():
    """Rows scanned before the numbers were recorded hold nothing for them."""
    rows = [_row('a', spindle_rpm=8000.0, feed_mm_min=1016.0),
            _row('b', spindle_rpm=None, feed_mm_min=None),
            _row('c', spindle_rpm=None, feed_mm_min=None)]
    speeds = _detail(rows)['speeds']
    assert speeds['spindle_rpm'] == {
        'min': 8000.0, 'max': 8000.0, 'most_used': 8000.0, 'operations': 1}
    assert speeds['operations_without'] == 2


def test_a_cutter_with_no_numbers_at_all_has_no_range():
    rows = [_row('a', spindle_rpm=None, feed_mm_min=None)]
    assert _detail(rows)['speeds'] == {
        'spindle_rpm': None, 'feed_mm_min': None, 'operations_without': 1}


def test_an_operation_with_a_speed_but_no_feed_still_counts_as_having_numbers():
    rows = [_row('a', spindle_rpm=500.0, feed_mm_min=None)]
    speeds = _detail(rows)['speeds']
    assert speeds['feed_mm_min'] is None
    assert speeds['operations_without'] == 0
