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
from geoworkbench.tablet.tablet_view import TabletView


def _view_with_sparse_gas() -> TabletView:
    depth = np.arange(1703.0, 1754.0, dtype=np.float64)
    values = np.full(depth.shape, np.nan)
    values[[0, 3, 6, 9, 12, 50]] = (10.0, 13.0, 16.0, 19.0, 22.0, 40.0)
    dataset = Dataset(
        "gas-mask-dataset",
        "Gas mask",
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
        values,
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
                ),
            ]
        )
    )
    view.resize(600, 800)
    view.set_dataset(dataset)
    view.set_visible_depth(1703.28, 1753.28)
    return view


def test_sparse_gas_plot_uses_explicit_segment_mask_without_symbols(qapp) -> None:
    view = _view_with_sparse_gas()
    qapp.processEvents()

    item = view._rendered["gas"].curve_items["C1"]
    x_values, y_values = item.getData()
    connect = item.curve.opts["connect"]

    assert x_values is not None and y_values is not None
    assert isinstance(connect, np.ndarray)
    assert connect.dtype == np.bool_
    assert connect.shape == y_values.shape
    assert np.count_nonzero(connect[:12]) >= 8
    assert not connect[-1]
    assert item.opts.get("symbol") is None
    view.close()


def test_viewport_inside_sparse_cadence_keeps_interpolated_line_context(qapp) -> None:
    view = _view_with_sparse_gas()
    view.set_visible_depth(1707.1, 1707.9)
    qapp.processEvents()

    item = view._rendered["gas"].curve_items["C1"]
    x_values, y_values = item.getData()
    connect = item.curve.opts["connect"]

    assert x_values is not None and y_values is not None
    assert len(y_values) >= 2
    assert np.count_nonzero(connect) >= 1
    assert np.all(np.isfinite(x_values[np.asarray(connect, dtype=bool)]))
    view.close()
