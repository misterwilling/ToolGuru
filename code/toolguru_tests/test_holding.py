"""The holding library: which cutters are picked and what is written for each."""

from __future__ import annotations

import json
from dataclasses import replace

from toolguru_tests.mock_adsk import setup_adsk_modules

setup_adsk_modules()

from toolguru_commands.commandPalette import actions
from toolguru_commands.commandPalette.state import AppState
from toolguru_lib.store import Store, data_path
from toolguru_tests.factories import (
    make_document, make_holder, make_observation, make_tool)

OTHER_HOLDER = make_holder(**{
    'product-id': 'TH-200', 'description': 'Other Holder',
    'segments': [{'height': 4.0, 'lower-diameter': 2.0, 'upper-diameter': 2.0}]})
PRESET = {'name': 'Roughing', 'n': 8000, 'v_f': 40.0}


def tool(number: int = 7, *, holder: dict | None = None, **overrides) -> dict:
    made = make_tool(**overrides)
    made['post-process'] = {'number': number}
    made['start-values'] = {'presets': [PRESET]}
    if holder is not None:
        made['holder'] = holder
    return made


SHORT = dict(geometry={'LCF': 0.75}, description='1/2 short flute')
DRILL = dict(type='drill', description='Drill')


def key(made: dict) -> str:
    return make_observation('x', tool=made).cutter_key


def scan(tmp_path, file_id: str, *tools: dict, modified: int = 1_700_086_400) -> None:
    Store(data_path(tmp_path)).replace_document(
        replace(make_document(file_id), date_modified=modified),
        [make_observation(file_id, tool=t) for t in tools])


def written(tmp_path) -> list[dict]:
    return [json.loads(text) for text in actions.library_tools(tmp_path)]


def assembly_of(tmp_path, holder_description: str) -> str:
    """The key of the assembly in the named holder, from the assembly tally."""
    state = AppState()
    actions.set_count_by(state, 'assembly', tmp_path)
    line = next(r for r in actions.view(state, tmp_path)['tally']
                if r['holder'] == holder_description)
    actions.set_count_by(state, 'cutter', tmp_path)
    return line['assembly_key']


def lines(tmp_path) -> dict[str, bool]:
    view = actions.view(AppState(), tmp_path)
    return {r.get('assembly_key', r['cutter_key']): r['in_library'] for r in view['tally']}


class TestPicking:
    def test_nothing_is_picked_until_a_line_is_ticked(self, tmp_path):
        scan(tmp_path, 'a', tool(), tool(**DRILL))
        view = actions.view(AppState(), tmp_path)
        assert [r['in_library'] for r in view['tally']] == [False, False]
        assert view['libraryCount'] == 0
        assert actions.library_tools(tmp_path) == []

    def test_a_ticked_line_is_picked_and_counted(self, tmp_path):
        scan(tmp_path, 'a', tool(), tool(**DRILL))
        actions.pick_for_library(AppState(), key(tool()), True, None, tmp_path)
        assert lines(tmp_path) == {key(tool()): True, key(tool(**DRILL)): False}
        assert actions.view(AppState(), tmp_path)['libraryCount'] == 1

    def test_unticking_takes_it_out(self, tmp_path):
        scan(tmp_path, 'a', tool())
        state = AppState()
        actions.pick_for_library(state, key(tool()), True, None, tmp_path)
        actions.pick_for_library(state, key(tool()), False, None, tmp_path)
        assert lines(tmp_path) == {key(tool()): False}
        assert actions.library_tools(tmp_path) == []

    def test_a_cutter_that_is_not_in_the_data_cannot_be_picked(self, tmp_path):
        state = AppState()
        actions.pick_for_library(state, 'no-such-cutter', True, None, tmp_path)
        assert state.error == 'That cutter is not in the data.'
        assert Store(data_path(tmp_path)).library_picks() == {}

    def test_an_assembly_that_is_not_the_cutters_cannot_be_chosen(self, tmp_path):
        scan(tmp_path, 'a', tool())
        state = AppState()
        actions.pick_for_library(state, key(tool()), True, 'made-up', tmp_path)
        assert state.error == (
            "That holder and stickout is no longer one of this cutter's.")
        assert lines(tmp_path) == {key(tool()): False}

    def test_nothing_is_picked_during_a_folder_scan(self, tmp_path):
        scan(tmp_path, 'a', tool())
        state = AppState()
        state.scan_running = True
        actions.pick_for_library(state, key(tool()), True, None, tmp_path)
        assert state.error == 'Stop the folder scan first.'
        assert Store(data_path(tmp_path)).library_picks() == {}

    def test_reset_forgets_the_picks(self, tmp_path):
        scan(tmp_path, 'a', tool())
        state = AppState()
        actions.pick_for_library(state, key(tool()), True, None, tmp_path)
        actions.reset_data(state, 'RESET', '20260101-120000', tmp_path)
        assert Store(data_path(tmp_path)).library_picks() == {}

    def test_a_pick_for_a_cutter_no_longer_scanned_is_ignored(self, tmp_path):
        scan(tmp_path, 'a', tool())
        actions.pick_for_library(AppState(), key(tool()), True, None, tmp_path)
        scan(tmp_path, 'a', tool(**DRILL))   # the rescan no longer has the end mill
        assert actions.view(AppState(), tmp_path)['libraryCount'] == 0
        assert actions.library_tools(tmp_path) == []


def line(made: dict, assembly_key: str | None = None) -> dict:
    return {'cutterKey': key(made), 'assemblyKey': assembly_key}


class TestPickingMany:
    def test_every_named_line_is_ticked_at_once(self, tmp_path):
        scan(tmp_path, 'a', tool(), tool(**DRILL), tool(**SHORT))
        actions.pick_many_for_library(
            AppState(), [line(tool()), line(tool(**DRILL))], True, tmp_path)
        assert lines(tmp_path) == {
            key(tool()): True, key(tool(**DRILL)): True, key(tool(**SHORT)): False}

    def test_every_named_line_is_unticked_at_once(self, tmp_path):
        scan(tmp_path, 'a', tool(), tool(**DRILL), tool(**SHORT))
        state = AppState()
        everything = [line(tool()), line(tool(**DRILL)), line(tool(**SHORT))]
        actions.pick_many_for_library(state, everything, True, tmp_path)
        actions.pick_many_for_library(state, everything[:2], False, tmp_path)
        assert lines(tmp_path) == {
            key(tool()): False, key(tool(**DRILL)): False, key(tool(**SHORT)): True}

    def test_a_cutter_already_ticked_keeps_the_setup_chosen_for_it(self, tmp_path):
        scan(tmp_path, 'a', tool())
        scan(tmp_path, 'b', tool())
        scan(tmp_path, 'c', tool(holder=OTHER_HOLDER))
        state = AppState()
        other = assembly_of(tmp_path, 'Other Holder')
        actions.pick_for_library(state, key(tool()), True, other, tmp_path)
        actions.pick_many_for_library(state, [line(tool())], True, tmp_path)
        assert written(tmp_path)[0]['holder']['product-id'] == 'TH-200'

    def test_one_assembly_line_ticks_the_cutter_in_that_assembly(self, tmp_path):
        scan(tmp_path, 'a', tool())
        scan(tmp_path, 'b', tool())
        scan(tmp_path, 'c', tool(holder=OTHER_HOLDER))
        other = assembly_of(tmp_path, 'Other Holder')
        actions.pick_many_for_library(AppState(), [line(tool(), other)], True, tmp_path)
        assert written(tmp_path)[0]['holder']['product-id'] == 'TH-200'

    def test_several_assembly_lines_of_one_cutter_tick_it_in_its_usual_setup(self, tmp_path):
        scan(tmp_path, 'a', tool())
        scan(tmp_path, 'b', tool())
        scan(tmp_path, 'c', tool(holder=OTHER_HOLDER))
        usual, other = assembly_of(tmp_path, 'Test Holder'), assembly_of(tmp_path, 'Other Holder')
        actions.pick_many_for_library(
            AppState(), [line(tool(), other), line(tool(), usual)], True, tmp_path)
        assert len(written(tmp_path)) == 1
        assert written(tmp_path)[0]['holder']['product-id'] == 'TH-100'

    def test_a_line_for_a_cutter_that_is_gone_is_passed_over(self, tmp_path):
        scan(tmp_path, 'a', tool())
        state = AppState()
        actions.pick_many_for_library(
            state, [{'cutterKey': 'gone', 'assemblyKey': None}, line(tool())], True, tmp_path)
        assert state.error == ''
        assert lines(tmp_path) == {key(tool()): True}

    def test_lines_that_make_no_sense_change_nothing(self, tmp_path):
        scan(tmp_path, 'a', tool())
        state = AppState()
        for bad in (None, 'abc', [key(tool())], [{'assemblyKey': 'x'}]):
            actions.pick_many_for_library(state, bad, True, tmp_path)
            assert state.error == 'The lines to tick were not understood.'
        assert lines(tmp_path) == {key(tool()): False}

    def test_nothing_is_ticked_during_a_folder_scan(self, tmp_path):
        scan(tmp_path, 'a', tool())
        state = AppState()
        state.scan_busy = True
        actions.pick_many_for_library(state, [line(tool())], True, tmp_path)
        assert state.error == 'Stop the folder scan first.'
        assert lines(tmp_path) == {key(tool()): False}


class TestWhatIsWritten:
    def test_the_tool_is_written_with_its_holder_and_presets(self, tmp_path):
        scan(tmp_path, 'a', tool())
        actions.pick_for_library(AppState(), key(tool()), True, None, tmp_path)
        (made,) = written(tmp_path)
        assert made['description'] == '1/2 flat end mill'
        assert made['holder']['product-id'] == 'TH-100'
        assert made['start-values'] == {'presets': [PRESET]}
        assert made['geometry']['DC'] == 0.5

    def test_the_usual_assembly_is_written_unless_another_is_chosen(self, tmp_path):
        scan(tmp_path, 'a', tool())
        scan(tmp_path, 'b', tool())
        scan(tmp_path, 'c', tool(holder=OTHER_HOLDER))
        state = AppState()
        actions.pick_for_library(state, key(tool()), True, None, tmp_path)
        assert written(tmp_path)[0]['holder']['product-id'] == 'TH-100'

        actions.pick_for_library(
            state, key(tool()), True, assembly_of(tmp_path, 'Other Holder'), tmp_path)
        assert written(tmp_path)[0]['holder']['product-id'] == 'TH-200'
        assert len(written(tmp_path)) == 1

    def test_with_no_usual_assembly_the_most_recently_used_is_written(self, tmp_path):
        scan(tmp_path, 'old', tool(), modified=1_000)
        scan(tmp_path, 'new', tool(holder=OTHER_HOLDER), modified=2_000)
        actions.pick_for_library(AppState(), key(tool()), True, None, tmp_path)
        assert written(tmp_path)[0]['holder']['product-id'] == 'TH-200'

    def test_the_tool_is_taken_from_the_latest_program_of_its_assembly(self, tmp_path):
        scan(tmp_path, 'old', tool(description='old name'), modified=1_000)
        scan(tmp_path, 'new', tool(description='new name'), modified=2_000)
        actions.pick_for_library(AppState(), key(tool()), True, None, tmp_path)
        assert written(tmp_path)[0]['description'] == 'new name'

    def test_the_usual_tool_number_is_written_whatever_the_source_had(self, tmp_path):
        scan(tmp_path, 'a', tool(7), modified=1_000)
        scan(tmp_path, 'b', tool(7), modified=1_500)
        scan(tmp_path, 'c', tool(3), modified=2_000)   # the latest, and the source
        actions.pick_for_library(AppState(), key(tool()), True, None, tmp_path)
        assert written(tmp_path)[0]['post-process']['number'] == 7

    def test_with_no_usual_number_the_sources_own_is_kept(self, tmp_path):
        scan(tmp_path, 'a', tool(7), modified=1_000)
        scan(tmp_path, 'b', tool(3), modified=2_000)
        actions.pick_for_library(AppState(), key(tool()), True, None, tmp_path)
        assert written(tmp_path)[0]['post-process']['number'] == 3

    def test_a_chosen_assembly_that_has_gone_falls_back_to_the_usual(self, tmp_path):
        scan(tmp_path, 'a', tool())
        scan(tmp_path, 'b', tool(holder=OTHER_HOLDER))
        scan(tmp_path, 'c', tool())
        state = AppState()
        actions.pick_for_library(
            state, key(tool()), True, assembly_of(tmp_path, 'Other Holder'), tmp_path)
        Store(data_path(tmp_path)).remove_document('b')
        assert written(tmp_path)[0]['holder']['product-id'] == 'TH-100'


def with_presets(*presets: dict, **overrides) -> dict:
    made = tool(**overrides)
    made['start-values'] = {'presets': list(presets)}
    return made


def preset(name: str, **numbers) -> dict:
    return {'name': name, 'guid': f'id-{name}', 'n': 8000, 'v_f': 40.0, **numbers}


def written_presets(tmp_path) -> list[tuple]:
    (made,) = written(tmp_path)
    return [(p['name'], p['n']) for p in made['start-values']['presets']]


class TestCombinedCuttingData:
    def test_presets_from_other_programs_are_added_after_the_tools_own(self, tmp_path):
        scan(tmp_path, 'old', with_presets(preset('Steel'), preset('Brass')), modified=1_000)
        scan(tmp_path, 'new', with_presets(preset('Aluminum')), modified=2_000)
        actions.pick_for_library(AppState(), key(tool()), True, None, tmp_path)
        assert [name for name, _ in written_presets(tmp_path)] == [
            'Aluminum', 'Brass', 'Steel']

    def test_the_same_name_takes_the_most_recently_saved_programs_numbers(self, tmp_path):
        scan(tmp_path, 'old', with_presets(preset('Aluminum', n=5000)), modified=1_000)
        scan(tmp_path, 'new', with_presets(preset('Aluminum', n=9000)), modified=2_000)
        actions.pick_for_library(AppState(), key(tool()), True, None, tmp_path)
        assert written_presets(tmp_path) == [('Aluminum', 9000)]

    def test_the_most_recent_wins_even_when_the_tool_is_written_from_another_setup(self, tmp_path):
        """The tool comes from its usual holder; a later program in another
        holder still decides the numbers of a preset both have."""
        usual = with_presets(preset('Aluminum', n=5000))
        scan(tmp_path, 'a', usual, modified=1_000)
        scan(tmp_path, 'b', usual, modified=1_500)
        scan(tmp_path, 'c', with_presets(preset('Aluminum', n=9000), holder=OTHER_HOLDER),
             modified=2_000)
        actions.pick_for_library(AppState(), key(tool()), True, None, tmp_path)
        (made,) = written(tmp_path)
        assert made['holder']['product-id'] == 'TH-100'
        assert written_presets(tmp_path) == [('Aluminum', 9000)]

    def test_a_merged_cutters_presets_come_along(self, tmp_path):
        scan(tmp_path, 'a', with_presets(preset('Aluminum')),
             with_presets(preset('Aluminum')))
        scan(tmp_path, 'b', with_presets(preset('Titanium', n=2000), **SHORT))
        state = AppState()
        actions.merge_cutters(state, [key(tool()), key(tool(**SHORT))], tmp_path)
        actions.pick_for_library(state, key(tool()), True, None, tmp_path)
        (made,) = written(tmp_path)
        assert made['geometry']['LCF'] == 1.25   # still the cutter that names the line
        assert written_presets(tmp_path) == [('Aluminum', 8000), ('Titanium', 2000)]

    def test_a_preset_from_a_millimetre_scan_is_written_in_the_inch_tools_unit(self, tmp_path):
        metric = with_presets(
            {'name': 'Metric', 'guid': 'm', 'n': 6000, 'v_f': 1016.0, 'f_z': 0.0508,
             'v_c': 304.8, 'v_f_plunge': 254.0, 'stepover': 2.54, 'use-stepover': True,
             'ramp-angle': 2},
            unit='millimeters',
            geometry={'DC': 12.7, 'LCF': 31.75, 'shoulder-length': 31.75, 'OAL': 76.2,
                      'SFDM': 12.7, 'LB': 38.1, 'assemblyGaugeLength': 101.6})
        assert key(metric) == key(tool())
        scan(tmp_path, 'a', with_presets(preset('Inch')), modified=3_000)
        scan(tmp_path, 'b', with_presets(preset('Inch')), modified=3_500)
        scan(tmp_path, 'c', metric, modified=1_000)
        actions.pick_for_library(AppState(), key(tool()), True, None, tmp_path)
        (made,) = written(tmp_path)
        assert made['unit'] == 'inches'
        added = made['start-values']['presets'][1]
        assert added['name'] == 'Metric'
        assert added['n'] == 6000 and added['ramp-angle'] == 2
        assert added['use-stepover'] is True
        assert round(added['v_f'], 6) == 40.0
        assert round(added['f_z'], 6) == 0.002
        assert round(added['v_c'], 6) == 1000.0
        assert round(added['v_f_plunge'], 6) == 10.0
        assert round(added['stepover'], 6) == 0.1

    def test_two_presets_never_share_an_id_in_one_tool(self, tmp_path):
        copied = dict(preset('Copy'), guid='id-Aluminum')
        scan(tmp_path, 'a', with_presets(preset('Aluminum')), modified=2_000)
        scan(tmp_path, 'b', with_presets(copied), modified=1_000)
        actions.pick_for_library(AppState(), key(tool()), True, None, tmp_path)
        (made,) = written(tmp_path)
        ids = [p['guid'] for p in made['start-values']['presets']]
        assert ids[0] == 'id-Aluminum'
        assert len(set(ids)) == 2

    def test_a_cutter_with_no_presets_anywhere_is_written_without_any(self, tmp_path):
        bare = make_tool()
        scan(tmp_path, 'a', bare)
        actions.pick_for_library(AppState(), key(bare), True, None, tmp_path)
        assert 'start-values' not in written(tmp_path)[0]


class TestAssemblyTally:
    def test_only_the_assembly_that_will_be_written_is_ticked(self, tmp_path):
        scan(tmp_path, 'a', tool())
        scan(tmp_path, 'b', tool())
        scan(tmp_path, 'c', tool(holder=OTHER_HOLDER))
        usual, other = assembly_of(tmp_path, 'Test Holder'), assembly_of(tmp_path, 'Other Holder')
        state = AppState()
        actions.set_count_by(state, 'assembly', tmp_path)
        actions.pick_for_library(state, key(tool()), True, None, tmp_path)
        assert lines(tmp_path) == {usual: True, other: False}

        actions.pick_for_library(state, key(tool()), True, other, tmp_path)
        assert lines(tmp_path) == {usual: False, other: True}
        assert actions.view(state, tmp_path)['libraryCount'] == 1


class TestDetail:
    def _detail(self, tmp_path) -> dict:
        state = AppState()
        actions.show_cutter(state, key(tool()))
        return actions.view(state, tmp_path)['detail']['library']

    def test_an_unpicked_cutter_shows_what_would_be_written(self, tmp_path):
        scan(tmp_path, 'a', tool())
        assert self._detail(tmp_path) == {
            'picked': False, 'choice': None,
            'assembly_key': assembly_of(tmp_path, 'Test Holder')}

    def test_a_chosen_assembly_is_shown_as_the_choice(self, tmp_path):
        scan(tmp_path, 'a', tool())
        scan(tmp_path, 'b', tool())
        scan(tmp_path, 'c', tool(holder=OTHER_HOLDER))
        other = assembly_of(tmp_path, 'Other Holder')
        actions.pick_for_library(AppState(), key(tool()), True, other, tmp_path)
        assert self._detail(tmp_path) == {
            'picked': True, 'choice': other, 'assembly_key': other}


class TestMergedLines:
    def _merged(self, tmp_path) -> AppState:
        scan(tmp_path, 'a', tool(), tool())
        scan(tmp_path, 'b', tool(**SHORT), modified=2_000_000_000)
        state = AppState()
        actions.merge_cutters(state, [key(tool()), key(tool(**SHORT))], tmp_path)
        return state

    def test_a_merged_line_is_written_as_the_cutter_that_names_it(self, tmp_path):
        state = self._merged(tmp_path)
        actions.pick_for_library(state, key(tool()), True, None, tmp_path)
        (made,) = written(tmp_path)
        assert made['geometry']['LCF'] == 1.25   # not the later, less used short one

    def test_ticking_before_merging_keeps_the_merged_line_ticked(self, tmp_path):
        scan(tmp_path, 'a', tool(), tool())
        scan(tmp_path, 'b', tool(**SHORT))
        state = AppState()
        actions.pick_for_library(state, key(tool(**SHORT)), True, None, tmp_path)
        actions.merge_cutters(state, [key(tool()), key(tool(**SHORT))], tmp_path)
        assert lines(tmp_path) == {key(tool()): True}
        assert len(written(tmp_path)) == 1

    def test_unticking_a_merged_line_unticks_every_cutter_in_it(self, tmp_path):
        state = self._merged(tmp_path)
        actions.pick_for_library(state, key(tool()), True, None, tmp_path)
        actions.pick_for_library(state, key(tool()), False, None, tmp_path)
        actions.split_cutters(state, key(tool()), tmp_path)
        assert set(lines(tmp_path).values()) == {False}


class TestWritten:
    def test_the_notice_names_the_library_and_the_count(self):
        state = AppState()
        actions.library_written(state, 12, 12)
        assert state.notice == (
            'Wrote 12 tools to “ToolGuru Holding” in your Local tool libraries. '
            'It replaces the one written before.')

    def test_one_tool_is_singular(self):
        state = AppState()
        actions.library_written(state, 1, 1)
        assert state.notice.startswith('Wrote 1 tool to ')

    def test_a_short_library_is_an_error_not_a_success(self):
        state = AppState()
        actions.library_written(state, 12, 11)
        assert state.notice == ''
        assert state.error == (
            'Fusion wrote 11 of 12 tools to “ToolGuru Holding”. '
            'See View → Text Commands.')
