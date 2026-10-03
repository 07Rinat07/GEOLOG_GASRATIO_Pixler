from __future__ import annotations

from dataclasses import dataclass, replace
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


class ReportLegendMode(str, Enum):
    FULL = "full"
    COMPACT = "compact"
    HIDE = "hide"


@dataclass(frozen=True, slots=True)
class ReportHeaderFields:
    """Language/profile-specific presentation-only report header values."""

    report_profile: str = "standard"
    report_title: str = ""
    report_subtitle: str = ""
    project_name: str = ""
    well_name: str = ""
    field_name: str = ""
    location: str = ""
    operator_name: str = ""
    contractor_name: str = ""
    rig_name: str = ""
    dataset_name: str = ""
    document_number: str = ""
    revision: str = ""
    document_status: str = ""
    report_date: str = ""
    prepared_by: str = ""
    checked_by: str = ""
    approved_by: str = ""
    confidentiality: str = ""
    remarks: str = ""


@dataclass(frozen=True, slots=True)
class InterpretationReportComposition:
    """Persisted renderer-neutral presentation choices for one dataset report."""

    orientation: ReportPageOrientation = ReportPageOrientation.PORTRAIT
    print_order: ReportPrintOrder = ReportPrintOrder.FIRST_TO_LAST
    cuttings: ReportTrackVisibility = ReportTrackVisibility.AUTO
    lba: ReportTrackVisibility = ReportTrackVisibility.AUTO
    legend_mode: ReportLegendMode = ReportLegendMode.FULL
    header_ru: ReportHeaderFields | None = None
    header_kk: ReportHeaderFields | None = None
    header_en: ReportHeaderFields | None = None


DEFAULT_INTERPRETATION_REPORT_COMPOSITION = InterpretationReportComposition()


def report_header_fields(
    composition: InterpretationReportComposition,
    language: str,
    report_profile: str = "standard",
) -> ReportHeaderFields | None:
    code = language.strip().casefold()
    if code == "kk":
        header = composition.header_kk
    elif code == "en":
        header = composition.header_en
    elif code == "ru":
        header = composition.header_ru
    else:
        raise ValueError(f"Unsupported report header language: {language!r}")
    if header is None:
        return None
    return header if header.report_profile == report_profile.strip().casefold() else None


def with_report_header_fields(
    composition: InterpretationReportComposition,
    language: str,
    header: ReportHeaderFields,
) -> InterpretationReportComposition:
    code = language.strip().casefold()
    if code == "kk":
        return replace(composition, header_kk=header)
    if code == "en":
        return replace(composition, header_en=header)
    if code == "ru":
        return replace(composition, header_ru=header)
    raise ValueError(f"Unsupported report header language: {language!r}")


__all__ = [
    "DEFAULT_INTERPRETATION_REPORT_COMPOSITION",
    "InterpretationReportComposition",
    "ReportHeaderFields",
    "ReportLegendMode",
    "ReportPageOrientation",
    "ReportPrintOrder",
    "ReportTrackVisibility",
    "report_header_fields",
    "with_report_header_fields",
]
