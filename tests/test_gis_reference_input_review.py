from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CalculationState, CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain, IndexType,
)
from geoworkbench.services.gis_reference_input_review import review_gis_reference_input
from geoworkbench.services.semantic_channels import SemanticChannelDictionary


def _dataset(mnemonic="GR", unit="API"):
    binding = SemanticChannelDictionary().resolve(mnemonic, unit=unit)
    curve = CurveData(CurveMetadata(
        "curve-1", mnemonic, binding.canonical_mnemonic, unit, "Source",
        "original-run", "source:las", binding,
    ), np.array([10.0, np.nan, 30.0]))
    return Dataset(
        "gis-1", "GIS", DatasetKind.GIS, DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]), curves={"selected": curve},
    )


def _review(dataset, method_id="igr-linear-1", curve_key="selected"):
    return review_gis_reference_input(dataset, method_id=method_id, curve_key=curve_key)


@pytest.mark.parametrize("mnemonic,unit,method", [
    ("GR", "API", "igr-linear-1"),
    ("GR", "gapi", "igr-linear-1"),
    ("RHOB", "g/cm3", "density-porosity-1"),
    ("RHOB", "g/cm^3", "density-porosity-1"),
])
def test_explicit_source_review_preserves_arrays_and_provenance(mnemonic, unit, method):
    dataset = _dataset(mnemonic, unit)
    source = dataset.curves["selected"]
    axis = dataset.active_index.values
    values = source.values
    before = values.copy()
    result = _review(dataset, method)
    assert result.ready_for_calibration and result.issues == ()
    assert result.dataset_id == dataset.dataset_id
    assert result.axis_id == dataset.active_index.index_id
    assert result.curve.source_dataset_id == "original-run"
    assert result.curve.finite_sample_count == 2
    assert result.curve.sample_md_bounds == (100.0, 102.0)
    assert result.curve.unit == unit
    assert dataset.active_index.values is axis and source.values is values
    np.testing.assert_array_equal(values, before)
    with pytest.raises(FrozenInstanceError):
        result.curve_key = "other"


@pytest.mark.parametrize("mnemonic,unit,method", [
    ("GR", "uR/h", "igr-linear-1"),
    ("RHOB", "kg/m3", "density-porosity-1"),
])
def test_same_quantity_different_unit_scale_requires_explicit_preparation(mnemonic, unit, method):
    result = _review(_dataset(mnemonic, unit), method)
    assert result.curve.issues == ()
    assert result.issues == ("method_unit_mismatch",)
    assert not result.ready_for_calibration


def test_wrong_family_is_rejected_even_when_good_alternative_exists():
    dataset = _dataset()
    dataset.curves["alternative"] = dataset.curves["selected"]
    dataset.curves["selected"] = _dataset("NPHI", "%").curves["selected"]
    result = _review(dataset)
    assert "method_family_mismatch" in result.issues
    assert result.curve.original_mnemonic == "NPHI"
    missing = _review(dataset, curve_key="GR")
    assert missing.curve is None and missing.issues == ("curve_not_found",)


@pytest.mark.parametrize("axis_type,unit", [(IndexType.TVD, "m"), (IndexType.MD, "ft")])
def test_axis_blockers_survive_source_review(axis_type, unit):
    dataset = _dataset()
    dataset.active_index.index_type = axis_type
    dataset.active_index.unit = unit
    result = _review(dataset)
    assert "axis:unverified_metre_md_alignment" in result.issues
    assert not result.ready_for_calibration


def test_review_rebuilds_inventory_and_does_not_promote_old_snapshot():
    dataset = _dataset()
    first = _review(dataset)
    curve = dataset.curves["selected"]
    curve.version += 1
    curve.state = CalculationState.STALE
    curve.metadata = replace(curve.metadata, unit="vendor-unit")
    second = _review(dataset)
    assert first.ready_for_calibration
    assert first.curve.version == 1
    assert second.curve.version == 2
    assert {"curve:curve_not_current", "curve:semantic_unit_changed",
            "curve:unknown_unit", "method_unit_mismatch"}.issubset(second.issues)
    assert not second.ready_for_calibration


@pytest.mark.parametrize("values", [np.array([np.nan] * 3), np.zeros((3, 1))])
def test_unusable_samples_do_not_become_calibration_inputs(values):
    dataset = _dataset()
    dataset.curves["selected"].values = values
    assert not _review(dataset).ready_for_calibration


def test_missing_curve_identity_and_provenance_are_explicit():
    dataset = _dataset()
    curve = dataset.curves["selected"]
    curve.metadata = replace(curve.metadata, curve_id="", provenance="")
    assert {"missing_curve_id", "curve:missing_source_provenance"}.issubset(
        _review(dataset).issues,
    )


@pytest.mark.parametrize("method", ["archie-water-saturation-1", "unknown", "", None, []])
def test_unsupported_methods_are_not_guessed(method):
    with pytest.raises(ValueError, match="Unsupported"):
        _review(_dataset(), method)


@pytest.mark.parametrize("key", ["", "  ", None, []])
def test_channel_selection_is_mandatory(key):
    with pytest.raises(ValueError, match="explicit curve key"):
        _review(_dataset(), curve_key=key)


@pytest.mark.parametrize("path", ["las/1.2/sample.las", "las/2.0/sample_2.0.las"])
def test_real_las_density_unit_is_rejected_without_guessing_or_source_changes(path):
    from geoworkbench.data.las_adapter import import_las_with_report
    from tools.fetch_external_format_fixtures import CORPUS

    source = CORPUS / path
    original = source.read_bytes()
    imported = import_las_with_report(source, DatasetKind.GIS)
    dataset = imported.dataset
    key = next(key for key, curve in dataset.curves.items()
               if curve.metadata.original_mnemonic == "RHOB")
    before = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    result = _review(dataset, "density-porosity-1", key)
    assert not result.ready_for_calibration
    assert result.curve.unit == "K/M3"
    assert "curve:unknown_unit" in result.issues
    assert "method_unit_mismatch" in result.issues
    assert source.read_bytes() == imported.source_document.to_bytes() == original
    for key, values in before.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)
