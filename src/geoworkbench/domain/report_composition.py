from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReportPageOrientation(str, Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class ReportPrintOrder(str, Enum):
    FIRST_TO_LAST = "first-to-last"
    LAST_TO_FIRST = "last-to-first"


class ReportTrackVisibility(str, Enum):
    AUTO = "auto"
    SHOW = "show"
    HIDE = "hide"


@dataclass(frozen=True, slots=True)
class InterpretationReportComposition:
    """Persisted renderer-neutral presentation choices for one dataset report."""

    orientation: ReportPageOrientation = ReportPageOrientation.PORTRAIT
    print_order: ReportPrintOrder = ReportPrintOrder.FIRST_TO_LAST
    cuttings: ReportTrackVisibility = ReportTrackVisibility.AUTO
    lba: ReportTrackVisibility = ReportTrackVisibility.AUTO


DEFAULT_INTERPRETATION_REPORT_COMPOSITION = InterpretationReportComposition()


__all__ = [
    "DEFAULT_INTERPRETATION_REPORT_COMPOSITION",
    "InterpretationReportComposition",
    "ReportPageOrientation",
    "ReportPrintOrder",
    "ReportTrackVisibility",
]
