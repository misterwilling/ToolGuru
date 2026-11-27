"""Reading a real Fusion document's CAM data into records."""

import json
import tempfile
import unittest
from pathlib import Path

from toolguru_lib import extract
from toolguru_lib.records import DocumentRecord
from toolguru_lib.store import Store, data_path
from toolguru_lib.tally import build_assembly_tally, build_tally

from toolguru_fusion_tests import helpers


class TestReadObservations(unittest.TestCase):
    """One setup: the end mill in two operations, the drill in one, the drill
    again in a suppressed operation, and a ball mill that no operation uses."""

    @classmethod
    def setUpClass(cls):
        cls.doc, cls.cam, setup = helpers.create_cam_document()
        helpers.add_operation(setup, 'face', helpers.END_MILL)
        helpers.add_operation(setup, 'contour2d', helpers.END_MILL)
        helpers.add_operation(setup, 'contour2d', helpers.DRILL)
        suppressed = helpers.add_operation(setup, 'contour2d', helpers.DRILL)
        suppressed.isSuppressed = True
        cls.cam.documentToolLibrary.add(helpers.make_tool(helpers.BALL_MILL))
        cls.observations = extract.read_observations(cls.cam, 'test-file')

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'doc'):
            helpers.close_document(cls.doc)

    def test_one_record_per_unsuppressed_operation(self):
        self.assertEqual(len(self.observations), 3)
        self.assertEqual([o.strategy for o in self.observations],
                         ['face', 'contour2d', 'contour2d'])

    def test_records_carry_the_file_and_setup(self):
        self.assertEqual({o.file_id for o in self.observations}, {'test-file'})
        self.assertEqual({o.setup_name for o in self.observations}, {'Setup1'})

    def test_end_mill_is_read_and_normalized_to_millimetres(self):
        first = self.observations[0]
        fields = json.loads(first.cutter_fields)
        self.assertEqual(first.tool_type, 'flat end mill')
        self.assertEqual(first.family, 'milling')
        self.assertEqual(first.unit, 'inches')
        self.assertEqual(first.tool_number, 7)
        self.assertEqual(first.description, 'test half inch end mill')
        self.assertEqual(fields['DC'], 12.7)
        self.assertEqual(fields['LCF'], 31.75)
        self.assertEqual(fields['NOF'], 3)
        self.assertEqual(fields['material'], 'carbide')

    def test_drill_is_read_in_its_own_unit(self):
        drill = self.observations[2]
        fields = json.loads(drill.cutter_fields)
        self.assertEqual(drill.tool_type, 'drill')
        self.assertEqual(drill.family, 'hole making')
        self.assertEqual(drill.unit, 'millimeters')
        self.assertEqual(drill.tool_number, 12)
        self.assertEqual(fields['DC'], 5.0)
        self.assertEqual(fields['NOF'], 2)

    def test_holder_and_stickout_are_read(self):
        end_mill, drill = self.observations[0], self.observations[2]
        self.assertEqual(end_mill.holder, 'test holder')
        self.assertEqual(end_mill.holder_product_id, 'th-100')
        self.assertEqual(end_mill.stickout_mm, 38.1)   # LB 1.5 in
        self.assertEqual(drill.holder_product_id, 'th-100')
        self.assertEqual(drill.stickout_mm, 50.0)

    def test_same_holder_in_inches_and_millimetres_has_one_shape(self):
        end_mill, drill = self.observations[0], self.observations[2]
        self.assertEqual(len(end_mill.holder_shape), 16)
        self.assertEqual(end_mill.holder_shape, drill.holder_shape)

    def test_scan_is_tallied_by_assembly_inside_fusion(self):
        rows = [dict(vars(o), date_created=100, date_modified=200)
                for o in self.observations]
        tally = build_assembly_tally(rows, 0.5)
        self.assertEqual(
            [(t['tool_type'], t['holder'], t['stickout_min_mm'], t['operations'])
             for t in tally],
            [('flat end mill', 'test holder', 38.1, 2),
             ('drill', 'test holder', 50.0, 1)])

    def test_same_cutter_in_separate_tool_entries_is_one_cutter(self):
        keys = [o.cutter_key for o in self.observations]
        self.assertEqual(keys[0], keys[1])
        self.assertNotEqual(keys[0], keys[2])

    def test_tool_present_but_unused_is_not_observed(self):
        # Each operation was given its own tool entry (4), plus the unused
        # ball mill: Fusion does not merge identical tools created separately.
        self.assertEqual(self.cam.documentToolLibrary.count, 5)
        self.assertEqual({o.tool_type for o in self.observations},
                         {'flat end mill', 'drill'})

    def test_operation_without_a_toolpath_has_no_cutting_time(self):
        self.assertEqual([o.cutting_time_s for o in self.observations],
                         [None, None, None])

    def test_setup_without_a_machine_gives_an_empty_machine(self):
        self.assertEqual({o.machine for o in self.observations}, {''})

    def test_raw_tool_json_is_kept(self):
        raw = json.loads(self.observations[2].tool_json)
        self.assertEqual(raw['type'], 'drill')
        self.assertEqual(raw['post-process']['number'], 12)

    def test_scan_is_stored_and_tallied_inside_fusion(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(data_path(Path(folder)))
            document = DocumentRecord(
                file_id='test-file', version=1, name='scratch', project='none',
                date_created=100, date_modified=200)
            store.replace_document(document, self.observations)
            store.replace_document(document, self.observations)
            self.assertEqual(
                store.counts(),
                {'documents': 1, 'observations': 3, 'cutters': 2})
            tally = build_tally(store.observation_rows())
            self.assertEqual(
                [(t['tool_type'], t['operations'], t['operations_without_time'])
                 for t in tally],
                [('flat end mill', 2, 2), ('drill', 1, 1)])

    def test_scanning_did_not_modify_the_document(self):
        operations_before = self.cam.allOperations.count
        extract.read_observations(self.cam, 'test-file')
        self.assertEqual(self.cam.allOperations.count, operations_before)
        self.assertEqual(self.cam.documentToolLibrary.count, 5)


class TestDocumentsThatCannotBeScanned(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = helpers.create_design_document()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'doc'):
            helpers.close_document(cls.doc)

    def test_document_never_opened_in_manufacturing_has_no_cam_data(self):
        with self.assertRaises(extract.ScanError) as raised:
            extract.cam_product(self.doc)
        self.assertEqual(str(raised.exception),
                         'This document has no Manufacturing data to scan.')

    def test_unsaved_document_is_refused(self):
        with self.assertRaises(extract.ScanError) as raised:
            extract.document_record(self.doc)
        self.assertEqual(str(raised.exception),
                         'Save this document to your hub before scanning it.')
