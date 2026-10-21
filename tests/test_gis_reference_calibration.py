from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CalculationState, CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain,
)
from geoworkbench.services.gis_reference_calibration import (
    create_gis_reference_calibration, evaluate_gis_reference_sample,
)
from geoworkbench.services.petrophysical_reference_models import PetrophysicalQuality
from geoworkbench.services.semantic_channels import SemanticChannelDictionary


def _dataset(density=False):
    name, unit = ("RHOB", "g/cm3") if density else ("GR", "API")
    binding = SemanticChannelDictionary().resolve(name, unit=unit)
    values = [2.42, np.nan, 2.9] if density else [65.0, np.nan, 145.0]
    curve = CurveData(CurveMetadata(
        "curve-1", name, binding.canonical_mnemonic, unit, "Source",
        "source-run", "source:las", binding,
    ), np.array(values))
    return Dataset("gis-1", "GIS", DatasetKind.GIS, DepthDomain.MD,
                   np.array([100.0, 101.0, 102.0]), curves={"selected": curve})


def _calibration(dataset, density=False, **changes):
    args = dict(
        method_id="density-porosity-1" if density else "igr-linear-1",
        curve_key="selected", calibration_id="calibration-1", tool_id="tool-1",
        reviewer="Reviewer", applicability_reference="Synthetic test evidence only",
        md_top_m=100.0, md_base_m=102.0,
        parameters=({"matrix_density_g_cm3": 2.71, "fluid_density_g_cm3": 1.0} if density
                    else {"clean_reference_api": 25.0, "shale_reference_api": 125.0}),
    )
    args.update(changes)
    return create_gis_reference_calibration(dataset, **args)


@pytest.mark.parametrize("density,expected", [(False, 0.4), (True, (2.71-2.42)/1.71)])
def test_actual_sample_carries_explicit_calibration_and_preserves_source(density, expected):
    dataset = _dataset(density)
    values, depths = dataset.curves["selected"].values, dataset.active_index.values
    before_values, before_depths = values.copy(), depths.copy()
    calibration = _calibration(dataset, density)
    result = evaluate_gis_reference_sample(dataset, calibration, sample_index=0)
    assert result.calibration is calibration
    assert result.md_m == 100.0 and result.source_value == values[0]
    assert result.estimate.value == pytest.approx(expected)
    assert calibration.source.curve.source_dataset_id == "source-run"
    assert calibration.source.curve.version == 1
    assert result.estimate.quality is PetrophysicalQuality.VALID
    np.testing.assert_array_equal(values, before_values)
    np.testing.assert_array_equal(depths, before_depths)
    assert dataset.curves["selected"].values is values
    with pytest.raises(FrozenInstanceError):
        calibration.calibration_id = "changed"


@pytest.mark.parametrize("density,quality", [
    (False, PetrophysicalQuality.OUTSIDE_REFERENCE_RANGE),
    (True, PetrophysicalQuality.OUTSIDE_PHYSICAL_RANGE),
])
def test_outside_range_is_retained_without_clipping(density, quality):
    dataset = _dataset(density)
    result = evaluate_gis_reference_sample(dataset, _calibration(dataset, density), sample_index=2)
    assert result.estimate.quality is quality
    assert not result.estimate.usable_as_fraction


@pytest.mark.parametrize("index", [-1, 3, 0.0, True, None])
def test_sample_selection_is_strict_and_bounded(index):
    dataset = _dataset()
    with pytest.raises(ValueError, match="integer"):
        evaluate_gis_reference_sample(dataset, _calibration(dataset), sample_index=index)


def test_nan_sample_is_not_interpolated_or_replaced():
    dataset = _dataset()
    with pytest.raises(ValueError, match="finite"):
        evaluate_gis_reference_sample(dataset, _calibration(dataset), sample_index=1)


@pytest.mark.parametrize("change", ["version", "state", "unit", "array", "axis", "axis_in_place"])
def test_changed_source_blocks_existing_calibration(change):
    dataset = _dataset()
    calibration = _calibration(dataset)
    curve = dataset.curves["selected"]
    if change == "version":
        curve.values[0] = 70.0
        curve.version += 1
    elif change == "state":
        curve.state = CalculationState.STALE
    elif change == "unit":
        curve.metadata = replace(curve.metadata, unit="uR/h")
    elif change == "array":
        curve.values = curve.values.copy()
    elif change == "axis":
        dataset.active_index.values = dataset.active_index.values.copy()
    else:
        dataset.active_index.values[1] = 101.5
    with pytest.raises(ValueError, match="stale|replaced|coordinates"):
        evaluate_gis_reference_sample(dataset, calibration, sample_index=0)


def test_another_dataset_with_copied_ids_requires_rebinding():
    dataset = _dataset()
    calibration = _calibration(dataset)
    other = _dataset()
    other.active_index.index_id = dataset.active_index.index_id
    with pytest.raises(ValueError, match="replaced"):
        evaluate_gis_reference_sample(other, calibration, sample_index=0)


@pytest.mark.parametrize("field", ["calibration_id", "tool_id", "reviewer", "applicability_reference"])
@pytest.mark.parametrize("value", ["  ", None])
def test_identity_and_expert_evidence_are_mandatory(field, value):
    with pytest.raises(ValueError, match="evidence"):
        _calibration(_dataset(), **{field: value})


@pytest.mark.parametrize("top,base", [(102, 100), (99, 102), (100, 103), (np.nan, 102), (True, 102)])
def test_scope_is_explicit_finite_ordered_and_inside_observed_bounds(top, base):
    with pytest.raises(ValueError):
        _calibration(_dataset(), md_top_m=top, md_base_m=base)


def test_sample_outside_narrow_scope_is_rejected():
    dataset = _dataset()
    calibration = _calibration(dataset, md_top_m=100, md_base_m=100)
    with pytest.raises(ValueError, match="scope"):
        evaluate_gis_reference_sample(dataset, calibration, sample_index=2)


@pytest.mark.parametrize("parameters", [
    {}, {"clean_reference_api": 25.0},
    {"clean_reference_api": 25.0, "shale_reference_api": 125.0, "extra": 1.0},
    {"clean_reference_api": 125.0, "shale_reference_api": 25.0},
    {"clean_reference_api": 25.0, "shale_reference_api": np.inf},
    {"clean_reference_api": False, "shale_reference_api": 125.0}, None,
])
def test_no_default_or_invalid_calibration_parameters(parameters):
    with pytest.raises(ValueError):
        _calibration(_dataset(), parameters=parameters)


def test_density_constraints_and_ineligible_source_are_not_bypassed():
    with pytest.raises(ValueError):
        _calibration(_dataset(True), True,
                     parameters={"matrix_density_g_cm3": 1.0, "fluid_density_g_cm3": 1.0})
    dataset = _dataset()
    dataset.curves["selected"].state = CalculationState.STALE
    with pytest.raises(ValueError, match="source review"):
        _calibration(dataset)


def test_parameters_are_copied_and_descending_md_uses_exact_source_row():
    dataset = _dataset()
    dataset.active_index.values[:] = [102.0, 101.0, 100.0]
    parameters = {"clean_reference_api": 25.0, "shale_reference_api": 125.0}
    calibration = _calibration(dataset, parameters=parameters)
    parameters["clean_reference_api"] = 50.0
    result = evaluate_gis_reference_sample(dataset, calibration, sample_index=0)
    assert result.md_m == 102.0 and result.estimate.value == pytest.approx(0.4)
