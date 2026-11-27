"""Finding programs in the hub and opening them, against a made-up hub.

The hub objects here are plain stand-ins with the few members `hub.py` reads.
What they cannot show (that Fusion's own calls behave this way) is checked
against a live hub by hand; see docs/PROGRESS.md.
"""

from types import SimpleNamespace

import pytest

from toolguru_tests.mock_adsk import setup_adsk_modules

setup_adsk_modules()

from toolguru_lib import hub
from toolguru_lib.records import FileRef, ScanError
from toolguru_tests.mock_adsk import MockCollection


def make_file(file_id: str, extension: str = 'f3d',
              version: int = 4) -> SimpleNamespace:
    return SimpleNamespace(id=file_id, name=f'Program {file_id}',
                           fileExtension=extension, versionNumber=version)


def make_folder(folder_id: str, files=(), folders=(), *, project: str = '',
                ) -> SimpleNamespace:
    """A folder; give `project` to make it a project's top folder."""
    folder = SimpleNamespace(
        id=folder_id, name=folder_id, isRoot=bool(project),
        dataFiles=MockCollection(files), dataFolders=MockCollection(folders),
        parentFolder=None,
        parentProject=SimpleNamespace(name=project) if project else None)
    for child in folders:
        child.parentFolder = folder
    return folder


def make_data(*roots) -> SimpleNamespace:
    known = {}

    def remember(folder):
        known[folder.id] = folder
        for i in range(folder.dataFolders.count):
            remember(folder.dataFolders.item(i))

    for root in roots:
        remember(root)
    def find_folder_by_id(folder_id):
        if folder_id not in known:   # as Fusion does for an id it cannot find
            raise RuntimeError('3 : invalid folder id')
        return known[folder_id]

    projects = [SimpleNamespace(name=root.parentProject.name, rootFolder=root)
                for root in roots]
    return SimpleNamespace(dataProjects=MockCollection(projects),
                           findFolderById=find_folder_by_id)


@pytest.fixture
def data():
    deep = make_folder('deep', [make_file('d1')])
    jobs = make_folder('jobs', [make_file('j1'), make_file('j2'),
                                make_file('sheet', 'f2d')], [deep])
    empty = make_folder('empty')
    return make_data(
        make_folder('root-1', [make_file('r1')], [jobs, empty], project='Mill'),
        make_folder('root-2', project='Lathe'))


class TestBrowse:
    def test_the_top_level_lists_projects_by_their_top_folder(self, data):
        assert hub.browse(data, '') == {
            'folderId': '', 'path': [], 'programs': 0,
            'folders': [{'id': 'root-1', 'name': 'Mill'},
                        {'id': 'root-2', 'name': 'Lathe'}]}

    def test_a_project_shows_its_folders_and_its_own_designs(self, data):
        assert hub.browse(data, 'root-1') == {
            'folderId': 'root-1',
            'path': [{'id': 'root-1', 'name': 'Mill'}],
            'folders': [{'id': 'jobs', 'name': 'jobs'},
                        {'id': 'empty', 'name': 'empty'}],
            'programs': 1}

    def test_a_folder_counts_only_fusion_designs_directly_inside(self, data):
        listing = hub.browse(data, 'jobs')
        assert listing['programs'] == 2
        assert listing['folders'] == [{'id': 'deep', 'name': 'deep'}]

    def test_the_path_runs_from_the_project_down(self, data):
        assert hub.browse(data, 'deep')['path'] == [
            {'id': 'root-1', 'name': 'Mill'}, {'id': 'jobs', 'name': 'jobs'},
            {'id': 'deep', 'name': 'deep'}]

    def test_a_folder_that_is_gone_is_reported_plainly(self, data):
        with pytest.raises(ScanError, match='no longer in your hub'):
            hub.browse(data, 'deleted')


class TestCollectPrograms:
    def test_without_subfolders_only_the_folder_itself_is_read(self, data):
        assert hub.collect_programs(hub.find_folder(data, 'jobs'), False) == [
            FileRef('j1', 'Program j1', 4), FileRef('j2', 'Program j2', 4)]

    def test_with_subfolders_everything_below_is_included(self, data):
        found = hub.collect_programs(hub.find_folder(data, 'root-1'), True)
        assert [f.file_id for f in found] == ['r1', 'j1', 'j2', 'd1']

    def test_drawings_and_other_files_are_left_out(self, data):
        found = hub.collect_programs(hub.find_folder(data, 'jobs'), True)
        assert 'sheet' not in [f.file_id for f in found]

    def test_an_empty_folder_has_no_programs(self, data):
        assert hub.collect_programs(hub.find_folder(data, 'empty'), True) == []

    def test_folder_label_names_the_project_and_each_folder(self, data):
        assert hub.folder_label(hub.find_folder(data, 'deep')) == (
            'Mill / jobs / deep')
        assert hub.folder_label(hub.find_folder(data, 'root-2')) == 'Lathe'


class FakeDocument:
    def __init__(self, file_id):
        self.dataFile = SimpleNamespace(id=file_id) if file_id else None
        self.closed_with = []

    def close(self, save_changes):
        self.closed_with.append(save_changes)


class FakeApp:
    """An application with some documents already open."""

    def __init__(self, in_hub, already_open=()):
        self.open_docs = [FakeDocument(file_id) for file_id in already_open]
        self.opened = []
        def find_file_by_id(file_id):
            if file_id not in in_hub:   # as Fusion does for an id it cannot find
                raise RuntimeError('3 : invalid id')
            return SimpleNamespace(id=file_id)

        self.data = SimpleNamespace(findFileById=find_file_by_id)
        self.documents = SimpleNamespace(
            count=len(self.open_docs),
            item=lambda i: self.open_docs[i],
            open=self._open)

    def _open(self, data_file, visible):
        doc = FakeDocument(data_file.id)
        self.opened.append(doc)
        return doc


class TestScanFile:
    @pytest.fixture(autouse=True)
    def read_any_document(self, monkeypatch):
        self.read = []

        def scan_document(doc):
            self.read.append(doc)
            if doc.dataFile.id == 'bad':
                raise ScanError('This document has no Manufacturing data to scan.')
            return 'document', ['observation']

        monkeypatch.setattr(hub.extract, 'scan_document', scan_document)

    def test_a_program_is_opened_read_and_closed_without_saving(self):
        app = FakeApp(in_hub={'a'}, already_open=[None, 'other'])
        assert hub.scan_file(app, 'a') == ('document', ['observation'])
        assert len(app.opened) == 1
        assert self.read == app.opened
        assert app.opened[0].closed_with == [False]

    def test_a_program_the_user_has_open_is_read_and_left_open(self):
        app = FakeApp(in_hub={'a'}, already_open=['other', 'a'])
        hub.scan_file(app, 'a')
        assert app.opened == []
        assert self.read == [app.open_docs[1]]
        assert app.open_docs[1].closed_with == []

    def test_a_program_that_cannot_be_read_is_still_closed_unsaved(self):
        app = FakeApp(in_hub={'bad'})
        with pytest.raises(ScanError):
            hub.scan_file(app, 'bad')
        assert app.opened[0].closed_with == [False]

    def test_a_file_deleted_since_the_count_is_reported_and_nothing_opens(self):
        app = FakeApp(in_hub=set())
        with pytest.raises(ScanError, match='no longer in your hub'):
            hub.scan_file(app, 'gone')
        assert app.opened == []
