from __future__ import annotations

from typing import NoReturn

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


def test_gas_scroll_and_zoom_do_not_recompute_conditioned_ratios(qapp, monkeypatch) -> None:
    depth = np.linspace(1000.0, 1100.0, 101)
    dataset = Dataset(
        "dataset-gas-hotpath",
        "Gas hot-path",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    c1 = CurveData(
        CurveMetadata(
            "curve-c1-hotpath",
            "C1",
            "C1",
            "%",
            "Methane",
            dataset.dataset_id,
        ),
        np.linspace(1.0, 3.0, depth.size),
    )
    dataset.curves[c1.metadata.curve_id] = c1

    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "gas",
                    "Gas",
                    TrackKind.GAS,
                    curve_mnemonics=["C1"],
                )
            ]
        )
    )
    view.set_dataset(dataset)
    qapp.processEvents()
    initial_range = view.visible_depth_range
    assert initial_range is not None

    def fail_conditioning(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError(
            "scroll/zoom must reuse precomputed gas curves instead of rerunning conditioning"
        )

    monkeypatch.setattr(
        "geoworkbench.calculations.gas_ratio.calculate_conditioned_ratios",
        fail_conditioning,
    )

    assert view.zoom_depth(0.5)
    assert view.scroll_depth(10.0)
    qapp.processEvents()
    assert view.visible_depth_range != initial_range
    view.close()
