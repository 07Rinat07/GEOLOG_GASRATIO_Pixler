from __future__ import annotations

from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.printing.header_fields import resolve_header_field
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import InterpretationReportIdentity
from geoworkbench.printing.report_document_control import ReportDocumentControl, report_document_control
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage


def form_report_document_control(
    session: ProjectSession, template: MasterlogTemplate | None,
    language: AppLanguage, *, title: str, interval: str,
) -> ReportDocumentControl:
    """Resolve form-owned presentation metadata with an authoritative output interval."""
    def value(field: str) -> str:
        return resolve_header_field(session, field, template, language) or ""

    return report_document_control(InterpretationReportIdentity(
        report_title=title, report_subtitle="",
        project_name=session.project.name, well_name=value("well.name"),
        field_name=value("header.field"), operator_name=value("header.customer"),
        contractor_name=value("header.contractor"), rig_name=value("header.rig"),
        dataset_name=value("dataset.name"), interval=interval,
        document_number=value("header.document_number"), revision=value("header.revision"),
        document_status=value("header.status"), report_date=value("header.report_date"),
        prepared_by=value("header.prepared_by"), checked_by=value("header.checked_by"),
        approved_by=value("header.approved_by"), confidentiality=value("header.confidentiality"),
    ), language)
