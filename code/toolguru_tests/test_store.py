"""Scan storage: rescans replace, Trial and Main never touch each other."""

import pytest

from toolguru_lib.store import Store, dataset_path
from toolguru_tests.factories import make_document, make_observation, make_tool


@pytest.fixture
def trial(tmp_path) -> Store:
    return Store(dataset_path('trial', tmp_path))


def test_new_dataset_is_empty(trial):
    assert trial.counts() == {'documents': 0, 'observations': 0, 'cutters': 0}
    assert trial.observation_rows() == []


def test_document_with_no_operations_is_still_recorded(trial):
    trial.replace_document(make_document(), [])
    assert trial.counts() == {'documents': 1, 'observations': 0, 'cutters': 0}


def test_counts_documents_observations_and_distinct_cutters(trial):
    ball = make_tool(type='ball end mill')
    trial.replace_document(make_document('a'), [
        make_observation('a'), make_observation('a'), make_observation('a', tool=ball)])
    trial.replace_document(make_document('b'), [make_observation('b')])
    assert trial.counts() == {'documents': 2, 'observations': 4, 'cutters': 2}


def test_rescanning_a_document_replaces_its_observations(trial):
    trial.replace_document(make_document('a'), [make_observation('a'), make_observation('a')])
    trial.replace_document(make_document('b'), [make_observation('b')])
    trial.replace_document(make_document('a'), [make_observation('a')])
    assert trial.counts() == {'documents': 2, 'observations': 2, 'cutters': 1}


def test_scanning_the_same_document_twice_does_not_double_counts(trial):
    observations = [make_observation('a'), make_observation('a')]
    trial.replace_document(make_document('a'), observations)
    first = trial.counts()
    trial.replace_document(make_document('a'), observations)
    assert trial.counts() == first == {'documents': 1, 'observations': 2, 'cutters': 1}


def test_observation_round_trips_with_document_dates(trial):
    document = make_document('a', date_created=100, date_modified=200)
    observation = make_observation('a', cutting_time_s=None)
    trial.replace_document(document, [observation])
    row = trial.observation_rows()[0]
    assert row['file_id'] == 'a'
    assert row['cutter_key'] == observation.cutter_key
    assert row['tool_number'] == 7
    assert row['cutting_time_s'] is None
    assert row['tool_json'] == observation.tool_json
    assert (row['date_created'], row['date_modified']) == (100, 200)


def test_clear_returns_the_dataset_to_empty(trial):
    trial.replace_document(make_document('a'), [make_observation('a')])
    trial.clear()
    assert trial.counts() == {'documents': 0, 'observations': 0, 'cutters': 0}


def test_clear_then_rescan_gives_the_same_result(trial):
    observations = [make_observation('a'), make_observation('a', tool=make_tool(type='drill'))]
    trial.replace_document(make_document('a'), observations)
    before = (trial.counts(), [r['cutter_key'] for r in trial.observation_rows()])
    trial.clear()
    trial.replace_document(make_document('a'), observations)
    assert (trial.counts(), [r['cutter_key'] for r in trial.observation_rows()]) == before


def test_clearing_trial_leaves_main_byte_identical(tmp_path):
    trial = Store(dataset_path('trial', tmp_path))
    main = Store(dataset_path('main', tmp_path))
    trial.replace_document(make_document('a'), [make_observation('a')])
    main.replace_document(make_document('m'), [make_observation('m')])
    main_bytes = main.path.read_bytes()

    trial.clear()

    assert main.path.read_bytes() == main_bytes
    assert main.counts() == {'documents': 1, 'observations': 1, 'cutters': 1}


def test_datasets_use_separate_files(tmp_path):
    assert dataset_path('trial', tmp_path) == tmp_path / 'trial.sqlite'
    assert dataset_path('main', tmp_path) == tmp_path / 'main.sqlite'


def test_unknown_dataset_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='scratch'):
        dataset_path('scratch', tmp_path)


def test_backup_and_clear_writes_the_backup_before_clearing(tmp_path):
    main = Store(dataset_path('main', tmp_path))
    main.replace_document(make_document('m'), [make_observation('m')])
    original = main.path.read_bytes()

    backup = main.backup_and_clear('20260101-120000')

    assert backup == tmp_path / 'main-backup-20260101-120000.sqlite'
    assert backup.read_bytes() == original
    assert Store(backup).counts() == {'documents': 1, 'observations': 1, 'cutters': 1}
    assert main.counts() == {'documents': 0, 'observations': 0, 'cutters': 0}


def test_backup_never_overwrites_an_existing_backup(tmp_path):
    main = Store(dataset_path('main', tmp_path))
    main.replace_document(make_document('m'), [make_observation('m')])
    main.backup_and_clear('stamp')
    main.replace_document(make_document('n'), [make_observation('n')])

    with pytest.raises(FileExistsError):
        main.backup_and_clear('stamp')
    assert main.counts()['documents'] == 1
