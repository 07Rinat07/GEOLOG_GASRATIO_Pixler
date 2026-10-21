"""Explicit, read-only petrophysical reference methods for verified GIS inputs.

INTERP-PETRO-01 data-only slice. No mnemonic matching, implicit unit conversion,
resampling, lithology classification, LAS mutations, or fluid/pay prediction.
Callers must explicitly validate GIS provenance/units and calibrate parameters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import exp, isfinite, log


class PetrophysicalQuality(str, Enum):
    VALID = "valid"
    OUTSIDE_REFERENCE_RANGE = "outside_reference_range"
    OUTSIDE_PHYSICAL_RANGE = "outside_physical_range"


@dataclass(frozen=True, slots=True)
class PetrophysicalEstimate:
    """Raw result and its calibration, never a direct pay or fluid decision."""

    method_id: str
    value: float
    unit: str
    quality: PetrophysicalQuality
    parameters: tuple[tuple[str, float], ...]

    @property
    def usable_as_fraction(self) -> bool:
        return self.quality is PetrophysicalQuality.VALID and 0.0 <= self.value <= 1.0


def gamma_ray_index(
    *,
    gamma_api: float,
    clean_reference_api: float,
    shale_reference_api: float,
) -> PetrophysicalEstimate:
    """Compute IGR, not Vclay or certified Vsh, using local GR end members.

    All inputs must already be measured in calibrated API units on a verified
    common depth axis. Do not clip out-of-range measurements to [0, 1].
    """
    measured = _finite("gamma_api", gamma_api)
    clean = _finite("clean_reference_api", clean_reference_api)
    shale = _finite("shale_reference_api", shale_reference_api)
    if shale <= clean:
        raise ValueError("shale_reference_api must exceed clean_reference_api")
    result = (measured - clean) / (shale - clean)
    if not isfinite(result):
        raise ValueError("gamma-ray index overflows the calibrated reference span")
    quality = (
        PetrophysicalQuality.VALID
        if 0.0 <= result <= 1.0
        else PetrophysicalQuality.OUTSIDE_REFERENCE_RANGE
    )
    return PetrophysicalEstimate(
        "igr-linear-1", result, "v/v", quality,
        (
            ("gamma_api", measured),
            ("clean_reference_api", clean),
            ("shale_reference_api", shale),
        ),
    )


def density_porosity(
    *,
    bulk_density_g_cm3: float,
    matrix_density_g_cm3: float,
    fluid_density_g_cm3: float,
) -> PetrophysicalEstimate:
    """Density-derived porosity from caller-calibrated matrix and fluid data."""
    bulk = _positive("bulk_density_g_cm3", bulk_density_g_cm3)
    matrix = _positive("matrix_density_g_cm3", matrix_density_g_cm3)
    fluid = _positive("fluid_density_g_cm3", fluid_density_g_cm3)
    if matrix <= fluid:
        raise ValueError("matrix_density_g_cm3 must exceed fluid_density_g_cm3")
    result = (matrix - bulk) / (matrix - fluid)
    if not isfinite(result):
        raise ValueError("density porosity overflows")
    quality = (
        PetrophysicalQuality.VALID
        if 0.0 <= result <= 1.0
        else PetrophysicalQuality.OUTSIDE_PHYSICAL_RANGE
    )
    return PetrophysicalEstimate(
        "density-porosity-1", result, "v/v", quality,
        (
            ("bulk_density_g_cm3", bulk),
            ("matrix_density_g_cm3", matrix),
            ("fluid_density_g_cm3", fluid),
        ),
    )


def archie_water_saturation(
    *,
    porosity_fraction: float,
    true_resistivity_ohm_m: float,
    formation_water_resistivity_ohm_m: float,
    tortuosity_factor: float,
    cementation_exponent: float,
    saturation_exponent: float,
) -> PetrophysicalEstimate:
    """Unclipped Archie Sw: (a*Rw / (phi**m * Rt))**(1/n).

    This method is limited to a validated Archie-type reservoir. Its output
    alone does not identify oil versus gas or establish producible pay.
    """
    porosity = _positive("porosity_fraction", porosity_fraction)
    if porosity > 1.0:
        raise ValueError("porosity_fraction must not exceed one")
    resistance = _positive("true_resistivity_ohm_m", true_resistivity_ohm_m)
    water = _positive("formation_water_resistivity_ohm_m", formation_water_resistivity_ohm_m)
    tortuosity = _positive("tortuosity_factor", tortuosity_factor)
    cementation = _positive("cementation_exponent", cementation_exponent)
    saturation = _positive("saturation_exponent", saturation_exponent)
    # Log domain prevents premature denominator underflow for tiny phi**m.
    log_sw = (
        log(tortuosity) + log(water) - cementation * log(porosity)
        - log(resistance)
    ) / saturation
    if not isfinite(log_sw):
        raise ValueError("Archie exponent is not finite")
    try:
        result = exp(log_sw)
    except OverflowError as error:
        raise ValueError("Archie saturation overflows physical representation") from error
    if not isfinite(result) or result == 0.0:
        raise ValueError("Archie saturation exceeds representable precision")
    quality = (
        PetrophysicalQuality.VALID
        if result <= 1.0
        else PetrophysicalQuality.OUTSIDE_PHYSICAL_RANGE
    )
    return PetrophysicalEstimate(
        "archie-water-saturation-1", result, "v/v", quality,
        (
            ("porosity_fraction", porosity),
            ("true_resistivity_ohm_m", resistance),
            ("formation_water_resistivity_ohm_m", water),
            ("tortuosity_factor", tortuosity),
            ("cementation_exponent", cementation),
            ("saturation_exponent", saturation),
        ),
    )


def _finite(name: str, raw: float) -> float:
    if isinstance(raw, bool):
        raise ValueError(f"{name} must be a finite numeric measurement")
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be a finite numeric measurement") from error
    if not isfinite(value):
        raise ValueError(f"{name} must be a finite numeric measurement")
    return value


def _positive(name: str, raw: float) -> float:
    value = _finite(name, raw)
    if value <= 0.0:
        raise ValueError(f"{name} must be positive")
    return value


__all__ = [
    "PetrophysicalEstimate",
    "PetrophysicalQuality",
    "archie_water_saturation",
    "density_porosity",
    "gamma_ray_index",
]
