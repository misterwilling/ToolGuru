"""User settings: one file beside the data file, defaults until saved."""

from toolguru_lib import settings as user_settings
from toolguru_lib.settings import Settings


def test_defaults_before_anything_is_saved(tmp_path):
    assert user_settings.load(tmp_path) == Settings(
        count_by='cutter', stickout_tolerance_mm=0.5, display_unit='in',
        description_width_px=240)
    assert not user_settings.settings_path(tmp_path).exists()


def test_saved_settings_are_read_back(tmp_path):
    user_settings.save(Settings('assembly', 1.25, 'mm', 410), tmp_path)
    assert user_settings.load(tmp_path) == Settings('assembly', 1.25, 'mm', 410)


def test_settings_file_sits_beside_the_data_file(tmp_path):
    assert user_settings.settings_path(tmp_path) == tmp_path / 'settings.json'


def test_a_file_from_before_a_setting_existed_gets_that_default(tmp_path):
    user_settings.settings_path(tmp_path).write_text(
        '{"count_by": "assembly"}', encoding='utf-8')
    assert user_settings.load(tmp_path) == Settings('assembly', 0.5, 'in', 240)
