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
from geoworkbench.services.report_passport import (
    ReportPassport,
    ReportRenderSettings,
    passport_sidecar_path,
    write_report_passport,
)


@dataclass(frozen=True, slots=True)
class PrintJobResult:
    output_format: PrintOutputFormat
    page_count: int
    paths: tuple[Path, ...] = ()
    passport_path: Path | None = None
    passport_sha256: str | None = None

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
        passport: ReportPassport | None = None,
    ) -> PrintJobResult:
        context = PrintDocumentContext(source_name, language)
        page_count = render_document_to_printer(widget, printer, job, context=context)
        return PrintJobResult(
            PrintOutputFormat.PRINTER,
            page_count,
            passport_sha256=passport.passport_sha256 if passport is not None else None,
        )

    def execute_file(
        self,
        widget: QWidget,
        job: PrintJobSettings,
        *,
        source_name: str,
        language: AppLanguage,
        overwrite: bool = False,
        passport: ReportPassport | None = None,
    ) -> PrintJobResult:
        if job.output_format is PrintOutputFormat.PRINTER:
            raise ValueError("Физический принтер требует отдельного printer job")
        target = job.normalized_target()
        if target is None:
            raise ValueError("Для файлового экспорта необходимо выбрать путь")
        if passport is not None:
            sidecar = passport_sidecar_path(target)
            if sidecar.exists() and not overwrite:
                raise FileExistsError(sidecar)
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
        passport_path = (
            write_report_passport(passport, target, overwrite=overwrite)
            if passport is not None
            else None
        )
        return PrintJobResult(
            job.output_format,
            result.page_count,
            result.paths,
            passport_path=passport_path,
            passport_sha256=passport.passport_sha256 if passport is not None else None,
        )


def report_render_settings(job: PrintJobSettings) -> ReportRenderSettings:
    page = job.page
    pagination = job.pagination
    return ReportRenderSettings(
        renderer="document-renderer:1",
        output_format=job.output_format.value,
        page_format=page.page_format.value,
        orientation=page.orientation.value,
        dpi=job.dpi,
        image_quality=job.image_quality,
        fit_form_columns=page.fit_form_columns,
        margins_mm=(
            page.margin_left_mm,
            page.margin_top_mm,
            page.margin_right_mm,
            page.margin_bottom_mm,
        ),
        range_mode=pagination.range_mode.value,
        units_per_page=pagination.units_per_page,
        overlap=pagination.overlap,
        show_page_numbers=pagination.show_page_numbers,
        show_page_range=pagination.show_page_range,
        strict_unicode=job.strict_unicode,
    )
