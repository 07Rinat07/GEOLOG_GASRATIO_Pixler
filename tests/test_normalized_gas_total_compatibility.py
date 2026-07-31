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
    NormalizedGasCalculationMode,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.hydrocarbon_interpretation import (
    build_hydrocarbon_interpretation_report,
)


def _curve(
    dataset: Dataset,
    mnemonic: str,
    values: np.ndarray,
    provenance: str,
) -> None:
    dataset.curves[mnemonic] = CurveData(
        CurveMetadata(
            mnemonic,
            mnemonic,
            mnemonic,
            "normalized gas units",
            mnemonic,
            dataset.dataset_id,
            provenance,
        ),
        values,
    )


def test_compare_mode_does_not_match_server_total_against_local_c1_norm() -> None:
    depth = np.arange(1_000.0, 1_080.0)
    dataset = Dataset(
        "total-vs-c1",
        "Total versus C1",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    server_total = np.ones(depth.shape)
    server_total[20:23] = (80.0, 120.0, 90.0)
    local_c1 = np.ones(depth.shape)
    local_c1[20:23] = (75.0, 110.0, 85.0)
    _curve(dataset, "NORMALIZED_TOTAL_GAS", server_total, "source:server")
    _curve(dataset, "C1_NORM", local_c1, "calculation:legacy-local")
    session = ProjectSession()
    session.add_dataset(dataset, "Well A")

    report = build_hydrocarbon_interpretation_report(
        session,
        normalized_gas_mode=NormalizedGasCalculationMode.COMPARE,
    )

    assert report.primary_mnemonic == "NORMALIZED_TOTAL_GAS"
    assert {candidate.primary_mnemonic for candidate in report.candidates} == {
        "NORMALIZED_TOTAL_GAS"
    }
    assert any(
        "C1_NORM не сопоставляется" in warning and "TG_NORM_CALC" in warning
        for warning in report.warnings
    )
