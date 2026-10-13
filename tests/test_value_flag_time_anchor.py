from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetIndex, DatasetKind, DepthDomain, IndexRole, IndexType
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.tablet_print import capture_tablet_print_snapshot
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


def test_curve_value_time_anchor_distinguishes_samples_at_repeated_depth(qapp):
    dataset = Dataset("flags", "Flags", DatasetKind.GTI, DepthDomain.MD,
                      np.array([100.0, 100.0, 101.0]))
    dataset.add_index(DatasetIndex("time", "TIME", IndexType.RELATIVE_TIME,
                                  IndexRole.TIME, "s", np.array([0.0, 60.0, 120.0])))
    dataset.upsert_curve("TG", np.array([10.0, 20.0, 30.0]), unit="%")
    layout = TabletLayout([TrackDefinition("gas", "Gas", TrackKind.CURVE,
                                          curve_mnemonics=["TG"])], vertical_index_id="time")
    session = ProjectSession()
    session.add_dataset(dataset)
    session.tablet_layouts[dataset.dataset_id] = layout
    controller = DepthAnnotationController(session)
    view = TabletView()
    view.set_layout_and_dataset(layout, dataset)
    before = dataset.depth.copy()
    try:
        axis = view._axis_values()
        record = controller.add_curve_value(track_id="gas", depth=100.0,
                                            axis_value=float(axis[1]), axis_id="time",
                                            mnemonic="TG", value=20.0, unit="%")
        track = view._rendered["gas"].widget
        expected_x = view._curve_pencil_display_x(track.definition, "TG", 20.0)
        assert expected_x != view._curve_pencil_display_x(track.definition, "TG", 10.0)
        for printing in (False, True):
            track.set_print_mode(printing)
            assert view._annotation_axis_value(record) == axis[1]
            assert view._annotation_anchor_x(track, record) == expected_x
        legacy = replace(record, axis_id=None, axis_value=None)
        assert view._annotation_anchor_x(track, legacy) == view._curve_pencil_display_x(
            track.definition, "TG", 10.0,
        )
        np.testing.assert_array_equal(dataset.depth, before)
        np.testing.assert_array_equal(dataset.curve_by_mnemonic("TG").values, [10, 20, 30])
    finally:
        view.clear()
        view.close()


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("suffix", [".json", ".geologpkg"])
def test_time_flags_reopen_and_print_at_distinct_samples(qapp, tmp_path, monkeypatch, language, suffix):
    dataset = Dataset("flags", "Flags", DatasetKind.GTI, DepthDomain.MD,
                      np.array([100.0, 100.0, 101.0]))
    dataset.add_index(DatasetIndex("time", "TIME", IndexType.RELATIVE_TIME,
                                  IndexRole.TIME, "s", np.array([0.0, 60.0, 120.0])))
    dataset.upsert_curve("TG", np.array([10.0, 20.0, 30.0]), unit="%")
    layout = TabletLayout([TrackDefinition("gas", "Gas", TrackKind.CURVE,
                                          curve_mnemonics=["TG"])], vertical_index_id="time")
    session = ProjectSession()
    session.add_dataset(dataset)
    session.tablet_layouts[dataset.dataset_id] = layout
    seed = TabletView(language=language)
    seed.set_layout_and_dataset(layout, dataset)
    try:
        axis_values = seed._axis_values().copy()
    finally:
        seed.clear()
        seed.close()
    controller = DepthAnnotationController(session)
    records = tuple(controller.add_curve_value(
        track_id="gas", depth=100.0, axis_value=float(axis_values[row]),
        axis_id="time", mnemonic="TG", value=value, unit="%",
    ) for row, value in ((0, 10.0), (1, 20.0)))
    identifiers = tuple(record.annotation_id for record in records)
    controller.set_value_print_selection(identifiers, (identifiers[1],))
    target = tmp_path / ("time-flags" + suffix)
    ProjectController(session=session).save_project(target)
    reopened = ProjectController().open_project(target)
    restored = DepthAnnotationController(reopened)
    flags = tuple(restored.get(identifier) for identifier in identifiers)
    assert [flag.axis_value for flag in flags] == list(axis_values[:2])
    assert [flag.parameter_value for flag in flags] == [10.0, 20.0]
    assert [flag.depth for flag in flags] == [100.0, 100.0]
    assert [flag.print_enabled for flag in flags] == [False, True]
    assert not reopened.dirty
    reopened_dataset = reopened.current_dataset
    assert reopened_dataset is not None
    before_objects = deepcopy(reopened.current_well.canvas_objects)
    view = TabletView(language=language)
    view.resize(600, 800)
    view.set_canvas_objects(list(reopened.current_well.canvas_objects))
    view.set_layout_and_dataset(reopened.tablet_layouts[dataset.dataset_id], reopened_dataset)
    view.show()
    qapp.processEvents()
    original_paint = view.paint_annotations_for_track
    painted = []

    def check_print_selection(track_id, painter):
        items = tuple(view._annotation_overlay.annotation_item(identifier) for identifier in identifiers)
        assert all(item is not None for item in items)
        assert not items[0].isVisible()
        assert items[1].isVisible()
        track = view._rendered[track_id].widget
        assert view._annotation_axis_value(flags[0]) != view._annotation_axis_value(flags[1])
        for flag, value in zip(flags, (10.0, 20.0), strict=True):
            assert view._annotation_anchor_x(track, flag) == view._curve_pencil_display_x(
                track.definition, "TG", value,
            )
        painted.append(track_id)
        original_paint(track_id, painter)

    monkeypatch.setattr(view, "paint_annotations_for_track", check_print_selection)
    try:
        snapshot = capture_tablet_print_snapshot(
            view, page_aspect_ratio=0.75, target_content_height=700,
            included_value_annotation_ids=(identifiers[1],), raster_scale=1.0,
        )
        assert snapshot.content_height > snapshot.header_height
        assert painted == ["gas"]
        assert all(view._annotation_overlay.annotation_item(identifier).isVisible()
                   for identifier in identifiers)
        assert reopened.current_well.canvas_objects == before_objects
        assert not reopened.dirty
        np.testing.assert_array_equal(reopened_dataset.depth, [100.0, 100.0, 101.0])
        np.testing.assert_array_equal(reopened_dataset.indexes["time"].values, [0.0, 60.0, 120.0])
        np.testing.assert_array_equal(reopened_dataset.curve_by_mnemonic("TG").values, [10.0, 20.0, 30.0])
    finally:
        view.clear()
        view.close()
        view.deleteLater()
        qapp.processEvents()
