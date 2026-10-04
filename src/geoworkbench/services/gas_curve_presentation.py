from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


# Gas-ratio channels are continuous depth trends in mudlogging practice.  Keep
# the identifier registry here because renderers need to recognize them, but do
# not turn them into scatter by default.  Explicit scatter rendering remains
# available to callers through select_gas_scatter_samples/point_series.
_GAS_RATIO_EXACT = frozenset(
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

# Explicit scatter mode is retained for specialized overlays and compatibility.
# Default ratio tracks no longer use these marker settings.
GAS_SCREEN_POINT_SIZE_PX = 1.6
GAS_PREVIEW_POINT_RADIUS_PX = 0.55
GAS_PRINT_POINT_RADIUS_PT = 0.55
GAS_SCATTER_VERTICAL_SPACING = 1.35


@dataclass(frozen=True, slots=True)
class GasRatioScale:
    minimum: float
    maximum: float
    logarithmic: bool = False


def gas_ratio_scale(identifiers: Iterable[object]) -> GasRatioScale | None:
    """Return the fixed industry-style display scale for one ratio curve."""

    tokens = {_token(value) for value in identifiers if _token(value)}
    if tokens & {"WH", "WETNESS"}:
        return GasRatioScale(0.0, 100.0)
    if tokens & {"BH", "BALANCE"}:
        return GasRatioScale(0.1, 100.0, True)
    if tokens & {"CH", "CHARACTER"}:
        return GasRatioScale(0.01, 10.0, True)
    if tokens & {"IC4_NC4", "IC5_NC5"}:
        return GasRatioScale(0.01, 100.0, True)
    if any(
        token in {"C1_C2", "C1_C3", "C1_C4", "C1_C5"}
        or token.startswith("PIXLER_C1_")
        for token in tokens
    ):
        return GasRatioScale(0.1, 1000.0, True)
    return None


def gas_ratio_position(value: float, scale: GasRatioScale) -> float | None:
    """Map a factual ratio value onto a stable 0..1 presentation position."""

    numeric = float(value)
    if not np.isfinite(numeric):
        return None
    minimum, maximum = scale.minimum, scale.maximum
    if scale.logarithmic:
        if numeric <= 0.0 or minimum <= 0.0 or maximum <= minimum:
            return None
        numeric = float(np.log10(numeric))
        minimum = float(np.log10(minimum))
        maximum = float(np.log10(maximum))
    if maximum <= minimum:
        return None
    return float(np.clip((numeric - minimum) / (maximum - minimum), 0.0, 1.0))


def gas_ratio_scale_ticks(scale: GasRatioScale) -> tuple[tuple[float, str], ...]:
    """Return compact labelled ticks for a fixed ratio scale."""

    if scale.logarithmic:
        low = float(np.log10(scale.minimum))
        high = float(np.log10(scale.maximum))
        powers = np.arange(int(np.ceil(low)), int(np.floor(high)) + 1)
        logarithmic_values = [10.0 ** float(power) for power in powers]
        if not logarithmic_values or logarithmic_values[0] > scale.minimum:
            logarithmic_values.insert(0, scale.minimum)
        if logarithmic_values[-1] < scale.maximum:
            logarithmic_values.append(scale.maximum)
        return tuple(
            (
                gas_ratio_position(value, scale) or 0.0,
                _format_ratio_tick(value),
            )
            for value in logarithmic_values
        )
    linear_values = (
        scale.minimum,
        (scale.minimum + scale.maximum) / 2.0,
        scale.maximum,
    )
    return tuple(
        (
            gas_ratio_position(value, scale) or 0.0,
            _format_ratio_tick(value),
        )
        for value in linear_values
    )


def _format_ratio_tick(value: float) -> str:
    if value >= 100.0 or abs(value - round(value)) < 1e-9:
        return f"{value:.0f}"
    if value >= 1.0:
        return f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{value:.2g}"


def gas_scatter_point_budget(vertical_pixels: float) -> int:
    """Return a density budget that keeps neighbouring point markers distinct."""

    span = max(1.0, float(vertical_pixels))
    return max(
        64,
        min(2_000, int(span / GAS_SCATTER_VERTICAL_SPACING)),
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


def is_gas_ratio_mnemonic(value: object) -> bool:
    """Return whether one identifier denotes a gas-ratio/interpretation trend."""

    token = _token(value)
    if not token or token.endswith("_REL"):
        return False
    return (
        token in _GAS_RATIO_EXACT
        or token.startswith("PIXLER_")
        or token.startswith("OPUS_RATIO_")
    )


def is_gas_point_mnemonic(value: object) -> bool:
    """Compatibility predicate: gas ratios are no longer point-only by default."""

    return False


def uses_gas_point_presentation(identifiers: Iterable[object]) -> bool:
    """Compatibility boundary for renderers: default gas curves use line geometry."""

    # Retain the API so saved layouts/plugins do not break.  A renderer that
    # genuinely needs discrete observations must request point_series explicitly.
    return False


__all__ = [
    "GAS_PREVIEW_POINT_RADIUS_PX",
    "GasRatioScale",
    "GAS_PRINT_POINT_RADIUS_PT",
    "GAS_SCATTER_VERTICAL_SPACING",
    "GAS_SCREEN_POINT_SIZE_PX",
    "gas_ratio_position",
    "gas_ratio_scale",
    "gas_ratio_scale_ticks",
    "gas_scatter_point_budget",
    "is_gas_point_mnemonic",
    "is_gas_ratio_mnemonic",
    "select_gas_scatter_samples",
    "uses_gas_point_presentation",
]
