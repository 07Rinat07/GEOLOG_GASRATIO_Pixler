from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from geoworkbench.domain.report_annotations import ReportAnnotationRecord


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


class ReportLayoutProfile(str, Enum):
    MODERN_OILFIELD = "modern_oilfield"


class ReportChartPanel(str, Enum):
    TOTAL = "total"
    RATIOS = "ratios"
    DRILLING = "drilling"
    OPUS = "opus"


DEFAULT_REPORT_CHART_PANEL_ORDER = (
    ReportChartPanel.TOTAL, ReportChartPanel.OPUS,
    ReportChartPanel.RATIOS, ReportChartPanel.DRILLING,
)


def normalize_report_chart_panels(value: object) -> tuple[ReportChartPanel, ...]:
    """Validate the bounded ordered selection of permitted depth-chart panels."""
    if not isinstance(value, (list, tuple)) or len(value) > len(ReportChartPanel):
        raise ValueError("Invalid report chart panels")
    panels = tuple(ReportChartPanel(item) for item in value)
    if len(set(panels)) != len(panels):
        raise ValueError("Duplicate report chart panels")
    return panels


@dataclass(frozen=True, slots=True)
class ReportChartPanelSettings:
    order: tuple[ReportChartPanel, ...] = DEFAULT_REPORT_CHART_PANEL_ORDER
    hidden: tuple[ReportChartPanel, ...] = ()

    def __post_init__(self) -> None:
        order = normalize_report_chart_panels(self.order)
        hidden = normalize_report_chart_panels(self.hidden)
        if set(order) != set(ReportChartPanel):
            raise ValueError("Report chart panel order must include every permitted panel")
        object.__setattr__(self, "order", order)
        object.__setattr__(self, "hidden", tuple(panel for panel in order if panel in hidden))


DEFAULT_REPORT_CHART_PANELS = ReportChartPanelSettings()


def report_chart_panels_from_mapping(value: object) -> ReportChartPanelSettings:
    if not isinstance(value, dict) or set(value) != {"order", "hidden"}:
        raise ValueError("Invalid report chart panel settings")
    return ReportChartPanelSettings(
        normalize_report_chart_panels(value["order"]),
        normalize_report_chart_panels(value["hidden"]),
    )


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
    summary: str = ""
    conclusion: str = ""


@dataclass(frozen=True, slots=True)
class InterpretationReportComposition:
    """Persisted renderer-neutral presentation choices for one dataset report."""

    composition_id: str = ""
    orientation: ReportPageOrientation = ReportPageOrientation.PORTRAIT
    print_order: ReportPrintOrder = ReportPrintOrder.FIRST_TO_LAST
    cuttings: ReportTrackVisibility = ReportTrackVisibility.AUTO
    lba: ReportTrackVisibility = ReportTrackVisibility.AUTO
    legend_mode: ReportLegendMode = ReportLegendMode.FULL
    layout_profile: ReportLayoutProfile = ReportLayoutProfile.MODERN_OILFIELD
    show_summary: bool = True
    show_conclusion: bool = True
    chart_panels: ReportChartPanelSettings = DEFAULT_REPORT_CHART_PANELS
    annotations: tuple[ReportAnnotationRecord, ...] = ()
    header_ru: ReportHeaderFields | None = None
    header_kk: ReportHeaderFields | None = None
    header_en: ReportHeaderFields | None = None


DEFAULT_INTERPRETATION_REPORT_COMPOSITION = InterpretationReportComposition()


def stable_report_composition_id(dataset_id: str) -> str:
    normalized = dataset_id.strip()
    if not normalized:
        raise ValueError("Dataset ID for report composition cannot be empty")
    return f"rpt-{uuid5(NAMESPACE_URL, 'geolog-report-composition:' + normalized).hex}"


def ensure_report_composition_id(
    composition: InterpretationReportComposition,
    dataset_id: str,
) -> InterpretationReportComposition:
    existing = composition.composition_id.strip()
    if existing:
        return (
            composition
            if existing == composition.composition_id
            else replace(composition, composition_id=existing)
        )
    return replace(
        composition,
        composition_id=stable_report_composition_id(dataset_id),
    )


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
    "DEFAULT_REPORT_CHART_PANELS",
    "ReportChartPanel",
    "ReportChartPanelSettings",
    "report_chart_panels_from_mapping",
    "DEFAULT_INTERPRETATION_REPORT_COMPOSITION",
    "InterpretationReportComposition",
    "ReportHeaderFields",
    "ReportLegendMode",
    "ReportLayoutProfile",
    "ReportPageOrientation",
    "ReportPrintOrder",
    "ReportAnnotationRecord",
    "ReportTrackVisibility",
    "ensure_report_composition_id",
    "report_header_fields",
    "stable_report_composition_id",
    "with_report_header_fields",
]
