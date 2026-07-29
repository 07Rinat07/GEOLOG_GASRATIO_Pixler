from __future__ import annotations

from dataclasses import dataclass
import math


class DatumCalculationError(ValueError):
    """Raised when an elevation input is incomplete or non-finite."""


@dataclass(frozen=True, slots=True)
class DatumElevations:
    """Absolute elevations of common drilling references in metres.

    ``datum_elevation_m`` is the absolute elevation of the selected vertical
    datum. Every other value is an offset measured upward from that datum.
    Negative offsets are therefore valid for references below the datum.
    """

    datum_elevation_m: float
    ground_level_m: float
    wellhead_m: float
    drill_floor_m: float
    rotary_table_m: float
    kelly_bushing_m: float

    def as_rows(self) -> tuple[tuple[str, float], ...]:
        return (
            ("Datum", self.datum_elevation_m),
            ("GL", self.ground_level_m),
            ("Wellhead", self.wellhead_m),
            ("DF", self.drill_floor_m),
            ("RT", self.rotary_table_m),
            ("KB/RKB", self.kelly_bushing_m),
        )


def calculate_datum_elevations(
    *,
    datum_elevation_m: float,
    gl_offset_m: float = 0.0,
    wellhead_above_gl_m: float = 0.0,
    df_above_gl_m: float = 0.0,
    rt_above_df_m: float = 0.0,
    kb_above_rt_m: float = 0.0,
) -> DatumElevations:
    """Resolve the drilling elevation chain against one vertical datum.

    The calculation follows the explicit chain used on well-site documents:

    * GL = datum + GL offset;
    * wellhead = GL + wellhead height;
    * DF = GL + drill-floor height;
    * RT = DF + rotary-table height;
    * KB/RKB = RT + kelly-bushing height.
    """

    values = (
        datum_elevation_m,
        gl_offset_m,
        wellhead_above_gl_m,
        df_above_gl_m,
        rt_above_df_m,
        kb_above_rt_m,
    )
    if any(not math.isfinite(float(value)) for value in values):
        raise DatumCalculationError("Все отметки должны быть конечными числами")

    datum = float(datum_elevation_m)
    ground = datum + float(gl_offset_m)
    wellhead = ground + float(wellhead_above_gl_m)
    drill_floor = ground + float(df_above_gl_m)
    rotary_table = drill_floor + float(rt_above_df_m)
    kelly_bushing = rotary_table + float(kb_above_rt_m)
    return DatumElevations(
        datum_elevation_m=datum,
        ground_level_m=ground,
        wellhead_m=wellhead,
        drill_floor_m=drill_floor,
        rotary_table_m=rotary_table,
        kelly_bushing_m=kelly_bushing,
    )
