from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.printing.tablet_print import capture_tablet_print_snapshot
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


def test_short_time_page_keeps_graph_body_below_tall_header(qapp) -> None:
    axis = np.linspace(0.0, 50.0, 101)
    dataset = Dataset(
        "short-time",
        "Short time",
        DatasetKind.GTI,
        DepthDomain.TIME,
        axis,
    )
    dataset.upsert_curve("ROP", np.linspace(1.0, 2.0, axis.size), unit="m/h")
    tracks = [
        TrackDefinition("time", "Время", TrackKind.DEPTH, width=124),
        TrackDefinition(
            "daily",
            "Суточные операции с очень длинным переносимым заголовком",
            TrackKind.GENERIC,
            ["ROP"],
            width=220,
        ),
    ]
    tablet = TabletView()
    tablet.resize(640, 420)
    tablet.set_layout_and_dataset(
        TabletLayout(tracks, visible_depth_top=0.0, visible_depth_bottom=50.0),
        dataset,
    )
    tablet.show()
    qapp.processEvents()

    snapshot = capture_tablet_print_snapshot(
        tablet,
        page_aspect_ratio=1.4,
        fit_columns=True,
        raster_scale=1.0,
        show_column_header=False,
        repeat_column_header_at_bottom=True,
        target_content_height=1,
        layout_content_height=420,
    )

    assert snapshot.content_height > snapshot.header_height
    assert snapshot.content_height - snapshot.header_height >= 1
