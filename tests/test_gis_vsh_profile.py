"""Linear Vsh is a separately reviewed interpretation, not automatic IGR."""

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from geoworkbench.services import gis_vsh_profile as service
from geoworkbench.services.gis_reference_calibration import (
    GisProfileRowLimitExceeded, GisProfileRowStatus, evaluate_gis_reference_profile,
)
from geoworkbench.services.gis_vsh_profile import LINEAR_VSH_METHOD_ID, evaluate_gis_vsh_profile
from geoworkbench.services.petrophysical_reference_models import PetrophysicalQuality
from test_gis_reference_calibration import _calibration, _dataset


def _vsh(dataset, calibration, **changes):
    args = dict(
        method_id=LINEAR_VSH_METHOD_ID, reviewer="Vsh reviewer",
        applicability_reference="Synthetic linear-response evidence",
        md_top_m=100, md_base_m=102,
    )
    args.update(changes)
    return evaluate_gis_vsh_profile(dataset, calibration, **args)


@pytest.mark.parametrize("descending", (False, True))
def test_explicit_linear_vsh_preserves_source_rows_and_unclipped_qc(descending):
    dataset = _dataset()
    depths = dataset.active_index.values
    values = dataset.curves["selected"].values
    if descending:
        depths[:] = [102., 101., 100.]
    old_depths, old_values = depths.copy(), values.copy()
    calibration = _calibration(dataset)
    igr = evaluate_gis_reference_profile(dataset, calibration, md_top_m=100, md_base_m=102)
    result = _vsh(dataset, calibration)
    assert result.calibration is calibration
    assert result.method_id == "vsh-gr-linear-1" and result.md_bounds == (100., 102.)
    assert result.reviewer == "Vsh reviewer"
    assert result.applicability_reference == "Synthetic linear-response evidence"
    assert tuple(row.sample_index for row in result.rows) == (0, 1, 2)
    assert tuple(row.md_m for row in result.rows) == tuple(depths)
    first, missing, outlier = result.rows
    assert first.estimate is not None and first.estimate.value == pytest.approx(0.4)
    assert first.estimate.method_id == result.method_id
    assert first.estimate.usable_as_fraction
    assert dict(first.estimate.parameters)["igr"] == pytest.approx(0.4)
    assert dict(first.estimate.parameters)["clean_reference_api"] == 25.0
    assert missing == igr.rows[1] and missing.status is GisProfileRowStatus.MISSING_SOURCE
    assert missing.estimate is None
    assert outlier.estimate is not None and outlier.estimate.value == pytest.approx(1.2)
    assert outlier.estimate.quality is PetrophysicalQuality.OUTSIDE_REFERENCE_RANGE
    assert not outlier.estimate.usable_as_fraction
    assert igr.rows[0].estimate.method_id == "igr-linear-1"
    assert dataset.active_index.values is depths and dataset.curves["selected"].values is values
    np.testing.assert_array_equal(depths, old_depths)
    np.testing.assert_array_equal(values, old_values)
    with pytest.raises(FrozenInstanceError):
        result.method_id = "other"


@pytest.mark.parametrize("field,value", (
    ("method_id", "igr-linear-1"), ("method_id", None), ("reviewer", " "),
    ("reviewer", None), ("applicability_reference", ""), ("applicability_reference", 123),
))
def test_vsh_requires_explicit_method_and_separate_evidence(field, value):
    dataset = _dataset()
    with pytest.raises(ValueError):
        _vsh(dataset, _calibration(dataset), **{field: value})


def test_density_calibration_cannot_be_used_as_gr_vsh():
    dataset = _dataset(True)
    with pytest.raises(ValueError, match="IGR"):
        _vsh(dataset, _calibration(dataset, True))


def test_zero_missing_and_negative_are_distinct():
    dataset = _dataset()
    dataset.curves["selected"].values[:] = [25., np.nan, 5.]
    result = _vsh(dataset, _calibration(dataset))
    zero, missing, negative = result.rows
    assert zero.estimate is not None and zero.estimate.value == 0.
    assert zero.estimate.usable_as_fraction
    assert missing.estimate is None
    assert negative.estimate is not None and negative.estimate.value == pytest.approx(-0.2)
    assert not negative.estimate.usable_as_fraction


def test_empty_singleton_budget_and_calibration_scope():
    dataset = _dataset()
    calibration = _calibration(dataset)
    assert _vsh(dataset, calibration, md_top_m=100.1, md_base_m=100.9).rows == ()
    assert _vsh(dataset, calibration, md_top_m=101, md_base_m=101).rows[0].estimate is None
    with pytest.raises(GisProfileRowLimitExceeded):
        _vsh(dataset, calibration, max_rows=2)
    with pytest.raises(ValueError, match="scope"):
        _vsh(dataset, calibration, md_base_m=103)


def test_changed_source_even_outside_requested_interval_blocks_vsh():
    dataset = _dataset()
    calibration = _calibration(dataset)
    dataset.curves["selected"].values[2] += 1.
    with pytest.raises(ValueError):
        _vsh(dataset, calibration, md_top_m=100, md_base_m=100)


def test_source_rechecked_after_interpretation(monkeypatch):
    dataset = _dataset()
    calibration = _calibration(dataset)
    evaluate = service.evaluate_gis_reference_profile
    def changed(*args, **kwargs):
        profile = evaluate(*args, **kwargs)
        dataset.curves["selected"].values[2] += 1.
        return profile
    monkeypatch.setattr(service, "evaluate_gis_reference_profile", changed)
    with pytest.raises(ValueError):
        _vsh(dataset, calibration)
