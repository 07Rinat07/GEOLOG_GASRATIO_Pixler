from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CalculationState, CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain,
    IndexType,
)
from geoworkbench.services.gis_input_inventory import inventory_gis_inputs
from geoworkbench.services.semantic_channels import SemanticChannelDictionary
from geoworkbench.services.uom_dictionary import QuantityClass


def _dataset(mnemonic="GR", unit="API"):
    binding = SemanticChannelDictionary().resolve(mnemonic, unit=unit)
    curve = CurveData(CurveMetadata(
        "curve-1", mnemonic, binding.canonical_mnemonic, unit, "Source curve",
        "original-run-1", "source:las", binding,
    ), np.array([10.0, np.nan, 30.0]))
    return Dataset(
        "gis-1", "GIS", DatasetKind.GIS, DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]), curves={mnemonic: curve},
    )


@pytest.mark.parametrize("mnemonic,unit", [
    ("GR", "API"), ("RHOB", "g/cm3"), ("NPHI", "%"),
    ("DT", "us/ft"), ("RT", "ohm.m"),
])
def test_inventory_preserves_source_and_counts_actual_samples(mnemonic, unit):
    dataset = _dataset(mnemonic, unit)
    curve = dataset.curves[mnemonic]
    depths = dataset.active_index.values
    values = curve.values
    before = values.copy()
    snapshot = inventory_gis_inputs(dataset)
    row = snapshot.curves[0]
    assert snapshot.axis_issues == row.issues == ()
    assert row.source_dataset_id == "original-run-1"
    assert row.unit == unit
    assert row.finite_sample_count == 2
    assert row.sample_md_bounds == (100.0, 102.0)
    assert dataset.active_index.values is depths and curve.values is values
    np.testing.assert_array_equal(values, before)
    assert row.version == curve.version
    assert row.semantic_confidence == curve.metadata.semantic.confidence
    assert row.semantic_evidence == curve.metadata.semantic.evidence
    assert snapshot.axis_confidence == dataset.active_index.confidence
    assert snapshot.axis_evidence == dataset.active_index.evidence
    with pytest.raises(FrozenInstanceError):
        row.unit = "changed"


@pytest.mark.parametrize("change,issue", [
    ({"unit": "psi"}, "unit_quantity_conflict"),
    ({"unit": "vendor-ticks"}, "unknown_unit"),
    ({"semantic": None}, "unverified_semantics"),
    ({"provenance": ""}, "missing_source_provenance"),
    ({"original_mnemonic": "RT"}, "semantic_mnemonic_changed"),
    ({"canonical_mnemonic": "RT"}, "semantic_mnemonic_changed"),
])
def test_changed_metadata_does_not_silently_revalidate_saved_binding(change, issue):
    dataset = _dataset()
    curve = dataset.curves["GR"]
    curve.metadata = replace(curve.metadata, **change)
    assert issue in inventory_gis_inputs(dataset).curves[0].issues


def test_semantic_quantity_and_current_state_are_checked_independently():
    dataset = _dataset()
    curve = dataset.curves["GR"]
    curve.metadata = replace(curve.metadata, semantic=replace(
        curve.metadata.semantic, quantity_class=QuantityClass.PRESSURE,
    ))
    curve.state = CalculationState.STALE
    assert {"semantic_quantity_conflict", "curve_not_current"}.issubset(
        inventory_gis_inputs(dataset).curves[0].issues
    )


@pytest.mark.parametrize("depths,issue", [
    ([100.0, 100.0, 102.0], "ambiguous_depth_order"),
    ([100.0, 102.0, 101.0], "ambiguous_depth_order"),
    ([100.0, np.nan, 102.0], "invalid_depth_samples"),
])
def test_unverified_depth_samples_never_produce_md_bounds(depths, issue):
    dataset = _dataset()
    dataset.active_index.values = np.array(depths)
    snapshot = inventory_gis_inputs(dataset)
    assert issue in snapshot.axis_issues
    assert snapshot.curves[0].sample_md_bounds is None


@pytest.mark.parametrize("kind,unit", [(IndexType.TVD, "m"), (IndexType.MD, "ft")])
def test_non_metre_md_axis_is_not_implicitly_correlated(kind, unit):
    dataset = _dataset()
    dataset.active_index.index_type = kind
    dataset.active_index.unit = unit
    snapshot = inventory_gis_inputs(dataset)
    assert "unverified_metre_md_alignment" in snapshot.axis_issues
    assert snapshot.curves[0].sample_md_bounds is None


def test_lag_axis_and_non_gis_dataset_are_explicitly_unverified():
    dataset = _dataset()
    dataset.headers["LAG_PROFILE_ID"] = "lag-1"
    dataset.kind = DatasetKind.GTI
    snapshot = inventory_gis_inputs(dataset)
    assert set(snapshot.axis_issues) == {"dataset_not_gis", "unverified_metre_md_alignment"}


def test_descending_axis_and_empty_dataset_keep_source_order():
    dataset = _dataset()
    dataset.active_index.values = np.array([102.0, 101.0, 100.0])
    assert inventory_gis_inputs(dataset).axis_issues == ()
    assert inventory_gis_inputs(dataset).curves[0].sample_md_bounds == (100.0, 102.0)
    np.testing.assert_array_equal(dataset.active_index.values, [102, 101, 100])
    dataset.curves.clear()
    assert inventory_gis_inputs(dataset).curves == ()


@pytest.mark.parametrize("values,issue", [
    (np.array([1.0]), "invalid_curve_samples"),
    (np.zeros((3, 1)), "invalid_curve_samples"),
    (np.array(["1", "2", "3"]), "invalid_curve_samples"),
    (np.array([np.nan, np.inf, -np.inf]), "no_finite_paired_samples"),
])
def test_unusable_curve_arrays_are_reported_without_coercion(values, issue):
    dataset = _dataset()
    dataset.curves["GR"].values = values
    row = inventory_gis_inputs(dataset).curves[0]
    assert issue in row.issues
    assert row.sample_md_bounds is None
    assert row.finite_sample_count == 0


def test_gas_curve_is_not_a_gis_input_merely_because_it_has_a_binding():
    row = inventory_gis_inputs(_dataset("C1", "%")).curves[0]
    assert "unsupported_gis_family" in row.issues


@pytest.mark.parametrize("relative_path,count,bounds", [
    ("las/1.2/sample.las", 3, (1669.75, 1670.0)),
    ("las/2.0/sample_2.0.las", 3, (1669.75, 1670.0)),
    ("las/2.0/sample_2.0_wrapped.las", 2, (909.875, 910.0)),
])
def test_real_las_inventory_keeps_source_bytes_values_and_unrecognized_units(
    relative_path, count, bounds,
):
    from geoworkbench.data.las_adapter import import_las_with_report
    from tools.fetch_external_format_fixtures import CORPUS

    source = CORPUS / relative_path
    original = source.read_bytes()
    imported = import_las_with_report(source, DatasetKind.GIS)
    dataset = imported.dataset
    before = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    inventory = inventory_gis_inputs(dataset)
    rows = {row.original_mnemonic: row for row in inventory.curves}
    assert inventory.axis_issues == ()
    assert rows["NPHI"].issues == ()
    assert rows["NPHI"].finite_sample_count == count
    assert rows["NPHI"].sample_md_bounds == bounds
    assert rows["DT"].unit == "US/M"
    assert "unknown_unit" in rows["DT"].issues
    assert imported.source_document.to_bytes() == source.read_bytes() == original
    for key, values in before.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)
