from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math


class DepthReferenceKind(StrEnum):
    """Supported well depth reference points.

    The selected reference must match the datum documented by the drilling,
    directional-survey or logging record. The enum does not assign an assumed
    height because rig-specific offsets must come from controlled source data.
    """

    RKB = "rkb"
    RT = "rt"
    DF = "df"
    GL = "gl"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class WellDepthPosition:
    ground_elevation_msl_m: float
    datum_height_above_ground_m: float
    datum_elevation_msl_m: float
    measured_depth_m: float
    true_vertical_depth_m: float
    bit_elevation_msl_m: float
    true_vertical_depth_subsea_m: float
    bit_below_ground_m: float
    md_minus_tvd_m: float


def calculate_well_depth_position(
    *,
    ground_elevation_msl_m: float,
    datum_height_above_ground_m: float,
    measured_depth_m: float,
    true_vertical_depth_m: float,
) -> WellDepthPosition:
    """Calculate the datum and bit elevations in one vertical reference system.

    Sign convention:
    - elevations are positive upward from mean sea level;
    - MD and TVD are positive from the selected well datum toward bottomhole;
    - TVDSS is reported positive downward below mean sea level.

    The function intentionally does not derive TVD from MD for a deviated well.
    TVD must come from a directional survey, trajectory model, or an explicit
    vertical-well assumption made by the caller.
    """

    values = (
        ground_elevation_msl_m,
        datum_height_above_ground_m,
        measured_depth_m,
        true_vertical_depth_m,
    )
    if any(not math.isfinite(value) for value in values):
        raise ValueError("All depth-reference values must be finite")
    if measured_depth_m < 0.0:
        raise ValueError("Measured depth cannot be negative")
    if true_vertical_depth_m < 0.0:
        raise ValueError("True vertical depth cannot be negative")
    if true_vertical_depth_m > measured_depth_m + 1e-6:
        raise ValueError("TVD cannot exceed MD when both use the same datum")
    if not -20_000.0 <= ground_elevation_msl_m <= 20_000.0:
        raise ValueError("Ground elevation is outside the supported range")
    if not -500.0 <= datum_height_above_ground_m <= 500.0:
        raise ValueError("Datum height above ground is outside the supported range")

    datum_elevation = ground_elevation_msl_m + datum_height_above_ground_m
    bit_elevation = datum_elevation - true_vertical_depth_m
    tvdss = true_vertical_depth_m - datum_elevation
    bit_below_ground = true_vertical_depth_m - datum_height_above_ground_m

    return WellDepthPosition(
        ground_elevation_msl_m=ground_elevation_msl_m,
        datum_height_above_ground_m=datum_height_above_ground_m,
        datum_elevation_msl_m=datum_elevation,
        measured_depth_m=measured_depth_m,
        true_vertical_depth_m=true_vertical_depth_m,
        bit_elevation_msl_m=bit_elevation,
        true_vertical_depth_subsea_m=tvdss,
        bit_below_ground_m=bit_below_ground,
        md_minus_tvd_m=measured_depth_m - true_vertical_depth_m,
    )
