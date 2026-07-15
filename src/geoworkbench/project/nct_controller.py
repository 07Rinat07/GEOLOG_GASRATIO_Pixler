from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.calculations.normal_compaction import (
    NormalCompactionConfig,
    NormalCompactionResult,
    calculate_normal_compaction_trend,
)
from geoworkbench.project.session import ProjectSession


@dataclass(slots=True)
class NctCalculationController:
    session: ProjectSession

    def calculate(
        self,
        calibration_top: float,
        calibration_bottom: float,
        *,
        minimum_points: int = 3,
    ) -> NormalCompactionResult:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        corrected = dataset.curve_by_mnemonic("DEXPC")
        if corrected is None:
            raise RuntimeError("Сначала рассчитайте скорректированную кривую DEXPC")
        result = calculate_normal_compaction_trend(
            dataset.depth,
            corrected.values,
            NormalCompactionConfig(
                calibration_top,
                calibration_bottom,
                minimum_points=minimum_points,
            ),
        )
        provenance = (
            "calculation:nct.linear:v1:"
            f"{calibration_top:g}-{calibration_bottom:g}:n={result.calibration_points}"
        )
        dataset.upsert_curve(
            "NCT",
            result.trend,
            unit="dimensionless",
            description="Нормальный тренд уплотнения DEXPC",
            provenance=provenance,
        )
        dataset.upsert_curve(
            "DEXPC_NCT",
            result.deviation,
            unit="dimensionless",
            description="Отклонение DEXPC - NCT",
            provenance=provenance,
        )
        self.session.dirty = True
        return result
