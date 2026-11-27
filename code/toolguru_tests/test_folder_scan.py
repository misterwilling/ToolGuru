"""Folder scan: count, confirm, one program per step, pause, resume."""

import pytest

from toolguru_tests.mock_adsk import setup_adsk_modules

setup_adsk_modules()

from toolguru_commands.commandPalette import actions
from toolguru_commands.commandPalette.state import AppState
from toolguru_lib import store as scan_store
from toolguru_lib.records import FileRef, ScanError
from toolguru_lib.store import Store, data_path
from toolguru_tests.factories import make_document, make_observation, make_tool

FILES = [FileRef('a', 'Program a'), FileRef('b', 'Program b'),
         FileRef('c', 'Program c')]
DRILL = make_tool(type='drill')


def scans(**by_file):
    """A `scan_one` that returns the given observations per file id, or raises
    the given exception. Records the order files were opened in."""
    opened = []

    def scan_one(file_id):
        opened.append(file_id)
        result = by_file[file_id]
        if isinstance(result, Exception):
            raise result
        return make_document(file_id), result

    scan_one.opened = opened
    return scan_one


def started(tmp_path, files=FILES) -> AppState:
    state = AppState()
    actions.propose_scan(state, 'Project / Folder', files)
    assert actions.start_scan(state, tmp_path) is True
    return state


def run_to_end(state, scan_one, tmp_path) -> int:
    steps = 1
    while actions.scan_step(state, scan_one, tmp_path):
        steps += 1
    return steps


class TestCountThenConfirm:
    def test_counting_a_folder_asks_before_anything_is_scanned(self, tmp_path):
        state = AppState()
        actions.propose_scan(state, 'Project / Folder', FILES)
        view = actions.view(state, tmp_path)
        assert view['confirmScan'] == {
            'folder': 'Project / Folder', 'count': 3, 'unchanged': 0}
        assert view['scan'] is None
        assert state.scan_running is False

    def test_an_empty_folder_is_reported_and_cannot_be_started(self, tmp_path):
        state = AppState()
        actions.propose_scan(state, 'Project / Empty', [])
        assert state.error == 'No Fusion designs in “Project / Empty”.'
        assert actions.view(state, tmp_path)['confirmScan'] is None
        assert actions.start_scan(state, tmp_path) is False
        assert state.error == 'Count a folder before starting a scan.'

    def test_starting_queues_the_files_and_closes_the_picker(self, tmp_path):
        state = AppState()
        actions.show_folder(state, {'folderId': 'f', 'path': [], 'folders': [],
                                    'programs': 3})
        actions.propose_scan(state, 'Project / Folder', FILES)

        assert actions.start_scan(state, tmp_path) is True

        view = actions.view(state, tmp_path)
        assert view['browser'] is None
        assert view['confirmScan'] is None
        assert view['scan'] == {
            'folder': 'Project / Folder', 'total': 3, 'pending': 3,
            'scanned': 0, 'unchanged': 0, 'skipped': 0, 'failed': 0, 'problems': [],
            'running': True}

    def test_browsing_elsewhere_drops_the_counted_folder(self, tmp_path):
        state = AppState()
        actions.propose_scan(state, 'Folder', FILES)
        actions.show_folder(state, {'folderId': 'g', 'path': [], 'folders': [],
                                    'programs': 0})
        assert actions.view(state, tmp_path)['confirmScan'] is None

    def test_closing_the_picker_drops_the_listing_and_the_count(self, tmp_path):
        state = AppState()
        actions.show_folder(state, {'folderId': 'f', 'path': [], 'folders': [],
                                    'programs': 3})
        actions.propose_scan(state, 'Folder', FILES)
        actions.close_folder_picker(state)
        view = actions.view(state, tmp_path)
        assert (view['browser'], view['confirmScan']) == (None, None)


class TestScanSteps:
    def test_each_step_scans_one_program_in_folder_order(self, tmp_path):
        state = started(tmp_path)
        scan_one = scans(a=[make_observation('a')], b=[make_observation('b')],
                         c=[make_observation('c', tool=DRILL)])

        assert actions.scan_step(state, scan_one, tmp_path) is True
        assert scan_one.opened == ['a']
        assert actions.view(state, tmp_path)['scan']['scanned'] == 1
        assert actions.view(state, tmp_path)['counts']['documents'] == 1

        assert actions.scan_step(state, scan_one, tmp_path) is True
        assert actions.scan_step(state, scan_one, tmp_path) is False
        assert scan_one.opened == ['a', 'b', 'c']

    def test_finishing_stops_the_loop_and_reports_the_outcome(self, tmp_path):
        state = started(tmp_path)
        scan_one = scans(a=[make_observation('a')], b=[make_observation('b')],
                         c=[make_observation('c', tool=DRILL)])

        assert run_to_end(state, scan_one, tmp_path) == 3

        view = actions.view(state, tmp_path)
        assert state.scan_running is False
        assert view['notice'] == (
            'Folder scan finished: 3 scanned, 0 skipped, 0 failed.')
        assert view['scan'] == {
            'folder': 'Project / Folder', 'total': 3, 'pending': 0,
            'scanned': 3, 'unchanged': 0, 'skipped': 0, 'failed': 0, 'problems': [],
            'running': False}
        assert view['counts'] == {'documents': 3, 'observations': 3, 'cutters': 2}

    def test_a_design_without_manufacturing_data_is_skipped(self, tmp_path):
        state = started(tmp_path)
        scan_one = scans(
            a=[make_observation('a')],
            b=ScanError('This document has no Manufacturing data to scan.'),
            c=[make_observation('c')])

        run_to_end(state, scan_one, tmp_path)

        view = actions.view(state, tmp_path)
        assert scan_one.opened == ['a', 'b', 'c']
        assert (view['scan']['scanned'], view['scan']['skipped']) == (2, 1)
        assert view['scan']['problems'] == [{
            'name': 'Program b', 'status': 'skipped',
            'message': 'This document has no Manufacturing data to scan.'}]
        assert view['counts']['documents'] == 2

    def test_a_program_that_raises_is_logged_and_the_scan_goes_on(self, tmp_path):
        state = started(tmp_path)
        scan_one = scans(a=RuntimeError('3 : file is locked'),
                         b=[make_observation('b')], c=[make_observation('c')])
        logged = []

        while actions.scan_step(state, scan_one, tmp_path, logged.append):
            pass

        view = actions.view(state, tmp_path)
        assert (view['scan']['scanned'], view['scan']['failed']) == (2, 1)
        assert view['scan']['problems'] == [{
            'name': 'Program a', 'status': 'failed',
            'message': 'RuntimeError: 3 : file is locked'}]
        assert len(logged) == 1
        assert logged[0].startswith('Could not scan "Program a":')
        assert 'RuntimeError: 3 : file is locked' in logged[0]
        assert view['notice'] == (
            'Folder scan finished: 2 scanned, 0 skipped, 1 failed.')

    def test_a_design_with_no_tooled_operations_is_skipped_not_counted(self, tmp_path):
        state = started(tmp_path, FILES[:2])
        run_to_end(state, scans(a=[], b=[make_observation('b')]), tmp_path)
        view = actions.view(state, tmp_path)
        assert view['counts']['documents'] == 1
        assert view['scan']['problems'] == [{
            'name': 'Program a', 'status': 'skipped',
            'message': 'No operations with tools.'}]

    def test_a_program_that_lost_its_operations_leaves_the_tally(self, tmp_path):
        state = AppState()
        actions.store_scan(state, make_document('a'),
                           [make_observation('a')], tmp_path)
        state = started(tmp_path, FILES[:1])
        run_to_end(state, scans(a=[]), tmp_path)
        assert actions.view(state, tmp_path)['counts'] == {
            'documents': 0, 'observations': 0, 'cutters': 0}

    def test_a_step_does_nothing_when_the_scan_is_not_running(self, tmp_path):
        state = AppState()
        Store(data_path(tmp_path)).start_job('Folder', FILES)
        scan_one = scans(a=[make_observation('a')])
        assert actions.scan_step(state, scan_one, tmp_path) is False
        assert scan_one.opened == []


class TestRepeatability:
    """The same folder gives the same tally however often it is scanned."""

    def _scan_folder(self, state, tmp_path):
        actions.propose_scan(state, 'Folder', FILES)
        actions.start_scan(state, tmp_path)
        run_to_end(state, scans(
            a=[make_observation('a'), make_observation('a', tool=DRILL)],
            b=[make_observation('b')],
            c=[make_observation('c', tool=DRILL)]), tmp_path)
        view = actions.view(state, tmp_path)
        return view['counts'], view['tally']

    def test_scanning_a_folder_twice_does_not_double_the_counts(self, tmp_path):
        state = AppState()
        first = self._scan_folder(state, tmp_path)
        assert first[0] == {'documents': 3, 'observations': 4, 'cutters': 2}
        assert self._scan_folder(state, tmp_path) == first

    def test_reset_then_rescan_gives_the_identical_tally(self, tmp_path):
        state = AppState()
        first = self._scan_folder(state, tmp_path)
        actions.reset_data(state, 'RESET', '20260101-120000', tmp_path)
        assert actions.view(state, tmp_path)['scan'] is None
        assert self._scan_folder(state, tmp_path) == first


class TestPauseAndResume:
    def test_stop_pauses_after_the_current_program(self, tmp_path):
        state = started(tmp_path)
        scan_one = scans(a=[make_observation('a')], b=[make_observation('b')],
                         c=[make_observation('c')])
        actions.scan_step(state, scan_one, tmp_path)

        actions.stop_scan(state)

        assert state.notice == 'Folder scan paused.'
        assert actions.scan_step(state, scan_one, tmp_path) is False
        assert scan_one.opened == ['a']
        view = actions.view(state, tmp_path)
        assert (view['scan']['pending'], view['scan']['running']) == (2, False)

    def test_resume_carries_on_where_it_stopped(self, tmp_path):
        state = started(tmp_path)
        scan_one = scans(a=[make_observation('a')], b=[make_observation('b')],
                         c=[make_observation('c')])
        actions.scan_step(state, scan_one, tmp_path)
        actions.stop_scan(state)

        assert actions.resume_scan(state, tmp_path) is True
        run_to_end(state, scan_one, tmp_path)

        assert scan_one.opened == ['a', 'b', 'c']
        assert actions.view(state, tmp_path)['scan']['scanned'] == 3

    def test_a_restarted_add_in_can_resume_from_the_data_file(self, tmp_path):
        first = started(tmp_path)
        scan_one = scans(a=[make_observation('a')], b=[make_observation('b')],
                         c=[make_observation('c')])
        actions.scan_step(first, scan_one, tmp_path)

        restarted = AppState()   # a new session knows nothing but the file
        view = actions.view(restarted, tmp_path)
        assert (view['scan']['pending'], view['scan']['running']) == (2, False)
        assert actions.resume_scan(restarted, tmp_path) is True
        run_to_end(restarted, scan_one, tmp_path)

        assert scan_one.opened == ['a', 'b', 'c']

    def test_resume_does_not_reopen_the_program_fusion_died_on(self, tmp_path):
        Store(data_path(tmp_path)).start_job('Folder', FILES)
        Store(data_path(tmp_path)).mark_item(0, scan_store.OPENING)
        scan_one = scans(b=[make_observation('b')], c=[make_observation('c')])
        state = AppState()

        assert actions.resume_scan(state, tmp_path) is True
        run_to_end(state, scan_one, tmp_path)

        view = actions.view(state, tmp_path)
        assert scan_one.opened == ['b', 'c']
        assert view['scan']['problems'] == [{
            'name': 'Program a', 'status': 'failed',
            'message': scan_store.INTERRUPTED}]

    def test_resume_with_nothing_left_is_refused(self, tmp_path):
        state = AppState()
        assert actions.resume_scan(state, tmp_path) is False
        assert state.error == 'There is no folder scan to resume.'
        assert state.scan_running is False

    def test_resume_while_running_does_not_start_a_second_loop(self, tmp_path):
        state = started(tmp_path)
        assert actions.resume_scan(state, tmp_path) is False
        assert state.scan_running is True

    def test_dismiss_forgets_the_queue_and_keeps_the_scanned_data(self, tmp_path):
        state = started(tmp_path)
        scan_one = scans(a=[make_observation('a')])
        actions.scan_step(state, scan_one, tmp_path)
        actions.stop_scan(state)

        actions.dismiss_scan(state, tmp_path)

        view = actions.view(state, tmp_path)
        assert view['scan'] is None
        assert view['counts']['documents'] == 1
        assert actions.resume_scan(state, tmp_path) is False


class TestNothingElseChangesDuringAScan:
    @pytest.mark.parametrize('action', [
        lambda s, d: actions.reset_data(s, 'RESET', '20260101-120000', d),
        lambda s, d: actions.dismiss_scan(s, d),
        lambda s, d: actions.propose_scan(s, 'Other', FILES[:1]),
        lambda s, d: actions.start_scan(s, d),
    ])
    def test_action_is_refused_while_scanning(self, tmp_path, action):
        state = started(tmp_path)
        Store(data_path(tmp_path)).replace_document(
            make_document('z'), [make_observation('z')])

        action(state, tmp_path)

        assert state.error == 'Stop the folder scan first.'
        assert state.scan_running is True
        store = Store(data_path(tmp_path))
        assert store.counts()['documents'] == 1
        assert store.job()['folder'] == 'Project / Folder'
        assert not (tmp_path / 'toolguru-backup-20260101-120000.sqlite').exists()

    def test_refuse_while_scanning_is_quiet_when_idle(self):
        state = AppState()
        assert actions.refuse_while_scanning(state) is False
        assert state.error == ''


class TestClicksWhileAProgramIsOpen:
    """Fusion handles palette clicks while it opens a document, so an action
    can run in the middle of a step. `during` stands in for that click."""

    def _scan_one(self, during):
        opened = []

        def scan_one(file_id):
            opened.append(file_id)
            if len(opened) == 1:
                during()
            return make_document(file_id), [make_observation(file_id)]

        scan_one.opened = opened
        return scan_one

    def test_other_actions_are_refused_even_after_stop(self, tmp_path):
        state = started(tmp_path)
        seen = {}

        def click_stop_then_reset():
            actions.stop_scan(state)
            actions.reset_data(state, 'RESET', '20260101-120000', tmp_path)
            seen['error'] = state.error
            seen['job'] = Store(data_path(tmp_path)).job()

        actions.scan_step(state, self._scan_one(click_stop_then_reset), tmp_path)

        assert seen['error'] == 'Stop the folder scan first.'
        assert seen['job']['total'] == 3
        assert actions.view(state, tmp_path)['counts']['documents'] == 1

    def test_a_second_step_does_not_open_another_program(self, tmp_path):
        state = started(tmp_path)
        nested = {}
        scan_one = self._scan_one(lambda: nested.update(
            more=actions.scan_step(state, scan_one, tmp_path)))

        assert actions.scan_step(state, scan_one, tmp_path) is True

        assert nested == {'more': False}
        assert scan_one.opened == ['a']

    def test_stop_lets_the_open_program_finish_then_pauses(self, tmp_path):
        state = started(tmp_path)
        scan_one = self._scan_one(lambda: actions.stop_scan(state))

        assert actions.scan_step(state, scan_one, tmp_path) is False

        view = actions.view(state, tmp_path)
        assert (view['scan']['scanned'], view['scan']['pending']) == (1, 2)
        assert view['scan']['running'] is False
        assert view['notice'] == 'Folder scan paused.'

    def test_stop_then_resume_keeps_one_loop_and_the_open_program(self, tmp_path):
        state = started(tmp_path)
        resumed = {}

        def stop_then_resume():
            actions.stop_scan(state)
            resumed['queue_a_step'] = actions.resume_scan(state, tmp_path)

        scan_one = self._scan_one(stop_then_resume)

        assert actions.scan_step(state, scan_one, tmp_path) is True

        assert resumed == {'queue_a_step': True}
        view = actions.view(state, tmp_path)
        assert (view['scan']['scanned'], view['scan']['failed']) == (1, 0)
        assert view['scan']['problems'] == []

    def test_stop_during_the_last_program_still_finishes(self, tmp_path):
        state = started(tmp_path, FILES[:1])
        scan_one = self._scan_one(lambda: actions.stop_scan(state))

        assert actions.scan_step(state, scan_one, tmp_path) is False

        assert state.notice == (
            'Folder scan finished: 1 scanned, 0 skipped, 0 failed.')
        assert state.scan_busy is False

    def test_a_program_that_raises_does_not_leave_the_scan_marked_busy(self, tmp_path):
        state = started(tmp_path)
        actions.scan_step(state, scans(a=RuntimeError('boom')), tmp_path)
        assert state.scan_busy is False
