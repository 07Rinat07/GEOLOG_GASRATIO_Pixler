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
GAS_SCREEN_POINT_SIZE_PX = 1.6
GAS_PREVIEW_POINT_RADIUS_PX = 0.70
GAS_PRINT_POINT_RADIUS_PT = 0.42



def gas_scatter_point_budget(vertical_pixels: float) -> int:
    """Return a density budget that keeps neighbouring point markers distinct."""

    span = max(1.0, float(vertical_pixels))
    # One representative source observation per roughly 1.2 vertical display
    # units gives a dense readable point-trace without marker overlap turning
    # into a solid line. This is intentionally much denser than the old
    # extrema-pair policy, which produced sparse dots and horizontal dash-like
    # pairs on printed Haworth/Pixler tracks.
    return max(72, min(2_400, int(span / 1.2)))


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
    denser than the marker budget it keeps one measured observation per stable
    depth bucket. This produces a dense, continuous-looking point trace without
    inventing connecting lines, horizontal min/max dash pairs, or markers across
    genuine missing-data gaps.
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

    # Keep exactly one *real* observation per depth bucket. The previous
    # min/max pair per bucket placed two markers at almost the same Y position;
    # on PDF/raster output that frequently looked like a short horizontal dash.
    # Selecting the source row nearest the bucket's depth centre preserves the
    # measured trend, preserves true gaps (empty buckets remain empty), and
    # guarantees that dense series cannot form same-row marker pairs.
    bucket_count = max(1, max_points)
    depth_span = max(high_depth - low_depth, np.finfo(float).eps)
    normalized = np.clip(
        (source_axis[rows] - low_depth) / depth_span,
        0.0,
        1.0,
    )
    buckets = np.minimum(
        bucket_count - 1,
        np.floor(normalized * bucket_count).astype(np.int64),
    )
    boundaries = np.flatnonzero(np.diff(buckets)) + 1
    starts = np.concatenate((np.asarray([0], dtype=np.int64), boundaries))
    ends = np.concatenate((boundaries, np.asarray([rows.size], dtype=np.int64)))
    selected: list[int] = []
    for start, end in zip(starts, ends, strict=True):
        bucket_rows = rows[int(start) : int(end)]
        if bucket_rows.size == 1:
            selected.append(int(bucket_rows[0]))
            continue
        bucket_index = int(buckets[int(start)])
        target_depth = low_depth + (bucket_index + 0.5) / bucket_count * depth_span
        local_axis = source_axis[bucket_rows]
        nearest = int(np.argmin(np.abs(local_axis - target_depth)))
        selected.append(int(bucket_rows[nearest]))

    # Preserve the physical viewport endpoints when they are real observations.
    # Replace, rather than append, so the one-marker-per-bucket invariant and
    # max_points cap remain exact.
    if selected:
        selected[0] = int(rows[0])
        selected[-1] = int(rows[-1])
    chosen = np.asarray(selected, dtype=np.int64)
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
