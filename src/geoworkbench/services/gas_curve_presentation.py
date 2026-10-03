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
GAS_SCREEN_POINT_SIZE_PX = 2.2
GAS_PREVIEW_POINT_RADIUS_PX = 0.85
GAS_PRINT_POINT_RADIUS_PT = 0.55

# Report charts need a denser, round marker trace than the interactive scatter.
# These values are report-only: tablet/curve-view density remains unchanged.
GAS_REPORT_PREVIEW_POINT_RADIUS_PX = 1.15
GAS_REPORT_PRINT_POINT_RADIUS_PT = 0.72



def gas_scatter_point_budget(vertical_pixels: float) -> int:
    """Return a density budget that keeps neighbouring point markers distinct."""

    span = max(1.0, float(vertical_pixels))
    return max(48, min(1_200, int(span / 2.5)))


def gas_report_scatter_point_budget(vertical_extent: float) -> int:
    """Return a dense report budget without merging markers into line-like worms."""

    span = max(1.0, float(vertical_extent))
    return max(72, min(1_800, int(span / 1.45)))


def select_report_gas_scatter_samples(
    axis: NDArray[np.float64],
    values: NDArray[np.float64],
    top: float,
    bottom: float,
    *,
    max_points: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Select one real observation per visual depth slot for report charts.

    The generic scatter selector keeps both local minima and maxima from one
    depth bucket. That is useful for exploratory views, but in a compact report
    two same-level markers can rasterize as a short dash. Reports instead use a
    denser one-point-per-slot trace: every plotted point is still a source
    observation, vertical density is uniform, and no synthetic line geometry is
    introduced.
    """

    source_axis = np.asarray(axis, dtype=np.float64)
    source_values = np.asarray(values, dtype=np.float64)
    if source_axis.ndim != 1 or source_values.ndim != 1:
        raise ValueError("Шкала и значения report scatter-кривой должны быть одномерными")
    if source_axis.shape != source_values.shape:
        raise ValueError("Шкала и значения report scatter-кривой имеют разную длину")
    if max_points < 1:
        raise ValueError("Бюджет report scatter-точек должен быть положительным")

    low_depth, high_depth = sorted((float(top), float(bottom)))
    usable = (
        np.isfinite(source_axis)
        & np.isfinite(source_values)
        & (source_axis >= low_depth)
        & (source_axis <= high_depth)
    )
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

    span = max(high_depth - low_depth, np.finfo(float).eps)
    normalized = np.clip((source_axis[rows] - low_depth) / span, 0.0, 1.0)
    bucket_count = max_points
    buckets = np.minimum(
        bucket_count - 1,
        np.floor(normalized * bucket_count).astype(np.int64),
    )
    boundaries = np.flatnonzero(np.diff(buckets)) + 1
    starts = np.concatenate((np.asarray([0], dtype=np.int64), boundaries))
    ends = np.concatenate((boundaries, np.asarray([rows.size], dtype=np.int64)))

    selected: list[int] = []
    for position, (start, end) in enumerate(zip(starts, ends, strict=True)):
        bucket_rows = rows[int(start) : int(end)]
        if bucket_rows.size == 0:
            continue
        if position == 0:
            chosen = int(bucket_rows[0])
        elif position == len(starts) - 1:
            chosen = int(bucket_rows[-1])
        else:
            bucket = int(buckets[int(start)])
            center_depth = low_depth + (bucket + 0.5) / bucket_count * span
            local = np.abs(source_axis[bucket_rows] - center_depth)
            chosen = int(bucket_rows[int(np.argmin(local))])
        selected.append(chosen)

    chosen_rows = np.asarray(selected, dtype=np.int64)
    return (
        source_values[chosen_rows].astype(np.float64, copy=True),
        source_axis[chosen_rows].astype(np.float64, copy=True),
    )


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
    denser than the marker budget it keeps local low/high values in stable depth
    buckets, so clusters remain visible without vertically overlapping thousands
    of markers into line-like strokes.
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

    # Two value-extrema per depth bucket preserve local scatter spread while
    # bounding total marker density. The final hard cap keeps the contract exact.
    bucket_count = max(1, max_points // 2)
    normalized = np.clip(
        (source_axis[rows] - low_depth) / max(high_depth - low_depth, np.finfo(float).eps),
        0.0,
        1.0,
    )
    buckets = np.minimum(
        bucket_count - 1,
        np.floor(normalized * bucket_count).astype(np.int64),
    )
    # Buckets are monotonic because rows are depth-sorted. Split once at
    # bucket boundaries instead of rescanning the full viewport for every bucket.
    boundaries = np.flatnonzero(np.diff(buckets)) + 1
    starts = np.concatenate((np.asarray([0], dtype=np.int64), boundaries))
    ends = np.concatenate((boundaries, np.asarray([rows.size], dtype=np.int64)))
    selected: list[int] = []
    for start, end in zip(starts, ends, strict=True):
        bucket_rows = rows[int(start) : int(end)]
        if bucket_rows.size == 1:
            selected.append(int(bucket_rows[0]))
            continue
        bucket_values = source_values[bucket_rows]
        selected.append(int(bucket_rows[int(np.argmin(bucket_values))]))
        selected.append(int(bucket_rows[int(np.argmax(bucket_values))]))

    chosen = np.asarray(sorted(set(selected), key=lambda row: (source_axis[row], row)), dtype=np.int64)
    if chosen.size > max_points:
        keep = np.linspace(0, chosen.size - 1, max_points, dtype=np.int64)
        chosen = chosen[keep]
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
    "GAS_REPORT_PREVIEW_POINT_RADIUS_PX",
    "GAS_REPORT_PRINT_POINT_RADIUS_PT",
    "GAS_SCREEN_POINT_SIZE_PX",
    "gas_report_scatter_point_budget",
    "gas_scatter_point_budget",
    "is_gas_point_mnemonic",
    "select_gas_scatter_samples",
    "select_report_gas_scatter_samples",
    "uses_gas_point_presentation",
]
