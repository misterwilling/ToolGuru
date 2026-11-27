"""The folder-scan queue kept in the data file."""

import pytest

from toolguru_lib import store as scan_store
from toolguru_lib.records import FileRef
from toolguru_lib.store import Store, data_path
from toolguru_tests.factories import make_document, make_observation

FILES = [FileRef('a', 'Program a'), FileRef('b', 'Program b'),
         FileRef('c', 'Program c')]


@pytest.fixture
def store(tmp_path) -> Store:
    return Store(data_path(tmp_path))


def test_a_new_data_file_has_no_folder_scan(store):
    assert store.job() is None
    assert store.next_pending() is None


def test_a_new_job_has_every_file_pending_in_folder_order(store):
    store.start_job('Project / Folder', FILES)
    assert store.job() == {
        'folder': 'Project / Folder', 'total': 3, 'pending': 3,
        'scanned': 0, 'unchanged': 0, 'skipped': 0, 'failed': 0, 'problems': []}
    assert store.next_pending() == (0, FileRef('a', 'Program a'))


def test_marking_a_file_moves_on_to_the_next_one(store):
    store.start_job('Folder', FILES)
    store.mark_item(0, scan_store.SCANNED)
    assert store.next_pending() == (1, FileRef('b', 'Program b'))
    assert store.job()['pending'] == 2
    assert store.job()['scanned'] == 1


def test_skipped_and_failed_files_are_listed_with_their_reason(store):
    store.start_job('Folder', FILES)
    store.mark_item(0, scan_store.SKIPPED, 'No Manufacturing data.')
    store.mark_item(1, scan_store.SCANNED)
    store.mark_item(2, scan_store.FAILED, 'RuntimeError: 3')
    job = store.job()
    assert (job['pending'], job['scanned'], job['skipped'], job['failed']) == (
        0, 1, 1, 1)
    assert job['problems'] == [
        {'name': 'Program a', 'status': 'skipped',
         'message': 'No Manufacturing data.'},
        {'name': 'Program c', 'status': 'failed', 'message': 'RuntimeError: 3'}]
    assert store.next_pending() is None


def test_the_queue_survives_reopening_the_data_file(tmp_path):
    Store(data_path(tmp_path)).start_job('Folder', FILES)
    Store(data_path(tmp_path)).mark_item(0, scan_store.SCANNED)
    reopened = Store(data_path(tmp_path))
    assert reopened.next_pending() == (1, FileRef('b', 'Program b'))


def test_a_file_being_opened_is_not_handed_out_again(store):
    store.start_job('Folder', FILES)
    store.mark_item(0, scan_store.OPENING)
    assert store.next_pending() == (1, FileRef('b', 'Program b'))
    assert store.job()['pending'] == 3   # still unsettled


def test_a_file_left_open_by_a_lost_scan_becomes_a_failure(store):
    store.start_job('Folder', FILES)
    store.mark_item(0, scan_store.OPENING)

    assert store.fail_interrupted() == 1

    job = store.job()
    assert (job['pending'], job['failed']) == (2, 1)
    assert job['problems'] == [{
        'name': 'Program a', 'status': 'failed',
        'message': scan_store.INTERRUPTED}]
    assert store.fail_interrupted() == 0


def test_starting_a_job_replaces_the_previous_one(store):
    store.start_job('Old', FILES)
    store.mark_item(0, scan_store.FAILED, 'boom')
    store.start_job('New', FILES[:1])
    assert store.job() == {
        'folder': 'New', 'total': 1, 'pending': 1,
        'scanned': 0, 'unchanged': 0, 'skipped': 0, 'failed': 0, 'problems': []}


def test_ending_a_job_keeps_the_scanned_data(store):
    store.replace_document(make_document('a'), [make_observation('a')])
    store.start_job('Folder', FILES)
    store.end_job()
    assert store.job() is None
    assert store.counts()['documents'] == 1


def test_clearing_the_data_also_clears_the_folder_scan(store):
    store.start_job('Folder', FILES)
    store.clear()
    assert store.job() is None
    assert store.next_pending() is None



def test_remove_document_forgets_its_observations_only(store):
    store.replace_document(make_document('a'), [make_observation('a')])
    store.replace_document(make_document('b'), [make_observation('b')])
    store.remove_document('a')
    assert store.counts() == {'documents': 1, 'observations': 1, 'cutters': 1}
    assert {row['file_id'] for row in store.observation_rows()} == {'b'}


def test_removing_a_document_that_was_never_scanned_changes_nothing(store):
    store.replace_document(make_document('a'), [make_observation('a')])
    store.remove_document('zzz')
    assert store.counts()['documents'] == 1
