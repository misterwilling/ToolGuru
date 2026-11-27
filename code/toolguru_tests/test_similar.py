"""Similar cutters: what is suggested, and what treating them as the same does."""

from __future__ import annotations

from toolguru_tests.mock_adsk import setup_adsk_modules

setup_adsk_modules()

from toolguru_commands.commandPalette import actions
from toolguru_commands.commandPalette.state import AppState
from toolguru_lib import saved, similar
from toolguru_lib.store import Store, data_path
from toolguru_tests.factories import make_document, make_observation, make_tool

LONG = make_tool()                                        # 1.25 in of flute
SHORT = make_tool(geometry={'LCF': 0.75}, description='1/2 short flute')
STUB = make_tool(geometry={'OAL': 2.5}, description='1/2 stub')
FOUR_FLUTE = make_tool(geometry={'NOF': 4})
BIGGER = make_tool(geometry={'DC': 0.625, 'SFDM': 0.625})
DRILL = make_tool(type='drill')


def key(tool: dict) -> str:
    return make_observation('x', tool=tool).cutter_key


def scan(tmp_path, file_id: str, *tools: dict) -> None:
    Store(data_path(tmp_path)).replace_document(
        make_document(file_id), [make_observation(file_id, tool=t) for t in tools])


def rows(tmp_path) -> list[dict]:
    return Store(data_path(tmp_path)).observation_rows()


def suggestions(tmp_path) -> list[dict]:
    store = Store(data_path(tmp_path))
    return similar.suggest(rows(tmp_path), store.merged_cutters(), store.not_similar())


def tally_lines(tmp_path) -> list[tuple]:
    view = actions.view(AppState(), tmp_path)
    return [(r['cutter_key'], r['programs'], r['operations'], r['merged'])
            for r in view['tally']]


class TestSuggest:
    def test_cutters_differing_only_in_length_are_suggested_most_used_first(self, tmp_path):
        scan(tmp_path, 'a', LONG, LONG)
        scan(tmp_path, 'b', LONG, SHORT)
        (group,) = suggestions(tmp_path)
        assert group['tool_type'] == 'flat end mill'
        assert group['differs'] == ['LCF']
        assert [(m['cutter_key'], m['programs'], m['operations'], m['merged'])
                for m in group['members']] == [
            (key(LONG), 2, 3, False), (key(SHORT), 1, 1, False)]
        assert group['members'][1]['description'] == '1/2 short flute'
        assert group['members'][1]['fields']['LCF'] == 19.05

    def test_a_different_flute_count_diameter_or_type_is_not_similar(self, tmp_path):
        scan(tmp_path, 'a', LONG, FOUR_FLUTE, BIGGER, DRILL)
        assert suggestions(tmp_path) == []

    def test_a_cutter_on_its_own_is_not_suggested(self, tmp_path):
        scan(tmp_path, 'a', LONG, LONG)
        assert suggestions(tmp_path) == []

    def test_the_group_with_the_most_operations_comes_first(self, tmp_path):
        four_short = make_tool(geometry={'NOF': 4, 'LCF': 0.75})
        scan(tmp_path, 'a', LONG, SHORT, FOUR_FLUTE, FOUR_FLUTE, four_short)
        assert [len(g['members']) for g in suggestions(tmp_path)] == [2, 2]
        assert suggestions(tmp_path)[0]['members'][0]['cutter_key'] == key(FOUR_FLUTE)

    def test_every_differing_field_is_named_in_a_fixed_order(self, tmp_path):
        scan(tmp_path, 'a', LONG, make_tool(geometry={'OAL': 2.5, 'LCF': 0.75}, BMC='hss'))
        assert suggestions(tmp_path)[0]['differs'] == ['LCF', 'OAL', 'material']

    def test_a_group_answered_not_the_same_is_not_suggested_again(self, tmp_path):
        scan(tmp_path, 'a', LONG, SHORT)
        Store(data_path(tmp_path)).mark_not_similar(suggestions(tmp_path)[0]['signature'])
        assert suggestions(tmp_path) == []

    def test_the_question_comes_back_when_a_new_cutter_joins_the_group(self, tmp_path):
        scan(tmp_path, 'a', LONG, SHORT)
        Store(data_path(tmp_path)).mark_not_similar(suggestions(tmp_path)[0]['signature'])
        scan(tmp_path, 'b', STUB)
        assert len(suggestions(tmp_path)[0]['members']) == 3

    def test_a_fully_merged_group_is_not_suggested(self, tmp_path):
        scan(tmp_path, 'a', LONG, SHORT)
        Store(data_path(tmp_path)).merge_cutters([key(LONG), key(SHORT)])
        assert suggestions(tmp_path) == []

    def test_a_new_cutter_beside_a_merged_group_is_suggested_with_it(self, tmp_path):
        scan(tmp_path, 'a', LONG, SHORT)
        Store(data_path(tmp_path)).merge_cutters([key(LONG), key(SHORT)])
        scan(tmp_path, 'b', STUB)
        (group,) = suggestions(tmp_path)
        assert sorted((m['cutter_key'], m['merged']) for m in group['members']) == sorted([
            (key(LONG), True), (key(SHORT), True), (key(STUB), False)])


class TestMergeStore:
    def test_merging_into_an_existing_group_joins_it(self, tmp_path):
        store = Store(data_path(tmp_path))
        store.merge_cutters(['a', 'b'])
        store.merge_cutters(['b', 'c'])
        assert len(set(store.merged_cutters().values())) == 1
        assert sorted(store.merged_cutters()) == ['a', 'b', 'c']

    def test_merging_two_groups_makes_one(self, tmp_path):
        store = Store(data_path(tmp_path))
        store.merge_cutters(['a', 'b'])
        store.merge_cutters(['c', 'd'])
        store.merge_cutters(['a', 'd'])
        assert len(set(store.merged_cutters().values())) == 1

    def test_separate_groups_stay_separate(self, tmp_path):
        store = Store(data_path(tmp_path))
        store.merge_cutters(['a', 'b'])
        store.merge_cutters(['c', 'd'])
        merged = store.merged_cutters()
        assert merged['a'] == merged['b'] != merged['c'] == merged['d']

    def test_one_cutter_is_not_a_merge(self, tmp_path):
        store = Store(data_path(tmp_path))
        store.merge_cutters(['a', 'a'])
        assert store.merged_cutters() == {}

    def test_splitting_undoes_the_whole_group_and_no_other(self, tmp_path):
        store = Store(data_path(tmp_path))
        store.merge_cutters(['a', 'b', 'c'])
        store.merge_cutters(['x', 'y'])
        assert store.split_cutters('b') == 3
        assert sorted(store.merged_cutters()) == ['x', 'y']
        assert store.split_cutters('b') == 0

    def test_reset_forgets_the_decisions(self, tmp_path):
        store = Store(data_path(tmp_path))
        store.merge_cutters(['a', 'b'])
        store.mark_not_similar('sig')
        store.clear()
        assert store.merged_cutters() == {}
        assert store.not_similar() == set()

    def test_a_saved_database_carries_the_decisions(self, tmp_path):
        scan(tmp_path, 'a', LONG, SHORT)
        Store(data_path(tmp_path)).merge_cutters([key(LONG), key(SHORT)])
        saved.save('Merged', base_dir=tmp_path)
        Store(data_path(tmp_path)).clear()
        saved.load_replacing('Merged', '20260101-120000', tmp_path)
        assert sorted(Store(data_path(tmp_path)).merged_cutters()) == sorted(
            [key(LONG), key(SHORT)])


class TestMergedView:
    def _merge(self, tmp_path) -> None:
        scan(tmp_path, 'a', LONG, LONG, SHORT)
        scan(tmp_path, 'b', LONG, DRILL)
        scan(tmp_path, 'c', SHORT)
        actions.merge_cutters(AppState(), [key(LONG), key(SHORT)], tmp_path)

    def test_unmerged_cutters_each_stand_for_one(self, tmp_path):
        scan(tmp_path, 'a', LONG, SHORT)
        assert sorted(tally_lines(tmp_path)) == sorted([
            (key(LONG), 1, 1, 1), (key(SHORT), 1, 1, 1)])

    def test_a_merge_is_one_line_named_for_the_most_used_with_combined_counts(self, tmp_path):
        self._merge(tmp_path)
        assert tally_lines(tmp_path) == [
            (key(LONG), 3, 5, 2), (key(DRILL), 1, 1, 1)]

    def test_the_merged_line_shows_the_most_used_cutters_geometry(self, tmp_path):
        self._merge(tmp_path)
        state = AppState()
        actions.show_cutter(state, key(LONG))
        assert actions.view(state, tmp_path)['detail']['fields']['LCF'] == 31.75

    def test_the_cutter_count_follows_the_merge(self, tmp_path):
        self._merge(tmp_path)
        assert actions.view(AppState(), tmp_path)['counts'] == {
            'documents': 3, 'observations': 6, 'cutters': 2}

    def test_the_detail_lists_what_was_merged(self, tmp_path):
        self._merge(tmp_path)
        state = AppState()
        actions.show_cutter(state, key(LONG))
        variants = actions.view(state, tmp_path)['detail']['variants']
        assert variants['differs'] == ['LCF']
        assert [(m['cutter_key'], m['programs'], m['operations'])
                for m in variants['members']] == [
            (key(LONG), 2, 3), (key(SHORT), 2, 2)]

    def test_an_unmerged_cutter_has_no_variants(self, tmp_path):
        scan(tmp_path, 'a', LONG)
        state = AppState()
        actions.show_cutter(state, key(LONG))
        assert actions.view(state, tmp_path)['detail']['variants'] is None

    def test_opening_the_less_used_cutter_shows_the_merged_line(self, tmp_path):
        self._merge(tmp_path)
        state = AppState()
        actions.show_cutter(state, key(SHORT))
        detail = actions.view(state, tmp_path)['detail']
        assert (detail['cutter_key'], detail['operations']) == (key(LONG), 5)

    def test_the_scanned_data_is_not_altered_by_a_merge(self, tmp_path):
        scan(tmp_path, 'a', LONG, SHORT)
        before = rows(tmp_path)
        actions.merge_cutters(AppState(), [key(LONG), key(SHORT)], tmp_path)
        assert rows(tmp_path) == before

    def test_splitting_brings_the_lines_back(self, tmp_path):
        self._merge(tmp_path)
        state = AppState()
        actions.split_cutters(state, key(SHORT), tmp_path)
        assert state.notice == 'Split: 2 cutters are counted apart again.'
        assert sorted(tally_lines(tmp_path)) == sorted([
            (key(LONG), 2, 3, 1), (key(SHORT), 2, 2, 1), (key(DRILL), 1, 1, 1)])


class TestSimilarScreen:
    def test_the_screen_is_only_sent_while_it_is_open(self, tmp_path):
        scan(tmp_path, 'a', LONG, SHORT)
        state = AppState()
        assert actions.view(state, tmp_path)['similar'] is None
        actions.open_similar(state)
        screen = actions.view(state, tmp_path)['similar']
        assert len(screen['suggestions']) == 1 and screen['merged'] == []
        actions.close_similar(state)
        assert actions.view(state, tmp_path)['similar'] is None

    def test_merging_moves_a_group_from_suggested_to_merged(self, tmp_path):
        scan(tmp_path, 'a', LONG, LONG, SHORT)
        state = AppState()
        actions.open_similar(state)
        actions.merge_cutters(state, [key(LONG), key(SHORT)], tmp_path)
        screen = actions.view(state, tmp_path)['similar']
        assert screen['suggestions'] == []
        (group,) = screen['merged']
        assert group['cutter_key'] == key(LONG)
        assert group['differs'] == ['LCF']
        assert [m['operations'] for m in group['members']] == [2, 1]
        assert state.notice == ('2 cutters are now counted as one. '
                                'Split them again from this screen at any time.')

    def test_not_the_same_removes_the_suggestion(self, tmp_path):
        scan(tmp_path, 'a', LONG, SHORT)
        state = AppState()
        actions.open_similar(state)
        name = actions.view(state, tmp_path)['similar']['suggestions'][0]['signature']
        actions.not_similar(state, name, tmp_path)
        assert actions.view(state, tmp_path)['similar']['suggestions'] == []
        assert tally_lines(tmp_path)[0][3] == 1   # nothing was merged

    def test_fewer_than_two_cutters_cannot_be_merged(self, tmp_path):
        state = AppState()
        for keys in (['a'], ['a', 'a'], 'ab', None, ['a', 5]):
            actions.merge_cutters(state, keys, tmp_path)
            assert state.error == 'Pick two or more cutters to treat as the same.'
        assert Store(data_path(tmp_path)).merged_cutters() == {}

    def test_splitting_an_unmerged_cutter_says_so(self, tmp_path):
        state = AppState()
        actions.split_cutters(state, 'nothing', tmp_path)
        assert state.error == 'That cutter is not merged with any other.'

    def test_nothing_is_decided_during_a_folder_scan(self, tmp_path):
        scan(tmp_path, 'a', LONG, SHORT)
        state = AppState()
        state.scan_running = True
        actions.merge_cutters(state, [key(LONG), key(SHORT)], tmp_path)
        assert state.error == 'Stop the folder scan first.'
        actions.not_similar(state, 'sig', tmp_path)
        store = Store(data_path(tmp_path))
        assert store.merged_cutters() == {} and store.not_similar() == set()
