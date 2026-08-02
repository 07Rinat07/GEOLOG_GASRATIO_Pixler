from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletVerticalAxisItem, TabletView
from geoworkbench.tablet.vertical_ruler import (
    VerticalRulerMode,
    VerticalRulerScaleSettings,
    VerticalRulerTrackSettings,
)


def _dataset() -> Dataset:
    depth = np.arange(1700.0, 1751.0, dtype=np.float64)
    dataset = Dataset(
        "shared-ruler-dataset",
        "Shared ruler",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    curve = CurveData(
        CurveMetadata(
            "curve-c1",
            "C1",
            "C1",
            "%",
            None,
            dataset.dataset_id,
        ),
        np.linspace(1.0, 2.0, depth.size),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    return dataset


def _axis_values(axis: TabletVerticalAxisItem) -> tuple[float, ...]:
    return tuple(tick.value for tick in axis.resolved_ticks)

def _axis_labels(axis: TabletVerticalAxisItem) -> tuple[str, ...]:
    return tuple(tick.label for tick in axis.resolved_ticks if tick.label)

def test_depth_and_graphical_tracks_share_one_layout_object_and_tick_values(qapp) -> None:
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            tracks=[
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition(
                    "curve",
                    "Curve",
                    TrackKind.CURVE,
                    width=220,
                    curve_mnemonics=["C1"],
                ),
                TrackDefinition(
                    "gas",
                    "Gas",
                    TrackKind.GAS,
                    width=180,
                    curve_mnemonics=["C1"],
                ),
            ],
            vertical_ruler_scale=VerticalRulerScaleSettings(
                major_step=5.0,
                minor_divisions=5,
            ),
        )
    )
    view.set_dataset(_dataset())
    qapp.processEvents()

    shared = view.shared_vertical_ruler_layout
    assert shared is not None
    axes = [
        view._rendered[track_id].plot.getAxis("left")
        for track_id in ("depth", "curve", "gas")
    ]
    assert all(isinstance(axis, TabletVerticalAxisItem) for axis in axes)
    typed_axes = [axis for axis in axes if isinstance(axis, TabletVerticalAxisItem)]
    assert all(axis.shared_layout is shared for axis in typed_axes)
    assert all(axis.isVisible() for axis in typed_axes)
    assert _axis_values(typed_axes[0]) == _axis_values(typed_axes[1])
    assert _axis_values(typed_axes[0]) == _axis_values(typed_axes[2])
    view.close()


def test_off_mode_hides_only_selected_column_and_keeps_common_depth(qapp) -> None:
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            tracks=[
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition(
                    "gas",
                    "Gas",
                    TrackKind.GAS,
                    width=180,
                    curve_mnemonics=["C1"],
                    vertical_ruler=VerticalRulerTrackSettings(
                        mode=VerticalRulerMode.OFF
                    ),
                ),
            ],
            vertical_ruler_scale=VerticalRulerScaleSettings(major_step=5.0),
        )
    )
    view.set_dataset(_dataset())

    shared = view.shared_vertical_ruler_layout
    depth_axis = view._rendered["depth"].plot.getAxis("left")
    gas_axis = view._rendered["gas"].plot.getAxis("left")
    assert shared is not None
    assert isinstance(depth_axis, TabletVerticalAxisItem)
    assert isinstance(gas_axis, TabletVerticalAxisItem)
    assert depth_axis.isVisible()
    assert depth_axis.shared_layout is shared
    assert not gas_axis.isVisible()
    assert gas_axis.shared_layout is None
    view.close()


def test_track_frequency_filters_only_values_from_shared_layout(qapp) -> None:
    settings = VerticalRulerTrackSettings(
        mode=VerticalRulerMode.LABELS_AND_TICKS,
        label_every_major=2,
        major_tick_every=2,
        minor_tick_every=3,
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            tracks=[
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition(
                    "gas",
                    "Gas",
                    TrackKind.GAS,
                    width=180,
                    curve_mnemonics=["C1"],
                    vertical_ruler=settings,
                ),
            ],
            vertical_ruler_scale=VerticalRulerScaleSettings(
                major_step=5.0,
                minor_divisions=5,
            ),
        )
    )
    view.set_dataset(_dataset())

    shared = view.shared_vertical_ruler_layout
    gas_axis = view._rendered["gas"].plot.getAxis("left")
    assert shared is not None
    assert isinstance(gas_axis, TabletVerticalAxisItem)
    shared_values = {tick.value for tick in shared.ticks}
    rendered_values = _axis_values(gas_axis)
    assert rendered_values
    assert set(rendered_values).issubset(shared_values)
    assert len(rendered_values) < len(shared.ticks)
    assert _axis_labels(gas_axis) == ("1700", "1710", "1720", "1730", "1740", "1750")
    view.close()


def test_automatic_narrow_track_hides_labels_but_not_shared_tick_values(qapp) -> None:
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            tracks=[
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition(
                    "curve",
                    "Curve",
                    TrackKind.CURVE,
                    width=80,
                    curve_mnemonics=["C1"],
                ),
            ],
            vertical_ruler_scale=VerticalRulerScaleSettings(major_step=5.0),
        )
    )
    view.set_dataset(_dataset())

    depth_axis = view._rendered["depth"].plot.getAxis("left")
    curve_axis = view._rendered["curve"].plot.getAxis("left")
    assert isinstance(depth_axis, TabletVerticalAxisItem)
    assert isinstance(curve_axis, TabletVerticalAxisItem)
    assert curve_axis.isVisible()
    assert _axis_values(curve_axis) == _axis_values(depth_axis)
    assert _axis_labels(curve_axis) == ()
    assert _axis_labels(depth_axis)
    view.close()
