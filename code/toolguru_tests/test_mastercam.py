"""Mastercam harvest records turned into ToolGuru's records."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from toolguru_lib import cutter, mastercam, similar
from toolguru_tests.factories import (
    make_harvest_holder, make_harvest_operation, make_harvest_record,
    make_harvest_transform, make_observation, make_tool)


def tool_of(**tool) -> dict:
    return mastercam.tool_record(make_harvest_operation(tool=tool), None)


class TestToolRecord:
    def test_an_end_mill_becomes_a_fusion_flat_end_mill(self):
        tool = tool_of()
        assert tool['type'] == 'flat end mill'
        assert tool['unit'] == 'inches'
        assert tool['BMC'] == 'carbide'
        assert tool['description'] == '1/2 FLAT ENDMILL'
        assert tool['product-id'] == 'EX-500'
        assert tool['post-process']['number'] == 7
        geometry = tool['geometry']
        assert (geometry['DC'], geometry['NOF'], geometry['LCF']) == (0.5, 3, 1.25)
        assert (geometry['SFDM'], geometry['RE'], geometry['LB']) == (0.5, 0, 1.5)

    @pytest.mark.parametrize('mastercam_type, fusion_type', [
        ('EndMillSphere', 'ball end mill'),
        ('EndMillBullnose', 'bull nose end mill'),
        ('ChamferMill', 'chamfer mill'),
        ('Drill', 'drill'),
        ('SpotDrill', 'spot drill'),
        ('TapRight', 'tap right hand'),
        ('ThreadMill', 'thread mill'),
        ('Bore', 'boring bar'),
    ])
    def test_tool_types_are_named_as_fusion_names_them(self, mastercam_type, fusion_type):
        assert tool_of(type=mastercam_type)['type'] == fusion_type

    def test_a_type_fusion_has_no_name_for_keeps_mastercams_in_words(self):
        tool = tool_of(type='HighFeedMill')
        assert tool['type'] == 'high feed mill'
        assert cutter.identify(tool).family == 'other'

    def test_a_ball_end_mills_corner_radius_is_half_its_diameter(self):
        # Mastercam may hold 0 there; Fusion always holds the radius.
        geometry = tool_of(type='EndMillSphere', corner_radius=0)['geometry']
        assert geometry['RE'] == 0.25
        assert geometry['tip-diameter'] == 0

    def test_a_flat_end_mills_tip_is_its_diameter_as_in_fusion(self):
        assert tool_of()['geometry']['tip-diameter'] == 0.5

    def test_a_bull_nose_tip_is_the_flat_inside_the_corners(self):
        geometry = tool_of(type='EndMillBullnose', corner_radius=0.03)['geometry']
        assert geometry['tip-diameter'] == pytest.approx(0.44)

    def test_a_chamfer_mills_angle_is_its_taper_angle(self):
        geometry = tool_of(type='ChamferMill', tip_angle=45, tip_diameter=0.02)['geometry']
        assert geometry['TA'] == 45
        assert geometry['tip-diameter'] == 0.02
        assert 'SIG' not in geometry

    def test_a_drills_angle_is_its_point_angle(self):
        geometry = tool_of(type='Drill', tip_angle=135)['geometry']
        assert geometry['SIG'] == 135
        assert geometry['TA'] == 0

    def test_an_end_mills_flat_tip_angle_is_not_an_angle_of_the_cutter(self):
        geometry = tool_of(tip_angle=180)['geometry']
        assert geometry['TA'] == 0
        assert 'SIG' not in geometry

    def test_threads_per_inch_become_a_pitch(self):
        assert tool_of(type='ThreadMill', threads=20)['geometry']['TP'] == 0.05

    def test_threads_on_a_tool_that_is_not_threaded_are_ignored(self):
        assert tool_of(threads=20)['geometry']['TP'] == 0

    def test_a_metric_part_keeps_millimetres(self):
        tool = tool_of(is_metric=True, diameter=12.0)
        assert tool['unit'] == 'millimeters'
        assert cutter.identify(tool).fields['DC'] == 12.0

    def test_the_holder_profile_is_turned_tool_end_first(self):
        holder = tool_of()['holder']
        assert holder['description'] == 'Test Chuck'
        assert holder['segments'] == [
            {'height': 1.0, 'lower-diameter': 1.0, 'upper-diameter': 1.25},
            {'height': 2.0, 'lower-diameter': 1.75, 'upper-diameter': 1.75},
        ]
        assert holder['gaugeLength'] == 3.0

    def test_no_holder_profile_means_no_holder(self):
        operation = make_harvest_operation(holder=make_harvest_holder(segments=[]))
        assert 'holder' not in mastercam.tool_record(operation, None)

    def test_overall_length_is_the_whole_tool_not_the_part_below_the_holder(self):
        assembly = {'tool': {'overall_length': 1.5, 'true_physical_length': 3.0}}
        tool = mastercam.tool_record(make_harvest_operation(), assembly)
        assert tool['geometry']['OAL'] == 3.0

    def test_without_the_assembly_the_overall_length_is_at_least_the_stickout(self):
        assert tool_of()['geometry']['OAL'] == 1.5

    def test_an_operation_without_a_tool_has_no_tool_record(self):
        assert mastercam.tool_record(make_harvest_operation(no_tool=True), None) is None

    def test_the_same_tool_is_the_same_record_every_time(self):
        # So importing a file twice stores exactly what it stored before.
        assert json.dumps(tool_of()) == json.dumps(tool_of())


class TestKeptApartFromFusion:
    # make_tool() is the same 1/2 inch 3-flute carbide end mill, as Fusion holds it.
    FUSION = make_tool(geometry={'tip-diameter': 0.5})
    MASTERCAM = mastercam.tool_record(
        make_harvest_operation(), {'tool': {'true_physical_length': 3.0}})

    def test_the_same_geometry_is_a_different_cutter(self):
        ours, theirs = cutter.identify(self.MASTERCAM), cutter.identify(self.FUSION)
        geometry = {k: v for k, v in ours.fields.items() if k != 'source'}
        assert geometry == theirs.fields
        assert ours.key != theirs.key

    def test_the_cutter_says_where_it_came_from(self):
        assert cutter.identify(self.MASTERCAM).fields['source'] == 'mastercam'
        assert 'source' not in cutter.identify(self.FUSION).fields

    def test_a_fusion_cutters_key_is_what_it_always_was(self):
        # Merges and library picks are stored against these keys.
        assert cutter.identify(make_tool()).key == 'f93b744d6d75e328'

    def test_two_mastercam_files_with_the_same_cutter_share_it(self):
        other = tool_of(name='HALF INCH EM', number=12)
        assert cutter.identify(other).key == cutter.identify(tool_of()).key

    def test_the_two_are_offered_as_similar_so_they_can_be_merged_by_hand(self):
        _, mastercam_rows = mastercam.convert(make_harvest_record())
        rows = [dict(vars(mastercam_rows[0]), id=1),
                dict(vars(make_observation('file-1', tool=self.FUSION)), id=2)]
        suggestions = similar.suggest(rows, {}, set())
        assert len(suggestions) == 1
        assert suggestions[0]['differs'] == ['source']
        assert len(suggestions[0]['members']) == 2


class TestCuttingTimes:
    def times(self, operations: list[dict]) -> tuple[list[float | None], float]:
        counted, uncredited = mastercam.cutting_times(operations)
        return [counted.get(i) for i in range(len(operations))], uncredited

    def test_an_operation_counts_its_own_time(self):
        assert self.times([make_harvest_operation(1, seconds=42.5)]) == ([42.5], 0.0)

    def test_an_out_of_date_operation_has_no_time(self):
        assert self.times([make_harvest_operation(1, seconds=None)]) == ([None], 0.0)

    def test_a_transform_of_everything_before_it_is_shared_out(self):
        # 300 s is exactly 3 x (40 + 60): three more copies of both.
        operations = [make_harvest_operation(1, seconds=40.0),
                      make_harvest_operation(2, seconds=60.0),
                      make_harvest_transform(3, 300.0)]
        assert self.times(operations) == ([160.0, 240.0, None], 0.0)

    def test_a_ghosted_original_runs_only_through_its_transform(self):
        operations = [make_harvest_operation(1, seconds=40.0, posting=False),
                      make_harvest_transform(2, 320.0)]
        assert self.times(operations) == ([320.0, None], 0.0)

    def test_a_transform_of_the_ghosted_operations_leaves_the_posted_ones_alone(self):
        # 200 s fits the ghosted pair (2 x 100) and not all three (130).
        operations = [make_harvest_operation(1, seconds=30.0),
                      make_harvest_operation(2, seconds=40.0, posting=False),
                      make_harvest_operation(3, seconds=60.0, posting=False),
                      make_harvest_transform(4, 200.0)]
        assert self.times(operations) == ([30.0, 80.0, 120.0, None], 0.0)

    def test_a_transform_of_the_last_few_operations_is_found(self):
        # 150 s is 3 x the last operation and no whole multiple of both.
        operations = [make_harvest_operation(1, seconds=37.0),
                      make_harvest_operation(2, seconds=50.0),
                      make_harvest_transform(3, 150.0)]
        assert self.times(operations) == ([37.0, 200.0, None], 0.0)

    def test_two_ways_to_split_the_last_few_prove_nothing(self):
        # 120 s is 2 x the last one and also 1 x the last two.
        operations = [make_harvest_operation(1, seconds=33.0),
                      make_harvest_operation(2, seconds=60.0),
                      make_harvest_operation(3, seconds=60.0),
                      make_harvest_transform(4, 120.0)]
        assert self.times(operations) == ([33.0, 60.0, 60.0, None], 120.0)

    def test_a_transform_that_fits_nothing_is_not_credited(self):
        operations = [make_harvest_operation(1, seconds=40.0),
                      make_harvest_transform(2, 123.4)]
        assert self.times(operations) == ([40.0, None], 123.4)

    def test_a_near_miss_is_not_a_fit(self):
        operations = [make_harvest_operation(1, seconds=40.0),
                      make_harvest_transform(2, 120.01)]
        assert self.times(operations) == ([40.0, None], 120.01)

    def test_a_second_transform_in_a_row_repeats_the_same_operations(self):
        operations = [make_harvest_operation(1, seconds=50.0),
                      make_harvest_operation(2, seconds=10.0, posting=False),
                      make_harvest_transform(3, 80.0),
                      make_harvest_transform(4, 40.0)]
        assert self.times(operations) == ([50.0, 120.0, None, None], 0.0)

    def test_a_ghosted_transform_is_not_run_at_all(self):
        operations = [make_harvest_operation(1, seconds=40.0),
                      make_harvest_transform(2, 80.0, posting=False),
                      make_harvest_transform(3, 77.7, posting=False)]
        assert self.times(operations) == ([40.0, None, None], 0.0)

    def test_a_ghosted_operation_nothing_repeats_has_no_time(self):
        operations = [make_harvest_operation(1, seconds=40.0, posting=False)]
        assert self.times(operations) == ([None], 0.0)

    def test_a_transform_only_repeats_operations_in_its_own_group(self):
        operations = [make_harvest_operation(1, seconds=40.0, toolpath_group='Side 1'),
                      make_harvest_transform(2, 80.0, toolpath_group='Side 2')]
        assert self.times(operations) == ([40.0, None], 80.0)

    def test_an_operation_with_no_time_cannot_prove_a_fit(self):
        operations = [make_harvest_operation(1, seconds=None),
                      make_harvest_operation(2, seconds=40.0),
                      make_harvest_transform(3, 80.0)]
        # The last one alone fits; the pair cannot be checked.
        assert self.times(operations) == ([None, 120.0, None], 0.0)

    def test_a_harvest_from_before_ghosting_was_recorded_counts_every_operation(self):
        operation = make_harvest_operation(1, seconds=40.0)
        del operation['posting']
        assert self.times([operation]) == ([40.0], 0.0)


class TestConvert:
    def test_the_document_is_the_part_file(self):
        document, _ = mastercam.convert(make_harvest_record())
        assert document.file_id == r'mastercam:c:\parts\example\bracket.mcam'
        assert document.name == 'Bracket'
        assert document.project == 'Example'
        assert document.version == 0
        assert document.uncredited_time_s is None

    def test_first_and_last_used_come_from_the_parts_own_history(self):
        document, _ = mastercam.convert(make_harvest_record())
        assert document.date_created == int(datetime(2024, 1, 10, 9, 0).timestamp())
        assert document.date_modified == int(datetime(2025, 6, 15, 8, 30).timestamp())
        assert document.scanned_at == int(datetime(2026, 3, 1, 10, 0).timestamp())

    def test_a_part_with_no_history_uses_when_the_file_was_saved(self):
        document, _ = mastercam.convert(make_harvest_record(history={'count': 0}))
        saved = int(datetime(2025, 6, 15, 8, 30).timestamp())
        assert (document.date_created, document.date_modified) == (saved, saved)

    def test_the_same_file_typed_in_another_case_is_the_same_document(self):
        lower, _ = mastercam.convert(make_harvest_record())
        upper, _ = mastercam.convert(make_harvest_record(path=r'C:\PARTS\Example\BRACKET.MCAM'))
        assert lower.file_id == upper.file_id

    def test_one_observation_for_each_operation_with_a_tool(self):
        record = make_harvest_record([
            make_harvest_operation(1), make_harvest_operation(2, no_tool=True),
            make_harvest_operation(3)])
        _, observations = mastercam.convert(record)
        assert [o.operation_name for o in observations] == ['OP 1', 'OP 3']

    def test_an_observation_reads_like_a_fusion_one(self):
        _, (observation,) = mastercam.convert(make_harvest_record())
        assert observation.file_id == r'mastercam:c:\parts\example\bracket.mcam'
        assert observation.setup_name == 'Side 1'
        assert observation.machine == 'Example VMC'
        assert observation.strategy == 'Contour (2D)'
        assert observation.tool_type == 'flat end mill'
        assert observation.family == 'milling'
        assert observation.description == '1/2 FLAT ENDMILL'
        assert observation.tool_number == 7
        assert observation.holder == 'Test Chuck'
        assert observation.stickout_mm == 38.1
        assert observation.cutting_time_s == 60.0
        assert json.loads(observation.tool_json)['source'] == 'mastercam'

    def test_speed_and_feed_are_stored_as_numbers_in_millimetres(self):
        _, (observation,) = mastercam.convert(make_harvest_record())
        assert observation.spindle_speed == '8000'
        assert observation.feed == '40 in/min'
        assert observation.spindle_rpm == 8000.0
        assert observation.feed_mm_min == 1016.0

    def test_a_metric_parts_feed_is_already_millimetres(self):
        record = make_harvest_record([make_harvest_operation(
            tool={'is_metric': True, 'diameter': 12.0}, feed_rate=900)])
        _, (observation,) = mastercam.convert(record)
        assert observation.feed == '900 mm/min'
        assert observation.feed_mm_min == 900.0

    def test_without_the_full_type_name_the_basic_type_is_the_strategy(self):
        operation = make_harvest_operation()
        del operation['type_name']
        _, (observation,) = mastercam.convert(make_harvest_record([operation]))
        assert observation.strategy == 'Contour'

    def test_a_transforms_time_reaches_the_tool(self):
        record = make_harvest_record([
            make_harvest_operation(1, seconds=40.0, posting=False),
            make_harvest_transform(2, 160.0)])
        document, (observation,) = mastercam.convert(record)
        assert observation.cutting_time_s == 160.0
        assert document.uncredited_time_s is None

    def test_transform_time_that_fits_nothing_is_kept_with_the_document(self):
        record = make_harvest_record([
            make_harvest_operation(1, seconds=40.0), make_harvest_transform(2, 99.0)])
        document, (observation,) = mastercam.convert(record)
        assert observation.cutting_time_s == 40.0
        assert document.uncredited_time_s == 99.0

    def test_the_holder_is_the_same_holder_whichever_operation_it_is_read_from(self):
        record = make_harvest_record([make_harvest_operation(1), make_harvest_operation(2)])
        _, (first, second) = mastercam.convert(record)
        assert first.holder_shape == second.holder_shape != ''
