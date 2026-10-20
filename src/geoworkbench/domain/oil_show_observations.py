"""Independent, provenance-aware DataLog oil-show observations.

A capillary-imprint score in historical lba_intensity is not a post-cut
residue, and UV+ and daylight/UV- observations must never overwrite each
other. This model stores observations only; it does not classify fluids.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from math import isfinite
from typing import Any, Mapping


class OilShowMethod(StrEnum):
    ODOUR = "odour"
    VISIBLE_STAIN = "visible_stain"
    DIRECT_FLUORESCENCE_UV = "direct_fluorescence_uv"
    SOLVENT_CUT_DAYLIGHT = "solvent_cut_daylight"
    SOLVENT_CUT_UV = "solvent_cut_uv"
    RESIDUE_DAYLIGHT = "residue_daylight"
    RESIDUE_UV = "residue_uv"
    CAPILLARY_DAYLIGHT = "capillary_daylight"
    CAPILLARY_UV = "capillary_uv"


class OilShowQuality(StrEnum):
    UNCHECKED = "unchecked"
    VERIFIED = "verified"
    SUSPECT = "suspect"


@dataclass(frozen=True, slots=True)
class OilShowObservation:
    """One test in one sample interval; optional values are truly unknown."""

    method: OilShowMethod
    area_percent: float | None = None
    colour: str | None = None
    brightness: str | None = None
    distribution: str | None = None
    reaction_speed: str | None = None
    notes: str | None = None
    quality: OilShowQuality = OilShowQuality.UNCHECKED
    source: str = "operator"

    def __post_init__(self) -> None:
        if not isinstance(self.method, OilShowMethod):
            raise ValueError("Oil-show method must be explicitly identified")
        if not isinstance(self.quality, OilShowQuality):
            raise ValueError("Oil-show QC must be explicitly identified")
        if self.area_percent is not None and (
            isinstance(self.area_percent, bool)
            or not isinstance(self.area_percent, (float, int))
            or not isfinite(self.area_percent)
            or not 0.0 <= self.area_percent <= 100.0
        ):
            raise ValueError("Oil-show area must be in the range 0–100 percent")
        for name, maximum in (
            ("colour", 100), ("brightness", 100),
            ("distribution", 120), ("reaction_speed", 100),
            ("notes", 2_000), ("source", 200),
        ):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, str) or len(value) > maximum
                or (name == "source" and not value.strip())
            ):
                raise ValueError(f"Invalid oil-show field {name}")


_MAX_PER_SAMPLE = len(OilShowMethod)
_OBSERVATION_KEYS = {field.name for field in fields(OilShowObservation)}


def validate_oil_show_observations(value: object) -> list[OilShowObservation]:
    """Fail closed: no duplicates or silent conversion from old LBA fields."""
    if not isinstance(value, (list, tuple)) or len(value) > _MAX_PER_SAMPLE:
        raise ValueError("Oil-show observations must be a bounded list")
    if not all(isinstance(item, OilShowObservation) for item in value):
        raise ValueError("Oil-show list contains invalid observations")
    observations = list(value)
    methods = [item.method for item in observations]
    if len(methods) != len(set(methods)):
        raise ValueError("Only one observation per method is supported")
    return observations


def oil_show_observations_from_list(value: object) -> list[OilShowObservation]:
    """Strict v38 JSON decoder with no implicit inferences or backfilling."""
    if not isinstance(value, list) or len(value) > _MAX_PER_SAMPLE:
        raise ValueError("Invalid oil-show observations list")
    result: list[OilShowObservation] = []
    for raw in value:
        if not isinstance(raw, dict) or set(raw) != _OBSERVATION_KEYS:
            raise ValueError("Invalid oil-show observation schema")
        try:
            method = raw["method"]
            quality = raw["quality"]
            if not isinstance(method, str) or not isinstance(quality, str):
                raise ValueError("Invalid observation method or quality")
            result.append(OilShowObservation(
                method=OilShowMethod(method),
                area_percent=raw["area_percent"],
                colour=raw["colour"],
                brightness=raw["brightness"],
                distribution=raw["distribution"],
                reaction_speed=raw["reaction_speed"],
                notes=raw["notes"],
                quality=OilShowQuality(quality),
                source=raw["source"],
            ))
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Malformed oil-show observation") from error
    return validate_oil_show_observations(result)


__all__ = [
    "OilShowMethod",
    "OilShowObservation",
    "OilShowQuality",
    "oil_show_observations_from_list",
    "validate_oil_show_observations",
]
