from dataclasses import replace

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetIndex, DatasetKind, DepthDomain, IndexRole, IndexType
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.session import ProjectSession
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
