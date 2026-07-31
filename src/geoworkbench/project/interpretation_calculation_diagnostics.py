from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import Dataset
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
    InterpretationCalculationIssue,
)
from geoworkbench.services.drilling_mode import (
    DrillingModeResolution,
    classify_drilling_modes,
    resolve_bit_rpm_curve,
)


Array = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class DexpGapInterval:
    """One contiguous depth interval where DEXP is unavailable."""

    top: float
    bottom: float
    point_count: int
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DexpCoverageDiagnostic:
    """Coverage, drilling modes and explainable gaps for the current DEXP curve."""

    total_points: int
    valid_points: int
    curve_mnemonic: str | None
    curve_source: str
    depth_unit: str
    reason_counts: tuple[tuple[str, int], ...]
    gap_intervals: tuple[DexpGapInterval, ...]
    resolution_messages: tuple[str, ...] = ()
    rotary_points: int = 0
    slide_points: int = 0
    slide_points_with_bit_rpm: int = 0
    slide_points_without_bit_rpm: int = 0
    not_drilling_points: int = 0
    unknown_mode_points: int = 0
    bit_rpm_mnemonic: str | None = None

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
    """Explain DEXP gaps without treating surface RPM as bit RPM during slide."""

    dataset = controller.session.current_dataset
    if dataset is None:
        return DexpCoverageDiagnostic(
            total_points=0,
            valid_points=0,
            curve_mnemonic=None,
            curve_source="missing",
            depth_unit="",
            reason_counts=(),
            gap_intervals=(),
        )

    depth = np.asarray(dataset.depth, dtype=np.float64)
    finite_depth = np.isfinite(depth)
    total_points = int(np.count_nonzero(finite_depth))
    depth_unit = dataset.active_index.unit or ""
    if total_points == 0:
        return DexpCoverageDiagnostic(
            total_points=0,
            valid_points=0,
            curve_mnemonic=None,
            curve_source="missing",
            depth_unit=depth_unit,
            reason_counts=(),
            gap_intervals=(),
        )

    issues: list[InterpretationCalculationIssue] = []
    try:
        resolution = controller.resolver.resolve_dataset(
            dataset,
            targets=("ROP", "RPM", "WOB", "BIT", "FLOW_IN", "FLOW_OUT"),
        )
    except (RuntimeError, ValueError) as exc:
        return _resolution_failure(depth, finite_depth, depth_unit, str(exc))

    arrays: dict[str, Array | None] = {}
    for key, candidates, target_unit in _INPUTS:
        arrays[key] = controller._converted_input(  # noqa: SLF001 - shared calculation path
            resolution,
            candidates,
            target_unit,
            issues,
        )
    flow = controller._converted_input(  # noqa: SLF001 - shared calculation path
        resolution,
        ("FLOW_IN", "FLOW_OUT"),
        "gpm",
        issues,
    )

    reason_masks = _input_reason_masks(finite_depth, arrays)
    modes = _resolve_modes(controller, dataset, arrays, flow, issues)
    formula_valid = _formula_valid_mask(finite_depth, arrays, modes, reason_masks)

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
        depth_unit=depth_unit,
        reason_counts=reason_counts,
        gap_intervals=gaps,
        resolution_messages=messages,
        rotary_points=modes.rotary_points if modes is not None else 0,
        slide_points=modes.slide_points if modes is not None else 0,
        slide_points_with_bit_rpm=(
            modes.slide_points_with_bit_rpm if modes is not None else 0
        ),
        slide_points_without_bit_rpm=(
            modes.slide_points_without_bit_rpm if modes is not None else 0
        ),
        not_drilling_points=(
            int(np.count_nonzero(modes.not_drilling_mask)) if modes is not None else 0
        ),
        unknown_mode_points=(
            int(np.count_nonzero(modes.unknown_mask & finite_depth))
            if modes is not None
            else 0
        ),
        bit_rpm_mnemonic=modes.bit_rpm_mnemonic if modes is not None else None,
    )


def _resolve_modes(
    controller: InterpretationCalculationController,
    dataset: Dataset,
    arrays: dict[str, Array | None],
    flow: Array | None,
    issues: list[InterpretationCalculationIssue],
) -> DrillingModeResolution | None:
    rop = arrays["rop"]
    surface_rpm = arrays["rpm"]
    wob = arrays["wob"]
    if rop is None or surface_rpm is None or wob is None:
        return None

    bit_rpm, bit_rpm_mnemonic = resolve_bit_rpm_curve(
        dataset,
        uom=controller.uom,
    )
    modes = classify_drilling_modes(
        rop,
        surface_rpm,
        wob,
        flow=flow,
        bit_rpm=bit_rpm,
    )
    modes = replace(modes, bit_rpm_mnemonic=bit_rpm_mnemonic)
    low_surface = (
        np.isfinite(rop)
        & (rop > 0.0)
        & np.isfinite(wob)
        & (wob > 0.0)
        & np.isfinite(surface_rpm)
        & (surface_rpm >= 0.0)
        & (surface_rpm <= 5.0)
    )
    if flow is None and np.any(low_surface):
        issues.append(
            InterpretationCalculationIssue(
                "drilling-mode-flow-missing",
                "Низкий поверхностный RPM обнаружен, но FLOW отсутствует: "
                "слайдирование нельзя надёжно отличить от остановки или соединения.",
            )
        )
    return modes


def _formula_valid_mask(
    finite_depth: BoolArray,
    arrays: dict[str, Array | None],
    modes: DrillingModeResolution | None,
    reason_masks: dict[str, BoolArray],
) -> BoolArray:
    formula_valid = finite_depth.copy()
    for key in ("rop", "wob", "bit"):
        values = arrays[key]
        if values is None:
            formula_valid[:] = False
        else:
            formula_valid &= np.isfinite(values) & (values > 0.0)

    if modes is None:
        rpm = arrays["rpm"]
        if rpm is None:
            formula_valid[:] = False
        else:
            formula_valid &= np.isfinite(rpm) & (rpm > 0.0)
    else:
        formula_valid &= np.isfinite(modes.effective_rpm) & (modes.effective_rpm > 0.0)
        reason_masks["slide_bit_rpm_missing"] = modes.slide_missing_bit_rpm_mask
        reason_masks["not_drilling"] = modes.not_drilling_mask
        reason_masks["drilling_mode_unknown"] = modes.unknown_mask & finite_depth
        # A zero surface RPM is expected during slide and must not be reported as
        # the primary defect when the real issue is missing downhole bit RPM.
        reason_masks["rpm_nonpositive"] &= ~modes.slide_mask

    wob = arrays["wob"]
    bit = arrays["bit"]
    if wob is not None and bit is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            weight_term = 12.0 * wob / (1_000_000.0 * bit)
        singular = formula_valid & np.isclose(weight_term, 1.0)
        reason_masks["formula_singular"] = singular
        formula_valid &= ~singular
    return formula_valid


def _input_reason_masks(
    finite_depth: BoolArray,
    arrays: dict[str, Array | None],
) -> dict[str, BoolArray]:
    result: dict[str, BoolArray] = {}
    for key, values in arrays.items():
        if values is None:
            result[f"{key}_missing"] = finite_depth.copy()
            result[f"{key}_nonpositive"] = np.zeros(finite_depth.shape, dtype=bool)
            continue
        finite = np.isfinite(values)
        result[f"{key}_missing"] = finite_depth & ~finite
        result[f"{key}_nonpositive"] = finite_depth & finite & (values <= 0.0)
    return result


def _resolution_failure(
    depth: Array,
    finite_depth: BoolArray,
    depth_unit: str,
    message: str,
) -> DexpCoverageDiagnostic:
    total_points = int(np.count_nonzero(finite_depth))
    return DexpCoverageDiagnostic(
        total_points=total_points,
        valid_points=0,
        curve_mnemonic=None,
        curve_source="missing",
        depth_unit=depth_unit,
        reason_counts=(("input_resolution", total_points),),
        gap_intervals=(
            DexpGapInterval(
                float(np.nanmin(depth[finite_depth])),
                float(np.nanmax(depth[finite_depth])),
                total_points,
                ("input_resolution",),
            ),
        ),
        resolution_messages=(message,),
    )


def _gap_intervals(
    depth: Array,
    missing_mask: BoolArray,
    reason_masks: dict[str, BoolArray],
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
            code for code, mask in reason_masks.items() if np.any(mask[group])
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
