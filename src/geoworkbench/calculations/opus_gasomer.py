from __future__ import annotations

import json
import warnings
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum
from functools import lru_cache
from importlib import resources
from math import isfinite
from typing import Any

import numpy as np
from numpy.typing import NDArray


OPUS_GASOMER_PROFILE_ID = "opus-gasomer-total-gas-workbook"
OPUS_GASOMER_PROFILE_VERSION = "1.1.0"
OPUS_GASOMER_INDICATORS = (
    "OPUS_GM_1",
    "OPUS_GM_2",
    "OPUS_GM_3",
    "OPUS_GM_4",
    "OPUS_GM_5",
)
OPUS_GASOMER_INPUTS = ("C1", "C2", "C3", "C4", "C5", "TOTAL_GAS")
OPUS_GASOMER_SYNCHRONOUS_MODE = "synchronous-rows"
OPUS_GASOMER_LEGACY_MAX_MODE = "legacy-max-selected-interval"

Array = NDArray[np.float64]
StateArray = NDArray[np.uint8]
CodeArray = NDArray[np.uint8]

_ROLLING_BLOCK_ELEMENTS = 1_500_000


class OpusGasomerValueState(IntEnum):
    """Auditable state of one source value or derived indicator."""

    AVAILABLE = 0
    MISSING = 1
    MEASURED_ZERO = 2
    BELOW_LOD = 3
    INVALID = 4


@dataclass(frozen=True, slots=True)
class OpusGasomerRow:
    """One reproducible workbook-style calculation row.

    This scalar contract deliberately precedes the production whole-well kernel.
    LOD states, vectorized row alignment and interval aggregation belong to OPUS-02/03.
    """

    normalized_percent: tuple[float, float, float, float, float]
    indicator_values: tuple[float, float, float, float, float]
    indicator_votes: tuple[int, int, int, int, int]
    class_code: int


@dataclass(frozen=True, slots=True)
class OpusGasomerIndicatorResult:
    values: Array
    class_codes: CodeArray
    states: StateArray

    @property
    def available_mask(self) -> NDArray[np.bool_]:
        return self.states == int(OpusGasomerValueState.AVAILABLE)


@dataclass(frozen=True, slots=True)
class OpusGasomerBatchResult:
    """Synchronous row-wise result; source arrays are never mutated."""

    normalized_percent: dict[str, Array]
    input_states: dict[str, StateArray]
    indicators: dict[str, OpusGasomerIndicatorResult]
    row_votes: CodeArray
    row_class_codes: CodeArray
    valid_vote_counts: CodeArray
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OpusGasomerIntervalResult:
    calculation_mode: str
    requested_top_depth: float
    requested_bottom_depth: float
    sample_top_depth: float
    sample_bottom_depth: float
    total_rows: int
    valid_rows: int
    class_code: int
    support_fraction: float
    class_counts: dict[int, int]
    indicator_available_counts: dict[str, int]
    indicator_median_values: dict[str, float | None]
    indicator_class_codes: dict[str, int]
    indicator_vote_support: dict[str, float]
    indicator_state_counts: dict[str, dict[str, int]]
    indicator_vote_counts: dict[str, dict[int, int]]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OpusGasomerLegacyMaxResult:
    calculation_mode: str
    requested_top_depth: float
    requested_bottom_depth: float
    maximum_allowed_span: float
    selected_rows: int
    maxima: dict[str, float]
    source_indices: dict[str, int | None]
    source_depths: dict[str, float | None]
    synthetic_composition: bool
    batch: OpusGasomerBatchResult
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OpusGasomerDetectorPolicy:
    smoothing_span: float
    background_half_span: float
    peak_exclusion_z: float
    robust_scale_factor: float
    robust_z_threshold: float
    minimum_delta_lod_multiple: float
    minimum_contrast: float
    maximum_candidate_separation: float
    minimum_interval_span: float
    minimum_candidate_samples: int
    low_background_warning_percent: float

    def __post_init__(self) -> None:
        nonnegative = (
            self.smoothing_span,
            self.minimum_interval_span,
        )
        positive = (
            self.background_half_span,
            self.peak_exclusion_z,
            self.robust_scale_factor,
            self.robust_z_threshold,
            self.minimum_delta_lod_multiple,
            self.minimum_contrast,
            self.maximum_candidate_separation,
            self.low_background_warning_percent,
        )
        if any(not isfinite(value) or value < 0.0 for value in nonnegative):
            raise ValueError("Неотрицательные параметры detector должны быть конечными")
        if any(not isfinite(value) or value <= 0.0 for value in positive):
            raise ValueError("Положительные параметры detector должны быть конечными")
        if self.minimum_candidate_samples < 1:
            raise ValueError("minimum_candidate_samples должен быть не меньше 1")


@dataclass(frozen=True, slots=True)
class OpusGasomerDetectedInterval:
    top_depth: float
    bottom_depth: float
    candidate_samples: int
    background_median: float
    peak_total_gas: float
    delta_peak: float
    max_robust_z: float
    max_contrast: float
    low_background_warning: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OpusGasomerDetectionResult:
    total_gas_percent: Array
    input_states: StateArray
    smoothed_total_gas: Array
    local_background: Array
    local_robust_scale: Array
    delta_total_gas: Array
    robust_z: Array
    contrast: Array
    raw_candidate_mask: NDArray[np.bool_]
    candidate_mask: NDArray[np.bool_]
    intervals: tuple[OpusGasomerDetectedInterval, ...]
    warnings: tuple[str, ...]


def load_opus_gasomer_detector_policy() -> OpusGasomerDetectorPolicy:
    payload = load_opus_gasomer_profile()["detector"]
    return OpusGasomerDetectorPolicy(
        smoothing_span=float(payload["smoothing_span"]),
        background_half_span=float(payload["background_half_span"]),
        peak_exclusion_z=float(payload["peak_exclusion_z"]),
        robust_scale_factor=float(payload["robust_scale_factor"]),
        robust_z_threshold=float(payload["robust_z_threshold"]),
        minimum_delta_lod_multiple=float(payload["minimum_delta_lod_multiple"]),
        minimum_contrast=float(payload["minimum_contrast"]),
        maximum_candidate_separation=float(payload["maximum_candidate_separation"]),
        minimum_interval_span=float(payload["minimum_interval_span"]),
        minimum_candidate_samples=int(payload["minimum_candidate_samples"]),
        low_background_warning_percent=float(payload["low_background_warning_percent"]),
    )


@lru_cache(maxsize=1)
def load_opus_gasomer_profile() -> dict[str, Any]:
    source = resources.files("geoworkbench").joinpath(
        "resources", "opus_gasomer_profile_v1.json"
    )
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema") != "geoworkbench.opus-gasomer-profile/v1":
        raise ValueError("Неподдерживаемая схема профиля ОПУС Газомер")
    if payload.get("profile_id") != OPUS_GASOMER_PROFILE_ID:
        raise ValueError("Неверный идентификатор профиля ОПУС Газомер")
    if payload.get("profile_version") != OPUS_GASOMER_PROFILE_VERSION:
        raise ValueError("Неподдерживаемая версия профиля ОПУС Газомер")
    return payload


def calculate_opus_gasomer_row(
    c1: float,
    c2: float,
    c3: float,
    c4: float,
    c5: float,
    total_gas: float,
) -> OpusGasomerRow:
    """Reproduce the five formulas for one positive, synchronous source row."""

    components = tuple(float(value) for value in (c1, c2, c3, c4, c5))
    total = float(total_gas)
    if not isfinite(total) or total <= 0.0:
        raise ValueError("TotalGas должен быть конечным положительным числом")
    if any(not isfinite(value) or value < 0.0 for value in components):
        raise ValueError("C1-C5 должны быть конечными неотрицательными числами")

    p1, p2, p3, p4, p5 = tuple(100.0 * value / total for value in components)
    if p1 <= 0.0:
        raise ValueError("Для OPUS_GM_5 требуется положительный C1")
    if p2 + p3 <= 0.0:
        raise ValueError("Для OPUS_GM_1 требуется положительная сумма C2+C3")
    if p2 + p3 + p4 <= 0.0:
        raise ValueError("Для OPUS_GM_2 требуется положительная сумма C2+C3+C4")

    values = (
        (p1 * p2) / ((p2 + p3) ** 2),
        (p1 * p2 * p3) / ((p2 + p3 + p4) ** 3),
        (p1 * p2 * p3) / 3.0,
        (p1 * p2 * p3 * p4 * p5) / 5.0,
        ((p2 * p3 * p4 * p5) / p1) * (p2 + p3 + p4 + p5) * 100.0,
    )
    calculated_votes = tuple(
        classify_opus_gasomer_value(name, value)
        for name, value in zip(OPUS_GASOMER_INDICATORS, values, strict=True)
    )
    votes = (
        calculated_votes[0],
        calculated_votes[1],
        calculated_votes[2],
        calculated_votes[3],
        calculated_votes[4],
    )
    profile = load_opus_gasomer_profile()
    consensus = profile["consensus"]
    class_code = unique_opus_gasomer_mode(
        votes,
        minimum_valid=int(consensus["minimum_valid_indicators"]),
        undefined_code=int(consensus["tie_result_class_code"]),
    )
    return OpusGasomerRow(
        normalized_percent=(p1, p2, p3, p4, p5),
        indicator_values=values,
        indicator_votes=votes,
        class_code=class_code,
    )


def classify_opus_gasomer_value(indicator: str, value: float) -> int:
    """Map one finite indicator to the workbook-derived data-driven palette."""

    profile = load_opus_gasomer_profile()
    undefined = int(profile["consensus"]["tie_result_class_code"])
    if not isfinite(value):
        return undefined
    try:
        band = profile["bands"][indicator]
    except KeyError as exc:
        raise KeyError(f"Неизвестный показатель ОПУС Газомер: {indicator}") from exc
    direction = str(band["direction"])
    for rule in band["rules"]:
        boundary = float(rule["boundary"])
        if direction == "upper" and value <= boundary:
            return int(rule["class_code"])
        if direction == "lower" and value >= boundary:
            return int(rule["class_code"])
    if direction not in {"upper", "lower"}:
        raise ValueError(f"Неверное направление палетки {indicator}: {direction}")
    return int(band["fallback_class_code"])


def unique_opus_gasomer_mode(
    votes: tuple[int, ...] | list[int],
    *,
    minimum_valid: int = 3,
    undefined_code: int = 7,
) -> int:
    """Return only a unique mode; ties and insufficient votes stay undefined."""

    valid = [int(code) for code in votes if int(code) != undefined_code]
    if len(valid) < minimum_valid:
        return undefined_code
    counts = Counter(valid)
    highest = max(counts.values())
    winners = [code for code, count in counts.items() if count == highest]
    return winners[0] if len(winners) == 1 else undefined_code


def calculate_opus_gasomer_batch(
    inputs: Mapping[str, Array],
    *,
    units: str | Mapping[str, str] = "%vol",
    lod: Mapping[str, float | None] | None = None,
) -> OpusGasomerBatchResult:
    """Calculate the Gasomer profile for synchronous C1-C5 and TotalGas rows.

    ``lod`` values use the source unit of the matching input. Missing LOD metadata
    is reported but does not invent a detection limit. A measured zero remains a
    separate state even when a positive LOD is configured.
    """

    arrays = _prepare_batch_inputs(inputs)
    scales = _resolve_unit_scales(units)
    converted = {
        name: arrays[name] * scales[name]
        for name in OPUS_GASOMER_INPUTS
    }
    lod_percent, warnings = _prepare_lod(lod, scales)
    input_states = {
        name: _value_states(converted[name], lod_percent[name])
        for name in OPUS_GASOMER_INPUTS
    }

    total = converted["TOTAL_GAS"]
    total_available = input_states["TOTAL_GAS"] == int(
        OpusGasomerValueState.AVAILABLE
    )
    normalized: dict[str, Array] = {}
    for name in OPUS_GASOMER_INPUTS[:5]:
        values = np.full(total.shape, np.nan, dtype=np.float64)
        component_usable = ~np.isin(
            input_states[name],
            (
                int(OpusGasomerValueState.MISSING),
                int(OpusGasomerValueState.INVALID),
            ),
        )
        mask = total_available & component_usable
        np.divide(converted[name] * 100.0, total, out=values, where=mask)
        normalized[name] = values

    p1, p2, p3, p4, p5 = (normalized[name] for name in OPUS_GASOMER_INPUTS[:5])
    required_inputs = {
        "OPUS_GM_1": ("TOTAL_GAS", "C1", "C2", "C3"),
        "OPUS_GM_2": ("TOTAL_GAS", "C1", "C2", "C3", "C4"),
        "OPUS_GM_3": ("TOTAL_GAS", "C1", "C2", "C3"),
        "OPUS_GM_4": OPUS_GASOMER_INPUTS,
        "OPUS_GM_5": OPUS_GASOMER_INPUTS,
    }
    formulas = {
        "OPUS_GM_1": lambda: (p1 * p2) / np.square(p2 + p3),
        "OPUS_GM_2": lambda: (p1 * p2 * p3) / np.power(p2 + p3 + p4, 3),
        "OPUS_GM_3": lambda: (p1 * p2 * p3) / 3.0,
        "OPUS_GM_4": lambda: (p1 * p2 * p3 * p4 * p5) / 5.0,
        "OPUS_GM_5": lambda: (
            ((p2 * p3 * p4 * p5) / p1) * (p2 + p3 + p4 + p5) * 100.0
        ),
    }

    indicators: dict[str, OpusGasomerIndicatorResult] = {}
    undefined_code = int(
        load_opus_gasomer_profile()["consensus"]["tie_result_class_code"]
    )
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        for indicator in OPUS_GASOMER_INDICATORS:
            states = _combined_indicator_states(
                input_states,
                required_inputs[indicator],
            )
            available = states == int(OpusGasomerValueState.AVAILABLE)
            calculated = np.asarray(formulas[indicator](), dtype=np.float64)
            values = np.full(total.shape, np.nan, dtype=np.float64)
            finite = available & np.isfinite(calculated)
            values[finite] = calculated[finite]
            states[available & ~np.isfinite(calculated)] = int(
                OpusGasomerValueState.INVALID
            )
            codes = _classify_opus_gasomer_array(
                indicator,
                values,
                states,
                undefined_code=undefined_code,
            )
            indicators[indicator] = OpusGasomerIndicatorResult(values, codes, states)

    row_votes = np.column_stack(
        [indicators[name].class_codes for name in OPUS_GASOMER_INDICATORS]
    ).astype(np.uint8, copy=False)
    consensus = load_opus_gasomer_profile()["consensus"]
    row_classes, valid_counts = _unique_opus_gasomer_modes(
        row_votes,
        minimum_valid=int(consensus["minimum_valid_indicators"]),
        undefined_code=undefined_code,
    )
    return OpusGasomerBatchResult(
        normalized_percent=normalized,
        input_states=input_states,
        indicators=indicators,
        row_votes=row_votes,
        row_class_codes=row_classes,
        valid_vote_counts=valid_counts,
        warnings=warnings,
    )


def aggregate_opus_gasomer_interval(
    depth: Array,
    batch: OpusGasomerBatchResult,
    *,
    top_depth: float,
    bottom_depth: float,
) -> OpusGasomerIntervalResult:
    """Aggregate only already-synchronous row classes inside one interval."""

    axis, mask = _interval_mask(
        depth,
        batch.row_class_codes.size,
        top_depth=top_depth,
        bottom_depth=bottom_depth,
    )
    selected_depth = axis[mask]
    selected_classes = batch.row_class_codes[mask]
    profile = load_opus_gasomer_profile()
    undefined_code = int(profile["consensus"]["tie_result_class_code"])
    valid = selected_classes != undefined_code
    valid_rows = int(np.count_nonzero(valid))
    class_counts = {
        class_code: int(np.count_nonzero(selected_classes == class_code))
        for class_code in range(1, 7)
    }
    warnings: list[str] = []
    if valid_rows == 0:
        class_code = undefined_code
        support_fraction = 0.0
        warnings.append("No valid synchronous row classes in interval")
    else:
        highest = max(class_counts.values())
        winners = [code for code, count in class_counts.items() if count == highest]
        if len(winners) == 1:
            class_code = winners[0]
            support_fraction = highest / valid_rows
        else:
            class_code = undefined_code
            support_fraction = highest / valid_rows
            warnings.append("Interval row-class support is tied")
    if class_code == 4:
        warnings.append("Class 4 requires independent evidence of water saturation")

    indicator_available_counts: dict[str, int] = {}
    indicator_median_values: dict[str, float | None] = {}
    indicator_class_codes: dict[str, int] = {}
    indicator_vote_support: dict[str, float] = {}
    indicator_state_counts: dict[str, dict[str, int]] = {}
    indicator_vote_counts: dict[str, dict[int, int]] = {}
    for name in OPUS_GASOMER_INDICATORS:
        indicator = batch.indicators[name]
        selected_states = indicator.states[mask]
        selected_votes = indicator.class_codes[mask]
        indicator_available_counts[name] = int(
            np.count_nonzero(
                selected_states == int(OpusGasomerValueState.AVAILABLE)
            )
        )
        selected_values = indicator.values[mask]
        finite_values = selected_values[np.isfinite(selected_values)]
        indicator_median_values[name] = (
            float(np.median(finite_values)) if finite_values.size else None
        )
        indicator_state_counts[name] = {
            state.name.casefold(): int(np.count_nonzero(selected_states == int(state)))
            for state in OpusGasomerValueState
        }
        indicator_vote_counts[name] = {
            code: int(np.count_nonzero(selected_votes == code))
            for code in range(1, 8)
        }
        valid_vote_counts = indicator_vote_counts[name]
        highest = max(valid_vote_counts[code] for code in range(1, 7))
        winners = [
            code for code in range(1, 7) if valid_vote_counts[code] == highest
        ]
        valid_indicator_votes = sum(valid_vote_counts[code] for code in range(1, 7))
        if highest > 0 and len(winners) == 1:
            indicator_class_codes[name] = winners[0]
            indicator_vote_support[name] = highest / valid_indicator_votes
        else:
            indicator_class_codes[name] = undefined_code
            indicator_vote_support[name] = 0.0

    return OpusGasomerIntervalResult(
        calculation_mode=OPUS_GASOMER_SYNCHRONOUS_MODE,
        requested_top_depth=float(top_depth),
        requested_bottom_depth=float(bottom_depth),
        sample_top_depth=float(np.min(selected_depth)),
        sample_bottom_depth=float(np.max(selected_depth)),
        total_rows=int(selected_depth.size),
        valid_rows=valid_rows,
        class_code=class_code,
        support_fraction=float(support_fraction),
        class_counts=class_counts,
        indicator_available_counts=indicator_available_counts,
        indicator_median_values=indicator_median_values,
        indicator_class_codes=indicator_class_codes,
        indicator_vote_support=indicator_vote_support,
        indicator_state_counts=indicator_state_counts,
        indicator_vote_counts=indicator_vote_counts,
        warnings=tuple(warnings),
    )


def calculate_opus_gasomer_legacy_max_interval(
    depth: Array,
    inputs: Mapping[str, Array],
    *,
    top_depth: float,
    bottom_depth: float,
    maximum_span: float,
    units: str | Mapping[str, str] = "%vol",
    lod: Mapping[str, float | None] | None = None,
) -> OpusGasomerLegacyMaxResult:
    """Reproduce workbook MAX only for one explicitly bounded compatibility interval."""

    if not isfinite(maximum_span) or maximum_span <= 0.0:
        raise ValueError("maximum_span должен быть конечным положительным числом")
    requested_span = bottom_depth - top_depth
    tolerance = np.finfo(np.float64).eps * max(
        1.0,
        abs(top_depth),
        abs(bottom_depth),
        abs(maximum_span),
    ) * 8.0
    if requested_span - maximum_span > tolerance:
        raise ValueError(
            "Выбранный legacy MAX интервал шире явно заданного maximum_span"
        )
    arrays = _prepare_batch_inputs(inputs)
    axis, mask = _interval_mask(
        depth,
        next(iter(arrays.values())).size,
        top_depth=top_depth,
        bottom_depth=bottom_depth,
    )
    maxima: dict[str, float] = {}
    source_indices: dict[str, int | None] = {}
    source_depths: dict[str, float | None] = {}
    for name in OPUS_GASOMER_INPUTS:
        values = arrays[name]
        valid = mask & np.isfinite(values) & (values >= 0.0)
        indices = np.flatnonzero(valid)
        if indices.size == 0:
            maxima[name] = float("nan")
            source_indices[name] = None
            source_depths[name] = None
            continue
        source_index = int(indices[int(np.argmax(values[indices]))])
        maxima[name] = float(values[source_index])
        source_indices[name] = source_index
        source_depths[name] = float(axis[source_index])

    batch = calculate_opus_gasomer_batch(
        {name: np.array([value], dtype=np.float64) for name, value in maxima.items()},
        units=units,
        lod=lod,
    )
    finite_source_depths = {
        value for value in source_depths.values() if value is not None
    }
    synthetic = len(finite_source_depths) > 1
    warnings = [
        "Compatibility mode: independent component maxima from one selected interval"
    ]
    if synthetic:
        warnings.append("Legacy MAX combines component maxima from different depths")
    warnings.extend(batch.warnings)
    return OpusGasomerLegacyMaxResult(
        calculation_mode=OPUS_GASOMER_LEGACY_MAX_MODE,
        requested_top_depth=float(top_depth),
        requested_bottom_depth=float(bottom_depth),
        maximum_allowed_span=float(maximum_span),
        selected_rows=int(np.count_nonzero(mask)),
        maxima=maxima,
        source_indices=source_indices,
        source_depths=source_depths,
        synthetic_composition=synthetic,
        batch=batch,
        warnings=tuple(warnings),
    )


def detect_opus_gasomer_intervals(
    depth: Array,
    total_gas: Array,
    *,
    unit: str = "%vol",
    total_gas_lod: float,
    policy: OpusGasomerDetectorPolicy | None = None,
) -> OpusGasomerDetectionResult:
    """Detect gas shows from local TotalGas dynamics without a 0.1% hard gate."""

    resolved_policy = policy or load_opus_gasomer_detector_policy()
    axis = np.asarray(depth, dtype=np.float64)
    source = np.asarray(total_gas, dtype=np.float64)
    if axis.ndim != 1 or source.ndim != 1 or axis.shape != source.shape:
        raise ValueError("Глубина и TotalGas должны быть одномерными массивами одной длины")
    if axis.size < 2 or not np.all(np.isfinite(axis)):
        raise ValueError("Для detector нужна конечная глубинная шкала минимум из двух строк")
    steps = np.diff(axis)
    increasing = bool(np.all(steps >= 0.0) and np.any(steps > 0.0))
    decreasing = bool(np.all(steps <= 0.0) and np.any(steps < 0.0))
    if not increasing and not decreasing:
        raise ValueError("Глубина detector должна быть монотонной")

    scale = _unit_scale_to_percent(unit)
    lod_percent = float(total_gas_lod) * scale
    if not isfinite(lod_percent) or lod_percent <= 0.0:
        raise ValueError("TotalGas LOD должен быть конечным положительным числом")
    values_percent = source * scale
    work_depth = axis[::-1] if decreasing else axis
    work_values = values_percent[::-1] if decreasing else values_percent
    work_states = _value_states(work_values, lod_percent)
    usable = ~np.isin(
        work_states,
        (
            int(OpusGasomerValueState.MISSING),
            int(OpusGasomerValueState.INVALID),
        ),
    )
    smoothed = _rolling_median_by_depth(
        work_depth,
        work_values,
        usable,
        half_span=resolved_policy.smoothing_span / 2.0,
    )
    background, robust_scale = _rolling_robust_background(
        work_depth,
        smoothed,
        np.isfinite(smoothed),
        half_span=resolved_policy.background_half_span,
        lod_floor=lod_percent,
        policy=resolved_policy,
    )
    delta = smoothed - background
    scale_floor = np.maximum(robust_scale, lod_percent)
    background_floor = np.maximum(background, lod_percent)
    robust_z = np.full(work_values.shape, np.nan, dtype=np.float64)
    contrast = np.full(work_values.shape, np.nan, dtype=np.float64)
    finite_metrics = (
        usable
        & np.isfinite(smoothed)
        & np.isfinite(background)
        & np.isfinite(scale_floor)
    )
    np.divide(delta, scale_floor, out=robust_z, where=finite_metrics)
    np.divide(smoothed, background_floor, out=contrast, where=finite_metrics)
    raw_candidates = (
        finite_metrics
        & (delta >= lod_percent * resolved_policy.minimum_delta_lod_multiple)
        & (robust_z >= resolved_policy.robust_z_threshold)
        & (contrast >= resolved_policy.minimum_contrast)
    )
    candidate_mask, intervals = _build_detected_intervals(
        work_depth,
        smoothed,
        background,
        delta,
        robust_z,
        contrast,
        raw_candidates,
        policy=resolved_policy,
    )
    warnings = [
        "Detector parameters are engineering defaults pending field validation"
    ]
    if any(interval.low_background_warning for interval in intervals):
        warnings.append(
            "Local background below "
            f"{resolved_policy.low_background_warning_percent:g} %vol is a confidence "
            "warning, not a hard gate"
        )

    def restore(values: NDArray[Any]) -> NDArray[Any]:
        return values[::-1].copy() if decreasing else values

    return OpusGasomerDetectionResult(
        total_gas_percent=restore(work_values),
        input_states=restore(work_states),
        smoothed_total_gas=restore(smoothed),
        local_background=restore(background),
        local_robust_scale=restore(robust_scale),
        delta_total_gas=restore(delta),
        robust_z=restore(robust_z),
        contrast=restore(contrast),
        raw_candidate_mask=restore(raw_candidates),
        candidate_mask=restore(candidate_mask),
        intervals=intervals,
        warnings=tuple(warnings),
    )


def _rolling_median_by_depth(
    depth: Array,
    values: Array,
    usable: NDArray[np.bool_],
    *,
    half_span: float,
) -> Array:
    radius = _regular_window_radius(depth, half_span)
    if radius is not None:
        return _rolling_nanmedian_regular(values, usable, radius=radius)
    result = np.full(values.shape, np.nan, dtype=np.float64)
    left = 0
    right = 0
    for index, center in enumerate(depth):
        while left < index and center - depth[left] > half_span:
            left += 1
        if right < index:
            right = index
        while right < depth.size and depth[right] - center <= half_span:
            right += 1
        selected = values[left:right][usable[left:right]]
        if selected.size:
            result[index] = float(np.median(selected))
    return result


def _rolling_robust_background(
    depth: Array,
    values: Array,
    usable: NDArray[np.bool_],
    *,
    half_span: float,
    lod_floor: float,
    policy: OpusGasomerDetectorPolicy,
) -> tuple[Array, Array]:
    radius = _regular_window_radius(depth, half_span)
    if radius is not None:
        return _rolling_robust_background_regular(
            values,
            usable,
            radius=radius,
            lod_floor=lod_floor,
            policy=policy,
        )
    background = np.full(values.shape, np.nan, dtype=np.float64)
    robust_scale = np.full(values.shape, np.nan, dtype=np.float64)
    left = 0
    right = 0
    for index, center in enumerate(depth):
        while left < index and center - depth[left] > half_span:
            left += 1
        if right < index:
            right = index
        while right < depth.size and depth[right] - center <= half_span:
            right += 1
        selected = values[left:right][usable[left:right]]
        if not selected.size:
            continue
        initial_median = float(np.median(selected))
        initial_mad = float(np.median(np.abs(selected - initial_median)))
        initial_scale = max(policy.robust_scale_factor * initial_mad, lod_floor)
        retained = selected[
            selected <= initial_median + policy.peak_exclusion_z * initial_scale
        ]
        if not retained.size:
            retained = selected
        median = float(np.median(retained))
        mad = float(np.median(np.abs(retained - median)))
        background[index] = median
        robust_scale[index] = policy.robust_scale_factor * mad
    return background, robust_scale


def _regular_window_radius(depth: Array, half_span: float) -> int | None:
    """Return an exact sample radius only for a strictly regular physical axis."""

    if depth.size < 2:
        return None
    differences = np.diff(depth)
    if not np.all(np.isfinite(differences) & (differences > 0.0)):
        return None
    step = float(np.median(differences))
    tolerance = max(
        step * 1.0e-9,
        np.finfo(np.float64).eps * max(1.0, float(np.max(np.abs(depth)))) * 16.0,
    )
    if np.any(np.abs(differences - step) > tolerance):
        return None
    return max(0, int(np.floor((half_span + tolerance) / step)))


def _rolling_nanmedian_regular(
    values: Array,
    usable: NDArray[np.bool_],
    *,
    radius: int,
) -> Array:
    masked = np.where(usable, values, np.nan)
    if radius == 0:
        return masked
    width = radius * 2 + 1
    padded = np.pad(masked, (radius, radius), constant_values=np.nan)
    windows = np.lib.stride_tricks.sliding_window_view(padded, width)
    result = np.full(values.shape, np.nan, dtype=np.float64)
    block_rows = max(1, _ROLLING_BLOCK_ELEMENTS // width)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="All-NaN slice encountered")
        for start in range(0, values.size, block_rows):
            stop = min(values.size, start + block_rows)
            result[start:stop] = np.nanmedian(windows[start:stop], axis=1)
    return result


def _rolling_robust_background_regular(
    values: Array,
    usable: NDArray[np.bool_],
    *,
    radius: int,
    lod_floor: float,
    policy: OpusGasomerDetectorPolicy,
) -> tuple[Array, Array]:
    masked = np.where(usable, values, np.nan)
    if radius == 0:
        background = masked.copy()
        robust_scale = np.zeros(values.shape, dtype=np.float64)
        robust_scale[~np.isfinite(background)] = np.nan
        return background, robust_scale
    width = radius * 2 + 1
    padded = np.pad(masked, (radius, radius), constant_values=np.nan)
    windows = np.lib.stride_tricks.sliding_window_view(padded, width)
    background = np.full(values.shape, np.nan, dtype=np.float64)
    robust_scale = np.full(values.shape, np.nan, dtype=np.float64)
    block_rows = max(1, _ROLLING_BLOCK_ELEMENTS // width)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="All-NaN slice encountered")
        for start in range(0, values.size, block_rows):
            stop = min(values.size, start + block_rows)
            block = windows[start:stop]
            initial_median = np.nanmedian(block, axis=1)
            initial_mad = np.nanmedian(
                np.abs(block - initial_median[:, np.newaxis]),
                axis=1,
            )
            initial_scale = np.maximum(
                policy.robust_scale_factor * initial_mad,
                lod_floor,
            )
            retained = np.where(
                block
                <= initial_median[:, np.newaxis]
                + policy.peak_exclusion_z * initial_scale[:, np.newaxis],
                block,
                np.nan,
            )
            median = np.nanmedian(retained, axis=1)
            mad = np.nanmedian(
                np.abs(retained - median[:, np.newaxis]),
                axis=1,
            )
            background[start:stop] = median
            robust_scale[start:stop] = policy.robust_scale_factor * mad
    return background, robust_scale


def _build_detected_intervals(
    depth: Array,
    smoothed: Array,
    background: Array,
    delta: Array,
    robust_z: Array,
    contrast: Array,
    raw_candidates: NDArray[np.bool_],
    *,
    policy: OpusGasomerDetectorPolicy,
) -> tuple[NDArray[np.bool_], tuple[OpusGasomerDetectedInterval, ...]]:
    candidate_indices = np.flatnonzero(raw_candidates)
    accepted = np.zeros(raw_candidates.shape, dtype=np.bool_)
    if not candidate_indices.size:
        return accepted, ()
    tolerance = np.finfo(np.float64).eps * max(1.0, float(np.max(np.abs(depth)))) * 8.0
    groups: list[NDArray[np.int64]] = []
    start = 0
    for offset in range(1, candidate_indices.size):
        previous = candidate_indices[offset - 1]
        current = candidate_indices[offset]
        if (
            depth[current] - depth[previous]
            - policy.maximum_candidate_separation
            > tolerance
        ):
            groups.append(candidate_indices[start:offset])
            start = offset
    groups.append(candidate_indices[start:])

    intervals: list[OpusGasomerDetectedInterval] = []
    for indices in groups:
        span = float(depth[indices[-1]] - depth[indices[0]])
        if (
            indices.size < policy.minimum_candidate_samples
            or span + tolerance < policy.minimum_interval_span
        ):
            continue
        accepted[indices] = True
        local_background = float(np.median(background[indices]))
        low_background = local_background < policy.low_background_warning_percent
        interval_warnings = (
            (
                "Local background below "
                f"{policy.low_background_warning_percent:g} %vol; interval retained",
            )
            if low_background
            else ()
        )
        intervals.append(
            OpusGasomerDetectedInterval(
                top_depth=float(depth[indices[0]]),
                bottom_depth=float(depth[indices[-1]]),
                candidate_samples=int(indices.size),
                background_median=local_background,
                peak_total_gas=float(np.max(smoothed[indices])),
                delta_peak=float(np.max(delta[indices])),
                max_robust_z=float(np.max(robust_z[indices])),
                max_contrast=float(np.max(contrast[indices])),
                low_background_warning=low_background,
                warnings=interval_warnings,
            )
        )
    return accepted, tuple(intervals)


def _interval_mask(
    depth: Array,
    expected_size: int,
    *,
    top_depth: float,
    bottom_depth: float,
) -> tuple[Array, NDArray[np.bool_]]:
    axis = np.asarray(depth, dtype=np.float64)
    if axis.ndim != 1 or axis.size != expected_size:
        raise ValueError("Глубина должна быть одномерной и совпадать с расчётными строками")
    if not isfinite(top_depth) or not isfinite(bottom_depth) or top_depth > bottom_depth:
        raise ValueError("Границы интервала должны быть конечными и top <= bottom")
    mask = np.isfinite(axis) & (axis >= top_depth) & (axis <= bottom_depth)
    if not np.any(mask):
        raise ValueError("В выбранном интервале нет глубинных строк")
    return axis, mask


def _prepare_batch_inputs(inputs: Mapping[str, Array]) -> dict[str, Array]:
    normalized = {str(name).strip().upper(): values for name, values in inputs.items()}
    missing = [name for name in OPUS_GASOMER_INPUTS if name not in normalized]
    if missing:
        raise KeyError(f"Отсутствуют входы ОПУС Газомер: {', '.join(missing)}")
    arrays: dict[str, Array] = {}
    shape: tuple[int, ...] | None = None
    for name in OPUS_GASOMER_INPUTS:
        values = np.asarray(normalized[name], dtype=np.float64)
        if values.ndim != 1:
            raise ValueError(f"{name} должен быть одномерным массивом")
        if shape is None:
            shape = values.shape
        elif values.shape != shape:
            raise ValueError("C1-C5 и TotalGas должны иметь одинаковую длину")
        arrays[name] = values
    return arrays


def _resolve_unit_scales(units: str | Mapping[str, str]) -> dict[str, float]:
    if isinstance(units, str):
        return {name: _unit_scale_to_percent(units) for name in OPUS_GASOMER_INPUTS}
    normalized = {str(name).strip().upper(): value for name, value in units.items()}
    missing = [name for name in OPUS_GASOMER_INPUTS if name not in normalized]
    if missing:
        raise KeyError(f"Не заданы единицы ОПУС Газомер: {', '.join(missing)}")
    return {
        name: _unit_scale_to_percent(str(normalized[name]))
        for name in OPUS_GASOMER_INPUTS
    }


def _unit_scale_to_percent(unit: str) -> float:
    normalized = unit.strip().casefold()
    normalized = normalized.replace("об.%", "%").replace("vol.", "vol")
    normalized = "".join(char for char in normalized if char not in " _-")
    if normalized in {
        "%",
        "%abs",
        "%vol",
        "vol%",
        "pct",
        "percent",
        "процент",
        "проценты",
    }:
        return 1.0
    if normalized in {"ppm", "ppmv", "ppmvol"}:
        return 1.0e-4
    raise ValueError(f"Неподдерживаемая единица ОПУС Газомер: {unit!r}")


def _prepare_lod(
    lod: Mapping[str, float | None] | None,
    scales: Mapping[str, float],
) -> tuple[dict[str, float | None], tuple[str, ...]]:
    normalized = (
        {}
        if lod is None
        else {str(name).strip().upper(): value for name, value in lod.items()}
    )
    converted: dict[str, float | None] = {}
    warnings: list[str] = []
    for name in OPUS_GASOMER_INPUTS:
        raw = normalized.get(name)
        if raw is None:
            converted[name] = None
            warnings.append(f"LOD metadata missing: {name}")
            continue
        value = float(raw)
        if not isfinite(value) or value < 0.0:
            raise ValueError(f"LOD {name} должен быть конечным неотрицательным числом")
        converted[name] = value * scales[name]
    return converted, tuple(warnings)


def _value_states(values: Array, lod: float | None) -> StateArray:
    states = np.full(values.shape, int(OpusGasomerValueState.AVAILABLE), dtype=np.uint8)
    states[np.isnan(values)] = int(OpusGasomerValueState.MISSING)
    states[np.isinf(values) | (values < 0.0)] = int(OpusGasomerValueState.INVALID)
    states[values == 0.0] = int(OpusGasomerValueState.MEASURED_ZERO)
    if lod is not None and lod > 0.0:
        states[(values > 0.0) & (values < lod)] = int(
            OpusGasomerValueState.BELOW_LOD
        )
    return states


def _combined_indicator_states(
    input_states: Mapping[str, StateArray],
    required: tuple[str, ...],
) -> StateArray:
    first = input_states[required[0]]
    combined = np.full(first.shape, int(OpusGasomerValueState.AVAILABLE), dtype=np.uint8)
    # A measured zero component is a valid numeric operand in the workbook.
    # It may make a particular division undefined, but it must not suppress the
    # other multiplicative formulas.  A zero TotalGas is different: every p_i
    # normalization divides by it, so all five indicators remain unavailable.
    if "TOTAL_GAS" in required:
        total_zero = input_states["TOTAL_GAS"] == int(
            OpusGasomerValueState.MEASURED_ZERO
        )
        combined[total_zero] = int(OpusGasomerValueState.MEASURED_ZERO)
    priorities = (
        OpusGasomerValueState.BELOW_LOD,
        OpusGasomerValueState.MISSING,
        OpusGasomerValueState.INVALID,
    )
    for state in priorities:
        mask = np.zeros(first.shape, dtype=np.bool_)
        for name in required:
            mask |= input_states[name] == int(state)
        combined[mask] = int(state)
    return combined


def _classify_opus_gasomer_array(
    indicator: str,
    values: Array,
    states: StateArray,
    *,
    undefined_code: int,
) -> CodeArray:
    profile = load_opus_gasomer_profile()
    band = profile["bands"][indicator]
    direction = str(band["direction"])
    codes = np.full(values.shape, undefined_code, dtype=np.uint8)
    available = states == int(OpusGasomerValueState.AVAILABLE)
    unmatched = available.copy()
    for rule in band["rules"]:
        boundary = float(rule["boundary"])
        if direction == "upper":
            selected = unmatched & (values <= boundary)
        elif direction == "lower":
            selected = unmatched & (values >= boundary)
        else:
            raise ValueError(f"Неверное направление палетки {indicator}: {direction}")
        codes[selected] = int(rule["class_code"])
        unmatched[selected] = False
    codes[unmatched] = int(band["fallback_class_code"])
    return codes


def _unique_opus_gasomer_modes(
    votes: CodeArray,
    *,
    minimum_valid: int,
    undefined_code: int,
) -> tuple[CodeArray, CodeArray]:
    if votes.ndim != 2 or votes.shape[1] != len(OPUS_GASOMER_INDICATORS):
        raise ValueError("Матрица голосов ОПУС Газомер должна иметь пять столбцов")
    valid_counts = np.count_nonzero(votes != undefined_code, axis=1).astype(np.uint8)
    counts = np.empty((votes.shape[0], 6), dtype=np.uint8)
    for class_code in range(1, 7):
        counts[:, class_code - 1] = np.count_nonzero(votes == class_code, axis=1)
    highest = np.max(counts, axis=1)
    winner_counts = np.count_nonzero(counts == highest[:, None], axis=1)
    winners = (np.argmax(counts, axis=1) + 1).astype(np.uint8)
    result = np.full(votes.shape[0], undefined_code, dtype=np.uint8)
    unique = (valid_counts >= minimum_valid) & (winner_counts == 1)
    result[unique] = winners[unique]
    return result, valid_counts


__all__ = [
    "OPUS_GASOMER_INDICATORS",
    "OPUS_GASOMER_INPUTS",
    "OPUS_GASOMER_LEGACY_MAX_MODE",
    "OPUS_GASOMER_PROFILE_ID",
    "OPUS_GASOMER_PROFILE_VERSION",
    "OPUS_GASOMER_SYNCHRONOUS_MODE",
    "OpusGasomerBatchResult",
    "OpusGasomerDetectedInterval",
    "OpusGasomerDetectionResult",
    "OpusGasomerDetectorPolicy",
    "OpusGasomerIndicatorResult",
    "OpusGasomerIntervalResult",
    "OpusGasomerLegacyMaxResult",
    "OpusGasomerRow",
    "OpusGasomerValueState",
    "aggregate_opus_gasomer_interval",
    "calculate_opus_gasomer_batch",
    "calculate_opus_gasomer_legacy_max_interval",
    "calculate_opus_gasomer_row",
    "classify_opus_gasomer_value",
    "detect_opus_gasomer_intervals",
    "load_opus_gasomer_detector_policy",
    "load_opus_gasomer_profile",
    "unique_opus_gasomer_mode",
]
