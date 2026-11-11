"""The usage tally: one row per cutter, counted from operations."""

from dataclasses import asdict

from toolguru_lib.tally import build_tally
from toolguru_tests.factories import make_observation, make_tool


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
