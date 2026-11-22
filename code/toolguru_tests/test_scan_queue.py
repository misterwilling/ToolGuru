"""The folder-scan queue kept in a dataset file."""

import pytest

from toolguru_lib import store as scan_store
from toolguru_lib.records import FileRef
from toolguru_lib.store import Store, dataset_path
from toolguru_tests.factories import make_document, make_observation

FILES = [FileRef('a', 'Program a'), FileRef('b', 'Program b'),
         FileRef('c', 'Program c')]


@pytest.fixture
def trial(tmp_path) -> Store:
    return Store(dataset_path('trial', tmp_path))


def test_a_dataset_starts_with_no_folder_scan(trial):
    assert trial.job() is None
    assert trial.next_pending() is None


def test_a_new_job_has_every_file_pending_in_folder_order(trial):
    trial.start_job('Project / Folder', FILES)
    assert trial.job() == {
        'folder': 'Project / Folder', 'total': 3, 'pending': 3,
        'scanned': 0, 'skipped': 0, 'failed': 0, 'problems': []}
    assert trial.next_pending() == (0, FileRef('a', 'Program a'))


def test_marking_a_file_moves_on_to_the_next_one(trial):
    trial.start_job('Folder', FILES)
    trial.mark_item(0, scan_store.SCANNED)
    assert trial.next_pending() == (1, FileRef('b', 'Program b'))
    assert trial.job()['pending'] == 2
    assert trial.job()['scanned'] == 1


def test_skipped_and_failed_files_are_listed_with_their_reason(trial):
    trial.start_job('Folder', FILES)
    trial.mark_item(0, scan_store.SKIPPED, 'No Manufacturing data.')
    trial.mark_item(1, scan_store.SCANNED)
    trial.mark_item(2, scan_store.FAILED, 'RuntimeError: 3')
    job = trial.job()
    assert (job['pending'], job['scanned'], job['skipped'], job['failed']) == (
        0, 1, 1, 1)
    assert job['problems'] == [
        {'name': 'Program a', 'status': 'skipped',
         'message': 'No Manufacturing data.'},
        {'name': 'Program c', 'status': 'failed', 'message': 'RuntimeError: 3'}]
    assert trial.next_pending() is None


def test_the_queue_survives_reopening_the_dataset_file(tmp_path):
    Store(dataset_path('trial', tmp_path)).start_job('Folder', FILES)
    Store(dataset_path('trial', tmp_path)).mark_item(0, scan_store.SCANNED)
    reopened = Store(dataset_path('trial', tmp_path))
    assert reopened.next_pending() == (1, FileRef('b', 'Program b'))


def test_a_file_being_opened_is_not_handed_out_again(trial):
    trial.start_job('Folder', FILES)
    trial.mark_item(0, scan_store.OPENING)
    assert trial.next_pending() == (1, FileRef('b', 'Program b'))
    assert trial.job()['pending'] == 3   # still unsettled


def test_a_file_left_open_by_a_lost_scan_becomes_a_failure(trial):
    trial.start_job('Folder', FILES)
    trial.mark_item(0, scan_store.OPENING)

    assert trial.fail_interrupted() == 1

    job = trial.job()
    assert (job['pending'], job['failed']) == (2, 1)
    assert job['problems'] == [{
        'name': 'Program a', 'status': 'failed',
        'message': scan_store.INTERRUPTED}]
    assert trial.fail_interrupted() == 0


def test_starting_a_job_replaces_the_previous_one(trial):
    trial.start_job('Old', FILES)
    trial.mark_item(0, scan_store.FAILED, 'boom')
    trial.start_job('New', FILES[:1])
    assert trial.job() == {
        'folder': 'New', 'total': 1, 'pending': 1,
        'scanned': 0, 'skipped': 0, 'failed': 0, 'problems': []}


def test_ending_a_job_keeps_the_scanned_data(trial):
    trial.replace_document(make_document('a'), [make_observation('a')])
    trial.start_job('Folder', FILES)
    trial.end_job()
    assert trial.job() is None
    assert trial.counts()['documents'] == 1


def test_clearing_the_dataset_also_clears_the_folder_scan(trial):
    trial.start_job('Folder', FILES)
    trial.clear()
    assert trial.job() is None
    assert trial.next_pending() is None


def test_each_dataset_has_its_own_folder_scan(tmp_path):
    Store(dataset_path('trial', tmp_path)).start_job('Folder', FILES)
    assert Store(dataset_path('main', tmp_path)).job() is None


def test_remove_document_forgets_its_observations_only(trial):
    trial.replace_document(make_document('a'), [make_observation('a')])
    trial.replace_document(make_document('b'), [make_observation('b')])
    trial.remove_document('a')
    assert trial.counts() == {'documents': 1, 'observations': 1, 'cutters': 1}
    assert {row['file_id'] for row in trial.observation_rows()} == {'b'}


def test_removing_a_document_that_was_never_scanned_changes_nothing(trial):
    trial.replace_document(make_document('a'), [make_observation('a')])
    trial.remove_document('zzz')
    assert trial.counts()['documents'] == 1
