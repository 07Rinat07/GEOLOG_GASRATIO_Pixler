from __future__ import annotations

from dataclasses import dataclass, replace

from geoworkbench.calculations.gas_ratio import (
    CONDITIONED_GAS_PROVENANCE,
    calculate_conditioned_ratios,
)
from geoworkbench.domain.models import Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.las_parameter_resolver import resolve_gas_ratio_inputs


@dataclass(frozen=True, slots=True)
class GasRatioCalculationOutcome:
    """Committed conditioned gas-ratio calculation for the active dataset."""

    dataset: Dataset
    created_mnemonics: tuple[str, ...]


@dataclass(slots=True)
class GasRatioProjectController:
    """Own conditioned Gas Ratio/Haworth/Pixler project mutation outside Qt."""

    session: ProjectSession

    def calculate_basic_ratios(self) -> GasRatioCalculationOutcome:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала откройте LAS-файл")

        # Resolve semantically instead of relying on source-column order or a short
        # exact-mnemonic list. The resolver uses the active Sensors catalog,
        # multilingual descriptions, chemical formulae, units and controlled aliases.
        inputs = resolve_gas_ratio_inputs(dataset)
        calculation = calculate_conditioned_ratios(dataset.depth, inputs)

        created: list[str] = []
        for result in calculation.curves.values():
            curve = dataset.upsert_curve(
                result.mnemonic,
                result.values,
                unit=result.unit,
                description=result.description,
                provenance=CONDITIONED_GAS_PROVENANCE,
            )
            # Generic upsert preserves existing metadata. A versioned calculation must
            # instead publish the metadata of the active calculation profile.
            curve.metadata = replace(
                curve.metadata,
                unit=result.unit,
                description=result.description,
                provenance=CONDITIONED_GAS_PROVENANCE,
            )
            created.append(result.mnemonic)

        # Commit QC provenance only after every derived curve write succeeded. This
        # preserves the previous QC summary when calculation/persistence raises.
        dataset.gas_conditioning_qc = calculation.conditioned_components.qc_summary
        self.session.dirty = True
        return GasRatioCalculationOutcome(dataset, tuple(created))


__all__ = ["GasRatioCalculationOutcome", "GasRatioProjectController"]
