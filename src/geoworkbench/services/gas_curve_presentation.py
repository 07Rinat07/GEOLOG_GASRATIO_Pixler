from __future__ import annotations

from collections.abc import Iterable

import numpy as np


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

# Compact filled markers are deliberately smaller than the former 4-5.6 px
# presentation. Dense 0.1-0.2 m sampling otherwise makes adjacent circles
# overlap vertically and look like short coloured line segments.
GAS_SCREEN_POINT_SIZE_PX = 2.8
GAS_PREVIEW_POINT_RADIUS_PX = 1.25
GAS_PRINT_POINT_RADIUS_PT = 0.9

# Minimum vertical separation between rendered observations in each output
# coordinate system. This is presentation-only thinning: source arrays and
# calculations remain untouched.
GAS_SCREEN_POINT_GAP_PX = 3.2
GAS_PREVIEW_POINT_GAP_PX = 3.0
GAS_PRINT_POINT_GAP_PT = 2.2


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


def gas_scatter_sample_indices(
    depth: np.ndarray,
    values: np.ndarray,
    *,
    top: float,
    bottom: float,
    vertical_span: float,
    minimum_gap: float,
) -> np.ndarray:
    """Return finite visible rows thinned by final vertical display density.

    Gas-ratio curves are factual samples, but plotting every 0.1-0.2 m sample
    with a multi-pixel marker makes neighbouring circles overlap and visually
    form short line segments. Keep the first visible observation and then only
    observations separated by the requested gap in final display coordinates.

    This is a rendering-only selection. No source values are interpolated,
    averaged, moved or connected.
    """

    depth_values = np.asarray(depth, dtype=np.float64)
    curve_values = np.asarray(values, dtype=np.float64)
    if depth_values.shape != curve_values.shape or depth_values.ndim != 1:
        return np.asarray([], dtype=np.int64)

    lower = min(float(top), float(bottom))
    upper = max(float(top), float(bottom))
    finite = (
        np.isfinite(depth_values)
        & np.isfinite(curve_values)
        & (depth_values >= lower)
        & (depth_values <= upper)
    )
    indices = np.flatnonzero(finite)
    if indices.size <= 1:
        return indices.astype(np.int64, copy=False)

    span = upper - lower
    display_span = max(0.0, float(vertical_span))
    gap = max(0.0, float(minimum_gap))
    if span <= 0.0 or display_span <= 0.0 or gap <= 0.0:
        return indices.astype(np.int64, copy=False)

    projected = (depth_values[indices] - lower) / span * display_span
    order = np.argsort(projected, kind="stable")
    sorted_indices = indices[order]
    sorted_projected = projected[order]

    selected: list[int] = []
    last_position: float | None = None
    for row, position in zip(sorted_indices, sorted_projected, strict=True):
        numeric_position = float(position)
        if last_position is None or numeric_position - last_position >= gap:
            selected.append(int(row))
            last_position = numeric_position

    return np.asarray(selected, dtype=np.int64)


def uses_gas_point_presentation(identifiers: Iterable[object]) -> bool:
    """Return True when any source/canonical identifier is a ratio/interpretation series."""

    return any(is_gas_point_mnemonic(value) for value in identifiers)


__all__ = [
    "GAS_PREVIEW_POINT_GAP_PX",
    "GAS_PREVIEW_POINT_RADIUS_PX",
    "GAS_PRINT_POINT_GAP_PT",
    "GAS_PRINT_POINT_RADIUS_PT",
    "GAS_SCREEN_POINT_GAP_PX",
    "GAS_SCREEN_POINT_SIZE_PX",
    "gas_scatter_sample_indices",
    "is_gas_point_mnemonic",
    "uses_gas_point_presentation",
]
