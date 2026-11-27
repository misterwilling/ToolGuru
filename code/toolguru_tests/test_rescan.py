"""When a program was scanned, and which programs a folder scan can skip."""

from __future__ import annotations

import sqlite3
from contextlib import closing

from toolguru_tests.mock_adsk import setup_adsk_modules

setup_adsk_modules()

from toolguru_commands.commandPalette import actions
from toolguru_commands.commandPalette.state import AppState
from toolguru_lib import saved
from toolguru_lib.records import SCAN_LEVEL, FileRef
from toolguru_lib.store import Store, data_path
from toolguru_tests.factories import make_document, make_observation


def store_scan(tmp_path, file_id: str, *, version: int = 3, operations: int = 1,
               scanned_at: int | None = 1_000, scan_level: int | None = None) -> None:
    Store(data_path(tmp_path)).replace_document(
        make_document(file_id, version=version, scanned_at=scanned_at,
                      scan_level=scan_level),
        [make_observation(file_id) for _ in range(operations)])


def operations(tmp_path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in Store(data_path(tmp_path)).observation_rows():
        counts[row['file_id']] = counts.get(row['file_id'], 0) + 1
    return counts


def scan_folder(tmp_path, files: list[FileRef]) -> tuple[AppState, list[str]]:
    """Count, start and run a folder scan. Returns the state and the files
    that were opened, in order."""
    opened: list[str] = []

    def scan_one(file_id: str):
        opened.append(file_id)
        version = next(f.version for f in files if f.file_id == file_id)
        return (make_document(file_id, version=version, scanned_at=2_000),
                [make_observation(file_id)])

    state = AppState()
    actions.propose_scan(state, 'Project / Folder', files)
    assert actions.start_scan(state, tmp_path) is True
    while actions.scan_step(state, scan_one, tmp_path):
        pass
    return state, opened


class TestScanTime:
    def test_the_scan_time_and_level_are_stored_with_the_program(self, tmp_path):
        store_scan(tmp_path, 'a', scanned_at=1_234)
        with closing(sqlite3.connect(data_path(tmp_path))) as conn:
            assert conn.execute(
                'SELECT scanned_at, scan_level FROM documents').fetchone() == (
                    1_234, SCAN_LEVEL)

    def test_a_file_from_before_scan_times_reads_as_never_timed_and_level_one(self, tmp_path):
        store_scan(tmp_path, 'a')
        path = data_path(tmp_path)
        with closing(sqlite3.connect(path)) as conn, conn:
            conn.execute('ALTER TABLE documents DROP COLUMN scanned_at')
            conn.execute('ALTER TABLE documents DROP COLUMN scan_level')

        reopened = Store(path)

        assert reopened.scan_marks() == {'a': (3, 1)}
        with closing(sqlite3.connect(path)) as conn:
            assert conn.execute('SELECT scanned_at FROM documents').fetchone() == (None,)
        assert reopened.counts()['observations'] == 1


class TestMergeKeepsTheMoreRecentScan:
    def _merge(self, tmp_path, saved_scan: dict, current_scan: dict) -> dict:
        store_scan(tmp_path, 'a', operations=5, **saved_scan)
        saved.save('Other', base_dir=tmp_path)
        store_scan(tmp_path, 'a', operations=2, **current_scan)
        return saved.load_adding('Other', tmp_path)

    def test_a_more_recent_scan_in_the_other_database_takes_over(self, tmp_path):
        result = self._merge(tmp_path, {'scanned_at': 2_000}, {'scanned_at': 1_000})
        assert result == {'added': 0, 'updated': 1, 'kept': 0}
        assert operations(tmp_path) == {'a': 5}

    def test_an_older_scan_in_the_other_database_is_ignored(self, tmp_path):
        result = self._merge(tmp_path, {'scanned_at': 1_000}, {'scanned_at': 2_000})
        assert result == {'added': 0, 'updated': 0, 'kept': 1}
        assert operations(tmp_path) == {'a': 2}

    def test_the_more_recent_scan_wins_even_with_an_earlier_program_version(self, tmp_path):
        self._merge(tmp_path, {'scanned_at': 2_000, 'version': 3},
                    {'scanned_at': 1_000, 'version': 4})
        assert operations(tmp_path) == {'a': 5}

    def test_a_scan_with_no_time_loses_to_one_that_has_a_time(self, tmp_path):
        self._merge(tmp_path, {'scanned_at': None, 'version': 9}, {'scanned_at': 1})
        assert operations(tmp_path) == {'a': 2}

    def test_two_scans_with_no_time_go_by_the_later_program_version(self, tmp_path):
        self._merge(tmp_path, {'scanned_at': None, 'version': 4},
                    {'scanned_at': None, 'version': 3})
        assert operations(tmp_path) == {'a': 5}

    def test_the_merged_program_keeps_its_scan_time(self, tmp_path):
        self._merge(tmp_path, {'scanned_at': 2_000}, {'scanned_at': 1_000})
        with closing(sqlite3.connect(data_path(tmp_path))) as conn:
            assert conn.execute('SELECT scanned_at FROM documents').fetchone() == (2_000,)


class TestSkipUnchanged:
    FILES = [FileRef('a', 'Program a', 3), FileRef('b', 'Program b', 3)]

    def test_a_program_already_scanned_at_this_version_is_not_opened(self, tmp_path):
        store_scan(tmp_path, 'a', version=3)
        state, opened = scan_folder(tmp_path, self.FILES)
        assert opened == ['b']
        job = actions.view(state, tmp_path)['scan']
        assert (job['total'], job['pending'], job['scanned'], job['unchanged']) == (
            2, 0, 1, 1)
        assert state.notice == (
            'Folder scan finished: 1 scanned, 1 unchanged, 0 skipped, 0 failed.')

    def test_the_skipped_programs_scan_is_left_as_it_was(self, tmp_path):
        store_scan(tmp_path, 'a', version=3, operations=4)
        scan_folder(tmp_path, self.FILES)
        assert operations(tmp_path) == {'a': 4, 'b': 1}

    def test_a_program_saved_since_is_opened_again(self, tmp_path):
        store_scan(tmp_path, 'a', version=2)
        _, opened = scan_folder(tmp_path, self.FILES)
        assert opened == ['a', 'b']

    def test_a_program_scanned_before_scans_recorded_as_much_is_opened_again(self, tmp_path):
        store_scan(tmp_path, 'a', version=3, scan_level=SCAN_LEVEL - 1)
        _, opened = scan_folder(tmp_path, self.FILES)
        assert opened == ['a', 'b']

    def test_a_file_whose_version_is_not_known_is_always_opened(self, tmp_path):
        store_scan(tmp_path, 'a', version=0)
        _, opened = scan_folder(tmp_path, [FileRef('a', 'Program a')])
        assert opened == ['a']

    def test_the_count_says_how_many_will_be_skipped_before_anything_starts(self, tmp_path):
        store_scan(tmp_path, 'a', version=3)
        state = AppState()
        actions.propose_scan(state, 'Project / Folder', self.FILES)
        assert actions.view(state, tmp_path)['confirmScan'] == {
            'folder': 'Project / Folder', 'count': 2, 'unchanged': 1}

    def test_a_folder_with_nothing_new_finishes_without_opening_anything(self, tmp_path):
        store_scan(tmp_path, 'a', version=3)
        store_scan(tmp_path, 'b', version=3)
        state, opened = scan_folder(tmp_path, self.FILES)
        assert opened == []
        assert state.scan_running is False
        assert state.notice == (
            'Folder scan finished: 0 scanned, 2 unchanged, 0 skipped, 0 failed.')

    def test_a_scan_with_nothing_skipped_does_not_mention_unchanged(self, tmp_path):
        state, _ = scan_folder(tmp_path, self.FILES)
        assert state.notice == 'Folder scan finished: 2 scanned, 0 skipped, 0 failed.'

    def test_scanning_the_same_folder_twice_opens_nothing_the_second_time(self, tmp_path):
        scan_folder(tmp_path, self.FILES)
        _, opened = scan_folder(tmp_path, self.FILES)
        assert opened == []
