"""Saved databases: saving the data under a name, loading one, adding one."""

from __future__ import annotations

import os
from dataclasses import replace

import pytest

from toolguru_tests.mock_adsk import setup_adsk_modules

setup_adsk_modules()

from toolguru_commands.commandPalette import actions
from toolguru_commands.commandPalette.state import AppState
from toolguru_lib import saved
from toolguru_lib.records import FileRef
from toolguru_lib.store import Store, data_path
from toolguru_tests.factories import make_document, make_observation, make_tool

EMPTY = {'documents': 0, 'observations': 0, 'cutters': 0}
STAMP = '20260101-120000'
DRILL = make_tool(type='drill', description='Drill')


def scan(tmp_path, file_id: str, operations: int = 1, version: int = 3,
         tool: dict | None = None) -> None:
    Store(data_path(tmp_path)).replace_document(
        replace(make_document(file_id), version=version),
        [make_observation(file_id, tool=tool) for _ in range(operations)])


def programs(tmp_path) -> dict[str, int]:
    """Operations per program in the data."""
    result: dict[str, int] = {}
    for row in Store(data_path(tmp_path)).observation_rows():
        result[row['file_id']] = result.get(row['file_id'], 0) + 1
    return result


class TestNames:
    def test_spaces_around_a_name_are_dropped(self):
        assert saved.clean_name('  Mill jobs 2026  ') == 'Mill jobs 2026'

    @pytest.mark.parametrize('name, message', [
        ('   ', 'Give the database a name.'),
        ('a/b', 'A name cannot contain any of < > : " / \\ | ? *'),
        ('..\\escape', 'A name cannot contain any of < > : " / \\ | ? *'),
        ('what?', 'A name cannot contain any of < > : " / \\ | ? *'),
        ('NUL', 'Windows does not allow that name. Choose another.'),
        ('ends with dot.', 'Windows does not allow that name. Choose another.'),
        ('x' * 61, 'Use a name of 60 characters or fewer.'),
    ])
    def test_a_name_that_cannot_be_a_file_is_refused(self, name, message):
        with pytest.raises(saved.SavedError) as error:
            saved.clean_name(name)
        assert str(error.value) == message

    def test_a_name_of_sixty_characters_is_allowed(self):
        assert saved.clean_name('x' * 60) == 'x' * 60


class TestSave:
    def test_saving_copies_the_data_into_the_saved_folder(self, tmp_path):
        scan(tmp_path, 'a', operations=2)
        entry = saved.save('First', base_dir=tmp_path)
        assert entry == {'name': 'First',
                         'counts': {'documents': 1, 'observations': 2, 'cutters': 1}}
        assert Store(tmp_path / 'saved' / 'First.sqlite').counts() == entry['counts']

    def test_saving_leaves_the_data_as_it_was(self, tmp_path):
        scan(tmp_path, 'a', operations=2)
        saved.save('First', base_dir=tmp_path)
        assert programs(tmp_path) == {'a': 2}

    def test_empty_data_is_not_saved(self, tmp_path):
        with pytest.raises(saved.SavedError) as error:
            saved.save('Nothing', base_dir=tmp_path)
        assert str(error.value) == 'There is nothing to save yet. Scan a program first.'
        assert saved.list_saved(tmp_path) == []

    def test_a_name_already_saved_is_not_overwritten(self, tmp_path):
        scan(tmp_path, 'a')
        saved.save('Mills', base_dir=tmp_path)
        scan(tmp_path, 'b')
        with pytest.raises(saved.SavedError) as error:
            saved.save('mills', base_dir=tmp_path)   # Windows: same file
        assert str(error.value) == (
            '“Mills” is already saved. Choose another name, or replace it.')
        assert Store(tmp_path / 'saved' / 'Mills.sqlite').counts()['documents'] == 1

    def test_replacing_a_saved_name_writes_the_new_data(self, tmp_path):
        scan(tmp_path, 'a')
        saved.save('Mills', base_dir=tmp_path)
        scan(tmp_path, 'b')
        saved.save('mills', replace=True, base_dir=tmp_path)
        assert [(e['name'], e['counts']['documents'])
                for e in saved.list_saved(tmp_path)] == [('mills', 2)]

    def test_a_saved_database_does_not_carry_a_folder_scan(self, tmp_path):
        scan(tmp_path, 'a')
        Store(data_path(tmp_path)).start_job('Folder', [FileRef('q', 'Queued')])
        saved.save('First', base_dir=tmp_path)
        assert Store(tmp_path / 'saved' / 'First.sqlite').job() is None
        assert Store(data_path(tmp_path)).job() is not None


class TestList:
    def test_nothing_saved_lists_nothing(self, tmp_path):
        assert saved.list_saved(tmp_path) == []

    def test_lists_newest_first_with_what_each_holds(self, tmp_path):
        scan(tmp_path, 'a')
        saved.save('Older', base_dir=tmp_path)
        scan(tmp_path, 'b', operations=3, tool=DRILL)
        saved.save('Newer', base_dir=tmp_path)
        os.utime(tmp_path / 'saved' / 'Older.sqlite', (1_700_000_000, 1_700_000_000))
        os.utime(tmp_path / 'saved' / 'Newer.sqlite', (1_700_000_500, 1_700_000_500))
        assert saved.list_saved(tmp_path) == [
            {'name': 'Newer', 'saved_at': 1_700_000_500,
             'counts': {'documents': 2, 'observations': 4, 'cutters': 2}},
            {'name': 'Older', 'saved_at': 1_700_000_000,
             'counts': {'documents': 1, 'observations': 1, 'cutters': 1}},
        ]

    def test_a_file_that_is_not_a_database_is_listed_as_unreadable(self, tmp_path):
        (tmp_path / 'saved').mkdir()
        (tmp_path / 'saved' / 'Broken.sqlite').write_text('not a database')
        assert [(e['name'], e['counts']) for e in saved.list_saved(tmp_path)] == [
            ('Broken', None)]

    def test_listing_does_not_change_the_saved_files(self, tmp_path):
        scan(tmp_path, 'a')
        saved.save('First', base_dir=tmp_path)
        path = tmp_path / 'saved' / 'First.sqlite'
        os.utime(path, (1_700_000_000, 1_700_000_000))
        saved.list_saved(tmp_path)
        assert int(path.stat().st_mtime) == 1_700_000_000


class TestLoadReplacing:
    def test_the_saved_database_takes_the_place_of_the_data(self, tmp_path):
        scan(tmp_path, 'a', operations=2)
        saved.save('First', base_dir=tmp_path)
        scan(tmp_path, 'b')
        Store(data_path(tmp_path)).remove_document('a')

        saved.load_replacing('First', STAMP, tmp_path)

        assert programs(tmp_path) == {'a': 2}

    def test_what_was_there_is_backed_up_first(self, tmp_path):
        scan(tmp_path, 'a')
        saved.save('First', base_dir=tmp_path)
        scan(tmp_path, 'b', operations=4)

        backup = saved.load_replacing('First', STAMP, tmp_path)

        assert backup == tmp_path / f'toolguru-backup-{STAMP}.sqlite'
        assert Store(backup).counts() == {'documents': 2, 'observations': 5, 'cutters': 1}

    def test_empty_data_is_not_backed_up(self, tmp_path):
        scan(tmp_path, 'a')
        saved.save('First', base_dir=tmp_path)
        Store(data_path(tmp_path)).clear()

        assert saved.load_replacing('First', STAMP, tmp_path) is None
        assert not (tmp_path / f'toolguru-backup-{STAMP}.sqlite').exists()
        assert programs(tmp_path) == {'a': 1}

    def test_loading_leaves_the_saved_database_in_the_list(self, tmp_path):
        scan(tmp_path, 'a')
        saved.save('First', base_dir=tmp_path)
        saved.load_replacing('First', STAMP, tmp_path)
        assert [e['name'] for e in saved.list_saved(tmp_path)] == ['First']

    def test_a_name_that_is_not_saved_changes_nothing(self, tmp_path):
        scan(tmp_path, 'a')
        with pytest.raises(saved.SavedError) as error:
            saved.load_replacing('Gone', STAMP, tmp_path)
        assert str(error.value) == '“Gone” is no longer among the saved databases.'
        assert programs(tmp_path) == {'a': 1}
        assert not (tmp_path / f'toolguru-backup-{STAMP}.sqlite').exists()

    def test_an_unreadable_file_changes_nothing(self, tmp_path):
        scan(tmp_path, 'a')
        (tmp_path / 'saved').mkdir()
        (tmp_path / 'saved' / 'Broken.sqlite').write_text('not a database')
        with pytest.raises(saved.SavedError) as error:
            saved.load_replacing('Broken', STAMP, tmp_path)
        assert str(error.value) == '“Broken” cannot be read as a ToolGuru database.'
        assert programs(tmp_path) == {'a': 1}


class TestLoadAdding:
    def test_programs_only_in_the_saved_database_are_added(self, tmp_path):
        scan(tmp_path, 'a', operations=2)
        saved.save('First', base_dir=tmp_path)
        Store(data_path(tmp_path)).clear()
        scan(tmp_path, 'b', operations=3)

        result = saved.load_adding('First', tmp_path)

        assert result == {'added': 1, 'updated': 0, 'kept': 0}
        assert programs(tmp_path) == {'a': 2, 'b': 3}

    def test_a_program_in_both_at_the_same_version_is_not_doubled(self, tmp_path):
        scan(tmp_path, 'a', operations=2)
        saved.save('First', base_dir=tmp_path)

        result = saved.load_adding('First', tmp_path)

        assert result == {'added': 0, 'updated': 0, 'kept': 1}
        assert programs(tmp_path) == {'a': 2}

    def test_a_later_version_in_the_saved_database_takes_over(self, tmp_path):
        scan(tmp_path, 'a', operations=5, version=4)
        saved.save('Later', base_dir=tmp_path)
        scan(tmp_path, 'a', operations=2, version=3)

        result = saved.load_adding('Later', tmp_path)

        assert result == {'added': 0, 'updated': 1, 'kept': 0}
        assert programs(tmp_path) == {'a': 5}

    def test_an_earlier_version_in_the_saved_database_is_ignored(self, tmp_path):
        scan(tmp_path, 'a', operations=5, version=3)
        saved.save('Earlier', base_dir=tmp_path)
        scan(tmp_path, 'a', operations=2, version=4)

        result = saved.load_adding('Earlier', tmp_path)

        assert result == {'added': 0, 'updated': 0, 'kept': 1}
        assert programs(tmp_path) == {'a': 2}

    def test_adding_leaves_the_saved_database_as_it_was(self, tmp_path):
        scan(tmp_path, 'a')
        saved.save('First', base_dir=tmp_path)
        scan(tmp_path, 'b')
        saved.load_adding('First', tmp_path)
        assert Store(tmp_path / 'saved' / 'First.sqlite').counts()['documents'] == 1


class TestActions:
    def test_the_list_is_only_sent_while_the_panel_is_open(self, tmp_path):
        state = AppState()
        scan(tmp_path, 'a')
        saved.save('First', base_dir=tmp_path)
        assert actions.view(state, tmp_path)['databases'] is None

        actions.open_databases(state)
        assert [e['name'] for e in actions.view(state, tmp_path)['databases']] == ['First']

        actions.close_databases(state)
        assert actions.view(state, tmp_path)['databases'] is None

    def test_saving_reports_what_was_saved(self, tmp_path):
        state = AppState()
        scan(tmp_path, 'a')
        scan(tmp_path, 'b')
        actions.save_database(state, ' Mills ', False, tmp_path)
        assert state.notice == 'Saved as “Mills”: 2 programs.'
        assert state.error == ''

    def test_a_refused_save_shows_why(self, tmp_path):
        state = AppState()
        scan(tmp_path, 'a')
        actions.save_database(state, 'a:b', False, tmp_path)
        assert state.error == 'A name cannot contain any of < > : " / \\ | ? *'
        assert state.notice == ''

    def test_loading_in_place_names_the_backup_and_closes_the_panel(self, tmp_path):
        state = AppState()
        scan(tmp_path, 'a')
        saved.save('First', base_dir=tmp_path)
        actions.open_databases(state)
        actions.show_cutter(state, 'some-cutter')

        actions.load_database(state, 'First', 'replace', STAMP, tmp_path)

        assert state.notice == (
            f'Loaded “First”. What was on screen is kept as toolguru-backup-{STAMP}.sqlite.')
        assert state.databases_open is False
        assert state.selected_cutter is None

    def test_adding_reports_what_happened_to_each_program(self, tmp_path):
        state = AppState()
        scan(tmp_path, 'a')
        scan(tmp_path, 'b', version=4)
        saved.save('First', base_dir=tmp_path)
        Store(data_path(tmp_path)).remove_document('a')
        scan(tmp_path, 'b', version=3)
        scan(tmp_path, 'c')
        saved.save('Second', base_dir=tmp_path)
        scan(tmp_path, 'c')

        actions.load_database(state, 'First', 'add', STAMP, tmp_path)

        assert state.notice == (
            'Merged “First”: 1 program added, 1 replaced by a more recent scan, 0 already here.')
        assert not (tmp_path / f'toolguru-backup-{STAMP}.sqlite').exists()

    def test_an_unknown_way_to_load_changes_nothing(self, tmp_path):
        state = AppState()
        scan(tmp_path, 'a')
        saved.save('First', base_dir=tmp_path)
        scan(tmp_path, 'b')
        actions.load_database(state, 'First', 'overwrite', STAMP, tmp_path)
        assert state.error == "Unknown way to load: 'overwrite'"
        assert programs(tmp_path) == {'a': 1, 'b': 1}

    def test_a_failed_load_keeps_the_panel_open(self, tmp_path):
        state = AppState()
        actions.open_databases(state)
        actions.load_database(state, 'Gone', 'replace', STAMP, tmp_path)
        assert state.error == '“Gone” is no longer among the saved databases.'
        assert state.databases_open is True

    @pytest.mark.parametrize('running, busy', [(True, False), (False, True)])
    def test_nothing_is_saved_or_loaded_during_a_folder_scan(self, tmp_path, running, busy):
        state = AppState()
        scan(tmp_path, 'a')
        saved.save('First', base_dir=tmp_path)
        scan(tmp_path, 'b')
        state.scan_running, state.scan_busy = running, busy

        actions.save_database(state, 'Second', False, tmp_path)
        assert state.error == 'Stop the folder scan first.'
        actions.load_database(state, 'First', 'replace', STAMP, tmp_path)
        assert state.error == 'Stop the folder scan first.'

        assert [e['name'] for e in saved.list_saved(tmp_path)] == ['First']
        assert programs(tmp_path) == {'a': 1, 'b': 1}
