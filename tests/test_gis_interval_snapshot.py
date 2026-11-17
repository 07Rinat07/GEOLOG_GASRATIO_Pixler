from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.services.gis_interval_sample_review import (
    GisIntervalReviewCancelled, review_gis_source_interval_batch,
)
from geoworkbench.services import gis_interval_snapshot as snapshot_module
from geoworkbench.services.gis_interval_snapshot import GisIntervalSnapshot
from test_gis_interval_compare import _two_curves


def test_snapshot_copies_selected_arrays_and_preserves_source_review():
    source = _two_curves()
    snapshot = GisIntervalSnapshot(source, ("RT",), lambda: False)
    assert snapshot.dataset is not source
    assert snapshot.dataset.active_index.values is not source.active_index.values
    assert snapshot.dataset.curves["RT"].values is not source.curves["RT"].values
    assert snapshot.dataset.curves["GR"].values.size == 0
    item, = review_gis_source_interval_batch(
        snapshot.dataset, curve_keys=("RT",), top_md_m=100, bottom_md_m=102,
    )
    assert item.review is not None and item.review.finite_value_bounds == (0.0, 20.0)
    assert snapshot.matches(lambda: False)
    np.testing.assert_equal(source.curves["RT"].values, [0.0, 20.0, np.nan])


@pytest.mark.parametrize("change", ["values", "axis_values", "unit", "version", "manifest", "replacement"])
def test_snapshot_rejects_source_edits_including_inplace_changes(change):
    source = _two_curves()
    snapshot = GisIntervalSnapshot(source, ("RT",), lambda: False)
    if change == "values":
        source.curves["RT"].values[0] = 9.0
    elif change == "axis_values":
        source.active_index.values[0] = 99.0
    elif change == "unit":
        source.curves["RT"].metadata = replace(source.curves["RT"].metadata, unit="changed")
    elif change == "version":
        source.curves["RT"].version += 1
    elif change == "manifest":
        source.parameters["changed"] = "yes"
    else:
        source.curves["RT"].values = source.curves["RT"].values.copy()
    assert not snapshot.matches(lambda: False)


def test_progress_and_cooperative_cancellation_do_not_return_partial_results():
    source = _two_curves()
    progress = []

    def on_progress(done, total):
        progress.append((done, total))

    with pytest.raises(GisIntervalReviewCancelled):
        review_gis_source_interval_batch(
            source, curve_keys=("GR", "RT"), top_md_m=100, bottom_md_m=102,
            progress=on_progress, cancelled=lambda: bool(progress),
        )
    assert progress == [(1, 2)]


def test_cancel_during_snapshot_is_explicit():
    with pytest.raises(GisIntervalReviewCancelled):
        GisIntervalSnapshot(_two_curves(), ("GR",), lambda: True)


def test_chunk_copy_preserves_dtype_shape_nan_and_c_order_of_strided_input():
    values = np.arange(300_000, dtype=float).reshape(2, 150_000)[:, ::-1]
    values[0, 1] = np.nan
    assert not values.flags.c_contiguous
    copied = snapshot_module._copy_array_bounded(values, lambda: False)
    assert copied.shape == values.shape and copied.dtype == values.dtype
    assert copied.flags.c_contiguous and not np.shares_memory(copied, values)
    np.testing.assert_array_equal(copied, values)
    copied[0, 0] = -99.0
    assert values[0, 0] != -99.0


def test_cancel_during_large_snapshot_axis_copy_leaves_original_arrays_untouched():
    source = _two_curves()
    count = 150_000
    axis = np.arange(count, dtype=float)
    values = np.linspace(0.0, 100.0, count)
    source.active_index.values = axis
    source.depth = axis
    source.curves["RT"].values = values
    calls = []

    def cancelled():
        calls.append(True)
        # Constructor entry, first 65,536 MD values, next MD chunk.
        return len(calls) >= 3

    with pytest.raises(GisIntervalReviewCancelled):
        GisIntervalSnapshot(source, ("RT",), cancelled)
    assert len(calls) == 3
    assert source.active_index.values is axis
    assert source.curves["RT"].values is values
    assert values[0] == 0.0 and values[-1] == 100.0


def test_cancel_during_selected_curve_copy_does_not_return_partial_snapshot(monkeypatch):
    source = _two_curves()
    count = 150_000
    axis = np.arange(count, dtype=float)
    values = np.ones(count, dtype=float)
    source.active_index.values = axis
    source.depth = axis
    source.curves["RT"].values = values
    original_copy = snapshot_module._copy_array_bounded
    copying_selected_curve = []
    polls = []

    def instrumented_copy(array, cancelled):
        if array is values:
            copying_selected_curve.append(True)
        return original_copy(array, cancelled)

    monkeypatch.setattr(snapshot_module, "_copy_array_bounded", instrumented_copy)

    def cancelled():
        if copying_selected_curve:
            polls.append(True)
            return len(polls) >= 2
        return False

    with pytest.raises(GisIntervalReviewCancelled):
        GisIntervalSnapshot(source, ("RT",), cancelled)
    assert copying_selected_curve and len(polls) == 2
    assert source.active_index.values is axis
    assert source.curves["RT"].values is values
    assert values[0] == values[-1] == 1.0



@pytest.mark.parametrize("change", ("signed_zero", "nan_payload", "axis_signed_zero"))
def test_snapshot_rejects_same_numeric_value_with_modified_source_bytes(change):
    """Source certification must not equate different IEEE-754 bit patterns."""
    source = _two_curves()
    if change == "axis_signed_zero":
        source.active_index.values[0] = 0.0
    snapshot = GisIntervalSnapshot(source, ("RT",), lambda: False)
    assert snapshot.matches(lambda: False)
    if change == "signed_zero":
        source.curves["RT"].values[0] = -0.0
        assert source.curves["RT"].values[0] == snapshot.dataset.curves["RT"].values[0]
    elif change == "nan_payload":
        # Both values are NaN, but the operator's source buffer was edited.
        array = source.curves["RT"].values
        before = array.view(np.uint64)[2]
        array.view(np.uint64)[2] = np.uint64(0x7ff8000000000051)
        assert before != array.view(np.uint64)[2]
        assert np.isnan(array[2]) and np.isnan(snapshot.dataset.curves["RT"].values[2])
    else:
        source.active_index.values[0] = -0.0
        assert source.active_index.values[0] == snapshot.dataset.active_index.values[0]
    assert snapshot.structure_matches()  # Same object, metadata, shape and dtype.
    assert not snapshot.matches(lambda: False)


def test_exact_byte_snapshot_accepts_unmodified_strided_source_with_nan_and_negative_zero():
    source = _two_curves()
    count = 135_001  # More than two bounded comparison chunks.
    axis = np.arange(count, dtype=float)[::-1]
    values = np.full(count, 2.0, dtype=float)[::-1]
    values[0] = -0.0
    values[65_536] = np.nan
    values[130_000] = np.inf
    assert not axis.flags.c_contiguous and not values.flags.c_contiguous
    source.active_index.values = axis
    source.depth = axis
    source.curves["RT"].values = values
    snapshot = GisIntervalSnapshot(source, ("RT",), lambda: False)
    assert snapshot.matches(lambda: False)
    assert snapshot.dataset.curves["RT"].values.flags.c_contiguous
    assert np.signbit(snapshot.dataset.curves["RT"].values[0])
    values[65_536] = -0.0
    assert not snapshot.matches(lambda: False)


def test_exact_byte_comparison_still_honors_cooperative_cancellation():
    source = _two_curves()
    count = 135_001
    source.active_index.values = np.arange(count, dtype=float)
    source.depth = source.active_index.values
    source.curves["RT"].values = np.zeros(count)
    snapshot = GisIntervalSnapshot(source, ("RT",), lambda: False)
    polls = []

    def cancelled():
        polls.append(True)
        return len(polls) >= 3

    with pytest.raises(GisIntervalReviewCancelled):
        snapshot_module._same_array(
            source.curves["RT"].values, snapshot.dataset.curves["RT"].values, cancelled,
        )
    assert len(polls) == 3
