"""Writing and removing a tool library in Fusion's Local libraries.

Uses a library of its own name, never the holding library, and removes it
when done. The tools are the made-up ones from helpers.
"""

import json
import unittest

from toolguru_lib import library

from toolguru_fusion_tests import helpers

NAME = 'ToolGuru Test Library'
PRESET = {'name': 'Test roughing', 'description': '', 'n': 8000, 'v_f': 40.0,
          'f_z': 0.002, 'v_c': 1000.0, 'v_f_plunge': 10.0, 'v_f_ramp': 20.0,
          'n_ramp': 8000, 'tool-coolant': 'flood'}


def as_json(definition: dict) -> str:
    """The tool as the scan stores it: Fusion's own JSON for it."""
    return helpers.make_tool(definition).toJson()


class TestWriteLibrary(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        library.delete_library(NAME)
        finishing = dict(PRESET, name='Test finishing', n=12000)
        end_mill = dict(helpers.END_MILL,
                        **{'start-values': {'presets': [PRESET, finishing]}})
        cls.tools = [as_json(end_mill), as_json(helpers.DRILL)]

    def tearDown(self):
        library.delete_library(NAME)

    def test_no_library_reads_as_none(self):
        self.assertIsNone(library.tool_count(NAME))
        self.assertFalse(library.delete_library(NAME))

    def test_the_written_library_holds_every_tool(self):
        self.assertEqual(library.write_library(NAME, self.tools), 2)
        self.assertEqual(library.tool_count(NAME), 2)

    def test_number_holder_and_preset_survive_the_write(self):
        library.write_library(NAME, self.tools)
        written = self._read()
        end_mill = next(t for t in written if t['type'] == 'flat end mill')
        self.assertEqual(end_mill['post-process']['number'], 7)
        self.assertEqual(end_mill['holder']['product-id'], 'TH-100')
        # Fusion stores lengths in its own unit, so 0.5 in comes back a hair off.
        self.assertAlmostEqual(end_mill['geometry']['DC'], 0.5, places=9)
        presets = end_mill['start-values']['presets']
        self.assertEqual([(p['name'], p['n']) for p in presets],
                         [('Test roughing', 8000), ('Test finishing', 12000)])

    def test_writing_again_replaces_the_library_instead_of_adding_a_second(self):
        library.write_library(NAME, self.tools)
        self.assertEqual(library.write_library(NAME, self.tools[:1]), 1)
        self.assertEqual(library.tool_count(NAME), 1)
        self.assertIsNone(library.tool_count(f'{NAME} 1'))

    def test_deleting_removes_it(self):
        library.write_library(NAME, self.tools)
        self.assertTrue(library.delete_library(NAME))
        self.assertIsNone(library.tool_count(NAME))

    def _read(self) -> list[dict]:
        import adsk.cam
        libraries = adsk.cam.CAMManager.get().libraryManager.toolLibraries
        root = libraries.urlByLocation(adsk.cam.LibraryLocations.LocalLibraryLocation)
        written = libraries.toolLibraryAtURL(root.join(NAME))
        return [json.loads(written.item(i).toJson()) for i in range(written.count)]
