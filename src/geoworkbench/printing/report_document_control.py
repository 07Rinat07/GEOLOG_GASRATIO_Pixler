from __future__ import annotations

from dataclasses import dataclass, replace

from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    InterpretationReportIdentity,
    default_interpretation_report_identity,
)
from geoworkbench.printing.hydrocarbon_report_i18n import hydrocarbon_report_labels
from geoworkbench.services.hydrocarbon_interpretation import HydrocarbonInterpretationReport
from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class ReportDocumentControl:
    """One renderer-neutral, localized presentation snapshot; never a generation audit."""

    title: str
    subtitle: str
    control: tuple[tuple[str, str], ...]
    context: tuple[tuple[str, str], ...]
    approvals: tuple[tuple[str, str], ...]
    notes: tuple[str, ...]

    @property
    def available_rows(self) -> tuple[tuple[str, str], ...]:
        return tuple(row for row in (*self.context, *self.control, *self.approvals) if row[1])


def resolved_report_identity(
    report: HydrocarbonInterpretationReport,
    identity: InterpretationReportIdentity | None,
    language: AppLanguage,
) -> InterpretationReportIdentity:
    details = (identity or default_interpretation_report_identity(report, language)).cleaned()
    if report.analysis_depth_interval is not None:
        details = replace(details, interval=report.analysis_depth_interval.formatted(report.depth_unit))
    return details


def report_document_control(
    identity: InterpretationReportIdentity,
    language: AppLanguage,
) -> ReportDocumentControl:
    details = identity.cleaned()
    labels = hydrocarbon_report_labels(language)
    control: tuple[tuple[str, str], ...] = (
        (labels.document, details.document_number),
        (labels.revision, details.revision),
        (labels.document_status, details.document_status),
    )
    # An empty date has no row, label or generated fallback in any adapter.
    if details.report_date:
        control += ((labels.report_date, details.report_date),)
    return ReportDocumentControl(
        title=details.report_title,
        subtitle=details.report_subtitle,
        control=control,
        context=(
            (labels.project, details.project_name),
            (labels.well, details.well_name),
            (labels.field_area, details.field_name),
            (labels.location, details.location),
            (labels.operator_customer, details.operator_name),
            (labels.service_company, details.contractor_name),
            (labels.rig, details.rig_name),
            (labels.dataset, details.dataset_name),
            (labels.report_interval, details.interval),
        ),
        approvals=(
            (labels.prepared_by, details.prepared_by),
            (labels.checked_by, details.checked_by),
            (labels.approved_by, details.approved_by),
        ),
        notes=tuple(value for value in (details.confidentiality, details.remarks) if value),
    )
