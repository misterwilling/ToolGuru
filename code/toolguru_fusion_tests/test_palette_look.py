"""What the palette's look depends on in a live Fusion session: the theme
values Fusion reports and the tool pictures in its install folder. Read-only.
"""

import sys
import unittest
from pathlib import Path
from urllib.parse import unquote, urlparse

import adsk.core

from toolguru_lib import theme, tool_pictures


class TestTheme(unittest.TestCase):

    def test_fusions_two_dark_themes_are_the_ones_treated_as_dark(self):
        themes = adsk.core.UserInterfaceThemes
        self.assertEqual(
            theme.DARK_THEMES,
            {themes.DarkBlueUserInterfaceTheme, themes.DarkGrayUserInterfaceTheme})
        self.assertEqual(
            theme.palette_theme(themes.LightGrayUserInterfaceTheme), 'light')
        self.assertEqual(
            theme.palette_theme(themes.ClassicUserInterfaceTheme), 'light')

    def test_the_active_theme_is_never_follow_the_device(self):
        preferences = adsk.core.Application.get().preferences.generalPreferences
        self.assertNotEqual(
            preferences.activeUserInterfaceTheme,
            adsk.core.UserInterfaceThemes.DeviceUserInterfaceTheme)


class TestToolPictures(unittest.TestCase):

    def test_every_mapped_tool_type_has_a_picture_in_this_fusion(self):
        pictures = tool_pictures.find_pictures(Path(sys.executable).parent)
        self.assertEqual(sorted(pictures), sorted(tool_pictures.PICTURE_NAMES))

    def test_a_picture_address_points_at_a_real_png(self):
        pictures = tool_pictures.find_pictures(Path(sys.executable).parent)
        address = urlparse(pictures['flat end mill'])
        self.assertEqual(address.scheme, 'file')
        path = Path(unquote(address.path).lstrip('/'))
        self.assertEqual(path.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
