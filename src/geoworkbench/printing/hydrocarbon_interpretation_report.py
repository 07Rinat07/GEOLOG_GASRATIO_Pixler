from __future__ import annotations

import os
from pathlib import Path
import tempfile

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

from geoworkbench.domain.models import Dataset
from geoworkbench.printing.hydrocarbon_interpretation_chart_front import (
    hydrocarbon_interpretation_html_with_front_chart,
)
from geoworkbench.printing.unicode_support import preflight_texts, print_font
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
    try:
        writer = QPdfWriter(str(temporary))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(QPageLayout.Orientation.Landscape)
        writer.setPageMargins(
            QMarginsF(14.0, 14.0, 14.0, 14.0),
            QPageLayout.Unit.Millimeter,
        )
        writer.setResolution(300)
        writer.setTitle("Mud-gas interpretation report")
        writer.setCreator("GEOLOG GASRATIO@Pixler")
        html = (
            hydrocarbon_interpretation_html_with_front_chart(report, dataset, language)
            if include_chart and dataset is not None
            else hydrocarbon_interpretation_html(report, language)
        )
        unicode_report = preflight_texts([html])
        if not unicode_report.ok:
            raise HydrocarbonInterpretationPdfError(unicode_report.error_message())
        document = QTextDocument()
        document.setDefaultFont(print_font(9.0 if include_chart else 10.0, text=html))
        document.setHtml(html)
        document.print_(writer)
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
