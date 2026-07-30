from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class GasRatioAssessment:
    """Versioned Wh/Bh/Ch palette result for one representative composition."""

    code: str
    wetness: float
    balance: float | None
    character: float | None
    phase_code: str | None
    profile_id: str = "haworth-datalog-wh-bh-ch-1985-1999"


@dataclass(frozen=True, slots=True)
class PixlerAssessment:
    """Screening result from the four methane/component ratios."""

    code: str
    c1_c2: float
    c1_c3: float | None
    c1_c4: float | None
    c1_c5: float | None
    profile_shape: str | None
    water_association_possible: bool
    profile_id: str = "pixler-c1-c2-c3-c4-c5-1969"


def classify_gas_ratio(
    *,
    wetness: float,
    balance: float | None,
    character: float | None,
) -> GasRatioAssessment:
    """Classify Wh/Bh/Ch using the Haworth/DATALOG interpretation palette.

    Wh and Bh establish the main fluid class. Ch is only a confirmation in the
    gas/condensate-light-oil transition: Ch < 0.5 supports a productive gas
    phase; Ch > 0.5 supports an associated liquid/light-oil phase.
    """

    if not np.isfinite(wetness) or wetness < 0.0:
        raise ValueError("Wh должен быть конечным неотрицательным значением")
    normalized_balance = _finite_nonnegative(balance)
    normalized_character = _finite_nonnegative(character)
    phase_code = (
        "productive_gas_phase"
        if normalized_character is not None and normalized_character < 0.5
        else "productive_liquid_phase"
        if normalized_character is not None and normalized_character > 0.5
        else "phase_boundary"
        if normalized_character == 0.5
        else None
    )

    if normalized_balance is not None and normalized_balance > 100.0:
        code = "very_light_dry_gas"
    elif wetness < 0.5:
        code = "light_dry_gas"
    elif wetness < 17.5:
        if (
            normalized_balance is not None
            and wetness < normalized_balance < 100.0
        ):
            code = "productive_gas_increasing_wetness"
        elif normalized_balance is not None and normalized_balance <= wetness:
            if phase_code == "productive_gas_phase":
                code = "wet_gas_or_gas_condensate"
            elif phase_code == "productive_liquid_phase":
                code = "light_oil_high_gor"
            else:
                code = "gas_condensate_or_high_api_oil"
        else:
            code = "gas_increasing_wetness"
    elif wetness <= 40.0:
        if (
            normalized_balance is not None
            and normalized_balance < wetness * 0.5
        ):
            code = "poor_low_gravity_oil"
        else:
            code = "productive_oil_decreasing_gravity"
    else:
        code = "heavy_or_residual_oil"

    return GasRatioAssessment(
        code,
        float(wetness),
        normalized_balance,
        normalized_character,
        phase_code,
    )


def classify_pixler_ratios(
    *,
    c1_c2: float,
    c1_c3: float | None,
    c1_c4: float | None,
    c1_c5: float | None,
) -> PixlerAssessment:
    """Classify a representative Pixler profile without claiming productivity.

    The C1/C2 bands are overlapping screening zones.  The curve shape is
    reported separately: a fall from C1/C3 to C1/C4 is only a possible
    water-association flag, while permeability needs regional boundary lines.
    """

    methane_ethane = _finite_positive(c1_c2)
    if methane_ethane is None:
        raise ValueError("C1/C2 должен быть конечным положительным значением")
    methane_propane = _finite_positive(c1_c3)
    methane_butane = _finite_positive(c1_c4)
    methane_pentane = _finite_positive(c1_c5)

    if methane_ethane < 2.0:
        code = "nonproductive_residual_or_very_heavy_oil"
    elif methane_ethane < 4.0:
        code = "low_api_oil"
    elif methane_ethane < 8.0:
        code = "medium_api_oil"
    elif methane_ethane < 10.0:
        code = "high_api_light_oil"
    elif methane_ethane <= 15.0:
        code = "light_oil_or_gas_condensate"
    elif methane_ethane <= 20.0:
        code = "gas_or_gas_condensate"
    elif methane_ethane <= 65.0:
        code = "gas"
    else:
        code = "very_light_methane_rich_gas"

    ratios = (
        methane_ethane,
        methane_propane,
        methane_butane,
        methane_pentane,
    )
    finite_ratios = tuple(value for value in ratios if value is not None)
    profile_shape = None
    if len(finite_ratios) >= 3:
        differences = np.diff(np.asarray(finite_ratios, dtype=np.float64))
        profile_shape = (
            "positive"
            if np.all(differences >= 0.0) and np.any(differences > 0.0)
            else "negative"
            if np.all(differences <= 0.0) and np.any(differences < 0.0)
            else "mixed"
        )
    water_association_possible = (
        methane_propane is not None
        and methane_butane is not None
        and methane_butane < methane_propane
    )
    return PixlerAssessment(
        code,
        methane_ethane,
        methane_propane,
        methane_butane,
        methane_pentane,
        profile_shape,
        water_association_possible,
    )


def _finite_nonnegative(value: float | None) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    return numeric if np.isfinite(numeric) and numeric >= 0.0 else None


def _finite_positive(value: float | None) -> float | None:
    normalized = _finite_nonnegative(value)
    return (
        normalized
        if normalized is not None and normalized > np.finfo(np.float64).eps
        else None
    )
