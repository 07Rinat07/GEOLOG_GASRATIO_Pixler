import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetIndex, DatasetKind, DepthDomain, IndexRole, IndexType
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.session import ProjectSession
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


@pytest.mark.parametrize("missing", [np.nan, np.inf, -np.inf])
@pytest.mark.parametrize("printing", [False, True])
def test_saved_time_flag_does_not_borrow_neighbour_value_in_gap(qapp, missing, printing):
    dataset = Dataset("gap", "Gap", DatasetKind.GTI, DepthDomain.MD,
                      np.array([100.0, 100.0, 101.0]))
    dataset.add_index(DatasetIndex("time", "TIME", IndexType.RELATIVE_TIME,
                                  IndexRole.TIME, "s", np.array([0.0, 60.0, 120.0])))
    dataset.upsert_curve("TG", np.array([10.0, 20.0, 30.0]), unit="%")
    layout = TabletLayout([TrackDefinition("gas", "Gas", TrackKind.CURVE,
                                          curve_mnemonics=["TG"])], vertical_index_id="time")
    session = ProjectSession()
    session.add_dataset(dataset)
    session.tablet_layouts[dataset.dataset_id] = layout
    view = TabletView()
    view.set_layout_and_dataset(layout, dataset)
    axis_values = view._axis_values().copy()
    flag = DepthAnnotationController(session).add_curve_value(
        track_id="gas", depth=100.0, axis_value=float(axis_values[1]),
        axis_id="time", mnemonic="TG", value=20.0, unit="%",
    )
    curve = dataset.curve_by_mnemonic("TG")
    assert curve is not None
    curve.values[1] = missing
    source_values = curve.values.copy()
    try:
        track = view._rendered["gas"].widget
        track.set_print_mode(printing)
        expected = view._curve_pencil_display_x(track.definition, "TG", 20.0)
        assert expected != view._curve_pencil_display_x(track.definition, "TG", 10.0)
        assert view._annotation_axis_value(flag) == axis_values[1]
        assert view._annotation_anchor_x(track, flag) == expected
        assert flag.parameter_value == 20.0
        np.testing.assert_array_equal(curve.values, source_values)
        np.testing.assert_array_equal(dataset.depth, [100.0, 100.0, 101.0])
        np.testing.assert_array_equal(dataset.indexes["time"].values, [0.0, 60.0, 120.0])
    finally:
        view.clear()
        view.close()
        view.deleteLater()
        qapp.processEvents()
