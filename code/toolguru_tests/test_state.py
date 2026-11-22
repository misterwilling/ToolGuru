"""Palette state and actions: what each button does to the datasets."""

import pytest

from toolguru_tests.mock_adsk import setup_adsk_modules

setup_adsk_modules()

from toolguru_commands.commandPalette import actions
from toolguru_commands.commandPalette.state import AppState
from toolguru_lib import settings as user_settings
from toolguru_lib.settings import Settings
from toolguru_lib.store import Store, dataset_path
from toolguru_tests.factories import (
    make_document, make_holder, make_observation, make_tool)

EMPTY = {'documents': 0, 'observations': 0, 'cutters': 0}
DEFAULTS = Settings()


class TestAppState:
    def test_starts_in_trial_with_nothing_to_report(self):
        assert AppState().serialize(EMPTY, [], DEFAULTS) == {
            'dataset': 'trial', 'counts': EMPTY,
            'countBy': 'cutter', 'stickoutToleranceMm': 0.5, 'tally': [],
            'lastScan': None, 'browser': None, 'confirmScan': None,
            'scan': None, 'notice': '', 'error': '',
        }

    def test_unknown_dataset_is_rejected_and_state_is_unchanged(self):
        state = AppState()
        with pytest.raises(ValueError, match='scratch'):
            state.set_dataset('scratch')
        assert state.dataset == 'trial'

    def test_switching_dataset_forgets_the_last_scan(self):
        state = AppState()
        state.last_scan = {'name': 'x'}
        state.set_dataset('main')
        assert state.dataset == 'main'
        assert state.last_scan is None

    def test_serialize_is_a_copy(self):
        state = AppState()
        state.last_scan = {'name': 'x'}
        state.serialize(EMPTY, [], DEFAULTS)['lastScan']['name'] = 'changed'
        assert state.last_scan == {'name': 'x'}


class TestActions:
    def test_view_of_a_new_trial_dataset_is_empty(self, tmp_path):
        assert actions.view(AppState(), tmp_path) == {
            'dataset': 'trial', 'counts': EMPTY,
            'countBy': 'cutter', 'stickoutToleranceMm': 0.5, 'tally': [],
            'lastScan': None, 'browser': None, 'confirmScan': None,
            'scan': None, 'notice': '', 'error': '',
        }

    def test_store_scan_reports_the_scan_and_fills_the_tally(self, tmp_path):
        state = AppState()
        observations = [
            make_observation('a'), make_observation('a', cutting_time_s=None),
            make_observation('a', tool=make_tool(type='drill'))]
        actions.store_scan(state, make_document('a'), observations, tmp_path)

        view = actions.view(state, tmp_path)
        assert view['lastScan'] == {
            'name': 'Program a', 'operations': 3, 'cutters': 2,
            'operationsWithoutTime': 1}
        assert view['counts'] == {'documents': 1, 'observations': 3, 'cutters': 2}
        assert [(row['tool_type'], row['operations']) for row in view['tally']] == [
            ('flat end mill', 2), ('drill', 1)]

    def test_scan_goes_to_the_active_dataset_only(self, tmp_path):
        state = AppState()
        actions.set_dataset(state, 'main')
        actions.store_scan(state, make_document('a'), [make_observation('a')], tmp_path)
        assert Store(dataset_path('main', tmp_path)).counts()['documents'] == 1
        assert Store(dataset_path('trial', tmp_path)).counts() == EMPTY

    def test_view_shows_only_the_active_dataset(self, tmp_path):
        state = AppState()
        actions.store_scan(state, make_document('a'), [make_observation('a')], tmp_path)
        actions.set_dataset(state, 'main')
        view = actions.view(state, tmp_path)
        assert view['dataset'] == 'main'
        assert view['counts'] == EMPTY
        assert view['lastScan'] is None

    def test_set_dataset_to_something_unknown_reports_an_error(self, tmp_path):
        state = AppState()
        actions.set_dataset(state, 'scratch')
        assert state.dataset == 'trial'
        assert state.error == "Unknown dataset: 'scratch'"

    def test_scan_failed_shows_the_message(self):
        state = AppState()
        actions.scan_failed(state, 'This document has no Manufacturing data to scan.')
        assert state.error == 'This document has no Manufacturing data to scan.'
        assert state.last_scan is None

    def test_a_new_action_clears_the_previous_message(self, tmp_path):
        state = AppState()
        actions.scan_failed(state, 'nope')
        actions.store_scan(state, make_document('a'), [], tmp_path)
        assert state.error == ''

    def test_clear_trial_empties_trial_and_leaves_main(self, tmp_path):
        state = AppState()
        actions.store_scan(state, make_document('a'), [make_observation('a')], tmp_path)
        actions.set_dataset(state, 'main')
        actions.store_scan(state, make_document('m'), [make_observation('m')], tmp_path)
        main_bytes = dataset_path('main', tmp_path).read_bytes()

        actions.clear_trial(state, tmp_path)

        assert Store(dataset_path('trial', tmp_path)).counts() == EMPTY
        assert dataset_path('main', tmp_path).read_bytes() == main_bytes
        assert state.notice == 'Trial data cleared.'
        assert state.last_scan['name'] == 'Program m'

    def test_clear_trial_while_in_trial_forgets_the_last_scan(self, tmp_path):
        state = AppState()
        actions.store_scan(state, make_document('a'), [make_observation('a')], tmp_path)
        actions.clear_trial(state, tmp_path)
        assert actions.view(state, tmp_path)['lastScan'] is None

    def test_reset_main_without_the_word_changes_nothing(self, tmp_path):
        state = AppState()
        actions.set_dataset(state, 'main')
        actions.store_scan(state, make_document('m'), [make_observation('m')], tmp_path)

        actions.reset_main(state, 'reset', '20260101-120000', tmp_path)

        assert state.error == 'Type RESET to reset the main data.'
        assert Store(dataset_path('main', tmp_path)).counts()['documents'] == 1
        assert not (tmp_path / 'main-backup-20260101-120000.sqlite').exists()

    def test_reset_main_backs_up_then_empties(self, tmp_path):
        state = AppState()
        actions.set_dataset(state, 'main')
        actions.store_scan(state, make_document('m'), [make_observation('m')], tmp_path)

        actions.reset_main(state, 'RESET', '20260101-120000', tmp_path)

        backup = tmp_path / 'main-backup-20260101-120000.sqlite'
        assert Store(backup).counts() == {'documents': 1, 'observations': 1, 'cutters': 1}
        assert Store(dataset_path('main', tmp_path)).counts() == EMPTY
        assert state.notice == (
            'Main data reset. Backup saved as main-backup-20260101-120000.sqlite.')


class TestCountBy:
    """One cutter used in two holders: one tool by cutter, two by assembly."""

    def _scan_one_cutter_in_two_holders(self, state, tmp_path):
        other = make_holder(**{
            'product-id': 'TH-200', 'description': 'Other Holder',
            'segments': [{'height': 4.0, 'lower-diameter': 2.0,
                          'upper-diameter': 2.0}]})
        actions.store_scan(state, make_document('a'), [
            make_observation('a'), make_observation('a'),
            make_observation('a', tool=make_tool(holder=other))], tmp_path)

    def test_counts_by_cutter_until_told_otherwise(self, tmp_path):
        state = AppState()
        self._scan_one_cutter_in_two_holders(state, tmp_path)
        view = actions.view(state, tmp_path)
        assert view['countBy'] == 'cutter'
        assert [row['operations'] for row in view['tally']] == [3]
        assert 'holder' not in view['tally'][0]

    def test_count_by_assembly_splits_the_cutter_by_holder(self, tmp_path):
        state = AppState()
        self._scan_one_cutter_in_two_holders(state, tmp_path)
        actions.set_count_by(state, 'assembly', tmp_path)
        view = actions.view(state, tmp_path)
        assert view['countBy'] == 'assembly'
        assert [(row['holder'], row['operations']) for row in view['tally']] == [
            ('Test Holder', 2), ('Other Holder', 1)]
        assert view['counts']['cutters'] == 1

    def test_count_by_is_remembered_by_a_new_session(self, tmp_path):
        actions.set_count_by(AppState(), 'assembly', tmp_path)
        assert actions.view(AppState(), tmp_path)['countBy'] == 'assembly'

    def test_switching_back_to_cutter_restores_the_cutter_tally(self, tmp_path):
        state = AppState()
        self._scan_one_cutter_in_two_holders(state, tmp_path)
        actions.set_count_by(state, 'assembly', tmp_path)
        actions.set_count_by(state, 'cutter', tmp_path)
        view = actions.view(state, tmp_path)
        assert [row['operations'] for row in view['tally']] == [3]

    def test_unknown_way_to_count_is_refused(self, tmp_path):
        state = AppState()
        actions.set_count_by(state, 'holder', tmp_path)
        assert state.error == "Unknown way to count: 'holder'"
        assert user_settings.load(tmp_path).count_by == 'cutter'

    def test_tolerance_decides_whether_two_stickouts_are_one_assembly(self, tmp_path):
        state = AppState()
        longer = make_tool(geometry={'LB': 1.51})   # 0.254 mm more stickout
        actions.store_scan(state, make_document('a'), [
            make_observation('a'), make_observation('a', tool=longer)], tmp_path)
        actions.set_count_by(state, 'assembly', tmp_path)
        assert len(actions.view(state, tmp_path)['tally']) == 1

        actions.set_stickout_tolerance(state, 0.1, tmp_path)

        view = actions.view(state, tmp_path)
        assert view['stickoutToleranceMm'] == 0.1
        assert sorted(row['stickout_min_mm'] for row in view['tally']) == [38.1, 38.354]

    def test_tolerance_keeps_the_count_by_choice(self, tmp_path):
        state = AppState()
        actions.set_count_by(state, 'assembly', tmp_path)
        actions.set_stickout_tolerance(state, 1, tmp_path)
        assert user_settings.load(tmp_path) == Settings('assembly', 1.0)

    @pytest.mark.parametrize(
        'bad', [-0.1, 'wide', None, True, float('nan'), float('inf')])
    def test_bad_tolerance_is_refused_and_nothing_is_saved(self, tmp_path, bad):
        state = AppState()
        actions.set_stickout_tolerance(state, bad, tmp_path)
        assert state.error == 'Stickout tolerance must be a number, zero or more.'
        assert user_settings.load(tmp_path).stickout_tolerance_mm == 0.5

    def test_clearing_trial_data_keeps_the_settings(self, tmp_path):
        state = AppState()
        actions.set_count_by(state, 'assembly', tmp_path)
        actions.set_stickout_tolerance(state, 2.0, tmp_path)
        actions.clear_trial(state, tmp_path)
        assert user_settings.load(tmp_path) == Settings('assembly', 2.0)
