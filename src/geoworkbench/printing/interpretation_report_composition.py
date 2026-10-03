from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    GeologyTrackVisibility,
    InterpretationGeologyTrackSettings,
)


class ReportPageOrientation(str, Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class ReportPrintOrder(str, Enum):
    FIRST_TO_LAST = "first-to-last"
    LAST_TO_FIRST = "last-to-first"


@dataclass(frozen=True, slots=True)
class InterpretationReportComposition:
    """Renderer-neutral persisted presentation choices for one dataset report."""

    orientation: ReportPageOrientation = ReportPageOrientation.PORTRAIT
    print_order: ReportPrintOrder = ReportPrintOrder.FIRST_TO_LAST
    cuttings: GeologyTrackVisibility = GeologyTrackVisibility.AUTO
    lba: GeologyTrackVisibility = GeologyTrackVisibility.AUTO

    @property
    def geology_tracks(self) -> InterpretationGeologyTrackSettings:
        return InterpretationGeologyTrackSettings(
            cuttings=self.cuttings,
            lba=self.lba,
        )


DEFAULT_INTERPRETATION_REPORT_COMPOSITION = InterpretationReportComposition()


__all__ = [
    "DEFAULT_INTERPRETATION_REPORT_COMPOSITION",
    "InterpretationReportComposition",
    "ReportPageOrientation",
    "ReportPrintOrder",
]
