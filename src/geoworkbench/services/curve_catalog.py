from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from geoworkbench.catalogs.sensors import SensorCatalog, SensorMatch
from geoworkbench.domain.models import CurveData, Dataset


class CurveCategory(StrEnum):
    GAS = "gas"
    DRILLING = "drilling"
    MUD = "mud"
    PETROPHYSICS = "petrophysics"
    DEXP = "dexp"
    OTHER = "other"


class CurveFamily(StrEnum):
    """Display-compatible parameter family used to build readable tablet tracks."""

    GAS = "gas"
    ROP = "rop"
    ROTARY_SPEED = "rotary_speed"
    WOB = "wob"
    TORQUE = "torque"
    PRESSURE = "pressure"
    HOOKLOAD = "hookload"
    FLOW = "flow"
    DRILLING_DEPTH = "drilling_depth"
    MUD_DENSITY = "mud_density"
    TEMPERATURE = "temperature"
    PIT_VOLUME = "pit_volume"
    CONDUCTIVITY = "conductivity"
    CHLORIDES = "chlorides"
    GAMMA_RAY = "gamma_ray"
    SP = "sp"
    CALIPER = "caliper"
    BULK_DENSITY = "bulk_density"
    NEUTRON = "neutron"
    SONIC = "sonic"
    RESISTIVITY = "resistivity"
    PEF = "pef"
    DEXP = "dexp"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class CurveCatalogEntry:
    curve_id: str
    mnemonic: str
    canonical_mnemonic: str
    unit: str
    description: str
    category: CurveCategory
    family: CurveFamily
    valid_count: int
    total_count: int
    minimum: float | None
    maximum: float | None
    reference_name: str = ""
    reference_source: str = ""
    reference_default_min: float | None = None
    reference_default_max: float | None = None
    matched_catalog_id: str | None = None
    match_method: str | None = None

    @property
    def coverage_percent(self) -> float:
        if self.total_count <= 0:
            return 0.0
        return 100.0 * self.valid_count / self.total_count

    @property
    def range_text(self) -> str:
        if self.minimum is None or self.maximum is None:
            return "—"
        return f"{self.minimum:g} … {self.maximum:g}"

    @property
    def reference_range_text(self) -> str:
        if self.reference_default_min is None or self.reference_default_max is None:
            return "—"
        return f"{self.reference_default_min:g} … {self.reference_default_max:g}"

    @property
    def is_catalog_matched(self) -> bool:
        return self.matched_catalog_id is not None


_GAS = {
    "TG",
    "TGAS",
    "TOTALGAS",
    "TOTAL_GAS",
    "TG_CALC",
    "C1",
    "C2",
    "C3",
    "IC4",
    "NC4",
    "C4",
    "IC5",
    "NC5",
    "C5",
}
_DEXP = {"DEXP", "DEXPC", "NCT", "DEXPC_NCT"}
_DRILLING = {
    "ROP",
    "ROP5",
    "BIT_RPM",
    "RPM",
    "WOB",
    "TORQUE",
    "TQ",
    "SPP",
    "STANDPIPE_PRESSURE",
    "HOOKLOAD",
    "HKLD",
    "FLOW",
    "FLOW_IN",
    "FLOW_OUT",
    "BIT_DEPTH",
    "HOLE_DEPTH",
}
_MUD = {
    "MW",
    "MUD_WEIGHT",
    "ECD",
    "MUD_TEMP",
    "TEMP_IN",
    "TEMP_OUT",
    "PIT_VOL",
    "PVT",
    "CONDUCTIVITY",
    "CHLORIDES",
}
_PETROPHYSICS = {
    "GR",
    "GAMMA",
    "SP",
    "CALI",
    "CAL",
    "RHOB",
    "NPHI",
    "DT",
    "DTC",
    "DTS",
    "RES",
    "RT",
    "ILD",
    "ILM",
    "LLD",
    "LLS",
    "MSFL",
    "PEF",
}

_CATEGORY_PRIORITY = {
    CurveCategory.GAS: 0,
    CurveCategory.DRILLING: 1,
    CurveCategory.MUD: 2,
    CurveCategory.PETROPHYSICS: 3,
    CurveCategory.DEXP: 4,
    CurveCategory.OTHER: 5,
}

_FAMILY_BY_MNEMONIC: dict[str, CurveFamily] = {
    **{name: CurveFamily.GAS for name in _GAS},
    **{name: CurveFamily.DEXP for name in _DEXP},
    "ROP": CurveFamily.ROP,
    "ROP5": CurveFamily.ROP,
    "BIT_RPM": CurveFamily.ROTARY_SPEED,
    "RPM": CurveFamily.ROTARY_SPEED,
    "WOB": CurveFamily.WOB,
    "TORQUE": CurveFamily.TORQUE,
    "TQ": CurveFamily.TORQUE,
    "SPP": CurveFamily.PRESSURE,
    "STANDPIPE_PRESSURE": CurveFamily.PRESSURE,
    "HOOKLOAD": CurveFamily.HOOKLOAD,
    "HKLD": CurveFamily.HOOKLOAD,
    "FLOW": CurveFamily.FLOW,
    "FLOW_IN": CurveFamily.FLOW,
    "FLOW_OUT": CurveFamily.FLOW,
    "BIT_DEPTH": CurveFamily.DRILLING_DEPTH,
    "HOLE_DEPTH": CurveFamily.DRILLING_DEPTH,
    "MW": CurveFamily.MUD_DENSITY,
    "MUD_WEIGHT": CurveFamily.MUD_DENSITY,
    "ECD": CurveFamily.MUD_DENSITY,
    "MUD_TEMP": CurveFamily.TEMPERATURE,
    "TEMP_IN": CurveFamily.TEMPERATURE,
    "TEMP_OUT": CurveFamily.TEMPERATURE,
    "PIT_VOL": CurveFamily.PIT_VOLUME,
    "PVT": CurveFamily.PIT_VOLUME,
    "CONDUCTIVITY": CurveFamily.CONDUCTIVITY,
    "CHLORIDES": CurveFamily.CHLORIDES,
    "GR": CurveFamily.GAMMA_RAY,
    "GAMMA": CurveFamily.GAMMA_RAY,
    "SP": CurveFamily.SP,
    "CALI": CurveFamily.CALIPER,
    "CAL": CurveFamily.CALIPER,
    "RHOB": CurveFamily.BULK_DENSITY,
    "NPHI": CurveFamily.NEUTRON,
    "DT": CurveFamily.SONIC,
    "DTC": CurveFamily.SONIC,
    "DTS": CurveFamily.SONIC,
    "RES": CurveFamily.RESISTIVITY,
    "RT": CurveFamily.RESISTIVITY,
    "ILD": CurveFamily.RESISTIVITY,
    "ILM": CurveFamily.RESISTIVITY,
    "LLD": CurveFamily.RESISTIVITY,
    "LLS": CurveFamily.RESISTIVITY,
    "MSFL": CurveFamily.RESISTIVITY,
    "PEF": CurveFamily.PEF,
}

_FAMILY_PRIORITY = {family: index for index, family in enumerate(CurveFamily)}


def _catalog_match(curve: CurveData, catalog: SensorCatalog | None = None) -> SensorMatch | None:
    metadata = curve.metadata
    if catalog is None:
        return None
    reference = catalog
    requested = metadata.canonical_mnemonic or metadata.original_mnemonic
    match = reference.match(
        requested,
        description=metadata.description or "",
        unit=metadata.unit or "",
    )
    if match is None and requested != metadata.original_mnemonic:
        match = reference.match(
            metadata.original_mnemonic,
            description=metadata.description or "",
            unit=metadata.unit or "",
        )
    return match


def classify_curve(curve: CurveData, catalog: SensorCatalog | None = None) -> CurveCategory:
    match = _catalog_match(curve, catalog)
    if match is not None:
        try:
            return CurveCategory(match.definition.category)
        except ValueError:
            pass
    metadata = curve.metadata
    canonical = (metadata.canonical_mnemonic or metadata.original_mnemonic).strip().upper()
    if canonical in _GAS:
        return CurveCategory.GAS
    if canonical in _DEXP:
        return CurveCategory.DEXP
    if canonical in _DRILLING:
        return CurveCategory.DRILLING
    if canonical in _MUD:
        return CurveCategory.MUD
    if canonical in _PETROPHYSICS:
        return CurveCategory.PETROPHYSICS
    return CurveCategory.OTHER


def classify_curve_family(curve: CurveData, catalog: SensorCatalog | None = None) -> CurveFamily:
    match = _catalog_match(curve, catalog)
    if match is not None:
        try:
            return CurveFamily(match.definition.family)
        except ValueError:
            pass
    metadata = curve.metadata
    canonical = (metadata.canonical_mnemonic or metadata.original_mnemonic).strip().upper()
    return _FAMILY_BY_MNEMONIC.get(canonical, CurveFamily.OTHER)


def analyze_dataset_curves(
    dataset: Dataset, catalog: SensorCatalog | None = None
) -> tuple[CurveCatalogEntry, ...]:
    reference = catalog
    entries: list[CurveCatalogEntry] = []
    for curve in dataset.curves.values():
        values = np.asarray(curve.values, dtype=float)
        finite = values[np.isfinite(values)]
        minimum = float(np.min(finite)) if finite.size else None
        maximum = float(np.max(finite)) if finite.size else None
        metadata = curve.metadata
        match = _catalog_match(curve, reference) if reference is not None else None
        definition = match.definition if match is not None else None
        description = (metadata.description or "").strip()
        if definition is not None and (
            not description or description == metadata.original_mnemonic
        ):
            description = definition.name_ru
        unit = (metadata.unit or "").strip()
        if definition is not None and not unit:
            unit = definition.unit
        entries.append(
            CurveCatalogEntry(
                curve_id=metadata.curve_id,
                mnemonic=metadata.original_mnemonic,
                canonical_mnemonic=(
                    definition.canonical_mnemonic
                    if definition is not None
                    else metadata.canonical_mnemonic or metadata.original_mnemonic
                ),
                unit=unit,
                description=description,
                category=classify_curve(curve, reference),
                family=classify_curve_family(curve, reference),
                valid_count=int(finite.size),
                total_count=int(values.size),
                minimum=minimum,
                maximum=maximum,
                reference_name=definition.name_ru if definition is not None else "",
                reference_source=definition.source if definition is not None else "",
                reference_default_min=(definition.default_min if definition is not None else None),
                reference_default_max=(definition.default_max if definition is not None else None),
                matched_catalog_id=(definition.sensor_id if definition is not None else None),
                match_method=(match.matched_by if match is not None else None),
            )
        )
    return tuple(
        sorted(
            entries,
            key=lambda item: (
                _CATEGORY_PRIORITY[item.category],
                _FAMILY_PRIORITY[item.family],
                -item.coverage_percent,
                item.mnemonic.casefold(),
            ),
        )
    )


def recommended_curve_mnemonics(
    dataset: Dataset,
    *,
    maximum: int = 12,
    catalog: SensorCatalog | None = None,
) -> list[str]:
    """Select a broad, finite-data working set instead of only the first category.

    The round-robin pass guarantees that available drilling, mud, petrophysical,
    DEXP and gas families are represented before extra curves from one family are
    added. This produces a more useful first tablet for mixed LAS files.
    """

    if maximum <= 0:
        return []
    entries = [item for item in analyze_dataset_curves(dataset, catalog) if item.valid_count > 0]
    buckets: dict[CurveCategory, list[CurveCatalogEntry]] = {
        category: [item for item in entries if item.category is category]
        for category in CurveCategory
    }
    category_limits = {
        CurveCategory.GAS: 6,
        CurveCategory.DRILLING: 5,
        CurveCategory.MUD: 3,
        CurveCategory.PETROPHYSICS: 4,
        CurveCategory.DEXP: 3,
        CurveCategory.OTHER: 2,
    }
    selected: list[str] = []
    used_by_category = {category: 0 for category in CurveCategory}
    while len(selected) < maximum:
        made_progress = False
        for category in CurveCategory:
            if used_by_category[category] >= category_limits[category]:
                continue
            bucket = buckets[category]
            while bucket and bucket[0].mnemonic in selected:
                bucket.pop(0)
            if not bucket:
                continue
            item = bucket.pop(0)
            selected.append(item.mnemonic)
            used_by_category[category] += 1
            made_progress = True
            if len(selected) >= maximum:
                break
        if not made_progress:
            break
    return selected


def robust_curve_range(
    curve: CurveData, *, logarithmic: bool = False
) -> tuple[float, float] | None:
    values = np.asarray(curve.values, dtype=float)
    finite = values[np.isfinite(values)]
    if logarithmic:
        finite = finite[finite > 0]
    if finite.size == 0:
        return None
    if finite.size < 10:
        minimum = float(np.min(finite))
        maximum = float(np.max(finite))
    else:
        minimum, maximum = (float(value) for value in np.nanpercentile(finite, [1.0, 99.0]))
    if not np.isfinite(minimum) or not np.isfinite(maximum):
        return None
    if minimum == maximum:
        padding = max(abs(minimum) * 0.05, 1.0)
        minimum -= padding
        maximum += padding
    else:
        padding = (maximum - minimum) * 0.04
        minimum -= padding
        maximum += padding
    if logarithmic:
        minimum = max(minimum, float(np.min(finite[finite > 0])))
    return minimum, maximum
