"""Folder scan against a live Fusion session.

The hub tests only read: they list projects and open no document. They name
nothing from the hub; they compare what `hub.py` reports with what Fusion
reports for whichever projects are there.
"""

import tempfile
import unittest
from pathlib import Path

import adsk.core

from toolguru_commands.commandPalette import actions
from toolguru_commands.commandPalette.state import AppState
from toolguru_lib import extract, hub
from toolguru_lib.records import DocumentRecord, FileRef, ScanError

from toolguru_fusion_tests import helpers


class TestHubBrowse(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = adsk.core.Application.get()
        cls.data = cls.app.data
        cls.top = hub.browse(cls.data, '')

    def test_the_top_level_lists_every_project_in_order(self):
        projects = self.data.dataProjects
        self.assertEqual(self.top['folderId'], '')
        self.assertEqual(self.top['path'], [])
        self.assertEqual(self.top['programs'], 0)
        self.assertEqual(
            [entry['name'] for entry in self.top['folders']],
            [projects.item(i).name for i in range(projects.count)])

    def test_a_project_opens_by_the_id_the_listing_gave(self):
        first = self.top['folders'][0]
        folder = hub.find_folder(self.data, first['id'])
        listing = hub.browse(self.data, first['id'])

        self.assertTrue(folder.isRoot)
        self.assertEqual(listing['folderId'], first['id'])
        self.assertEqual(listing['path'], [first])
        self.assertEqual(hub.folder_label(folder), first['name'])
        self.assertEqual(len(listing['folders']), folder.dataFolders.count)
        self.assertEqual(
            listing['programs'], len(hub.collect_programs(folder, False)))

    def test_a_folder_id_that_does_not_exist_is_a_scan_error(self):
        with self.assertRaises(ScanError) as caught:
            hub.find_folder(self.data, 'not-a-folder-id')
        self.assertEqual(str(caught.exception),
                         'That folder is no longer in your hub.')

    def test_a_file_id_that_does_not_exist_opens_nothing(self):
        before = self.app.documents.count
        with self.assertRaises(ScanError) as caught:
            hub.scan_file(self.app, 'not-a-file-id')
        self.assertEqual(str(caught.exception),
                         'This file is no longer in your hub.')
        self.assertEqual(self.app.documents.count, before)

    def test_first_saved_is_the_oldest_version_not_the_files_own_date(self):
        data_file = self._a_design_saved_more_than_once()
        if data_file is None:
            self.skipTest('No design with several versions at the top of a project.')
        versions = data_file.versions
        dates = {versions.item(i).versionNumber: versions.item(i).dateCreated
                 for i in range(versions.count)}

        self.assertEqual(extract.first_saved(data_file), dates[min(dates)])
        self.assertEqual(data_file.dateCreated, dates[max(dates)])
        self.assertLess(extract.first_saved(data_file), data_file.dateCreated)

    def _a_design_saved_more_than_once(self):
        projects = self.data.dataProjects
        for p in range(projects.count):
            files = projects.item(p).rootFolder.dataFiles
            for f in range(files.count):
                data_file = files.item(f)
                if (data_file.fileExtension == hub.PROGRAM_EXTENSION
                        and data_file.versionNumber > 1):
                    return data_file
        return None


class TestScanSteps(unittest.TestCase):
    """The scan loop's step, reading a real document into a real dataset
    file: one program with two tools, then a design with nothing to scan."""

    @classmethod
    def setUpClass(cls):
        cls.doc, cls.cam, setup = helpers.create_cam_document()
        helpers.add_operation(setup, 'face', helpers.END_MILL)
        helpers.add_operation(setup, 'contour2d', helpers.DRILL)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'doc'):
            helpers.close_document(cls.doc)

    def _scan_one(self, file_id):
        if file_id == 'plain-design':
            raise ScanError('This document has no Manufacturing data to scan.')
        return (DocumentRecord(file_id, 1, 'Program', 'Project', 100, 200),
                extract.read_observations(self.cam, file_id))

    def test_a_queued_folder_is_scanned_one_program_per_step(self):
        with tempfile.TemporaryDirectory() as folder:
            base_dir = Path(folder)
            state = AppState()
            actions.propose_scan(state, 'Project / Folder', [
                FileRef('program', 'Program'),
                FileRef('plain-design', 'Plain design')])
            self.assertTrue(actions.start_scan(state, base_dir))

            self.assertTrue(actions.scan_step(state, self._scan_one, base_dir))
            midway = actions.view(state, base_dir)
            self.assertEqual(midway['scan']['pending'], 1)
            self.assertTrue(midway['scan']['running'])

            self.assertFalse(actions.scan_step(state, self._scan_one, base_dir))
            view = actions.view(state, base_dir)

        self.assertEqual(view['counts'],
                         {'documents': 1, 'observations': 2, 'cutters': 2})
        self.assertEqual(
            sorted(row['tool_type'] for row in view['tally']),
            ['drill', 'flat end mill'])
        self.assertEqual(view['scan'], {
            'folder': 'Project / Folder', 'total': 2, 'pending': 0,
            'scanned': 1, 'skipped': 1, 'failed': 0, 'running': False,
            'problems': [{
                'name': 'Plain design', 'status': 'skipped',
                'message': 'This document has no Manufacturing data to scan.'}]})
        self.assertEqual(
            view['notice'],
            'Folder scan finished: 1 scanned, 1 skipped, 0 failed.')
