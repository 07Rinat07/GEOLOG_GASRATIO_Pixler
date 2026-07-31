from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
    InterpretationCalculationIssue,
)


Array = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class DexpGapInterval:
    """One contiguous depth interval where DEXP is unavailable."""

    top: float
    bottom: float
    point_count: int
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DexpCoverageDiagnostic:
    """Coverage and explainable-gap summary for the current DEXP curve."""

    total_points: int
    valid_points: int
    curve_mnemonic: str | None
    curve_source: str
    depth_unit: str
    reason_counts: tuple[tuple[str, int], ...]
    gap_intervals: tuple[DexpGapInterval, ...]
    resolution_messages: tuple[str, ...] = ()

    @property
    def coverage_percent(self) -> float:
        if self.total_points <= 0:
            return 0.0
        return 100.0 * self.valid_points / self.total_points

    @property
    def missing_points(self) -> int:
        return max(0, self.total_points - self.valid_points)


_INPUTS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("rop", ("ROP",), "ft/h"),
    ("rpm", ("RPM",), "1/min"),
    ("wob", ("WOB",), "lbf"),
    ("bit", ("BIT",), "in"),
)


def diagnose_dexp_coverage(
    controller: InterpretationCalculationController,
) -> DexpCoverageDiagnostic:
    """Explain DEXP gaps without interpolating or inventing drilling data."""

    dataset = controller.session.current_dataset
    if dataset is None:
        return DexpCoverageDiagnostic(0, 0, None, "missing", "", (), ())

    depth = np.asarray(dataset.depth, dtype=np.float64)
    finite_depth = np.isfinite(depth)
    total_points = int(np.count_nonzero(finite_depth))
    if total_points == 0:
        return DexpCoverageDiagnostic(
            0,
            0,
            None,
            "missing",
            dataset.active_index.unit or "",
            (),
            (),
        )

    issues: list[InterpretationCalculationIssue] = []
    try:
        resolution = controller.resolver.resolve_dataset(
            dataset,
            targets=("ROP", "RPM", "WOB", "BIT"),
        )
    except (RuntimeError, ValueError) as exc:
        return DexpCoverageDiagnostic(
            total_points,
            0,
            None,
            "missing",
            dataset.active_index.unit or "",
            (("input_resolution", total_points),),
            (
                DexpGapInterval(
                    float(np.nanmin(depth[finite_depth])),
                    float(np.nanmax(depth[finite_depth])),
                    total_points,
                    ("input_resolution",),
                ),
            ),
            (str(exc),),
        )

    arrays: dict[str, Array | None] = {}
    for key, candidates, target_unit in _INPUTS:
        arrays[key] = controller._converted_input(  # noqa: SLF001 - shared calculation path
            resolution,
            candidates,
            target_unit,
            issues,
        )

    reason_masks = _input_reason_masks(finite_depth, arrays)
    formula_valid = finite_depth.copy()
    for values in arrays.values():
        if values is None:
            formula_valid[:] = False
            continue
        formula_valid &= np.isfinite(values) & (values > 0.0)

    wob = arrays["wob"]
    bit = arrays["bit"]
    if wob is not None and bit is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            weight_term = 12.0 * wob / (1_000_000.0 * bit)
        singular = formula_valid & np.isclose(weight_term, 1.0)
        reason_masks["formula_singular"] = singular
        formula_valid &= ~singular

    curve = dataset.curve_by_mnemonic("DEXP")
    if curve is None:
        valid_mask = formula_valid
        curve_mnemonic = None
        curve_source = "potential"
    else:
        values = np.asarray(curve.values, dtype=np.float64)
        valid_mask = finite_depth & np.isfinite(values)
        curve_mnemonic = curve.metadata.original_mnemonic
        curve_source = (
            "calculation"
            if curve.metadata.provenance.startswith("calculation:")
            else "source"
        )
        explained = np.zeros(depth.shape, dtype=bool)
        for mask in reason_masks.values():
            explained |= mask
        reason_masks["output_nonfinite"] = finite_depth & ~valid_mask & ~explained

    missing_mask = finite_depth & ~valid_mask
    reason_counts = tuple(
        sorted(
            (
                (code, int(np.count_nonzero(mask & missing_mask)))
                for code, mask in reason_masks.items()
                if np.any(mask & missing_mask)
            ),
            key=lambda item: (-item[1], item[0]),
        )
    )
    gaps = _gap_intervals(depth, missing_mask, reason_masks)
    messages = tuple(dict.fromkeys(issue.message for issue in issues))
    return DexpCoverageDiagnostic(
        total_points=total_points,
        valid_points=int(np.count_nonzero(valid_mask)),
        curve_mnemonic=curve_mnemonic,
        curve_source=curve_source,
        depth_unit=dataset.active_index.unit or "",
        reason_counts=reason_counts,
        gap_intervals=gaps,
        resolution_messages=messages,
    )


def _input_reason_masks(
    finite_depth: NDArray[np.bool_],
    arrays: dict[str, Array | None],
) -> dict[str, NDArray[np.bool_]]:
    result: dict[str, NDArray[np.bool_]] = {}
    for key, values in arrays.items():
        if values is None:
            result[f"{key}_missing"] = finite_depth.copy()
            continue
        finite = np.isfinite(values)
        result[f"{key}_missing"] = finite_depth & ~finite
        result[f"{key}_nonpositive"] = finite_depth & finite & (values <= 0.0)
    return result


def _gap_intervals(
    depth: Array,
    missing_mask: NDArray[np.bool_],
    reason_masks: dict[str, NDArray[np.bool_]],
) -> tuple[DexpGapInterval, ...]:
    indices = np.flatnonzero(missing_mask)
    if indices.size == 0:
        return ()
    split_points = np.flatnonzero(np.diff(indices) > 1) + 1
    groups = np.split(indices, split_points)
    result: list[DexpGapInterval] = []
    for group in groups:
        if group.size == 0:
            continue
        reasons = tuple(
            code
            for code, mask in reason_masks.items()
            if np.any(mask[group])
        )
        if not reasons:
            reasons = ("output_nonfinite",)
        result.append(
            DexpGapInterval(
                top=float(depth[int(group[0])]),
                bottom=float(depth[int(group[-1])]),
                point_count=int(group.size),
                reason_codes=reasons,
            )
        )
    return tuple(result)


__all__ = [
    "DexpCoverageDiagnostic",
    "DexpGapInterval",
    "diagnose_dexp_coverage",
]
