"""Scan storage: rescans replace, and a reset backs up before it empties."""

import sqlite3
from contextlib import closing

import pytest

from toolguru_lib.store import Store, data_path
from toolguru_tests.factories import make_document, make_observation, make_tool


@pytest.fixture
def store(tmp_path) -> Store:
    return Store(data_path(tmp_path))


def test_the_data_is_kept_in_one_file_in_the_data_folder(tmp_path):
    assert data_path(tmp_path) == tmp_path / 'toolguru.sqlite'


def test_a_new_data_file_is_empty(store):
    assert store.counts() == {'documents': 0, 'observations': 0, 'cutters': 0}
    assert store.observation_rows() == []


def test_document_with_no_operations_is_still_recorded(store):
    store.replace_document(make_document(), [])
    assert store.counts() == {'documents': 1, 'observations': 0, 'cutters': 0}


def test_counts_documents_observations_and_distinct_cutters(store):
    ball = make_tool(type='ball end mill')
    store.replace_document(make_document('a'), [
        make_observation('a'), make_observation('a'), make_observation('a', tool=ball)])
    store.replace_document(make_document('b'), [make_observation('b')])
    assert store.counts() == {'documents': 2, 'observations': 4, 'cutters': 2}


def test_rescanning_a_document_replaces_its_observations(store):
    store.replace_document(make_document('a'), [make_observation('a'), make_observation('a')])
    store.replace_document(make_document('b'), [make_observation('b')])
    store.replace_document(make_document('a'), [make_observation('a')])
    assert store.counts() == {'documents': 2, 'observations': 2, 'cutters': 1}


def test_scanning_the_same_document_twice_does_not_double_counts(store):
    observations = [make_observation('a'), make_observation('a')]
    store.replace_document(make_document('a'), observations)
    first = store.counts()
    store.replace_document(make_document('a'), observations)
    assert store.counts() == first == {'documents': 1, 'observations': 2, 'cutters': 1}


def test_observation_round_trips_with_document_name_and_dates(store):
    document = make_document('a', date_created=100, date_modified=200)
    observation = make_observation('a', cutting_time_s=None)
    store.replace_document(document, [observation])
    row = store.observation_rows()[0]
    assert row['file_id'] == 'a'
    assert row['document_name'] == 'Program a'
    assert row['cutter_key'] == observation.cutter_key
    assert row['tool_number'] == 7
    assert row['cutting_time_s'] is None
    assert row['tool_json'] == observation.tool_json
    assert (row['date_created'], row['date_modified']) == (100, 200)


def test_clear_empties_the_data(store):
    store.replace_document(make_document('a'), [make_observation('a')])
    store.clear()
    assert store.counts() == {'documents': 0, 'observations': 0, 'cutters': 0}


def test_clear_then_rescan_gives_the_same_result(store):
    observations = [make_observation('a'), make_observation('a', tool=make_tool(type='drill'))]
    store.replace_document(make_document('a'), observations)
    before = (store.counts(), [r['cutter_key'] for r in store.observation_rows()])
    store.clear()
    store.replace_document(make_document('a'), observations)
    assert (store.counts(), [r['cutter_key'] for r in store.observation_rows()]) == before


def test_backup_and_clear_writes_the_backup_before_clearing(store, tmp_path):
    store.replace_document(make_document('m'), [make_observation('m')])
    original = store.path.read_bytes()

    backup = store.backup_and_clear('20260101-120000')

    assert backup == tmp_path / 'toolguru-backup-20260101-120000.sqlite'
    assert backup.read_bytes() == original
    assert Store(backup).counts() == {'documents': 1, 'observations': 1, 'cutters': 1}
    assert store.counts() == {'documents': 0, 'observations': 0, 'cutters': 0}


def test_backup_never_overwrites_an_existing_backup(store):
    store.replace_document(make_document('m'), [make_observation('m')])
    store.backup_and_clear('stamp')
    store.replace_document(make_document('n'), [make_observation('n')])

    with pytest.raises(FileExistsError):
        store.backup_and_clear('stamp')
    assert store.counts()['documents'] == 1


def test_holder_and_stickout_round_trip(store):
    observation = make_observation('a')
    store.replace_document(make_document('a'), [observation])
    row = store.observation_rows()[0]
    assert row['holder'] == 'Test Holder'
    assert row['holder_product_id'] == 'th-100'
    assert row['holder_shape'] == observation.holder_shape != ''
    assert row['stickout_mm'] == 38.1


def test_a_file_from_before_holders_were_recorded_is_upgraded(store):
    """A file written by the first release has no holder columns. Opening it
    adds them and fills them from the stored tool JSON, so no rescan is needed."""
    observation = make_observation('a')
    store.replace_document(make_document('a'), [observation])
    with closing(sqlite3.connect(store.path)) as conn, conn:
        for column in ('holder_product_id', 'holder_shape', 'stickout_mm'):
            conn.execute(f'ALTER TABLE observations DROP COLUMN {column}')

    reopened = Store(store.path)

    row = reopened.observation_rows()[0]
    assert row['holder_product_id'] == 'th-100'
    assert row['holder_shape'] == observation.holder_shape
    assert row['stickout_mm'] == 38.1
    reopened.replace_document(make_document('b'), [make_observation('b')])
    assert reopened.counts() == {'documents': 2, 'observations': 2, 'cutters': 1}


def test_speed_and_feed_numbers_round_trip(store):
    store.replace_document(make_document('a'), [
        make_observation('a', spindle_rpm=8000.0, feed_mm_min=1016.0)])
    row = store.observation_rows()[0]
    assert (row['spindle_rpm'], row['feed_mm_min']) == (8000.0, 1016.0)
    assert (row['spindle_speed'], row['feed']) == ('8000', '40 in/min')


def test_a_speed_or_feed_of_zero_is_stored_as_not_set(store):
    """Fusion holds zero for a speed nobody set; it must not drag a range to 0."""
    store.replace_document(make_document('a'), [
        make_observation('a', spindle_rpm=0.0, feed_mm_min=0.0)])
    row = store.observation_rows()[0]
    assert (row['spindle_rpm'], row['feed_mm_min']) == (None, None)


def test_a_feed_is_stored_to_a_thousandth(store):
    store.replace_document(make_document('a'), [
        make_observation('a', feed_mm_min=338.6666666666667)])
    assert store.observation_rows()[0]['feed_mm_min'] == 338.667


def test_a_file_from_before_speeds_were_numbers_gains_empty_columns(store):
    """The numbers cannot be worked out from what an older file holds, so
    they stay empty until a rescan, and everything else is left as it was."""
    observation = make_observation('a')
    store.replace_document(make_document('a'), [observation])
    with closing(sqlite3.connect(store.path)) as conn, conn:
        for column in ('spindle_rpm', 'feed_mm_min'):
            conn.execute(f'ALTER TABLE observations DROP COLUMN {column}')
        conn.execute("UPDATE observations SET holder_shape = 'kept'")

    reopened = Store(store.path)

    row = reopened.observation_rows()[0]
    assert (row['spindle_rpm'], row['feed_mm_min']) == (None, None)
    assert row['holder_shape'] == 'kept'   # the holder columns were not refilled
    reopened.replace_document(make_document('b'), [make_observation('b')])
    assert reopened.observation_rows()[1]['spindle_rpm'] == 8000.0
