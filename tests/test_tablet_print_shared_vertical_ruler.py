from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.printing.tablet_print import capture_tablet_print_snapshot
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView
from geoworkbench.tablet.vertical_ruler import (
    VerticalRulerMode,
    VerticalRulerScaleSettings,
    VerticalRulerTrackSettings,
)


def _dataset() -> Dataset:
    depth = np.arange(1700.0, 1751.0, dtype=np.float64)
    dataset = Dataset(
        "print-ruler-dataset",
        "Print ruler",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    dataset.curves["curve-c1"] = CurveData(
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
    return dataset


def _view() -> TabletView:
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
                        mode=VerticalRulerMode.LABELS_AND_TICKS,
                        label_every_major=2,
                        major_tick_every=2,
                        minor_tick_every=3,
                    ),
                ),
            ],
            vertical_ruler_scale=VerticalRulerScaleSettings(
                major_step=5.0,
                minor_divisions=5,
            ),
        )
    )
    view.resize(720, 760)
    view.set_dataset(_dataset())
    view.set_visible_depth(1700.0, 1725.0)
    return view


def test_print_snapshot_records_one_resolved_ruler_for_all_columns(qapp) -> None:
    view = _view()
    qapp.processEvents()

    snapshot = capture_tablet_print_snapshot(
        view,
        page_aspect_ratio=1.4,
        fit_columns=True,
        target_content_height=840,
        layout_content_height=840,
    )

    layout = snapshot.vertical_ruler_layout
    ticks_by_track = dict(snapshot.vertical_ruler_ticks_by_track)
    assert layout is not None
    assert layout.minimum == 1700.0
    assert layout.maximum == 1725.0
    assert layout.major_step == 5.0
    assert set(ticks_by_track) == {"depth", "gas"}
    shared_values = {tick.value for tick in layout.ticks}
    depth_values = {tick.value for tick in ticks_by_track["depth"]}
    gas_values = {tick.value for tick in ticks_by_track["gas"]}
    assert depth_values == shared_values
    assert gas_values
    assert gas_values.issubset(shared_values)
    assert len(gas_values) < len(depth_values)
    view.close()


def test_adjacent_print_pages_keep_the_exact_shared_boundary_tick(qapp) -> None:
    view = _view()
    qapp.processEvents()

    view.set_visible_depth(1700.0, 1725.0)
    first = capture_tablet_print_snapshot(
        view,
        page_aspect_ratio=1.4,
        target_content_height=840,
        layout_content_height=840,
    )
    view.set_visible_depth(1725.0, 1750.0)
    second = capture_tablet_print_snapshot(
        view,
        page_aspect_ratio=1.4,
        target_content_height=840,
        layout_content_height=840,
    )

    assert first.vertical_ruler_layout is not None
    assert second.vertical_ruler_layout is not None
    first_values = {tick.value for tick in first.vertical_ruler_layout.ticks}
    second_values = {tick.value for tick in second.vertical_ruler_layout.ticks}
    assert 1725.0 in first_values
    assert 1725.0 in second_values
    assert first.vertical_ruler_layout.maximum == second.vertical_ruler_layout.minimum
    view.close()


def test_print_capture_restores_screen_ruler_mode_and_range(qapp) -> None:
    view = _view()
    qapp.processEvents()
    original_range = view.visible_depth_range
    original_layout = view.shared_vertical_ruler_layout

    snapshot = capture_tablet_print_snapshot(
        view,
        page_aspect_ratio=1.4,
        target_content_height=840,
        layout_content_height=840,
    )

    assert snapshot.vertical_ruler_layout is not None
    assert view.visible_depth_range == original_range
    assert view.shared_vertical_ruler_layout is not None
    assert view.shared_vertical_ruler_layout is not snapshot.vertical_ruler_layout
    assert view.shared_vertical_ruler_layout == original_layout
    view.close()
