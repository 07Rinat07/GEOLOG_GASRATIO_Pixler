from __future__ import annotations

from dataclasses import dataclass, replace
import math
import re

import numpy as np

from geoworkbench.domain.models import Dataset
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
)


_INTERVAL_PATTERN = re.compile(
    r"^\s*([+-]?\d+(?:[.,]\d+)?)\s*(?:–|—|-|\.\.|\bto\b|\bдо\b)\s*"
    r"([+-]?\d+(?:[.,]\d+)?)\s*(?:m|м)?\s*$",
    re.IGNORECASE,
)


class ReportDepthRangeError(ValueError):
    """Raised when a user-supplied report interval cannot be applied safely."""


@dataclass(frozen=True, slots=True)
class ReportDepthRange:
    """Validated inclusive depth range used by report content and charts."""

    top_depth: float
    bottom_depth: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.top_depth) or not math.isfinite(self.bottom_depth):
            raise ReportDepthRangeError("Границы интервала должны быть конечными числами")
        if self.bottom_depth < self.top_depth:
            raise ReportDepthRangeError("Нижняя граница интервала меньше верхней")

    def formatted(self, unit: str = "") -> str:
        suffix = f" {unit.strip()}" if unit.strip() else ""
        return f"{self.top_depth:.2f}–{self.bottom_depth:.2f}{suffix}"


def resolve_report_depth_range(
    interval_text: str,
    dataset: Dataset,
) -> ReportDepthRange:
    """Resolve the presentation interval into a fail-closed dataset depth range."""

    depth = np.asarray(dataset.depth, dtype=np.float64)
    finite = depth[np.isfinite(depth)]
    if depth.ndim != 1 or finite.size < 1:
        raise ReportDepthRangeError("В наборе данных нет конечной оси глубины")

    data_top = float(np.min(finite))
    data_bottom = float(np.max(finite))
    text = str(interval_text).strip()
    if not text:
        return ReportDepthRange(data_top, data_bottom)

    match = _INTERVAL_PATTERN.fullmatch(text)
    if match is None:
        raise ReportDepthRangeError(
            "Интервал должен иметь вид «1980–2016.20 m»"
        )
    try:
        top = float(match.group(1).replace(",", "."))
        bottom = float(match.group(2).replace(",", "."))
    except ValueError as exc:
        raise ReportDepthRangeError("Не удалось прочитать границы интервала") from exc
    if not math.isfinite(top) or not math.isfinite(bottom) or bottom <= top:
        raise ReportDepthRangeError(
            "Верхняя граница интервала должна быть меньше нижней"
        )

    tolerance = max(1.0e-7, abs(data_bottom - data_top) * 1.0e-10)
    if top < data_top - tolerance or bottom > data_bottom + tolerance:
        raise ReportDepthRangeError(
            "Выбранный интервал выходит за диапазон данных "
            f"{data_top:.2f}–{data_bottom:.2f}"
        )
    return ReportDepthRange(
        max(top, data_top),
        min(bottom, data_bottom),
    )


def scope_report_to_depth_range(
    report: HydrocarbonInterpretationReport,
    depth_range: ReportDepthRange,
) -> HydrocarbonInterpretationReport:
    """Keep only report interval records that overlap the requested print range."""

    candidates = tuple(
        item
        for item in report.candidates
        if _overlaps(item.top_depth, item.bottom_depth, depth_range)
    )
    manual_intervals = tuple(
        item
        for item in report.manual_intervals
        if _overlaps(item.top_depth, item.bottom_depth, depth_range)
    )
    opus_gasomer = report.opus_gasomer
    if opus_gasomer is not None:
        opus_gasomer = replace(
            opus_gasomer,
            intervals=tuple(
                item
                for item in opus_gasomer.intervals
                if _overlaps(item.top_depth, item.bottom_depth, depth_range)
            ),
        )
    return replace(
        report,
        candidates=candidates,
        manual_intervals=manual_intervals,
        opus_gasomer=opus_gasomer,
    )


def _overlaps(
    first_depth: float,
    second_depth: float,
    depth_range: ReportDepthRange,
) -> bool:
    low = min(float(first_depth), float(second_depth))
    high = max(float(first_depth), float(second_depth))
    return high >= depth_range.top_depth and low <= depth_range.bottom_depth


__all__ = [
    "ReportDepthRange",
    "ReportDepthRangeError",
    "resolve_report_depth_range",
    "scope_report_to_depth_range",
]
