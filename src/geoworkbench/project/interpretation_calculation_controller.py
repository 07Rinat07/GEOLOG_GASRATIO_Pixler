from __future__ import annotations

from enum import StrEnum

from geoworkbench.domain.models import Dataset
from geoworkbench.project.interpretation_calculation_controller_legacy import (
    DEFAULT_NORMALIZED_GAS_REFERENCE,
    Array,
    InterpretationCalculationController as _LegacyInterpretationCalculationController,
    InterpretationCalculationIssue,
    InterpretationCalculationResult,
    NormalizedGasReference,
)


class NormalizedGasCalculationMode(StrEnum):
    """Controls whether local normalized gas is calculated alongside source data."""

    COMPARE = "compare"
    SERVER = "server"
    LOCAL = "local"


class InterpretationCalculationController(_LegacyInterpretationCalculationController):
    """Preserve source normalized gas and store the local result independently."""

    normalized_gas_mode: NormalizedGasCalculationMode = NormalizedGasCalculationMode.COMPARE

    def calculate_standard_curves(
        self,
        *,
        normal_mud_density_ppg: float | None = None,
        normalized_gas_reference: NormalizedGasReference
        | None = DEFAULT_NORMALIZED_GAS_REFERENCE,
        normalized_gas_mode: NormalizedGasCalculationMode | str | None = None,
    ) -> InterpretationCalculationResult:
        mode = self._normalized_gas_mode(normalized_gas_mode)
        reference = (
            None
            if mode is NormalizedGasCalculationMode.SERVER
            else normalized_gas_reference
        )
        return super().calculate_standard_curves(
            normal_mud_density_ppg=normal_mud_density_ppg,
            normalized_gas_reference=reference,
        )

    def _normalized_gas_mode(
        self,
        requested: NormalizedGasCalculationMode | str | None,
    ) -> NormalizedGasCalculationMode:
        value = requested if requested is not None else self.normalized_gas_mode
        try:
            return NormalizedGasCalculationMode(str(value))
        except ValueError as exc:
            raise ValueError(f"Неизвестный режим нормализованного газа: {value}") from exc

    def _install_curve(
        self,
        dataset: Dataset,
        mnemonic: str,
        values: Array,
        *,
        unit: str,
        description: str,
        provenance: str,
        created: list[str],
        updated: list[str],
        skipped: list[str],
        issues: list[InterpretationCalculationIssue],
    ) -> None:
        target_mnemonic = mnemonic
        target_description = description
        if mnemonic == "TG_NORM" and provenance.startswith("calculation:"):
            target_mnemonic = "TG_NORM_CALC"
            target_description = f"{description} — local program calculation"
        super()._install_curve(
            dataset,
            target_mnemonic,
            values,
            unit=unit,
            description=target_description,
            provenance=provenance,
            created=created,
            updated=updated,
            skipped=skipped,
            issues=issues,
        )


__all__ = [
    "DEFAULT_NORMALIZED_GAS_REFERENCE",
    "InterpretationCalculationController",
    "InterpretationCalculationIssue",
    "InterpretationCalculationResult",
    "NormalizedGasCalculationMode",
    "NormalizedGasReference",
]
