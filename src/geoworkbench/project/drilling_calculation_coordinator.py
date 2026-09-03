from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationResult,
    NormalizedGasCalculationMode,
    NormalizedGasReference,
)
from geoworkbench.services.drilling_input_plan import DrillingInputPlan


class DrillingCalculationPort(Protocol):
    """Mutation boundary required by the drilling-calculation feature."""

    def set_drilling_input_plan(self, plan: DrillingInputPlan) -> None: ...

    def calculate_standard_curves(
        self,
        *,
        normal_mud_density_ppg: float | None = None,
        normalized_gas_reference: NormalizedGasReference | None = None,
        normalized_gas_mode: NormalizedGasCalculationMode | str | None = None,
    ) -> InterpretationCalculationResult: ...


@dataclass(frozen=True, slots=True)
class DrillingCalculationOutcome:
    result: InterpretationCalculationResult
    visible_curves: tuple[str, ...]


@dataclass(slots=True)
class DrillingCalculationCoordinator:
    """Apply drilling inputs and calculate through a project-controller boundary.

    Qt widgets may collect values and render the returned result, but project/session
    mutation stays behind this coordinator and the calculation controller.
    """

    controller: DrillingCalculationPort

    def apply_and_calculate(
        self,
        *,
        plan: DrillingInputPlan,
        normalized_reference: NormalizedGasReference,
        normal_mud_density_ppg: float | None,
        normalized_gas_mode: NormalizedGasCalculationMode | str | None,
    ) -> DrillingCalculationOutcome:
        self.controller.set_drilling_input_plan(plan)
        result = self.controller.calculate_standard_curves(
            normal_mud_density_ppg=normal_mud_density_ppg,
            normalized_gas_reference=normalized_reference,
            normalized_gas_mode=normalized_gas_mode,
        )
        visible = tuple(
            dict.fromkeys(
                (
                    *result.track_curves.get("gas_ratio_pixler", ()),
                    *result.track_curves.get("normalized_gas", ()),
                    *result.track_curves.get("dexp", ()),
                )
            )
        )
        return DrillingCalculationOutcome(result=result, visible_curves=visible)


__all__ = [
    "DrillingCalculationCoordinator",
    "DrillingCalculationOutcome",
    "DrillingCalculationPort",
]
