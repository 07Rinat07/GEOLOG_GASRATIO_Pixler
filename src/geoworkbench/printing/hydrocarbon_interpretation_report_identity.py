from __future__ import annotations

from dataclasses import dataclass, fields

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

    def cleaned(self) -> InterpretationReportIdentity:
        values = {
            field.name: str(getattr(self, field.name)).strip()
            for field in fields(self)
        }
        return InterpretationReportIdentity(**values)


def default_interpretation_report_identity(
    report: HydrocarbonInterpretationReport,
    language: AppLanguage = AppLanguage.RU,
    *,
    interval: str = "",
) -> InterpretationReportIdentity:
    text = _DEFAULT_TEXT[language]
    return InterpretationReportIdentity(
        report_title=text["title"],
        report_subtitle=text["subtitle"],
        project_name=report.project_name,
        well_name=report.well_name,
        dataset_name=report.dataset_name,
        interval=interval,
        revision="00",
        document_status=text["status"],
        report_date=report.generated_at,
        confidentiality=text["confidentiality"],
    )


__all__ = [
    "InterpretationReportIdentity",
    "default_interpretation_report_identity",
]
