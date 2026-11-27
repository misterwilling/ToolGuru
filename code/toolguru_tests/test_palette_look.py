"""The palette's look: light or dark, and Fusion's picture of each tool type."""

from toolguru_lib import cutter, theme, tool_pictures

PICTURE_FOLDER = ('Applications', 'CAM360', 'tool-library', 'static', 'png')


def _install(tmp_path, *file_names):
    folder = tmp_path.joinpath(*PICTURE_FOLDER)
    folder.mkdir(parents=True)
    for name in file_names:
        (folder / name).write_bytes(b'png')
    return folder


def test_the_two_dark_themes_are_dark_and_the_rest_are_light():
    # 0 classic, 1 light gray, 2 dark blue, 3 dark gray, 4 follow the device
    assert [theme.palette_theme(value) for value in range(5)] == [
        'light', 'light', 'dark', 'dark', 'light']


def test_a_picture_is_found_whatever_build_stamp_its_name_carries(tmp_path):
    folder = _install(tmp_path, 'ToolEndMill-rUFRgqvD.png', 'ToolDrill-Cx_W-9.png')
    assert tool_pictures.find_pictures(tmp_path) == {
        'flat end mill': (folder / 'ToolEndMill-rUFRgqvD.png').as_uri(),
        'drill': (folder / 'ToolDrill-Cx_W-9.png').as_uri()}


def test_a_right_hand_tap_does_not_pick_up_the_left_hand_or_taper_picture(tmp_path):
    folder = _install(tmp_path, 'ToolTapLeft-aaa.png', 'ToolTaperMill-bbb.png',
                      'ToolTap-ccc.png')
    pictures = tool_pictures.find_pictures(tmp_path)
    assert pictures['tap right hand'] == (folder / 'ToolTap-ccc.png').as_uri()
    assert pictures['tap left hand'] == (folder / 'ToolTapLeft-aaa.png').as_uri()
    assert pictures['tapered mill'] == (folder / 'ToolTaperMill-bbb.png').as_uri()


def test_a_type_whose_picture_is_missing_is_left_out(tmp_path):
    _install(tmp_path, 'ToolReamer-abc.png', 'ToolReamer-abc.txt')
    assert list(tool_pictures.find_pictures(tmp_path)) == ['reamer']


def test_an_install_without_the_picture_folder_gives_no_pictures(tmp_path):
    assert tool_pictures.find_pictures(tmp_path) == {}


def test_every_tool_type_in_scope_has_a_picture_except_form_mills_and_probes():
    in_scope = {tool_type for tool_type in cutter._FAMILY_BY_TYPE}
    assert in_scope - set(tool_pictures.PICTURE_NAMES) == {'form mill', 'probe'}
    assert set(tool_pictures.PICTURE_NAMES) <= in_scope
