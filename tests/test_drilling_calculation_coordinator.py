from __future__ import annotations

from pathlib import Path

from geoworkbench.project.drilling_calculation_coordinator import (
    DrillingCalculationCoordinator,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationResult,
    NormalizedGasCalculationMode,
    NormalizedGasReference,
)
from geoworkbench.services.drilling_input_plan import DrillingInputPlan


class _Controller:
    def __init__(self, result: InterpretationCalculationResult) -> None:
        self.result = result
        self.plan: DrillingInputPlan | None = None
        self.call: tuple[float | None, NormalizedGasReference, object] | None = None

    def set_drilling_input_plan(self, plan: DrillingInputPlan) -> None:
        self.plan = plan

    def calculate_standard_curves(
        self,
        *,
        normal_mud_density_ppg: float | None = None,
        normalized_gas_reference: NormalizedGasReference | None = None,
        normalized_gas_mode: NormalizedGasCalculationMode | str | None = None,
    ) -> InterpretationCalculationResult:
        assert normalized_gas_reference is not None
        self.call = (
            normal_mud_density_ppg,
            normalized_gas_reference,
            normalized_gas_mode,
        )
        return self.result


def _result() -> InterpretationCalculationResult:
    return InterpretationCalculationResult(
        created=("PIX",),
        updated=("DEXP",),
        skipped=(),
        issues=(),
        track_curves={
            "gas_ratio_pixler": ("PIX", "C1_REL"),
            "normalized_gas": ("C1_REL", "C1_NORM"),
            "dexp": ("DEXP",),
            "other": ("SHOULD_NOT_OPEN",),
        },
    )


def test_coordinator_owns_drilling_project_mutation_boundary() -> None:
    controller = _Controller(_result())
    coordinator = DrillingCalculationCoordinator(controller)
    plan = DrillingInputPlan()
    reference = NormalizedGasReference(
        rop_ref_fph=42.0,
        bit_ref_in=8.5,
        flow_ref_gpm=430.0,
        gas_system_efficiency=0.9,
    )

    outcome = coordinator.apply_and_calculate(
        plan=plan,
        normalized_reference=reference,
        normal_mud_density_ppg=9.4,
        normalized_gas_mode=NormalizedGasCalculationMode.LOCAL,
    )

    assert controller.plan is plan
    assert controller.call == (9.4, reference, NormalizedGasCalculationMode.LOCAL)
    assert outcome.result is controller.result
    assert outcome.visible_curves == ("PIX", "C1_REL", "C1_NORM", "DEXP")


def test_drilling_main_window_has_no_direct_calculation_mutators() -> None:
    source = Path("src/geoworkbench/ui/main_window_drilling.py").read_text(encoding="utf-8")

    assert "self.interpretation_calculation_controller.set_drilling_input_plan(" not in source
    assert "self.interpretation_calculation_controller.calculate_standard_curves(" not in source
