from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from geoworkbench.tablet.sampling import select_visible_samples


FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class RelativeGasBand:
    """One cumulative component band for a 0–100% relative-gas track."""

    mnemonic: str
    lower: FloatArray
    upper: FloatArray


@dataclass(frozen=True, slots=True)
class RelativeGasStack:
    """Viewport geometry shared by every component of a stacked gas display."""

    depth: FloatArray
    baseline: FloatArray
    bands: tuple[RelativeGasBand, ...]


def is_relative_gas_mnemonic(mnemonic: str) -> bool:
    return mnemonic.strip().upper().endswith("_REL")


def is_relative_gas_track(mnemonics: list[str] | tuple[str, ...]) -> bool:
    cleaned = [item for item in mnemonics if item.strip()]
    return len(cleaned) >= 2 and all(is_relative_gas_mnemonic(item) for item in cleaned)


def build_relative_gas_stack(
    depth: FloatArray,
    components: dict[str, FloatArray],
    top: float,
    bottom: float,
    *,
    max_points: int,
) -> RelativeGasStack:
    """Build auditable stacked-fill geometry without inventing gas readings.

    Relative curves are expected to be percentages, but the renderer normalizes
    every valid row again so imported/vendor relative curves also close exactly
    at 100%. Missing components inside a valid row contribute a zero-width band.
    A row with no finite positive composition remains ``NaN`` and therefore
    creates a visible gap instead of a false zero or a bridge between intervals.
    """

    axis = np.asarray(depth, dtype=np.float64)
    if not components:
        return RelativeGasStack(
            depth=np.array([], dtype=np.float64),
            baseline=np.array([], dtype=np.float64),
            bands=(),
        )
    names = tuple(components)
    arrays = [np.asarray(components[name], dtype=np.float64) for name in names]
    if any(values.shape != axis.shape for values in arrays):
        raise ValueError("Шкала глубины и относительные газы должны иметь одинаковую форму")
    if max_points < 2:
        raise ValueError("Для отрисовки требуется минимум две точки")

    unique_axis, matrix = _collapse_duplicate_depth(axis, np.vstack(arrays))
    finite_nonnegative = np.isfinite(matrix) & (matrix >= 0.0)
    cleaned = np.where(finite_nonnegative, matrix, np.nan)
    totals = np.nansum(cleaned, axis=0)
    row_valid = np.any(finite_nonnegative, axis=0) & np.isfinite(totals) & (totals > 0.0)

    normalized = np.full(cleaned.shape, np.nan, dtype=np.float64)
    if np.any(row_valid):
        normalized[:, row_valid] = (
            np.where(np.isfinite(cleaned[:, row_valid]), cleaned[:, row_valid], 0.0)
            / totals[row_valid]
            * 100.0
        )

    marker = np.where(row_valid, 100.0, np.nan)
    _, selected_depth = select_visible_samples(
        unique_axis,
        marker,
        top,
        bottom,
        max_points=max_points,
    )
    if selected_depth.size == 0:
        return RelativeGasStack(
            depth=selected_depth,
            baseline=np.array([], dtype=np.float64),
            bands=tuple(
                RelativeGasBand(
                    mnemonic=name,
                    lower=np.array([], dtype=np.float64),
                    upper=np.array([], dtype=np.float64),
                )
                for name in names
            ),
        )

    selected_components = np.full((len(names), selected_depth.size), np.nan, dtype=np.float64)
    positions = np.searchsorted(unique_axis, selected_depth)
    within = positions < unique_axis.size
    matched = np.zeros(selected_depth.shape, dtype=bool)
    matched[within] = np.isclose(
        unique_axis[positions[within]],
        selected_depth[within],
        rtol=0.0,
        atol=np.finfo(np.float64).eps * 32.0,
    )
    if np.any(matched):
        selected_components[:, matched] = normalized[:, positions[matched]]

    selected_valid = np.any(np.isfinite(selected_components), axis=0)
    baseline = np.where(selected_valid, 0.0, np.nan)
    cumulative = baseline.copy()
    bands: list[RelativeGasBand] = []
    for row, name in enumerate(names):
        values = selected_components[row]
        lower = cumulative.copy()
        upper = np.where(selected_valid, cumulative + np.nan_to_num(values, nan=0.0), np.nan)
        bands.append(RelativeGasBand(name, lower, upper))
        cumulative = upper

    # Floating-point input and vendor percentages can leave tiny deviations.
    # The final visible band must terminate exactly at the 100% boundary.
    if bands:
        final = bands[-1]
        bands[-1] = RelativeGasBand(
            final.mnemonic,
            final.lower,
            np.where(selected_valid, 100.0, np.nan),
        )

    return RelativeGasStack(selected_depth, baseline, tuple(bands))


def _collapse_duplicate_depth(axis: FloatArray, matrix: FloatArray) -> tuple[FloatArray, FloatArray]:
    valid_axis = np.isfinite(axis)
    axis = axis[valid_axis]
    matrix = matrix[:, valid_axis]
    if axis.size == 0:
        return axis, matrix
    order = np.argsort(axis, kind="stable")
    axis = axis[order]
    matrix = matrix[:, order]
    unique_axis, starts, counts = np.unique(axis, return_index=True, return_counts=True)
    if unique_axis.size == axis.size:
        return axis, matrix

    collapsed = np.full((matrix.shape[0], unique_axis.size), np.nan, dtype=np.float64)
    for output_index, (start, count) in enumerate(zip(starts, counts, strict=True)):
        group = matrix[:, start : start + count]
        for row in range(group.shape[0]):
            finite = group[row, np.isfinite(group[row])]
            if finite.size:
                collapsed[row, output_index] = float(np.mean(finite))
    return unique_axis.astype(np.float64, copy=False), collapsed
