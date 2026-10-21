"""Read-only raw gas coverage for the complete dataset after an update."""
from dataclasses import dataclass, replace

import numpy as np

from geoworkbench.domain.models import CalculationState, Dataset
from geoworkbench.services.gas_curve_presentation import is_gas_ratio_mnemonic
from geoworkbench.services.las_parameter_resolver import LasParameterResolver

GAS_COMPONENTS = ("TG", "C1", "C2", "C3", "C4", "IC4", "NC4", "C5", "IC5", "NC5")


@dataclass(frozen=True)
class GasComponentCoverage:
    component: str
    source: str = ""
    count: int = 0
    last_index: str = ""
    ambiguous: bool = False


@dataclass(frozen=True)
class GasUpdateCoverage:
    rows: int
    components: tuple[GasComponentCoverage, ...]
    stale_ratios: tuple[str, ...]


def gas_update_coverage(dataset: Dataset) -> GasUpdateCoverage:
    # A projection shares arrays without copying or modifying the original dataset.
    source = replace(dataset, curves={
        key: curve for key, curve in dataset.curves.items()
        if curve.metadata.provenance.strip().casefold() in {"", "source"}
    })
    resolution = LasParameterResolver().resolve_dataset(source, targets=GAS_COMPONENTS)
    index = dataset.active_index.values
    components = []
    for component in GAS_COMPONENTS:
        match = resolution.get(component)
        if match is None:
            components.append(GasComponentCoverage(
                component, ambiguous=component in resolution.ambiguities,
            ))
            continue
        positions = np.flatnonzero(np.isfinite(match.curve.values))
        last = int(positions[-1]) if positions.size else -1
        components.append(GasComponentCoverage(
            component, match.source_mnemonic, int(positions.size),
            str(index[last]) if 0 <= last < len(index) else "",
        ))
    stale = tuple(sorted({
        curve.metadata.original_mnemonic for curve in dataset.curves.values()
        if curve.state == CalculationState.STALE and any(
            is_gas_ratio_mnemonic(name) or (name or "").upper() == "TG_CALC"
            for name in (curve.metadata.original_mnemonic, curve.metadata.canonical_mnemonic)
        )
    }))
    return GasUpdateCoverage(len(index), tuple(components), stale)
