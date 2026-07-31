from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import numpy as np
from numpy.typing import NDArray

from geoworkbench.catalogs.sensors import normalize_sensor_key, normalize_unit
from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.services.uom_dictionary import UomDictionary, default_uom_dictionary


Array = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
ModeArray = NDArray[np.int16]


class DrillingModeCode(IntEnum):
    """Numeric drilling-mode codes stored alongside calculated DEXP curves."""

    UNKNOWN = 0
    ROTARY = 1
    SLIDE = 2
    NOT_DRILLING = 3


@dataclass(frozen=True, slots=True)
class DrillingModeResolution:
    """Per-sample drilling mode and the RPM that is valid for DEXP."""

    mode_codes: ModeArray
    effective_rpm: Array
    rotary_mask: BoolArray
    slide_mask: BoolArray
    slide_missing_bit_rpm_mask: BoolArray
    not_drilling_mask: BoolArray
    unknown_mask: BoolArray
    repairable_mask: BoolArray
    bit_rpm_mnemonic: str | None = None

    @property
    def rotary_points(self) -> int:
        return int(np.count_nonzero(self.rotary_mask))

    @property
    def slide_points(self) -> int:
        return int(np.count_nonzero(self.slide_mask))

    @property
    def slide_points_with_bit_rpm(self) -> int:
        return int(np.count_nonzero(self.slide_mask & np.isfinite(self.effective_rpm)))

    @property
    def slide_points_without_bit_rpm(self) -> int:
        return int(np.count_nonzero(self.slide_missing_bit_rpm_mask))


_BIT_RPM_ALIASES = {
    "BITRPM",
    "RPMBIT",
    "DOWNHOLERPM",
    "DHRPM",
    "BOTTOMHOLERPM",
    "BHARPM",
    "MOTORRPM",
    "MUDMOTORRPM",
    "PDMRPM",
    "TOOLRPM",
    "TURBINERPM",
    "ЗАБОЙНЫЕОБОРОТЫ",
    "ОБОРОТЫДОЛОТА",
    "ОБОРОТЫЗАБОЙНОГОДВИГАТЕЛЯ",
}
_SURFACE_RPM_ALIASES = {
    "RPM",
    "SURFACERPM",
    "ROTARYRPM",
    "ROTARYTABLERPM",
    "TOPDRIVERPM",
    "ОБОРОТЫРОТОРА",
    "ОБОРОТЫВЕРХНЕГОПРИВОДА",
}


def classify_drilling_modes(
    rop: Array,
    surface_rpm: Array,
    wob: Array,
    *,
    flow: Array | None = None,
    bit_rpm: Array | None = None,
    rotary_threshold_rpm: float = 5.0,
    minimum_flow: float = 0.0,
) -> DrillingModeResolution:
    """Classify rotary, slide and non-drilling samples without inventing bit RPM.

    A low surface RPM is treated as slide only when positive circulation is
    available. This avoids confusing connections and pumps-off intervals with
    slide drilling. During slide the effective RPM is taken only from a real
    downhole/bit/motor RPM curve; otherwise DEXP remains unavailable.
    """

    arrays = [np.asarray(rop, dtype=np.float64), np.asarray(surface_rpm, dtype=np.float64), np.asarray(wob, dtype=np.float64)]
    if any(item.ndim != 1 for item in arrays):
        raise ValueError("ROP, RPM и WOB должны быть одномерными массивами")
    if len({item.shape for item in arrays}) != 1:
        raise ValueError("ROP, RPM и WOB должны иметь одинаковую длину")
    if not np.isfinite(rotary_threshold_rpm) or rotary_threshold_rpm < 0.0:
        raise ValueError("Порог роторного RPM должен быть неотрицательным")
    if not np.isfinite(minimum_flow) or minimum_flow < 0.0:
        raise ValueError("Минимальный расход должен быть неотрицательным")

    rop_values, surface_values, wob_values = arrays
    shape = rop_values.shape
    flow_values = _optional_array(flow, shape, "FLOW")
    bit_values = _optional_array(bit_rpm, shape, "BIT_RPM")

    finite_rop = np.isfinite(rop_values)
    finite_surface = np.isfinite(surface_values)
    finite_wob = np.isfinite(wob_values)
    drilling_load = finite_rop & finite_wob & (rop_values > 0.0) & (wob_values > 0.0)

    rotary = drilling_load & finite_surface & (surface_values > rotary_threshold_rpm)
    low_surface = (
        drilling_load
        & finite_surface
        & (surface_values >= 0.0)
        & (surface_values <= rotary_threshold_rpm)
    )

    if flow_values is None:
        slide = np.zeros(shape, dtype=bool)
        circulation_stopped = np.zeros(shape, dtype=bool)
    else:
        finite_flow = np.isfinite(flow_values)
        slide = low_surface & finite_flow & (flow_values > minimum_flow)
        circulation_stopped = low_surface & finite_flow & (flow_values <= minimum_flow)

    not_drilling = (
        (finite_rop & (rop_values <= 0.0))
        | (finite_wob & (wob_values <= 0.0))
        | circulation_stopped
    )
    classified = rotary | slide | not_drilling
    unknown = ~classified

    mode_codes = np.full(shape, int(DrillingModeCode.UNKNOWN), dtype=np.int16)
    mode_codes[rotary] = int(DrillingModeCode.ROTARY)
    mode_codes[slide] = int(DrillingModeCode.SLIDE)
    mode_codes[not_drilling] = int(DrillingModeCode.NOT_DRILLING)

    effective_rpm = np.full(shape, np.nan, dtype=np.float64)
    effective_rpm[rotary] = surface_values[rotary]
    bit_valid = np.zeros(shape, dtype=bool)
    if bit_values is not None:
        bit_valid = np.isfinite(bit_values) & (bit_values > 0.0)
        use_bit = slide & bit_valid
        effective_rpm[use_bit] = bit_values[use_bit]

    slide_missing_bit_rpm = slide & ~bit_valid
    repairable = rotary | (slide & bit_valid)
    return DrillingModeResolution(
        mode_codes=mode_codes,
        effective_rpm=effective_rpm,
        rotary_mask=rotary,
        slide_mask=slide,
        slide_missing_bit_rpm_mask=slide_missing_bit_rpm,
        not_drilling_mask=not_drilling,
        unknown_mask=unknown,
        repairable_mask=repairable,
    )


def resolve_bit_rpm_curve(
    dataset: Dataset,
    *,
    uom: UomDictionary | None = None,
) -> tuple[Array | None, str | None]:
    """Return an explicit downhole/bit RPM curve, never the surface RPM curve."""

    dictionary = uom or default_uom_dictionary()
    candidates: list[tuple[int, int, str, CurveData, Array]] = []
    for curve in dataset.curves.values():
        original = curve.metadata.original_mnemonic or ""
        canonical = curve.metadata.canonical_mnemonic or ""
        description = curve.metadata.description or ""
        keys = {
            normalize_sensor_key(original),
            normalize_sensor_key(canonical),
        }
        keys.discard("")
        if keys & _SURFACE_RPM_ALIASES:
            continue

        exact = bool(keys & _BIT_RPM_ALIASES)
        description_key = normalize_sensor_key(description)
        descriptive = (
            ("RPM" in description_key and any(marker in description_key for marker in ("BIT", "MOTOR", "DOWNHOLE", "BHA", "PDM", "TURBINE")))
            or ("ОБОРОТ" in description_key and any(marker in description_key for marker in ("ДОЛОТ", "ЗАБОЙ", "ДВИГАТЕЛ")))
        )
        if not exact and not descriptive:
            continue

        converted = _convert_rpm_curve(curve, dictionary)
        if converted is None or converted.shape != dataset.depth.shape:
            continue
        valid_count = int(np.count_nonzero(np.isfinite(converted) & (converted > 0.0)))
        if valid_count == 0:
            continue
        score = 0 if exact else 1
        candidates.append((score, -valid_count, original.casefold(), curve, converted))

    if not candidates:
        return None, None
    _, _, _, curve, values = min(candidates, key=lambda item: item[:3])
    return values, curve.metadata.original_mnemonic


def _convert_rpm_curve(curve: CurveData, dictionary: UomDictionary) -> Array | None:
    unit = curve.metadata.unit or ""
    conversion = dictionary.conversion(unit, "1/min")
    if conversion is not None:
        return conversion.convert_array(curve.values)
    if normalize_unit(unit) in {"rpm", "1/min", "rev/min", "r/min", "об/мин"}:
        return np.asarray(curve.values, dtype=np.float64).copy()
    return None


def _optional_array(value: Array | None, shape: tuple[int, ...], name: str) -> Array | None:
    if value is None:
        return None
    result = np.asarray(value, dtype=np.float64)
    if result.ndim != 1 or result.shape != shape:
        raise ValueError(f"{name} должен совпадать по форме с ROP")
    return result


__all__ = [
    "DrillingModeCode",
    "DrillingModeResolution",
    "classify_drilling_modes",
    "resolve_bit_rpm_curve",
]
