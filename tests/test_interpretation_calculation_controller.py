from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.project.session import ProjectSession


def _add_curve(
    dataset: Dataset,
    mnemonic: str,
    values: np.ndarray,
    unit: str,
    *,
    provenance: str = "source",
) -> None:
    dataset.curves[mnemonic] = CurveData(
        CurveMetadata(
            mnemonic,
            mnemonic,
            mnemonic,
            unit,
            mnemonic,
            dataset.dataset_id,
            provenance,
        ),
        np.asarray(values, dtype=np.float64),
    )


def _session() -> ProjectSession:
    row_count = 40
    dataset = Dataset(
        "mud-log",
        "Mud log",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.arange(2_000.0, 2_000.0 + row_count),
    )
    values = {
        "C1": (80.0, "%"),
        "C2": (10.0, "%"),
        "C3": (5.0, "%"),
        "IC4": (1.0, "%"),
        "NC4": (2.0, "%"),
        "IC5": (1.0, "%"),
        "NC5": (1.0, "%"),
        "ROP": (18.288, "m/h"),
        "RPM": (100.0, "rpm"),
        "WOB": (22.6796185, "t"),
        "BIT": (254.0, "mm"),
        "FLOW": (1_892.705892, "L/min"),
        "MW": (1.437917128, "g/cm3"),
    }
    for mnemonic, (value, unit) in values.items():
        _add_curve(dataset, mnemonic, np.full(row_count, value), unit)
    session = ProjectSession()
    session.add_dataset(dataset, "Well A")
    session.dirty = False
    return session


def test_standard_interpretation_suite_converts_field_units_and_creates_curves() -> None:
    session = _session()
    result = InterpretationCalculationController(session).calculate_standard_curves(
        normal_mud_density_ppg=9.0
    )
    dataset = session.current_dataset
    assert dataset is not None

    expected_curves = {
        "WH",
        "BH",
        "CH",
        "C1_C2",
        "C1_C3",
        "C1_C4",
        "C1_C5",
        "C1_NORM",
        "C1_NORM_REF",
        "C2_NORM",
        "C3_NORM",
        "IC4_NORM",
        "NC4_NORM",
        "IC5_NORM",
        "NC5_NORM",
        "TG_NORM_CALC",
        "DEXP",
        "DEXPC",
    }
    assert expected_curves <= set(result.changed)
    assert expected_curves <= {
        curve.metadata.original_mnemonic for curve in dataset.curves.values()
    }
    np.testing.assert_allclose(dataset.curve_by_mnemonic("WH").values, 20.0)
    np.testing.assert_allclose(dataset.curve_by_mnemonic("C1_C4").values, 80.0 / 3.0)
    np.testing.assert_allclose(
        dataset.curve_by_mnemonic("C1_NORM").values,
        11.6 * 80.0 * 500.0 / (60.0 * 10.0**2),
        rtol=1e-7,
    )
    np.testing.assert_allclose(
        dataset.curve_by_mnemonic("TG_NORM_CALC").values,
        100.0 * 50.0 / 60.0,
        rtol=1e-7,
    )
    np.testing.assert_allclose(
        dataset.curve_by_mnemonic("C2_NORM").values,
        10.0 * 50.0 / 60.0,
        rtol=1e-7,
    )
    np.testing.assert_allclose(
        dataset.curve_by_mnemonic("DEXP").values,
        1.6368638103758524,
        rtol=1e-6,
    )
    np.testing.assert_allclose(
        dataset.curve_by_mnemonic("DEXPC").values,
        1.6368638103758524 * 0.75,
        rtol=1e-6,
    )
    assert result.track_curves["gas_ratio_pixler"][:3] == ("WH", "BH", "CH")
    assert result.track_curves["normalized_gas"] == (
        "TG_NORM_CALC",
        "C1_NORM",
        "C1_NORM_REF",
        "C2_NORM",
        "C3_NORM",
        "IC4_NORM",
        "NC4_NORM",
        "IC5_NORM",
        "NC5_NORM",
    )
    assert result.track_curves["dexp"][:2] == ("DEXP", "DEXPC")
    assert session.dirty is True


def test_standard_interpretation_suite_does_not_overwrite_source_curve() -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    original = np.full(dataset.depth.shape, 777.0)
    _add_curve(dataset, "WH", original, "%", provenance="source:las")

    result = InterpretationCalculationController(session).calculate_standard_curves()

    np.testing.assert_array_equal(dataset.curve_by_mnemonic("WH").values, original)
    assert "WH" in result.skipped
    assert any(issue.code == "source-protected" for issue in result.issues)


def test_standard_suite_preserves_server_normalized_total_gas_alias() -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    server_values = np.full(dataset.depth.shape, 321.0)
    _add_curve(
        dataset,
        "NORMALIZED_TOTAL_GAS",
        server_values,
        "normalized gas units",
        provenance="source:server",
    )

    result = InterpretationCalculationController(session).calculate_standard_curves()

    np.testing.assert_array_equal(
        dataset.curve_by_mnemonic("NORMALIZED_TOTAL_GAS").values,
        server_values,
    )
    local = dataset.curve_by_mnemonic("TG_NORM_CALC")
    assert local is not None
    assert local.metadata.provenance.startswith("calculation:")
    assert "TG_NORM_CALC" in result.changed
    assert "NORMALIZED_TOTAL_GAS" in result.track_curves["normalized_gas"]
    assert "TG_NORM_CALC" in result.track_curves["normalized_gas"]
    assert not any(
        issue.code == "source-protected" and "NORMALIZED_TOTAL_GAS" in issue.message
        for issue in result.issues
    )


def test_standard_suite_uses_geoscape_c4_c5_as_contextual_normal_isomers() -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    dataset.curves.pop("NC4")
    dataset.curves.pop("NC5")
    _add_curve(dataset, "C4", np.full(dataset.depth.shape, 3.0), "%")
    _add_curve(dataset, "C5", np.full(dataset.depth.shape, 2.0), "%")

    result = InterpretationCalculationController(session).calculate_standard_curves()

    resolution = InterpretationCalculationController(session).resolver.resolve_dataset(
        dataset,
        targets=("NC4", "NC5"),
    )
    assert resolution.require("NC4").source_mnemonic == "C4"
    assert resolution.require("NC5").source_mnemonic == "C5"
    np.testing.assert_allclose(dataset.curve_by_mnemonic("NC4_REL").values, 3.0 / 102.0 * 100.0)
    np.testing.assert_allclose(dataset.curve_by_mnemonic("NC5_REL").values, 2.0 / 102.0 * 100.0)
    assert {"NC4_REL", "NC5_REL"} <= set(result.changed)


def test_standard_suite_preserves_empty_source_and_uses_contextual_fallback() -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    dataset.curve_by_mnemonic("NC4").values[:] = np.nan
    dataset.curve_by_mnemonic("NC5").values[:] = np.nan
    _add_curve(dataset, "C4", np.full(dataset.depth.shape, 3.0), "%")
    _add_curve(dataset, "C5", np.full(dataset.depth.shape, 2.0), "%")

    result = InterpretationCalculationController(session).calculate_standard_curves()

    source_nc4 = dataset.curves["NC4"]
    source_nc5 = dataset.curves["NC5"]
    assert np.all(np.isnan(source_nc4.values))
    assert np.all(np.isnan(source_nc5.values))
    resolved = InterpretationCalculationController(session).resolver.resolve_dataset(
        dataset,
        targets=("NC4", "NC5"),
    )
    assert resolved.require("NC4").source_mnemonic == "C4"
    assert resolved.require("NC5").source_mnemonic == "C5"
    assert dataset.curve_by_mnemonic("NC4_DERIVED") is None
    assert dataset.curve_by_mnemonic("NC5_DERIVED") is None
    assert {"NC4_REL", "NC5_REL"} <= set(result.changed)
