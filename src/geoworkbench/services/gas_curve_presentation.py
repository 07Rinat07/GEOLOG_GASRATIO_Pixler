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
    display_values: np.ndarray,
    *,
    top: float,
    bottom: float,
    vertical_span: float,
    minimum_gap: float,
    horizontal_span: float = 0.0,
    marker_diameter: float = 0.0,
) -> np.ndarray:
    """Return visible extrema representatives without marker overlap.

    display_values should use the same monotonic x transform as the final
    plot, normally normalized to 0..1. Dense samples are grouped by final
    vertical display position. Local minima and maxima become candidates, then
    the strongest excursions from the visible median are accepted first while
    rejecting candidates that would overlap an already accepted marker.

    The selection is presentation-only: source rows are neither moved,
    interpolated nor connected.
    """

    depth_values = np.asarray(depth, dtype=np.float64)
    x_values = np.asarray(display_values, dtype=np.float64)
    if depth_values.shape != x_values.shape or depth_values.ndim != 1:
        return np.asarray([], dtype=np.int64)

    lower = min(float(top), float(bottom))
    upper = max(float(top), float(bottom))
    finite = (
        np.isfinite(depth_values)
        & np.isfinite(x_values)
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

    projected_y = (depth_values[indices] - lower) / span * display_span
    order = np.argsort(projected_y, kind="stable")
    sorted_indices = indices[order]
    sorted_y = projected_y[order]
    sorted_x_values = x_values[sorted_indices]

    bucket_ids = np.floor(sorted_y / gap).astype(np.int64)
    candidate_rows: set[int] = set()
    for bucket_id in np.unique(bucket_ids):
        positions = np.flatnonzero(bucket_ids == bucket_id)
        if positions.size == 0:
            continue
        rows = sorted_indices[positions]
        local_values = x_values[rows]
        candidate_rows.add(int(rows[int(np.argmin(local_values))]))
        candidate_rows.add(int(rows[int(np.argmax(local_values))]))

    visible_median = float(np.median(sorted_x_values))
    x_span = max(0.0, float(horizontal_span))
    diameter = max(0.0, float(marker_diameter))
    projected_by_row = {
        int(row): float(position)
        for row, position in zip(sorted_indices, sorted_y, strict=True)
    }

    ranked = sorted(
        candidate_rows,
        key=lambda row: (
            -abs(float(x_values[row]) - visible_median),
            projected_by_row[row],
            row,
        ),
    )
    accepted: list[int] = []
    for row in ranked:
        y = projected_by_row[row]
        x = float(np.clip(x_values[row], 0.0, 1.0)) * x_span
        overlaps = False
        for accepted_row in accepted:
            accepted_y = projected_by_row[accepted_row]
            delta_y = abs(y - accepted_y)
            if delta_y >= gap:
                continue
            if x_span <= 0.0 or diameter <= 0.0:
                overlaps = True
                break
            accepted_x = (
                float(np.clip(x_values[accepted_row], 0.0, 1.0)) * x_span
            )
            if abs(x - accepted_x) < diameter:
                overlaps = True
                break
        if not overlaps:
            accepted.append(row)

    accepted.sort(key=lambda row: (projected_by_row[row], row))
    return np.asarray(accepted, dtype=np.int64)

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
