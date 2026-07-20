from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    Dataset,
    DatasetKind,
    DepthDomain,
    InterpretationInterval,
    WellInterpretation,
)
from geoworkbench.tablet.interval_interaction import (
    IntervalEditMode,
    choose_resize_edge,
    normalize_drag_range,
    resize_interval_range,
    snap_depth_to_samples,
)
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


def make_view(qapp) -> TabletView:
    dataset = Dataset(
        "dataset",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0, 180.0]),
    )
    interpretation = WellInterpretation(
        "primary",
        "Primary",
        intervals=[
            InterpretationInterval(
                "reservoir",
                120.0,
                150.0,
                "Reservoir",
                "Sand A",
                "#fde68a",
            )
        ],
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [TrackDefinition("interpretation", "Interpretation", TrackKind.INTERPRETATION)]
        )
    )
    view.set_interpretations([interpretation], interpretation.interpretation_id)
    view.set_dataset(dataset)
    qapp.processEvents()
    return view


def test_interval_interaction_helpers_snap_normalize_and_choose_edge() -> None:
    interval = InterpretationInterval("interval", 100.0, 140.0, "Reservoir", "A", "#fde68a")

    assert snap_depth_to_samples(107.0, [100.0, 110.0, 120.0]) == 110.0
    assert normalize_drag_range(140.0, 100.0).top_depth == 100.0
    assert normalize_drag_range(100.0, 100.0) is None
    assert choose_resize_edge(interval, 102.0, tolerance=3.0) == "top"
    assert choose_resize_edge(interval, 138.0, tolerance=3.0) == "bottom"
    assert choose_resize_edge(interval, 120.0, tolerance=3.0) is None
    assert resize_interval_range(interval, "top", 110.0, minimum_span=1.0).top_depth == 110.0
    assert resize_interval_range(interval, "bottom", 90.0, minimum_span=1.0) is None


def test_tablet_create_mode_emits_snapped_interval_request(qapp) -> None:
    view = make_view(qapp)
    requests: list[tuple[str, float, float, str]] = []
    view.interval_create_requested.connect(
        lambda interpretation_id, top, bottom, interval_type: requests.append(
            (interpretation_id, top, bottom, interval_type)
        )
    )

    view.set_interval_edit_mode(IntervalEditMode.CREATE)
    assert view.begin_interval_drag("interpretation", 0.5, 108.0)
    assert view.update_interval_drag(172.0)
    assert view.interval_preview_range == (110.0, 170.0)
    assert view.finish_interval_drag(172.0)

    assert requests == [("primary", 110.0, 170.0, "Reservoir")]
    assert view.interval_preview_range is None
    view.close()


def test_tablet_resize_mode_emits_boundary_update(qapp) -> None:
    view = make_view(qapp)
    requests: list[tuple[str, str, float, float]] = []
    view.interval_resize_requested.connect(
        lambda interpretation_id, interval_id, top, bottom: requests.append(
            (interpretation_id, interval_id, top, bottom)
        )
    )

    view.set_interval_edit_mode(IntervalEditMode.RESIZE)
    assert view.begin_interval_drag("interpretation", 0.5, 149.0)
    assert view.update_interval_drag(169.0)
    assert view.interval_preview_range == (120.0, 170.0)
    assert view.finish_interval_drag(169.0)

    assert requests == [("primary", "reservoir", 120.0, 170.0)]
    view.close()


def test_tablet_escape_style_cancel_removes_preview(qapp) -> None:
    view = make_view(qapp)
    view.set_interval_edit_mode(IntervalEditMode.CREATE)
    assert view.begin_interval_drag("interpretation", 0.5, 100.0)
    assert view.update_interval_drag(140.0)

    view.cancel_interval_interaction()

    assert view.interval_preview_range is None
    assert view._rendered["interpretation"].interpretation_preview is None
    view.close()
