"""DataLog / MOL show-method inventory for legacy cuttings observations.

The vendor workbook describes distinct daylight (UV-) and ultraviolet (UV+)
tests. Historical project fields combine some of these measurements; they
cannot be losslessly mapped to specific test conditions. This read-only
adapter therefore reports exactly what was recorded and what is missing.

No oil-phase diagnosis, H2S diagnosis, reserve/pay flag, automatic API gravity,
or conversion of Florovskaya 1-5 into a DataLog quantity is permitted here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Protocol


class ShowMethod(StrEnum):
    ODOUR = "odour"
    STAIN_DAYLIGHT = "stain_uv_minus"
    NATURAL_FLUORESCENCE_UV = "natural_fluorescence_uv_plus"
    SOLVENT_CUT_DAYLIGHT = "solvent_cut_uv_minus"
    SOLVENT_CUT_UV = "solvent_cut_uv_plus"
    RESIDUE_DAYLIGHT = "solvent_residue_uv_minus"
    RESIDUE_UV = "solvent_residue_uv_plus"
    CAPILLARY_EXTRACT_DAYLIGHT = "capillary_extract_daylight"
    CAPILLARY_EXTRACT_UV = "capillary_extract_uv_plus"
    FLOROVSKAYA_CAPILLARY = "florovskaya_capillary"


class LegacyShowGroup(StrEnum):
    ODOUR = "odour"
    STAIN_PARTIAL = "stain_partial"
    NATURAL_FLUORESCENCE_UNSPLIT = "natural_fluorescence_unsplit"
    SOLVENT_CUT_UNSPLIT = "solvent_cut_unsplit"
    RESIDUE_UNSPLIT = "residue_unsplit"
    FLOROVSKAYA_CAPILLARY = "florovskaya_capillary"


@dataclass(frozen=True, slots=True)
class ShowMethodContract:
    method: ShowMethod
    required_dimensions: tuple[str, ...]
    observation_light: str
    source_section: str


# Explicit method inventory transcribed from the user's DataLog/MOL reference
# workbook, not guessed classification thresholds or vendor software internals.
DATALOG_METHODS: tuple[ShowMethodContract, ...] = (
    ShowMethodContract(ShowMethod.ODOUR, ("strength",), "daylight", "Odour"),
    ShowMethodContract(
        ShowMethod.STAIN_DAYLIGHT,
        ("area_percent", "distribution", "colour"),
        "uv_minus", "Stain",
    ),
    ShowMethodContract(
        ShowMethod.NATURAL_FLUORESCENCE_UV,
        ("area_percent", "distribution", "brightness", "colour"),
        "uv_plus", "DIF",
    ),
    ShowMethodContract(
        ShowMethod.SOLVENT_CUT_DAYLIGHT,
        ("speed", "behaviour", "colour"), "uv_minus", "Reagent",
    ),
    ShowMethodContract(
        ShowMethod.SOLVENT_CUT_UV,
        ("speed", "behaviour", "brightness", "colour"), "uv_plus", "Reagent",
    ),
    ShowMethodContract(
        ShowMethod.RESIDUE_DAYLIGHT,
        ("strength", "colour"), "uv_minus", "Residue",
    ),
    ShowMethodContract(
        ShowMethod.RESIDUE_UV,
        ("strength", "colour"), "uv_plus", "Residue",
    ),
    ShowMethodContract(
        ShowMethod.CAPILLARY_EXTRACT_DAYLIGHT,
        ("type", "colour"), "uv_minus", "Workflow diagram: step 6",
    ),
    ShowMethodContract(
        ShowMethod.CAPILLARY_EXTRACT_UV,
        ("type", "colour"), "uv_plus", "Workflow diagram: step 7",
    ),
    ShowMethodContract(
        ShowMethod.FLOROVSKAYA_CAPILLARY,
        ("group_or_type", "pattern_score", "colour"),
        "capillary_extract_uv", "Florovskaya",
    ),
)


@dataclass(frozen=True, slots=True)
class ShowQualityControls:
    """None is unobserved, not a passed QC check."""

    depth_lag_verified: bool | None = None
    mud_background_checked: bool | None = None
    spot_plate_clean_checked: bool | None = None
    solvent_blank_checked: bool | None = None
    potential_mud_additive_contamination: bool | None = None
    coal_or_organic_interference: bool | None = None
    mineral_fluorescence_interference: bool | None = None


@dataclass(frozen=True, slots=True)
class RecordedLegacyShow:
    """Only exact stored fields; does not infer UV conditions from colours."""

    group: LegacyShowGroup
    attributes: tuple[tuple[str, str | int], ...]


@dataclass(frozen=True, slots=True)
class DatalogShowEvidenceAudit:
    sample_id: str
    top_md_m: float
    bottom_md_m: float
    source_method_id: str
    recorded: tuple[RecordedLegacyShow, ...]
    missing_method_details: tuple[str, ...]
    quality_warnings: tuple[str, ...]
    candidate_for_human_review: bool

    @property
    def proves_fluid_phase(self) -> bool:
        return False

    @property
    def proves_hydrocarbon_saturation(self) -> bool:
        return False

    @property
    def has_all_separately_recorded_datalog_methods(self) -> bool:
        # The old LAS / project schema has no UV±-separated full set.
        return False


class _LegacyCuttings(Protocol):
    sample_id: str
    top_depth: float
    bottom_depth: float
    lba_odour: str | None
    lba_stain: str | None
    lba_distribution: str | None
    lba_color: str | None
    lba_cut: str | None
    lba_cut_speed: str | None
    lba_cut_color: str | None
    lba_residue_type: str | None
    lba_residue_color: str | None
    lba_group: int | None
    lba_type_id: str | None
    lba_intensity: int | None


_RECORD_FIELDS: tuple[tuple[LegacyShowGroup, tuple[str, ...]], ...] = (
    (LegacyShowGroup.ODOUR, ("lba_odour",)),
    (LegacyShowGroup.STAIN_PARTIAL, ("lba_stain",)),
    (LegacyShowGroup.NATURAL_FLUORESCENCE_UNSPLIT, ("lba_distribution",)),
    (LegacyShowGroup.SOLVENT_CUT_UNSPLIT, (
        "lba_cut", "lba_cut_speed", "lba_cut_color",
    )),
    (LegacyShowGroup.RESIDUE_UNSPLIT, ("lba_residue_type", "lba_residue_color")),
    (LegacyShowGroup.FLOROVSKAYA_CAPILLARY, (
        "lba_group", "lba_type_id", "lba_intensity", "lba_color",
    )),
)


def audit_legacy_datalog_show(
    sample: _LegacyCuttings,
    *,
    quality: ShowQualityControls = ShowQualityControls(),
) -> DatalogShowEvidenceAudit:
    """Summarize measurement completeness without changing source data."""
    if not isinstance(quality, ShowQualityControls):
        raise TypeError("quality must be ShowQualityControls")
    for name in quality.__dataclass_fields__:
        value = getattr(quality, name)
        if value is not None and not isinstance(value, bool):
            raise ValueError(f"{name} must be bool or unknown")

    sid = getattr(sample, "sample_id", None)
    if not isinstance(sid, str) or not sid.strip():
        raise ValueError("sample_id is required")
    top = _depth(getattr(sample, "top_depth", None), "top_depth")
    bottom = _depth(getattr(sample, "bottom_depth", None), "bottom_depth")
    if top < 0 or bottom <= top:
        raise ValueError("sample depths must satisfy 0 <= top < bottom")

    recorded: list[RecordedLegacyShow] = []
    for group, fields in _RECORD_FIELDS:
        pairs: list[tuple[str, str | int]] = []
        for key in fields:
            raw = getattr(sample, key, None)
            if raw is None:
                continue
            if isinstance(raw, str):
                if raw.strip():
                    pairs.append((key, raw.strip()))
            elif key == "lba_group" and isinstance(raw, int) and not isinstance(raw, bool) and 1 <= raw <= 5:
                pairs.append((key, raw))
            elif key == "lba_intensity" and isinstance(raw, int) and not isinstance(raw, bool) and 1 <= raw <= 5:
                pairs.append((key, raw))
            else:
                raise ValueError(f"{key} contains an invalid historical value")
        if pairs:
            recorded.append(RecordedLegacyShow(group, tuple(pairs)))

    kinds = {entry.group for entry in recorded}
    # The following dimensions simply do not exist as separate measurements
    # in the current CuttingsSample model; this is not a failed analysis.
    gaps = [
        "stain_area_percent_and_colour_not_separated",
        "natural_fluorescence_area_percent_and_brightness_not_separated",
        "natural_fluorescence_colour_not_proven_distinct_from_florovskaya",
        "solvent_cut_uv_minus_and_uv_plus_not_separated",
        "solvent_cut_uv_plus_brightness_not_separated",
        "residue_uv_minus_and_uv_plus_not_separated",
        "capillary_extract_uv_minus_and_uv_plus_not_separated",
        "quantitative_fluorimetry_requires_external_calibration",
    ]
    if LegacyShowGroup.ODOUR not in kinds:
        gaps.append("odour_unrecorded")
    if LegacyShowGroup.STAIN_PARTIAL not in kinds:
        gaps.append("stain_unrecorded")
    if LegacyShowGroup.NATURAL_FLUORESCENCE_UNSPLIT not in kinds:
        gaps.append("natural_fluorescence_distribution_unrecorded")
    if LegacyShowGroup.SOLVENT_CUT_UNSPLIT not in kinds:
        gaps.append("solvent_cut_unrecorded")
    if LegacyShowGroup.RESIDUE_UNSPLIT not in kinds:
        gaps.append("solvent_residue_unrecorded")
    if LegacyShowGroup.FLOROVSKAYA_CAPILLARY not in kinds:
        gaps.append("florovskaya_unrecorded")

    warnings: list[str] = []
    if recorded:
        for name in (
            "depth_lag_verified",
            "mud_background_checked",
            "spot_plate_clean_checked",
        ):
            if getattr(quality, name) is not True:
                warnings.append(f"{name}_unverified")
        if (
            LegacyShowGroup.SOLVENT_CUT_UNSPLIT in kinds
            or LegacyShowGroup.RESIDUE_UNSPLIT in kinds
        ) and quality.solvent_blank_checked is not True:
            warnings.append("solvent_blank_unverified")
    for name in (
        "potential_mud_additive_contamination",
        "coal_or_organic_interference",
        "mineral_fluorescence_interference",
    ):
        if getattr(quality, name) is True:
            warnings.append(name)

    conflicting = any(
        getattr(quality, name) is True
        for name in (
            "potential_mud_additive_contamination",
            "coal_or_organic_interference",
            "mineral_fluorescence_interference",
        )
    )
    return DatalogShowEvidenceAudit(
        sample_id=sid,
        top_md_m=top,
        bottom_md_m=bottom,
        source_method_id="datalog-mol-workbook-v1-show-audit",
        recorded=tuple(recorded),
        missing_method_details=tuple(gaps),
        quality_warnings=tuple(warnings),
        candidate_for_human_review=bool(recorded) and not conflicting,
    )


def _depth(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{field} must be finite MD metres")
    if not isfinite(value):
        raise ValueError(f"{field} must be finite MD metres")
    return float(value)


__all__ = [
    "DATALOG_METHODS",
    "DatalogShowEvidenceAudit",
    "LegacyShowGroup",
    "RecordedLegacyShow",
    "ShowMethod",
    "ShowMethodContract",
    "ShowQualityControls",
    "audit_legacy_datalog_show",
]
