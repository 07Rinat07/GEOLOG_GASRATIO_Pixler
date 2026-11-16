"""Data-only Archie interval evaluation on explicitly paired, reviewed source rows.

No automatic curve discovery, alignment, resampling, LAS writes or fluid typing.
The caller must establish source provenance and model applicability independently.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from geoworkbench.services.petrophysical_reference_models import (
    PetrophysicalEstimate, archie_water_saturation,
)

ARCHIE_PROFILE_METHOD_ID = "archie-water-saturation-1"


class ArchieRowStatus(str, Enum):
    ESTIMATED = "estimated"
    MISSING_INPUT = "missing_input"
    INVALID_INPUT = "invalid_input"


@dataclass(frozen=True, slots=True)
class ArchieInputRow:
    sample_index: int
    md_m: float
    porosity_fraction: float | None
    true_resistivity_ohm_m: float | None


@dataclass(frozen=True, slots=True)
class ArchieProfileRow:
    sample_index: int
    md_m: float
    status: ArchieRowStatus
    estimate: PetrophysicalEstimate | None
    issue: str | None = None


@dataclass(frozen=True, slots=True)
class ArchieProfile:
    method_id: str
    reviewer: str
    applicability_reference: str
    porosity_source: str
    resistivity_source: str
    water_resistivity_reference: str
    md_bounds: tuple[float, float]
    rows: tuple[ArchieProfileRow, ...]


def evaluate_archie_rows(
    rows: tuple[ArchieInputRow, ...], *,
    reviewer: str,
    applicability_reference: str,
    porosity_source: str,
    resistivity_source: str,
    water_resistivity_reference: str,
    formation_water_resistivity_ohm_m: float,
    tortuosity_factor: float,
    cementation_exponent: float,
    saturation_exponent: float,
    max_rows: int = 10_000,
) -> ArchieProfile:
    """Evaluate already paired exact MD rows without inventing alignment.

    This function cannot establish that two input curves are co-registered.
    The caller must verify original MD/row identity, units, provenance and
    Archie applicability before constructing rows; text is an attestation,
    not automatic source validation. Invalid individual measurements retain
    their row and QC. Global coefficients fail the entire calculation.
    """
    evidence = (reviewer, applicability_reference, porosity_source,
                resistivity_source, water_resistivity_reference)
    if any(not isinstance(value, str) or not value.strip() for value in evidence):
        raise ValueError("Reviewer, model evidence and all source references are required")
    if type(max_rows) is not int or max_rows < 1:
        raise ValueError("Positive integer row budget required")
    if not isinstance(rows, tuple) or not rows or len(rows) > max_rows:
        raise ValueError("Nonempty immutable rows within budget required")
    # Validate global coefficients even when every measurement is missing.
    archie_water_saturation(
        porosity_fraction=1.0, true_resistivity_ohm_m=1.0,
        formation_water_resistivity_ohm_m=formation_water_resistivity_ohm_m,
        tortuosity_factor=tortuosity_factor,
        cementation_exponent=cementation_exponent,
        saturation_exponent=saturation_exponent,
    )
    output: list[ArchieProfileRow] = []
    previous_md: float | None = None
    direction = 0
    previous_index = -1
    for row in rows:
        if not isinstance(row, ArchieInputRow) or type(row.sample_index) is not int:
            raise ValueError("Exact source row identity required")
        if row.sample_index <= previous_index:
            raise ValueError("Source row indices must be strictly increasing")
        previous_index = row.sample_index
        if isinstance(row.md_m, bool):
            raise ValueError("Finite MD required")
        try:
            md = float(row.md_m)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Finite MD required") from exc
        if not isfinite(md):
            raise ValueError("Finite MD required")
        if previous_md is not None:
            delta = md - previous_md
            if delta == 0 or (direction and (delta > 0) != (direction > 0)):
                raise ValueError("Exact MD axis must be strictly monotonic")
            direction = 1 if delta > 0 else -1
        previous_md = md
        if row.porosity_fraction is None or row.true_resistivity_ohm_m is None:
            output.append(ArchieProfileRow(row.sample_index, md, ArchieRowStatus.MISSING_INPUT, None))
            continue
        try:
            estimate = archie_water_saturation(
                porosity_fraction=row.porosity_fraction,
                true_resistivity_ohm_m=row.true_resistivity_ohm_m,
                formation_water_resistivity_ohm_m=formation_water_resistivity_ohm_m,
                tortuosity_factor=tortuosity_factor,
                cementation_exponent=cementation_exponent,
                saturation_exponent=saturation_exponent,
            )
        except ValueError as exc:
            output.append(ArchieProfileRow(
                row.sample_index, md, ArchieRowStatus.INVALID_INPUT, None, str(exc),
            ))
        else:
            output.append(ArchieProfileRow(row.sample_index, md, ArchieRowStatus.ESTIMATED, estimate))
    bounds = (min(rows[0].md_m, rows[-1].md_m), max(rows[0].md_m, rows[-1].md_m))
    return ArchieProfile(
        ARCHIE_PROFILE_METHOD_ID, *(value.strip() for value in evidence),
        bounds, tuple(output),
    )
