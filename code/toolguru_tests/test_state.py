"""Palette state and actions: what each button does to the data."""

import pytest

from toolguru_tests.mock_adsk import setup_adsk_modules

setup_adsk_modules()

from toolguru_commands.commandPalette import actions
from toolguru_commands.commandPalette.state import AppState
from toolguru_lib import settings as user_settings
from toolguru_lib.settings import Settings
from toolguru_lib.store import Store, data_path
from toolguru_tests.factories import (
    make_document, make_holder, make_observation, make_tool)

EMPTY = {'documents': 0, 'observations': 0, 'cutters': 0}
DEFAULTS = Settings()


class TestAppState:
    def test_starts_with_nothing_to_report(self):
        assert AppState().serialize(EMPTY, [], DEFAULTS) == {
            'counts': EMPTY,
            'countBy': 'cutter', 'stickoutToleranceMm': 0.5,
            'displayUnit': 'in', 'descriptionWidthPx': 240, 'tally': [],
            'detail': None, 'databases': None, 'similar': None, 'libraryCount': 0,
            'lastScan': None, 'browser': None, 'confirmScan': None,
            'scan': None, 'notice': '', 'error': '',
        }

    def test_serialize_is_a_copy(self):
        state = AppState()
        state.last_scan = {'name': 'x'}
        state.serialize(EMPTY, [], DEFAULTS)['lastScan']['name'] = 'changed'
        assert state.last_scan == {'name': 'x'}


class TestActions:
    def test_view_before_anything_is_scanned_is_empty(self, tmp_path):
        assert actions.view(AppState(), tmp_path) == {
            'counts': EMPTY,
            'countBy': 'cutter', 'stickoutToleranceMm': 0.5,
            'displayUnit': 'in', 'descriptionWidthPx': 240, 'tally': [],
            'detail': None, 'databases': None, 'similar': None, 'libraryCount': 0,
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

    def test_reset_without_the_word_changes_nothing(self, tmp_path):
        state = AppState()
        actions.store_scan(state, make_document('m'), [make_observation('m')], tmp_path)

        actions.reset_data(state, 'reset', '20260101-120000', tmp_path)

        assert state.error == 'Type RESET to reset the data.'
        assert Store(data_path(tmp_path)).counts()['documents'] == 1
        assert not (tmp_path / 'toolguru-backup-20260101-120000.sqlite').exists()

    def test_reset_backs_up_then_empties(self, tmp_path):
        state = AppState()
        actions.store_scan(state, make_document('m'), [make_observation('m')], tmp_path)

        actions.reset_data(state, 'RESET', '20260101-120000', tmp_path)

        backup = tmp_path / 'toolguru-backup-20260101-120000.sqlite'
        assert Store(backup).counts() == {'documents': 1, 'observations': 1, 'cutters': 1}
        assert Store(data_path(tmp_path)).counts() == EMPTY
        assert state.notice == (
            'Data reset. Backup saved as toolguru-backup-20260101-120000.sqlite.')

    def test_reset_forgets_the_last_scan(self, tmp_path):
        state = AppState()
        actions.store_scan(state, make_document('m'), [make_observation('m')], tmp_path)
        actions.reset_data(state, 'RESET', '20260101-120000', tmp_path)
        assert actions.view(state, tmp_path)['lastScan'] is None


class TestDisplayUnit:
    """Lengths are shown in inches unless the user picks millimetres."""

    def test_lengths_are_shown_in_inches_until_told_otherwise(self, tmp_path):
        assert actions.view(AppState(), tmp_path)['displayUnit'] == 'in'

    def test_the_choice_is_remembered_by_a_new_session(self, tmp_path):
        actions.set_display_unit(AppState(), 'mm', tmp_path)
        assert actions.view(AppState(), tmp_path)['displayUnit'] == 'mm'

    def test_changing_the_unit_keeps_the_other_settings(self, tmp_path):
        state = AppState()
        actions.set_count_by(state, 'assembly', tmp_path)
        actions.set_stickout_tolerance(state, 1.25, tmp_path)
        actions.set_display_unit(state, 'mm', tmp_path)
        assert user_settings.load(tmp_path) == Settings('assembly', 1.25, 'mm')

    def test_changing_the_unit_does_not_change_the_stored_numbers(self, tmp_path):
        state = AppState()
        actions.store_scan(state, make_document('a'), [make_observation('a')], tmp_path)
        before = actions.view(state, tmp_path)['tally']
        actions.set_display_unit(state, 'mm', tmp_path)
        assert actions.view(state, tmp_path)['tally'] == before
        assert before[0]['diameter_mm'] == 12.7

    def test_an_unknown_unit_is_refused(self, tmp_path):
        state = AppState()
        actions.set_display_unit(state, 'cm', tmp_path)
        assert state.error == "Unknown unit: 'cm'"
        assert user_settings.load(tmp_path).display_unit == 'in'


class TestDescriptionWidth:
    """The tally's description column stays as wide as the user left it."""

    def test_the_column_starts_240_pixels_wide(self, tmp_path):
        assert actions.view(AppState(), tmp_path)['descriptionWidthPx'] == 240

    def test_the_width_is_remembered_by_a_new_session(self, tmp_path):
        actions.set_description_width(AppState(), 410, tmp_path)
        assert actions.view(AppState(), tmp_path)['descriptionWidthPx'] == 410

    def test_the_width_is_stored_as_a_whole_number_of_pixels(self, tmp_path):
        actions.set_description_width(AppState(), 312.6, tmp_path)
        assert user_settings.load(tmp_path).description_width_px == 313

    def test_changing_the_width_keeps_the_other_settings(self, tmp_path):
        state = AppState()
        actions.set_count_by(state, 'assembly', tmp_path)
        actions.set_display_unit(state, 'mm', tmp_path)
        actions.set_description_width(state, 500, tmp_path)
        assert user_settings.load(tmp_path) == Settings('assembly', 0.5, 'mm', 500)

    @pytest.mark.parametrize('width', [0, -40, 0.4, '300', None, True,
                                       float('nan'), float('inf')])
    def test_a_width_that_is_not_a_number_of_pixels_is_refused(self, tmp_path, width):
        state = AppState()
        actions.set_description_width(state, 410, tmp_path)
        actions.set_description_width(state, width, tmp_path)
        assert state.error == 'The column width must be a number of pixels, one or more.'
        assert user_settings.load(tmp_path).description_width_px == 410


class TestCutterDetail:
    """Opening one cutter's detail from the tally."""

    def _scan(self, state, tmp_path, file_id='a'):
        actions.store_scan(state, make_document(file_id), [
            make_observation(file_id),
            make_observation(file_id, tool=make_tool(type='drill'))], tmp_path)
        return {row['tool_type']: row['cutter_key']
                for row in actions.view(state, tmp_path)['tally']}

    def test_no_detail_until_a_cutter_is_opened(self, tmp_path):
        state = AppState()
        self._scan(state, tmp_path)
        assert actions.view(state, tmp_path)['detail'] is None

    def test_show_cutter_adds_that_cutters_detail_to_the_view(self, tmp_path):
        state = AppState()
        keys = self._scan(state, tmp_path)
        actions.show_cutter(state, keys['drill'])
        detail = actions.view(state, tmp_path)['detail']
        assert (detail['cutter_key'], detail['tool_type'], detail['operations']) == (
            keys['drill'], 'drill', 1)
        assert [p['name'] for p in detail['program_list']] == ['Program a']

    def test_close_cutter_removes_the_detail(self, tmp_path):
        state = AppState()
        keys = self._scan(state, tmp_path)
        actions.show_cutter(state, keys['drill'])
        actions.close_cutter(state)
        assert actions.view(state, tmp_path)['detail'] is None

    def test_an_open_detail_follows_new_scans(self, tmp_path):
        state = AppState()
        keys = self._scan(state, tmp_path, 'a')
        actions.show_cutter(state, keys['drill'])
        self._scan(state, tmp_path, 'b')
        assert actions.view(state, tmp_path)['detail']['programs'] == 2

    def test_detail_uses_the_saved_stickout_tolerance(self, tmp_path):
        state = AppState()
        actions.store_scan(state, make_document('a'), [
            make_observation('a'),
            make_observation('a', tool=make_tool(geometry={'LB': 1.51}))], tmp_path)
        actions.show_cutter(state, actions.view(state, tmp_path)['tally'][0]['cutter_key'])
        assert len(actions.view(state, tmp_path)['detail']['assemblies']) == 1
        actions.set_stickout_tolerance(state, 0, tmp_path)
        assert len(actions.view(state, tmp_path)['detail']['assemblies']) == 2

    def test_a_cutter_that_is_not_in_the_data_shows_no_detail(self, tmp_path):
        state = AppState()
        self._scan(state, tmp_path)
        actions.show_cutter(state, 'no-such-cutter')
        assert actions.view(state, tmp_path)['detail'] is None

    def test_resetting_the_data_closes_the_detail_for_good(self, tmp_path):
        state = AppState()
        keys = self._scan(state, tmp_path)
        actions.show_cutter(state, keys['drill'])
        actions.reset_data(state, 'RESET', '20260101-120000', tmp_path)
        self._scan(state, tmp_path)   # the same cutter comes back
        assert actions.view(state, tmp_path)['detail'] is None


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

    def test_resetting_the_data_keeps_the_settings(self, tmp_path):
        state = AppState()
        actions.set_count_by(state, 'assembly', tmp_path)
        actions.set_stickout_tolerance(state, 2.0, tmp_path)
        actions.reset_data(state, 'RESET', '20260101-120000', tmp_path)
        assert user_settings.load(tmp_path) == Settings('assembly', 2.0)
