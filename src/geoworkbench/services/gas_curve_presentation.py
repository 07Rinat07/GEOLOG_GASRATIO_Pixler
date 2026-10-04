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



def gas_scatter_point_budget(vertical_pixels: float) -> int:
    """Return a dense marker budget without collapsing a ratio trace into a worm."""

    span = max(1.0, float(vertical_pixels))
    # One factual marker roughly every 1.35 output units keeps the trace visually
    # continuous at report scale while leaving more than one marker diameter
    # between neighbouring print points.
    return max(64, min(1_600, int(span / 1.35)))


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
    denser than the marker budget it keeps one observation nearest the centre of
    each stable depth bucket. This yields a dense dotted trace without horizontal
    min/max pairs, synthetic line geometry, or vertically overlapping worms.
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

    # Use exactly one factual observation per vertical depth bucket. Earlier
    # min/max pairs placed two distant X values at almost the same Y coordinate;
    # on printed reports those pairs looked like short horizontal dashes. A
    # single sample nearest each bucket centre produces the dense dotted trace
    # expected by mud-logging practice without inventing connecting segments.
    bucket_count = max(1, max_points)
    normalized = np.clip(
        (source_axis[rows] - low_depth)
        / max(high_depth - low_depth, np.finfo(float).eps),
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
    span = max(high_depth - low_depth, np.finfo(float).eps)
    for start, end in zip(starts, ends, strict=True):
        bucket_rows = rows[int(start) : int(end)]
        bucket_id = int(buckets[int(start)])
        centre_depth = low_depth + ((bucket_id + 0.5) / bucket_count) * span
        nearest = int(
            np.argmin(np.abs(source_axis[bucket_rows] - centre_depth))
        )
        selected.append(int(bucket_rows[nearest]))

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
