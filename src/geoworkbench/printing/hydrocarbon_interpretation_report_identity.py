from __future__ import annotations

from dataclasses import dataclass, fields, replace
from html import escape

from geoworkbench.domain.report_composition import ReportHeaderFields
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.localization import AppLanguage


_DEFAULT_TEXT = {
    AppLanguage.RU: {
        "title": "Отчёт по интерпретации газового каротажа",
        "subtitle": "Интерпретация данных поверхностного газового каротажа",
        "status": "Рабочий",
        "confidentiality": "Для служебного использования",
    },
    AppLanguage.KK: {
        "title": "Газ каротажын интерпретациялау есебі",
        "subtitle": "Жерүсті газ каротажы деректерін интерпретациялау",
        "status": "Жұмыс нұсқасы",
        "confidentiality": "Қызметтік пайдалану үшін",
    },
    AppLanguage.EN: {
        "title": "Mud-gas interpretation report",
        "subtitle": "Surface data logging interpretation",
        "status": "Working",
        "confidentiality": "For internal use",
    },
}

_OPUS_TEXT = {
    AppLanguage.RU: {
        "title": "Дополнительный отчёт ОПУС по C1-C5",
        "subtitle": "Скрининг газопроявлений по всей глубине; рабочая единица % об.",
    },
    AppLanguage.KK: {
        "title": "C1-C5 бойынша қосымша ОПУС есебі",
        "subtitle": "Бүкіл тереңдік бойынша газ көріністерін скринингтеу; жұмыс бірлігі көлемдік %",
    },
    AppLanguage.EN: {
        "title": "Additional OPUS C1-C5 report",
        "subtitle": "Whole-depth gas-show screening; working unit % by volume",
    },
}


@dataclass(frozen=True, slots=True)
class InterpretationReportIdentity:
    """User-editable document details used only for report presentation."""

    report_title: str
    report_subtitle: str
    project_name: str
    well_name: str
    field_name: str = ""
    location: str = ""
    operator_name: str = ""
    contractor_name: str = ""
    rig_name: str = ""
    dataset_name: str = ""
    interval: str = ""
    document_number: str = ""
    revision: str = "00"
    document_status: str = ""
    report_date: str = ""
    prepared_by: str = ""
    checked_by: str = ""
    approved_by: str = ""
    confidentiality: str = ""
    remarks: str = ""
    summary: str = ""
    conclusion: str = ""

    def cleaned(self) -> InterpretationReportIdentity:
        values = {
            field.name: str(getattr(self, field.name)).strip()
            for field in fields(self)
        }
        return InterpretationReportIdentity(**values)


def report_with_presentation_identity(
    report: HydrocarbonInterpretationReport,
    identity: InterpretationReportIdentity | None,
) -> HydrocarbonInterpretationReport:
    """Return a view of the report with the edited document passport.

    This does not change the geological interpretation or the source report.
    The copy is used only when rendering textual project/well/dataset headings.
    """
    if identity is None:
        return report
    details = identity.cleaned()
    return replace(
        report,
        project_name=details.project_name,
        well_name=details.well_name,
        dataset_name=details.dataset_name,
    )


def report_header_fields_from_identity(
    identity: InterpretationReportIdentity,
    report_profile: str = "standard",
) -> ReportHeaderFields:
    cleaned = identity.cleaned()
    return ReportHeaderFields(
        report_profile=report_profile.strip().casefold() or "standard",
        report_title=cleaned.report_title,
        report_subtitle=cleaned.report_subtitle,
        project_name=cleaned.project_name,
        well_name=cleaned.well_name,
        field_name=cleaned.field_name,
        location=cleaned.location,
        operator_name=cleaned.operator_name,
        contractor_name=cleaned.contractor_name,
        rig_name=cleaned.rig_name,
        dataset_name=cleaned.dataset_name,
        document_number=cleaned.document_number,
        revision=cleaned.revision,
        document_status=cleaned.document_status,
        report_date=cleaned.report_date,
        prepared_by=cleaned.prepared_by,
        checked_by=cleaned.checked_by,
        approved_by=cleaned.approved_by,
        confidentiality=cleaned.confidentiality,
        remarks=cleaned.remarks,
        summary=cleaned.summary,
        conclusion=cleaned.conclusion,
    )


def identity_with_report_header_fields(
    defaults: InterpretationReportIdentity,
    header: ReportHeaderFields | None,
) -> InterpretationReportIdentity:
    if header is None:
        return defaults.cleaned()
    values = {
        field.name: getattr(header, field.name)
        for field in fields(header)
        if field.name != "report_profile"
    }
    return replace(defaults.cleaned(), **values)




_OPTIONAL_SECTION_LABELS = {
    AppLanguage.RU: ("Краткое резюме", "Заключение"),
    AppLanguage.KK: ("Қысқаша түйін", "Қорытынды"),
    AppLanguage.EN: ("Executive summary", "Conclusion"),
}


def report_optional_section_labels(
    language: AppLanguage,
) -> tuple[str, str]:
    return _OPTIONAL_SECTION_LABELS[language]


def inject_report_optional_sections_html(
    html: str,
    identity: InterpretationReportIdentity | None,
    language: AppLanguage,
) -> str:
    if identity is None:
        return html
    summary = identity.summary.strip()
    conclusion = identity.conclusion.strip()
    if not summary and not conclusion:
        return html
    summary_label, conclusion_label = report_optional_section_labels(language)

    def section(label: str, value: str, css_class: str) -> str:
        body = "<br/>".join(escape(line) for line in value.splitlines())
        return (
            f"<section class='{css_class}'><h2>{escape(label)}</h2>"
            f"<p>{body}</p></section>"
        )

    rendered = html
    if summary:
        summary_html = section(summary_label, summary, "report-summary")
        heading_end = rendered.lower().find("</h1>")
        paragraph_end = (
            rendered.lower().find("</p>", heading_end + 5)
            if heading_end >= 0
            else -1
        )
        if paragraph_end >= 0:
            insert_at = paragraph_end + 4
            rendered = rendered[:insert_at] + summary_html + rendered[insert_at:]
        else:
            body_start = rendered.lower().find("<body")
            body_open_end = rendered.find(">", body_start) if body_start >= 0 else -1
            if body_open_end >= 0:
                insert_at = body_open_end + 1
                rendered = rendered[:insert_at] + summary_html + rendered[insert_at:]
            else:
                rendered = summary_html + rendered

    if conclusion:
        conclusion_html = section(conclusion_label, conclusion, "report-conclusion")
        body_end = rendered.lower().rfind("</body>")
        if body_end >= 0:
            rendered = rendered[:body_end] + conclusion_html + rendered[body_end:]
        else:
            rendered += conclusion_html
    return rendered

def default_interpretation_report_identity(
    report: HydrocarbonInterpretationReport,
    language: AppLanguage = AppLanguage.RU,
    *,
    interval: str = "",
) -> InterpretationReportIdentity:
    text = _DEFAULT_TEXT[language]
    presentation = _OPUS_TEXT[language] if report.report_profile == "opus" else text
    return InterpretationReportIdentity(
        report_title=presentation["title"],
        report_subtitle=presentation["subtitle"],
        project_name=report.project_name,
        well_name=report.well_name,
        dataset_name=report.dataset_name,
        interval=interval,
        revision="00",
        document_status=text["status"],
        report_date="",
        confidentiality=text["confidentiality"],
    )


__all__ = [
    "InterpretationReportIdentity",
    "default_interpretation_report_identity",
    "identity_with_report_header_fields",
    "inject_report_optional_sections_html",
    "report_header_fields_from_identity",
    "report_optional_section_labels",
    "report_with_presentation_identity",
]
