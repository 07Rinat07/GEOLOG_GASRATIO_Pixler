from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from numpy.typing import NDArray


# Ratio/interpretation curves are sampled observations whose visual meaning is
# clearer as discrete points. Ordinary depth-series gas concentrations (TG, C1-C5,
# normalized total/components) remain lines so the operator can read continuous
# depth trends. Relative-gas *_REL curves keep their separate cumulative stacked
# presentation.
_GAS_POINT_EXACT = frozenset(
    {
        "WETNESS",
        "BALANCE",
        "CHARACTER",
        "WH",
        "BH",
        "CH",
        "C1_C2",
        "C1_C3",
        "C2_C3",
        "C1_C2C3",
        "C1_C4",
        "C1_C5",
        "IC4_NC4",
        "IC5_NC5",
        "OPUS3",
        "OPUS4",
        "OPUS_K1_3",
        "OPUS_1_5",
        "OPUS_GM_1",
        "OPUS_GM_2",
        "OPUS_GM_3",
        "OPUS_GM_4",
        "OPUS_GM_5",
    }
)

# Keep ratio markers visually distinct from a line even on dense 0.1–0.2 m
# acquisition grids. Large markers overlap vertically and become "worms".
GAS_SCREEN_POINT_SIZE_PX = 1.8
GAS_PREVIEW_POINT_RADIUS_PX = 0.65
GAS_PRINT_POINT_RADIUS_PT = 0.55

_GAS_SCATTER_VERTICAL_SPACING = 1.25



def gas_scatter_point_budget(vertical_pixels: float) -> int:
    """Return a density budget that keeps neighbouring point markers distinct."""

    span = max(1.0, float(vertical_pixels))
    return max(72, min(2_400, int(span / _GAS_SCATTER_VERTICAL_SPACING)))


def select_gas_scatter_samples(
    axis: NDArray[np.float64],
    values: NDArray[np.float64],
    top: float,
    bottom: float,
    *,
    max_points: int,
    positive_values_only: bool = False,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Select finite gas-ratio observations without inventing line geometry.

    The selector operates on actual finite observations only. When a viewport is
    denser than the marker budget it keeps one factual observation near each
    evenly spaced target depth. This yields a continuous dotted visual trace
    without connecting lines, paired extrema dashes, or marker-overlap worms.
    """

    source_axis = np.asarray(axis, dtype=np.float64)
    source_values = np.asarray(values, dtype=np.float64)
    if source_axis.ndim != 1 or source_values.ndim != 1:
        raise ValueError("Шкала и значения scatter-кривой должны быть одномерными")
    if source_axis.shape != source_values.shape:
        raise ValueError("Шкала и значения scatter-кривой имеют разную длину")
    if max_points < 1:
        raise ValueError("Бюджет scatter-точек должен быть положительным")

    low_depth, high_depth = sorted((float(top), float(bottom)))
    usable = (
        np.isfinite(source_axis)
        & np.isfinite(source_values)
        & (source_axis >= low_depth)
        & (source_axis <= high_depth)
    )
    if positive_values_only:
        usable &= source_values > 0.0

    rows = np.flatnonzero(usable)
    if rows.size == 0:
        return (
            np.asarray([], dtype=np.float64),
            np.asarray([], dtype=np.float64),
        )
    rows = rows[np.argsort(source_axis[rows], kind="stable")]
    if rows.size <= max_points:
        return (
            source_values[rows].astype(np.float64, copy=True),
            source_axis[rows].astype(np.float64, copy=True),
        )

    # Use one factual observation near each evenly spaced target depth.
    # Keeping a single representative per vertical slot produces a dense dotted
    # trace without the paired min/max rows that can rasterize as short dashes.
    sorted_axis = source_axis[rows]
    targets = np.linspace(low_depth, high_depth, max_points, dtype=np.float64)
    insertion = np.searchsorted(sorted_axis, targets, side="left")
    insertion = np.clip(insertion, 0, rows.size - 1)
    previous = np.clip(insertion - 1, 0, rows.size - 1)
    choose_previous = (
        np.abs(sorted_axis[previous] - targets)
        <= np.abs(sorted_axis[insertion] - targets)
    )
    positions = np.where(choose_previous, previous, insertion)
    positions[0] = 0
    positions[-1] = rows.size - 1
    chosen = rows[np.unique(positions)]
    return (
        source_values[chosen].astype(np.float64, copy=True),
        source_axis[chosen].astype(np.float64, copy=True),
    )

def _token(value: object) -> str:
    return str(value or "").strip().upper().replace("-", "_").rsplit(":", 1)[-1]


def is_gas_point_mnemonic(value: object) -> bool:
    """Return whether one curve identifier should be presented as sampled points."""

    token = _token(value)
    if not token or token.endswith("_REL"):
        return False
    return (
        token in _GAS_POINT_EXACT
        or token.startswith("PIXLER_")
        or token.startswith("OPUS_RATIO_")
    )


def uses_gas_point_presentation(identifiers: Iterable[object]) -> bool:
    """Return True when any source/canonical identifier is a ratio/interpretation series."""

    return any(is_gas_point_mnemonic(value) for value in identifiers)


__all__ = [
    "GAS_PREVIEW_POINT_RADIUS_PX",
    "GAS_PRINT_POINT_RADIUS_PT",
    "GAS_SCREEN_POINT_SIZE_PX",
    "gas_scatter_point_budget",
    "is_gas_point_mnemonic",
    "select_gas_scatter_samples",
    "uses_gas_point_presentation",
]
