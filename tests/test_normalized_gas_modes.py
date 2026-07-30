from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    CuttingsSample,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
    NormalizedGasCalculationMode,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.hydrocarbon_interpretation import (
    build_hydrocarbon_interpretation_report,
)


def _add_curve(
    dataset: Dataset,
    mnemonic: str,
    values: np.ndarray,
    unit: str,
    provenance: str,
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


def _calculation_session() -> ProjectSession:
    depth = np.arange(2_000.0, 2_060.0)
    dataset = Dataset(
        "normalized-gas-calculation",
        "Normalized gas calculation",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    constants = {
        "C1": (80.0, "%"),
        "C2": (10.0, "%"),
        "C3": (5.0, "%"),
        "IC4": (1.0, "%"),
        "NC4": (2.0, "%"),
        "IC5": (1.0, "%"),
        "NC5": (1.0, "%"),
        "ROP": (60.0, "ft/h"),
        "BIT": (10.0, "in"),
        "FLOW": (500.0, "gpm"),
    }
    for mnemonic, (value, unit) in constants.items():
        _add_curve(
            dataset,
            mnemonic,
            np.full(depth.shape, value),
            unit,
            "source:test",
        )
    server = np.full(depth.shape, 321.0)
    _add_curve(
        dataset,
        "NORMALIZED_TOTAL_GAS",
        server,
        "normalized gas units",
        "source:server",
    )
    session = ProjectSession()
    session.add_dataset(dataset, "Well A")
    session.dirty = False
    return session


def test_server_curve_is_preserved_and_local_total_is_stored_separately() -> None:
    session = _calculation_session()
    dataset = session.current_dataset
    assert dataset is not None
    original_server = dataset.curve_by_mnemonic("NORMALIZED_TOTAL_GAS").values.copy()

    result = InterpretationCalculationController(session).calculate_standard_curves(
        normalized_gas_mode=NormalizedGasCalculationMode.COMPARE
    )

    np.testing.assert_array_equal(
        dataset.curve_by_mnemonic("NORMALIZED_TOTAL_GAS").values,
        original_server,
    )
    local = dataset.curve_by_mnemonic("TG_NORM_CALC")
    assert local is not None
    assert local.metadata.provenance.startswith("calculation:")
    np.testing.assert_allclose(local.values, 100.0 * 50.0 / 60.0, rtol=1e-7)
    assert "TG_NORM_CALC" in result.changed
    assert "NORMALIZED_TOTAL_GAS" in result.track_curves["normalized_gas"]
    assert "TG_NORM_CALC" in result.track_curves["normalized_gas"]


def _comparison_session() -> ProjectSession:
    depth = np.arange(1_000.0, 1_080.0)
    dataset = Dataset(
        "normalized-gas-comparison",
        "Normalized gas comparison",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    server = np.ones(depth.shape)
    server[20:23] = (80.0, 120.0, 90.0)
    local = np.ones(depth.shape)
    local[21:24] = (75.0, 110.0, 85.0)
    _add_curve(
        dataset,
        "NORMALIZED_TOTAL_GAS",
        server,
        "normalized gas units",
        "source:server",
    )
    _add_curve(
        dataset,
        "TG_NORM_CALC",
        local,
        "normalized gas units",
        "calculation:test",
    )
    components = {
        "C1": 90.0,
        "C2": 5.0,
        "C3": 3.0,
        "IC4": 0.5,
        "NC4": 0.5,
        "IC5": 0.25,
        "NC5": 0.25,
    }
    for mnemonic, value in components.items():
        _add_curve(
            dataset,
            mnemonic,
            np.full(depth.shape, value),
            "%",
            "source:test",
        )
    session = ProjectSession()
    well = session.add_dataset(dataset, "Well B")
    well.cuttings.append(
        CuttingsSample(
            "lba-overlap",
            1_019.5,
            1_024.5,
            lba_group=2,
            lba_type_id="ПБ",
            lba_intensity=3,
            lba_color="ЖК — жёлто-коричневый",
        )
    )
    return session


def test_compare_mode_reports_both_sources_and_correlates_each_with_lba() -> None:
    report = build_hydrocarbon_interpretation_report(
        _comparison_session(),
        normalized_gas_mode=NormalizedGasCalculationMode.COMPARE,
    )

    assert report.primary_mnemonic is not None
    assert "NORMALIZED_TOTAL_GAS" in report.primary_mnemonic
    assert "TG_NORM_CALC" in report.primary_mnemonic
    assert {candidate.primary_mnemonic for candidate in report.candidates} == {
        "NORMALIZED_TOTAL_GAS",
        "TG_NORM_CALC",
    }
    assert all(candidate.lba_assessments for candidate in report.candidates)
    assert all(
        any(item.startswith("normalized-gas source=") for item in candidate.evidence)
        for candidate in report.candidates
    )
    assert any("совпадающих интервалов" in warning for warning in report.warnings)


def test_server_and_local_report_modes_filter_candidate_source() -> None:
    session = _comparison_session()

    server = build_hydrocarbon_interpretation_report(
        session,
        normalized_gas_mode=NormalizedGasCalculationMode.SERVER,
    )
    local = build_hydrocarbon_interpretation_report(
        session,
        normalized_gas_mode=NormalizedGasCalculationMode.LOCAL,
    )

    assert {candidate.primary_mnemonic for candidate in server.candidates} == {
        "NORMALIZED_TOTAL_GAS"
    }
    assert {candidate.primary_mnemonic for candidate in local.candidates} == {
        "TG_NORM_CALC"
    }
