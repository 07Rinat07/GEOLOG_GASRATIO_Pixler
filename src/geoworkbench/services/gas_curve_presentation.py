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

# Scatter markers must remain visually discrete after report/page downscaling.
# Larger historical radii overlapped at normal mud-logging sample cadence and
# produced the "worm/short segment" effect seen in whole-well reports.
GAS_SCREEN_POINT_SIZE_PX = 2.8
GAS_PREVIEW_POINT_RADIUS_PX = 1.15
GAS_PRINT_POINT_RADIUS_PT = 0.60
GAS_PRINT_CAPTURE_POINT_SIZE_PX = 3.2

# Density budgets are expressed in final display units rather than source-row
# count. This keeps dense ratio observations as a readable point cloud.
GAS_SCREEN_POINTS_PER_PX = 0.45
GAS_PREVIEW_POINTS_PER_PX = 0.40
GAS_PRINT_POINTS_PER_PT = 0.50
GAS_MASTERLOG_POINTS_PER_MM = 1.20


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


def gas_scatter_point_budget(
    display_height: float,
    *,
    density: float,
    minimum: int = 16,
    maximum: int = 1_800,
) -> int:
    """Return a display-density-aware point budget for one scatter series."""

    height = max(1.0, float(display_height))
    requested = int(round(height * max(0.05, float(density))))
    return max(int(minimum), min(int(maximum), requested))


def select_gas_scatter_indices(
    depth: FloatArray,
    values: FloatArray,
    *,
    max_points: int,
    valid_mask: NDArray[np.bool_] | None = None,
) -> IntArray:
    """Select finite observations for marker-only rendering.

    Dense point-series are bucketed by depth. Each bucket preserves horizontal
    spread by keeping its minimum and maximum value observations; no synthetic
    samples or connecting geometry are created.
    """

    axis = np.asarray(depth, dtype=np.float64)
    data = np.asarray(values, dtype=np.float64)
    if axis.shape != data.shape:
        raise ValueError("Шкала и gas-ratio значения должны иметь одинаковую форму")
    if max_points < 1:
        raise ValueError("Бюджет scatter-точек должен быть положительным")

    usable = np.isfinite(axis) & np.isfinite(data)
    if valid_mask is not None:
        mask = np.asarray(valid_mask, dtype=bool)
        if mask.shape != axis.shape:
            raise ValueError("Маска scatter-точек должна совпадать со шкалой")
        usable &= mask

    indices = np.flatnonzero(usable)
    if indices.size == 0:
        return indices.astype(np.int64, copy=False)
    indices = indices[np.argsort(axis[indices], kind="stable")]
    if indices.size <= max_points:
        return indices.astype(np.int64, copy=False)

    bucket_count = max(1, min(indices.size, max_points // 2 or 1))
    selected: list[int] = []
    for bucket in np.array_split(indices, bucket_count):
        if bucket.size == 0:
            continue
        if bucket.size == 1:
            selected.append(int(bucket[0]))
            continue
        bucket_values = data[bucket]
        selected.append(int(bucket[int(np.argmin(bucket_values))]))
        selected.append(int(bucket[int(np.argmax(bucket_values))]))

    unique = np.asarray(sorted(set(selected), key=lambda index: axis[index]), dtype=np.int64)
    if unique.size <= max_points:
        return unique

    keep = np.linspace(0, unique.size - 1, max_points, dtype=np.int64)
    return unique[keep]


def _token(value: object) -> str:
    return (
        str(value or "")
        .strip()
        .upper()
        .replace("-", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .rsplit(":", 1)[-1]
    )


def is_gas_point_mnemonic(value: object) -> bool:
    """Return whether one curve identifier should be presented as sampled points."""

    token = _token(value)
    if not token or token.endswith("_REL"):
        return False
    return (
        token in _GAS_POINT_EXACT
        or token.startswith("PIXLER_")
        or token.startswith("HAWORTH_")
        or token.startswith("OPUS_RATIO_")
        or token.endswith("_RATIO")
        or "_RATIO_" in token
    )


def uses_gas_point_presentation(identifiers: Iterable[object]) -> bool:
    """Return True when any source/canonical identifier is a ratio/interpretation series."""

    return any(is_gas_point_mnemonic(value) for value in identifiers)


__all__ = [
    "GAS_MASTERLOG_POINTS_PER_MM",
    "GAS_PREVIEW_POINT_RADIUS_PX",
    "GAS_PREVIEW_POINTS_PER_PX",
    "GAS_PRINT_CAPTURE_POINT_SIZE_PX",
    "GAS_PRINT_POINT_RADIUS_PT",
    "GAS_PRINT_POINTS_PER_PT",
    "GAS_SCREEN_POINT_SIZE_PX",
    "GAS_SCREEN_POINTS_PER_PX",
    "gas_scatter_point_budget",
    "select_gas_scatter_indices",
    "is_gas_point_mnemonic",
    "uses_gas_point_presentation",
]
