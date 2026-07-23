from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QPageLayout
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QWidget

from geoworkbench.printing.document_export import (
    export_document_pages,
    export_document_pdf,
    render_document_to_printer,
)
from geoworkbench.printing.document_renderer import PrintDocumentContext
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class PrintJobResult:
    output_format: PrintOutputFormat
    page_count: int
    paths: tuple[Path, ...] = ()

    @property
    def primary_path(self) -> Path | None:
        return self.paths[0] if self.paths else None


class PrintJobExecutor:
    """Execute configured print/export jobs independently from window dialogs."""

    def create_printer(self, widget: QWidget, job: PrintJobSettings) -> QPrinter:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setResolution(job.dpi)
        printer.setPageSize(job.page.page_size_for_content(widget.width(), widget.height()))
        printer.setPageOrientation(job.page.qt_orientation)
        printer.setPageMargins(job.page.qt_margins, QPageLayout.Unit.Millimeter)
        return printer

    def render_to_printer(
        self,
        widget: QWidget,
        printer: QPrinter,
        job: PrintJobSettings,
        *,
        source_name: str,
        language: AppLanguage,
    ) -> PrintJobResult:
        context = PrintDocumentContext(source_name, language)
        page_count = render_document_to_printer(widget, printer, job, context=context)
        return PrintJobResult(PrintOutputFormat.PRINTER, page_count)

    def execute_file(
        self,
        widget: QWidget,
        job: PrintJobSettings,
        *,
        source_name: str,
        language: AppLanguage,
        overwrite: bool = False,
    ) -> PrintJobResult:
        if job.output_format is PrintOutputFormat.PRINTER:
            raise ValueError("Физический принтер требует отдельного printer job")
        target = job.normalized_target()
        if target is None:
            raise ValueError("Для файлового экспорта необходимо выбрать путь")
        context = PrintDocumentContext(source_name, language)
        if job.output_format is PrintOutputFormat.PDF:
            result = export_document_pdf(
                widget,
                target,
                job,
                context=context,
                overwrite=overwrite,
            )
        else:
            result = export_document_pages(
                widget,
                target,
                job,
                context=context,
                overwrite=overwrite,
            )
        return PrintJobResult(job.output_format, result.page_count, result.paths)
