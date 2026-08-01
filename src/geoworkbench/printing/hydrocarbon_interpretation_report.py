from __future__ import annotations

import os
from pathlib import Path
import tempfile

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter

from geoworkbench.domain.models import Dataset
from geoworkbench.printing.hydrocarbon_interpretation_pdf_renderer import (
    render_hydrocarbon_interpretation_report,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    InterpretationReportIdentity,
    default_interpretation_report_identity,
)
from geoworkbench.printing.unicode_support import preflight_texts
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
    hydrocarbon_interpretation_html,
)
from geoworkbench.services.localization import AppLanguage


class HydrocarbonInterpretationPdfError(RuntimeError):
    pass


def export_hydrocarbon_interpretation_pdf(
    report: HydrocarbonInterpretationReport,
    target: str | Path,
    *,
    language: AppLanguage = AppLanguage.RU,
    dataset: Dataset | None = None,
    include_chart: bool = False,
    orientation: QPageLayout.Orientation = QPageLayout.Orientation.Landscape,
    identity: InterpretationReportIdentity | None = None,
    overwrite: bool = False,
) -> Path:
    destination = Path(target)
    if destination.suffix.casefold() != ".pdf":
        destination = destination.with_suffix(".pdf")
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}-",
        suffix=".pdf",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    details = (
        identity
        or default_interpretation_report_identity(report, language)
    ).cleaned()
    try:
        writer = QPdfWriter(str(temporary))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(orientation)
        writer.setPageMargins(
            QMarginsF(14.0, 14.0, 14.0, 14.0),
            QPageLayout.Unit.Millimeter,
        )
        # The renderer works in PostScript points. At 72 DPI one logical
        # painter unit is exactly one point, so fonts and chart geometry share
        # the same physical scale without an additional DPI transform.
        writer.setResolution(72)
        writer.setTitle(details.report_title)
        writer.setSubject(details.report_subtitle)
        writer.setCreator("GEOLOG GASRATIO@Pixler")

        html = hydrocarbon_interpretation_html(report, language)
        if dataset is not None:
            from geoworkbench.services.hydrocarbon_interpretation_gas_html import (
                inject_interval_gas_statistics_html,
            )

            html = inject_interval_gas_statistics_html(
                html,
                report,
                dataset,
                language,
            )
        identity_texts = (
            details.report_title,
            details.report_subtitle,
            details.project_name,
            details.well_name,
            details.field_name,
            details.location,
            details.operator_name,
            details.contractor_name,
            details.rig_name,
            details.dataset_name,
            details.interval,
            details.document_number,
            details.revision,
            details.document_status,
            details.report_date,
            details.prepared_by,
            details.checked_by,
            details.approved_by,
            details.confidentiality,
            details.remarks,
        )
        unicode_report = preflight_texts([html, *identity_texts])
        if not unicode_report.ok:
            raise HydrocarbonInterpretationPdfError(unicode_report.error_message())

        render_hydrocarbon_interpretation_report(
            writer,
            report,
            language=language,
            dataset=dataset,
            include_chart=include_chart,
            identity=details,
        )
        del writer
        if temporary.stat().st_size <= 0:
            raise HydrocarbonInterpretationPdfError("Не удалось сформировать PDF-отчёт")
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, (FileExistsError, HydrocarbonInterpretationPdfError)):
            raise
        raise HydrocarbonInterpretationPdfError(
            f"Не удалось экспортировать PDF: {destination}"
        ) from exc
    return destination
