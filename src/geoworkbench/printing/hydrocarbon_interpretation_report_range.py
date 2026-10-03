from __future__ import annotations

from dataclasses import replace
import math
import re

import numpy as np

from geoworkbench.domain.models import Dataset
from geoworkbench.domain.depth_interval import (
    DepthInterval as ReportDepthRange,
    DepthIntervalError as ReportDepthRangeError,
)
from geoworkbench.printing.hydrocarbon_report_i18n import hydrocarbon_report_labels
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
)


_INTERVAL_PATTERN = re.compile(
    r"^\s*([+-]?\d+(?:[.,]\d+)?)\s*(?:–|—|-|\.\.|\bto\b|\bдо\b)\s*"
    r"([+-]?\d+(?:[.,]\d+)?)\s*(?:m|м)?\s*$",
    re.IGNORECASE,
)


def resolve_report_depth_range(
    interval_text: str,
    dataset: Dataset,
    *,
    language: AppLanguage = AppLanguage.RU,
) -> ReportDepthRange:
    """Resolve the presentation interval into a fail-closed dataset depth range."""

    labels = hydrocarbon_report_labels(language)
    depth = np.asarray(dataset.depth, dtype=np.float64)
    finite = depth[np.isfinite(depth)]
    if depth.ndim != 1 or finite.size < 1:
        raise ReportDepthRangeError(labels.range_no_depth_axis)

    data_top = float(np.min(finite))
    data_bottom = float(np.max(finite))
    text = str(interval_text).strip()
    if not text:
        return ReportDepthRange(data_top, data_bottom)

    match = _INTERVAL_PATTERN.fullmatch(text)
    if match is None:
        raise ReportDepthRangeError(labels.range_format_required)
    try:
        top = float(match.group(1).replace(",", "."))
        bottom = float(match.group(2).replace(",", "."))
    except ValueError as exc:
        raise ReportDepthRangeError(labels.range_parse_failed) from exc
    if not math.isfinite(top) or not math.isfinite(bottom) or bottom <= top:
        raise ReportDepthRangeError(labels.range_order_invalid)

    tolerance = max(1.0e-7, abs(data_bottom - data_top) * 1.0e-10)
    if top < data_top - tolerance or bottom > data_bottom + tolerance:
        raise ReportDepthRangeError(
            labels.range_outside_data.format(top=data_top, bottom=data_bottom)
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
