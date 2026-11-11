"""Multi-curve review remains source-bound and never fills missing values."""

from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.domain.models import IndexType
from geoworkbench.services import gis_interval_sample_review as service
from test_gis_external_exact_review import _copy
from test_gis_input_inventory import _dataset


def _two_curves():
    dataset = _dataset("GR", "API")
    rt = _dataset("RT", "ohm.m").curves["RT"]
    rt.metadata = replace(rt.metadata, curve_id="resistivity")
    rt.values = np.array([0.0, 20.0, np.nan])
    dataset.curves["RT"] = rt
    return dataset


def test_batch_uses_one_inventory_and_keeps_per_curve_units_and_gaps(monkeypatch):
    dataset = _two_curves()
    before = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    original = service.inventory_gis_inputs
    calls = []

    def inventory(data):
        calls.append(data)
        return original(data)

    monkeypatch.setattr(service, "inventory_gis_inputs", inventory)
    gr, rt = service.review_gis_source_interval_batch(
        dataset, curve_keys=("GR", "RT"), top_md_m=100, bottom_md_m=102,
    )
    assert calls == [dataset]
    assert gr.review is not None and rt.review is not None
    assert (gr.source.unit, gr.review.finite_value_bounds, gr.review.missing_md_preview) == (
        "API", (10.0, 30.0), (101.0,),
    )
    assert (rt.source.unit, rt.review.finite_value_bounds, rt.review.missing_md_preview) == (
        "ohm.m", (0.0, 20.0), (102.0,),
    )
    for key, values in before.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)


def test_invalid_or_removed_curve_stays_blocked_while_other_source_is_reviewed():
    dataset = _two_curves()
    dataset.curves["RT"].metadata = replace(dataset.curves["RT"].metadata, unit="invalid")
    gr, rt, removed = service.review_gis_source_interval_batch(
        dataset, curve_keys=("GR", "RT", "removed"), top_md_m=100, bottom_md_m=102,
    )
    assert gr.review is not None and gr.issues == ()
    assert rt.review is None and "curve:unknown_unit" in rt.issues
    assert removed.review is None and removed.issues == ("curve_not_found",)


def test_invalid_axis_blocks_every_selected_curve_and_no_values_is_not_negative():
    dataset = _two_curves()
    dataset.active_index.index_type = IndexType.TVD
    blocked = service.review_gis_source_interval_batch(
        dataset, curve_keys=("GR", "RT"), top_md_m=100, bottom_md_m=102,
    )
    assert all(item.review is None and "axis:unverified_metre_md_alignment" in item.issues for item in blocked)
    dataset.active_index.index_type = IndexType.MD
    dataset.curves["RT"].values[:] = np.nan
    item, = service.review_gis_source_interval_batch(
        dataset, curve_keys=("RT",), top_md_m=100, bottom_md_m=102,
    )
    assert item.review is not None
    assert (item.review.finite_count, item.review.missing_count, item.review.finite_value_bounds) == (0, 3, None)


@pytest.mark.parametrize("keys", [(), ("GR", "GR"), ("",), tuple(str(i) for i in range(9)), ["GR"]])
def test_invalid_selection_is_rejected(keys):
    with pytest.raises(ValueError):
        service.review_gis_source_interval_batch(_two_curves(), curve_keys=keys, top_md_m=100, bottom_md_m=102)


def test_batch_rechecks_live_source_on_each_run():
    dataset = _two_curves()
    kwargs = dict(curve_keys=("RT",), top_md_m=100, bottom_md_m=102)
    first, = service.review_gis_source_interval_batch(dataset, **kwargs)
    dataset.curves["RT"].metadata = replace(dataset.curves["RT"].metadata, unit="invalid")
    second, = service.review_gis_source_interval_batch(dataset, **kwargs)
    assert first.review is not None and second.review is None


def test_batch_does_not_present_interpolated_external_data_as_source(monkeypatch, tmp_path):
    _, _, _, combined = _copy(monkeypatch, tmp_path, source_depth=(100.0, 102.0))
    key = next(iter(combined.curves))
    item, = service.review_gis_source_interval_batch(
        combined, curve_keys=(key,), top_md_m=100, bottom_md_m=102,
    )
    assert item.review is None
    assert "curve:external_source_unverified" in item.issues


def test_batch_chunked_summary_preserves_order_bounds_and_missing_values():
    dataset = _two_curves()
    count = 150_001
    dataset.active_index.values = np.arange(count - 1, -1, -1, dtype=float)
    dataset.depth = dataset.active_index.values
    dataset.curves["GR"].values = np.ones(count)
    values = np.ones(count)
    values[0] = 0.0
    values[[1, 65_536, 150_000]] = np.nan
    values[80_000] = np.inf
    values[90_000] = -5.0
    values[100_000] = 30.0
    dataset.curves["RT"].values = values
    before = values.copy()

    item, = service.review_gis_source_interval_batch(
        dataset, curve_keys=("RT",), top_md_m=0, bottom_md_m=count - 1,
    )
    assert item.review is not None
    assert (item.review.sample_count, item.review.finite_count, item.review.missing_count) == (
        count, count - 4, 4,
    )
    assert item.review.missing_md_preview == (149_999.0, 84_464.0, 70_000.0, 0.0)
    assert item.review.finite_md_bounds == (2.0, 150_000.0)
    assert item.review.finite_value_bounds == (-5.0, 30.0)
    np.testing.assert_array_equal(values, before)


def test_batch_cancellation_interrupts_one_large_curve_without_partial_progress():
    dataset = _two_curves()
    count = 150_000
    dataset.active_index.values = np.arange(count, dtype=float)
    dataset.depth = dataset.active_index.values
    dataset.curves["GR"].values = np.ones(count)
    dataset.curves["RT"].values = np.ones(count)
    polls = []
    progress = []

    def cancelled():
        polls.append(True)
        # 1: before inventory, 2: before the curve, 3: first 65,536 rows,
        # 4: the next chunk. No curve-level result may have been emitted.
        return len(polls) >= 4

    with pytest.raises(service.GisIntervalReviewCancelled):
        service.review_gis_source_interval_batch(
            dataset, curve_keys=("RT",), top_md_m=0, bottom_md_m=count - 1,
            progress=lambda done, total: progress.append((done, total)),
            cancelled=cancelled,
        )
    assert len(polls) == 4
    assert progress == []
