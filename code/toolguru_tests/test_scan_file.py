"""Importing a scan file: reading it, and what the Import button does."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest

from toolguru_tests.mock_adsk import setup_adsk_modules

setup_adsk_modules()

from toolguru_commands.commandPalette import actions
from toolguru_commands.commandPalette.state import AppState
from toolguru_lib import saved, scan_file
from toolguru_lib.records import ScanError
from toolguru_lib.store import Store, data_path
from toolguru_tests.factories import (
    make_document, make_harvest_operation, make_harvest_record,
    make_harvest_transform, make_observation, make_tool)

OTHER = r'C:\Parts\Example\Plate.mcam'


def write(tmp_path, records: list, name: str = 'harvest.jsonl') -> Path:
    path = tmp_path / name
    path.write_text(''.join(
        (record if isinstance(record, str) else json.dumps(record)) + '\n'
        for record in records), encoding='utf-8')
    return path


class TestRead:
    def test_each_file_that_was_read_is_a_program(self, tmp_path):
        found = scan_file.read(write(tmp_path, [
            make_harvest_record(), make_harvest_record(path=OTHER)]))
        assert [document.name for document, _ in found.programs] == ['Bracket', 'Plate']
        assert [len(observations) for _, observations in found.programs] == [1, 1]
        assert found.not_read == 0

    def test_the_last_line_for_a_file_is_the_one_that_counts(self, tmp_path):
        # The harvester adds a line each time it reads a file again.
        first = make_harvest_record([make_harvest_operation(1)])
        again = make_harvest_record([make_harvest_operation(1), make_harvest_operation(2)])
        found = scan_file.read(write(tmp_path, [first, make_harvest_record(path=OTHER), again]))
        counts = {document.name: len(observations) for document, observations in found.programs}
        assert counts == {'Bracket': 2, 'Plate': 1}

    def test_a_later_line_wins_even_when_the_path_is_typed_in_another_case(self, tmp_path):
        again = make_harvest_record([], path=r'c:\parts\EXAMPLE\bracket.MCAM')
        found = scan_file.read(write(tmp_path, [make_harvest_record(), again]))
        assert [len(observations) for _, observations in found.programs] == [0]

    @pytest.mark.parametrize('status', ['not_opened', 'newer_version', 'crashed', 'read_failed'])
    def test_a_file_the_harvester_could_not_read_is_counted_not_imported(self, tmp_path, status):
        unread = make_harvest_record(path=OTHER, status=status, operations=None)
        found = scan_file.read(write(tmp_path, [make_harvest_record(), unread]))
        assert [document.name for document, _ in found.programs] == ['Bracket']
        assert found.not_read == 1

    def test_a_file_that_opened_later_replaces_its_failed_line(self, tmp_path):
        failed = make_harvest_record(status='not_opened')
        found = scan_file.read(write(tmp_path, [failed, make_harvest_record()]))
        assert (len(found.programs), found.not_read) == (1, 0)

    def test_blank_and_damaged_lines_are_passed_over(self, tmp_path):
        found = scan_file.read(write(tmp_path, [
            '', make_harvest_record(), '{"path": "cut off', '[1, 2]']))
        assert len(found.programs) == 1

    def test_a_file_saved_with_a_byte_order_mark_is_read(self, tmp_path):
        path = tmp_path / 'harvest.jsonl'
        path.write_text(json.dumps(make_harvest_record()) + '\n', encoding='utf-8-sig')
        assert len(scan_file.read(path).programs) == 1

    def test_a_file_that_is_not_a_scan_file_is_refused(self, tmp_path):
        with pytest.raises(ScanError, match='not a scan file ToolGuru can read'):
            scan_file.read(write(tmp_path, ['{"hello": "world"}', 'plain text'], 'notes.jsonl'))

    def test_a_missing_file_is_refused_with_its_name(self, tmp_path):
        with pytest.raises(ScanError, match='Could not read “gone.jsonl”'):
            scan_file.read(tmp_path / 'gone.jsonl')


class TestImport:
    def test_the_programs_join_the_tally_as_mastercam_cutters(self, tmp_path):
        state = AppState()
        actions.import_scan_file(state, write(tmp_path, [make_harvest_record()]), tmp_path)

        view = actions.view(state, tmp_path)
        assert state.error == ''
        assert view['counts'] == {'documents': 1, 'observations': 1, 'cutters': 1}
        (line,) = view['tally']
        assert line['source'] == 'mastercam'
        assert line['tool_type'] == 'flat end mill'
        assert line['diameter_mm'] == 12.7
        assert line['machines'] == ['Example VMC']
        assert line['time_s'] == 60.0

    def test_a_fusion_cutter_of_the_same_geometry_stays_its_own_line(self, tmp_path):
        Store(data_path(tmp_path)).replace_document(
            make_document('a'), [make_observation('a')])
        actions.import_scan_file(
            AppState(), write(tmp_path, [make_harvest_record()]), tmp_path)

        tally = actions.view(AppState(), tmp_path)['tally']
        assert sorted(line['source'] for line in tally) == ['fusion', 'mastercam']
        assert [line['operations'] for line in tally] == [1, 1]

    def test_importing_the_same_file_twice_changes_nothing(self, tmp_path):
        path = write(tmp_path, [make_harvest_record(), make_harvest_record(path=OTHER)])
        actions.import_scan_file(AppState(), path, tmp_path)
        once = actions.view(AppState(), tmp_path)
        actions.import_scan_file(AppState(), path, tmp_path)
        assert actions.view(AppState(), tmp_path) == once
        assert once['counts'] == {'documents': 2, 'observations': 2, 'cutters': 1}

    def test_a_newer_harvest_of_a_program_replaces_the_older_one(self, tmp_path):
        actions.import_scan_file(AppState(), write(tmp_path, [make_harvest_record(
            [make_harvest_operation(1), make_harvest_operation(2)])]), tmp_path)
        actions.import_scan_file(AppState(), write(tmp_path, [make_harvest_record(
            [make_harvest_operation(1)])]), tmp_path)
        assert Store(data_path(tmp_path)).counts()['observations'] == 1

    def test_a_program_that_lost_its_tooled_operations_leaves_the_data(self, tmp_path):
        actions.import_scan_file(
            AppState(), write(tmp_path, [make_harvest_record()]), tmp_path)
        actions.import_scan_file(
            AppState(), write(tmp_path, [make_harvest_record([])]), tmp_path)
        assert Store(data_path(tmp_path)).counts()['documents'] == 0

    def test_programs_scanned_in_fusion_are_left_alone(self, tmp_path):
        Store(data_path(tmp_path)).replace_document(
            make_document('a'), [make_observation('a')])
        actions.import_scan_file(
            AppState(), write(tmp_path, [make_harvest_record()]), tmp_path)
        files = {row['file_id'] for row in Store(data_path(tmp_path)).observation_rows()}
        assert files == {'a', r'mastercam:c:\parts\example\bracket.mcam'}

    def test_the_notice_says_what_came_in(self, tmp_path):
        state = AppState()
        state.last_scan = {'name': 'Earlier'}
        actions.import_scan_file(state, write(tmp_path, [
            make_harvest_record([make_harvest_operation(1), make_harvest_operation(2)]),
            make_harvest_record(path=OTHER)]), tmp_path)
        assert state.notice == ('Imported 2 programs from “harvest.jsonl”: '
                                '3 operations using 1 cutter.')
        assert state.last_scan is None

    def test_the_notice_counts_what_did_not_come_in(self, tmp_path):
        state = AppState()
        actions.import_scan_file(state, write(tmp_path, [
            make_harvest_record([
                make_harvest_operation(1, seconds=None),
                make_harvest_operation(2, seconds=40.0),
                make_harvest_transform(3, 4010.3)]),
            make_harvest_record([], path=OTHER),
            make_harvest_record(path=r'C:\Parts\Example\New.mcam', status='newer_version'),
        ]), tmp_path)
        assert state.notice == (
            'Imported 1 program from “harvest.jsonl”: 2 operations using 1 cutter. '
            '1 file had no operations with tools. '
            '1 file could not be read when the scan file was made. '
            '1 operation has no cutting time. '
            '1 h 07 min of repeated (transform) cutting time could not be given to a tool.')

    def test_uncredited_transform_time_is_shown_with_the_totals(self, tmp_path):
        actions.import_scan_file(AppState(), write(tmp_path, [make_harvest_record([
            make_harvest_operation(1, seconds=40.0),
            make_harvest_transform(2, 99.5)])]), tmp_path)
        assert actions.view(AppState(), tmp_path)['uncreditedTimeS'] == 99.5

    def test_a_file_that_cannot_be_read_changes_nothing(self, tmp_path):
        Store(data_path(tmp_path)).replace_document(
            make_document('a'), [make_observation('a')])
        state = AppState()
        actions.import_scan_file(state, write(tmp_path, ['nothing here']), tmp_path)
        assert 'not a scan file ToolGuru can read' in state.error
        assert state.notice == ''
        assert Store(data_path(tmp_path)).counts()['documents'] == 1

    def test_nothing_is_imported_while_a_folder_scan_runs(self, tmp_path):
        state = AppState()
        state.scan_running = True
        actions.import_scan_file(state, write(tmp_path, [make_harvest_record()]), tmp_path)
        assert state.error == actions.SCANNING
        assert Store(data_path(tmp_path)).counts()['documents'] == 0


class TestStore:
    def test_many_programs_are_stored_together_or_not_at_all(self, tmp_path):
        store = Store(data_path(tmp_path))
        store.replace_document(make_document('kept'), [make_observation('kept')])
        broken = replace(make_observation('b'), setup_name=None)   # the column refuses it
        with pytest.raises(sqlite3.IntegrityError):
            store.replace_documents([
                (make_document('a'), [make_observation('a')]),
                (make_document('b'), [broken])])
        assert {row['file_id'] for row in store.observation_rows()} == {'kept'}

    def test_uncredited_time_is_kept_with_its_program_and_added_up(self, tmp_path):
        store = Store(data_path(tmp_path))
        store.replace_documents([
            (replace(make_document('a'), uncredited_time_s=10.5), [make_observation('a')]),
            (replace(make_document('b'), uncredited_time_s=4.25), [make_observation('b')]),
            (make_document('c'), [make_observation('c')])])
        assert store.uncredited_time_s() == 14.75
        store.remove_document('a')
        assert store.uncredited_time_s() == 4.25

    def test_a_file_from_before_uncredited_time_reads_as_having_none(self, tmp_path):
        store = Store(data_path(tmp_path))
        store.replace_document(make_document('a'), [make_observation('a')])
        with closing(sqlite3.connect(store.path)) as conn, conn:
            conn.execute('ALTER TABLE documents DROP COLUMN uncredited_time_s')

        reopened = Store(store.path)

        assert reopened.uncredited_time_s() == 0.0
        assert reopened.counts()['documents'] == 1
        reopened.replace_document(
            replace(make_document('b'), uncredited_time_s=7.0), [make_observation('b')])
        assert reopened.uncredited_time_s() == 7.0

    def test_uncredited_time_survives_a_save_and_a_merge_back(self, tmp_path):
        Store(data_path(tmp_path)).replace_document(
            replace(make_document('a'), uncredited_time_s=12.0, scanned_at=5),
            [make_observation('a')])
        saved.save('Kept', False, tmp_path)
        Store(data_path(tmp_path)).clear()
        saved.load_adding('Kept', tmp_path)
        assert Store(data_path(tmp_path)).uncredited_time_s() == 12.0


class TestNeverWrittenToFusion:
    """A Mastercam tool is ToolGuru's own rewriting of it. Fusion has crashed
    on such a record, so none is ever handed to Fusion."""
    # The same end mill as Fusion holds it, so the two can be merged.
    FUSION = make_tool(geometry={'tip-diameter': 0.5})

    def imported(self, tmp_path) -> str:
        """Import one Mastercam program; returns its cutter's key."""
        actions.import_scan_file(
            AppState(), write(tmp_path, [make_harvest_record()]), tmp_path)
        (line,) = [line for line in actions.view(AppState(), tmp_path)['tally']
                   if line['source'] == 'mastercam']
        return line['cutter_key']

    def test_a_mastercam_line_is_marked_as_not_writable(self, tmp_path):
        self.imported(tmp_path)
        Store(data_path(tmp_path)).replace_document(
            make_document('a'), [make_observation('a')])
        lines = {line['source']: line['writable']
                 for line in actions.view(AppState(), tmp_path)['tally']}
        assert lines == {'mastercam': False, 'fusion': True}

    def test_ticking_one_is_refused(self, tmp_path):
        key = self.imported(tmp_path)
        state = AppState()
        actions.pick_for_library(state, key, True, None, tmp_path)
        assert state.error == actions.NOT_WRITABLE
        assert Store(data_path(tmp_path)).library_picks() == {}
        assert actions.library_tools(tmp_path) == []

    def test_tick_all_passes_over_it(self, tmp_path):
        key = self.imported(tmp_path)
        Store(data_path(tmp_path)).replace_document(
            make_document('a'), [make_observation('a')])
        fusion_key = make_observation('a').cutter_key
        state = AppState()
        actions.pick_many_for_library(state, [
            {'cutterKey': key, 'assemblyKey': None},
            {'cutterKey': fusion_key, 'assemblyKey': None}], True, tmp_path)
        assert state.error == ''
        assert set(Store(data_path(tmp_path)).library_picks()) == {fusion_key}
        assert len(actions.library_tools(tmp_path)) == 1

    def test_a_pick_stored_some_other_way_still_writes_nothing(self, tmp_path):
        key = self.imported(tmp_path)
        Store(data_path(tmp_path)).pick_for_library([key], None)
        view = actions.view(AppState(), tmp_path)
        assert actions.library_tools(tmp_path) == []
        assert view['libraryCount'] == 0
        assert view['tally'][0]['in_library'] is False

    def test_its_detail_opens_and_says_it_cannot_be_written(self, tmp_path):
        key = self.imported(tmp_path)
        state = AppState()
        actions.show_cutter(state, key)
        detail = actions.view(state, tmp_path)['detail']
        assert detail['library'] == {
            'picked': False, 'choice': None, 'assembly_key': None, 'writable': False}
        assert detail['fields']['source'] == 'mastercam'

    def test_merged_with_a_fusion_cutter_the_line_is_written_from_the_fusion_scan(self, tmp_path):
        key = self.imported(tmp_path)
        # Used more in Mastercam, so the Mastercam cutter names the merged line.
        actions.import_scan_file(AppState(), write(tmp_path, [make_harvest_record(
            [make_harvest_operation(1), make_harvest_operation(2), make_harvest_operation(3)],
            path=OTHER)]), tmp_path)
        fusion = make_observation('a', tool=self.FUSION)
        Store(data_path(tmp_path)).replace_document(make_document('a'), [fusion])
        state = AppState()
        actions.merge_cutters(state, [key, fusion.cutter_key], tmp_path)
        (line,) = actions.view(AppState(), tmp_path)['tally']
        assert (line['cutter_key'], line['merged'], line['writable']) == (key, 2, True)

        actions.pick_for_library(state, key, True, None, tmp_path)

        assert state.error == ''
        (written,) = [json.loads(tool) for tool in actions.library_tools(tmp_path)]
        assert 'source' not in written
        assert written['holder']['description'] == 'Test Holder'   # the Fusion scan's
        assert written['vendor'] == 'Example Tooling'
