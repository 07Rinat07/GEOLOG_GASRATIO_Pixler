from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from geoworkbench.domain.models import CuttingsComponent, CuttingsSample, LithologyInterval
from geoworkbench.services import interpretation_gis_interval_evidence as service
from geoworkbench.services.gis_interval_snapshot import GisIntervalSourceChanged
from test_gis_external_exact_review import _copy
from test_report_geology_snapshot import _session


def _combined(monkeypatch, tmp_path, **kwargs):
    session, receiver, original, dataset = _copy(monkeypatch, tmp_path, **kwargs)
    session.current_dataset_id = dataset.dataset_id
    key = next(iter(dataset.curves))
    well = session.current_well
    well.lithology = [LithologyInterval("lith-1", 100.0, 102.0, "limestone")]
    well.cuttings = [
        CuttingsSample(
            "sample-1", 100.0, 101.0,
            [CuttingsComponent("limestone", 100.0)],
            calcite_percent=0.0,
        ),
    ]
    return session, receiver, original, dataset, key


def test_combined_evidence_retains_md_source_and_separate_geology_coverage(monkeypatch, tmp_path):
    session, receiver, original, dataset, key = _combined(monkeypatch, tmp_path)
    dataset.curves[key].values[1] = np.nan
    before = dataset.curves[key].values.copy()
    original_before = original.curves["gr"].values.copy()
    axis_before = dataset.active_index.values.copy()
    dirty_before = session.dirty
    result = service.review_gas_geology_gis_interval(
        session, top_depth=100.0, bottom_depth=102.0, curve_keys=(key,),
    )

    assert result.geology.well_id == session.current_well.well_id
    assert result.geology.dataset_id == dataset.dataset_id
    assert result.geology.depth_axis_id == dataset.active_index.index_id
    assert result.geology.depth_unit == "m"
    assert result.geology.coverage("lithology") == 1.0
    assert result.geology.coverage("calcimetry") == 0.5
    calcimetry, = (item for item in result.geology.intersections if item.kind == "calcimetry")
    assert calcimetry.source_id == "sample-1"
    assert dict(calcimetry.attributes)["calcite_percent"] == 0.0

    item, = result.gis
    assert item.curve_key == key and item.issues == ()
    assert item.source is not None and item.review is not None
    assert item.source.curve_id == dataset.curves[key].metadata.curve_id
    assert item.source.provenance == dataset.curves[key].metadata.provenance
    assert item.source.unit == "API"
    assert item.review.top_md_m == 100.0 and item.review.bottom_md_m == 102.0
    assert item.review.sample_count == 3 and item.review.finite_count == 2
    assert item.review.missing_count == 1 and item.review.missing_md_preview == (101.0,)
    assert item.review.finite_md_bounds == (100.0, 102.0)
    assert item.review.finite_value_bounds == (0.0, 2.0)

    assert receiver.curves == {} and session.dirty == dirty_before
    np.testing.assert_array_equal(dataset.curves[key].values, before)
    np.testing.assert_array_equal(original.curves["gr"].values, original_before)
    np.testing.assert_array_equal(dataset.active_index.values, axis_before)
    with pytest.raises(FrozenInstanceError):
        result.gis = ()


def test_no_selected_gis_preserves_geology_without_gis_snapshot(monkeypatch):
    session = _session()

    def unexpected(*args, **kwargs):
        pytest.fail("No GIS should be generated or copied without explicit selection")

    monkeypatch.setattr(service, "GisIntervalSnapshot", unexpected)
    result = service.review_gas_geology_gis_interval(
        session, top_depth=1004.0, bottom_depth=1012.0,
    )
    assert result.gis == ()
    assert result.geology.intersections
    assert result.geology.dataset_id == session.current_dataset.dataset_id


def test_unverified_interpolated_gis_is_blocked_not_represented_as_measured(monkeypatch, tmp_path):
    session, _, _, _, key = _combined(
        monkeypatch, tmp_path, source_depth=(100.0, 102.0),
    )
    result = service.review_gas_geology_gis_interval(
        session, top_depth=100.0, bottom_depth=102.0, curve_keys=(key,),
    )
    item, = result.gis
    assert item.curve_key == key and item.review is None
    assert "axis:dataset_not_gis" in item.issues
    assert "curve:external_source_unverified" in item.issues
    assert result.geology.coverage("lithology") == 1.0


def test_selected_order_and_missing_curve_are_explicit(monkeypatch, tmp_path):
    session, _, _, _, key = _combined(monkeypatch, tmp_path)
    result = service.review_gas_geology_gis_interval(
        session, top_depth=100.0, bottom_depth=102.0, curve_keys=("not-loaded", key),
    )
    missing, measured = result.gis
    assert missing.curve_key == "not-loaded" and missing.review is None
    assert "curve_not_found" in missing.issues
    assert measured.curve_key == key and measured.review is not None


@pytest.mark.parametrize("curve_keys", [("GR", "GR"), ("",), (1,), ["GR"], tuple(str(i) for i in range(9))])
def test_invalid_gis_selection_is_rejected(curve_keys):
    with pytest.raises(ValueError, match="unique GIS curve keys"):
        service.review_gas_geology_gis_interval(
            _session(), top_depth=1004.0, bottom_depth=1012.0, curve_keys=curve_keys,
        )


def test_changed_live_gis_during_combined_review_never_returns_stale_evidence(monkeypatch, tmp_path):
    session, _, _, dataset, key = _combined(monkeypatch, tmp_path)
    original_review = service.review_gis_source_interval_batch

    def change_source(*args, **kwargs):
        result = original_review(*args, **kwargs)
        dataset.curves[key].values[0] = 99.0
        return result

    monkeypatch.setattr(service, "review_gis_source_interval_batch", change_source)
    with pytest.raises(GisIntervalSourceChanged, match="GIS source changed"):
        service.review_gas_geology_gis_interval(
            session, top_depth=100.0, bottom_depth=102.0, curve_keys=(key,),
        )
