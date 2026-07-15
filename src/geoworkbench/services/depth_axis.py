from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import floor, isfinite

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    new_id,
)


class DepthDirection(StrEnum):
    ASCENDING = "ascending"
    DESCENDING = "descending"
    MIXED = "mixed"
    CONSTANT = "constant"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DepthAxisReport:
    direction: DepthDirection
    start: float | None
    stop: float | None
    nominal_step: float | None
    is_uniform: bool
    duplicate_count: int
    missing_count: int
    gap_count: int


def analyze_depth_axis(values: NDArray[np.float64]) -> DepthAxisReport:
    depth = np.asarray(values, dtype=np.float64)
    if depth.ndim != 1:
        raise ValueError("Шкала глубины должна быть одномерной")
    finite_mask = np.isfinite(depth)
    finite = depth[finite_mask]
    missing_count = int(depth.size - finite.size)
    if finite.size == 0:
        return DepthAxisReport(
            DepthDirection.UNKNOWN, None, None, None, False, 0, missing_count, 0
        )
    if finite.size == 1:
        value = float(finite[0])
        return DepthAxisReport(
            DepthDirection.UNKNOWN, value, value, None, True, 0, missing_count, 0
        )

    differences = np.diff(finite)
    scale = max(1.0, float(np.max(np.abs(finite))))
    absolute_tolerance = np.finfo(np.float64).eps * scale * 16
    zero = np.isclose(differences, 0.0, rtol=0.0, atol=absolute_tolerance)
    positive = differences > absolute_tolerance
    negative = differences < -absolute_tolerance
    duplicate_count = int(np.count_nonzero(zero))

    if np.all(zero):
        direction = DepthDirection.CONSTANT
    elif np.all(positive | zero) and np.any(positive):
        direction = DepthDirection.ASCENDING
    elif np.all(negative | zero) and np.any(negative):
        direction = DepthDirection.DESCENDING
    else:
        direction = DepthDirection.MIXED

    nonzero_steps = np.abs(differences[~zero])
    nominal_step = float(np.median(nonzero_steps)) if nonzero_steps.size else None
    is_uniform = bool(
        nominal_step is not None
        and np.allclose(nonzero_steps, nominal_step, rtol=1e-6, atol=absolute_tolerance)
    )
    gap_count = (
        int(np.count_nonzero(nonzero_steps > nominal_step * 1.5))
        if nominal_step is not None
        else 0
    )
    return DepthAxisReport(
        direction=direction,
        start=float(finite[0]),
        stop=float(finite[-1]),
        nominal_step=nominal_step,
        is_uniform=is_uniform,
        duplicate_count=duplicate_count,
        missing_count=missing_count,
        gap_count=gap_count,
    )


def build_depth_grid(start: float, stop: float, step: float) -> NDArray[np.float64]:
    if not all(isfinite(value) for value in (start, stop, step)):
        raise ValueError("Границы и шаг глубины должны быть конечными")
    if start >= stop:
        raise ValueError("Начальная глубина должна быть меньше конечной")
    if step <= 0:
        raise ValueError("Шаг глубины должен быть положительным")
    count = floor((stop - start) / step + 1e-10) + 1
    return start + np.arange(count, dtype=np.float64) * step


def create_ascending_depth_copy(dataset: Dataset, *, name: str | None = None) -> Dataset:
    report = analyze_depth_axis(dataset.depth)
    if report.direction is not DepthDirection.DESCENDING:
        raise ValueError("Автоматический разворот доступен только для убывающей глубины")
    dataset_id = new_id()
    result = Dataset(
        dataset_id=dataset_id,
        name=name or f"{dataset.name} — глубина по возрастанию",
        kind=DatasetKind.DERIVED,
        depth_domain=dataset.depth_domain,
        depth=np.asarray(dataset.depth[::-1], dtype=np.float64).copy(),
        source_path=dataset.source_path,
        headers=dict(dataset.headers),
        parameters=dict(dataset.parameters),
    )
    for curve in dataset.curves.values():
        metadata = curve.metadata
        new_curve_id = new_id()
        result.curves[new_curve_id] = CurveData(
            CurveMetadata(
                curve_id=new_curve_id,
                original_mnemonic=metadata.original_mnemonic,
                canonical_mnemonic=metadata.canonical_mnemonic,
                unit=metadata.unit,
                description=metadata.description,
                source_dataset_id=dataset_id,
                provenance=f"transform:reverse-depth:{dataset.dataset_id}",
            ),
            np.asarray(curve.values[::-1], dtype=np.float64).copy(),
        )
    result.headers.update(
        {
            "STRT": f"{result.depth[0]:g}",
            "STOP": f"{result.depth[-1]:g}",
            "STEP": f"{report.nominal_step:g}" if report.nominal_step is not None else "",
        }
    )
    return result
