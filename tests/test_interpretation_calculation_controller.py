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
    assert result.track_curves["normalized_gas"] == ("C1_NORM",)
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
