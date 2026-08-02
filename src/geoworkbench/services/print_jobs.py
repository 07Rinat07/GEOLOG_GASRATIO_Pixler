from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import json
import re
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtWidgets import QWidget

from geoworkbench.printing.document_export import (
    export_document_pages,
    export_document_pdf,
    render_document_to_printer,
)
from geoworkbench.printing.document_renderer import (
    PrintDocumentContext,
    build_document_plan,
    printable_content_dimensions,
)
from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
from geoworkbench.printing.printer_gate import (
    PhysicalPrinterGate,
    PrinterCapabilities,
    PrinterGateRequest,
    evaluate_physical_printer_gate,
    selected_page_count,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.report_passport import (
    ReportPassport,
    ReportRenderSettings,
)
from geoworkbench.services.report_output_transaction import (
    execute_report_output_transaction,
)


class PhysicalPrintGateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PrintJobResult:
    output_format: PrintOutputFormat
    page_count: int
    paths: tuple[Path, ...] = ()
    passport_path: Path | None = None
    passport_sha256: str | None = None
    printer_gate: PhysicalPrinterGate | None = None

    @property
    def primary_path(self) -> Path | None:
        return self.paths[0] if self.paths else None


class PrintJobExecutor:
    """Execute configured print/export jobs independently from window dialogs."""

    def available_printers(self) -> tuple[tuple[str, bool], ...]:
        try:
            available = QPrinterInfo.availablePrinters()
        except (OSError, RuntimeError):
            return ()
        printers = {
            info.printerName().strip(): bool(info.isDefault())
            for info in available
            if info.printerName().strip()
        }
        return tuple(
            sorted(
                printers.items(),
                key=lambda item: (not item[1], item[0].casefold()),
            )
        )

    def create_printer(self, widget: QWidget, job: PrintJobSettings) -> QPrinter:
        if job.printer_name is not None:
            printer_info = QPrinterInfo.printerInfo(job.printer_name)
            if printer_info.isNull():
                raise ValueError(
                    f"Выбранный принтер недоступен: {job.printer_name}"
                )
            printer = QPrinter(printer_info, QPrinter.PrinterMode.HighResolution)
        else:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setCopyCount(job.copy_count)
        self.configure_printer(printer, widget, job)
        # Keep Qt's default open page range (0..0). The final automatic page
        # count depends on the selected full report header and is resolved only
        # when the context-aware renderer starts.
        return printer

    def configure_printer(self, printer: QPrinter, widget: QWidget, job: PrintJobSettings) -> None:
        content_width, content_height = printable_content_dimensions(widget, job)
        # Qt positions the painter at the printable area's origin when fullPage
        # is disabled. The renderer therefore uses a zero-based page rectangle
        # and the configured margins are applied exactly once.
        printer.setFullPage(False)
        printer.setResolution(job.dpi)
        printer.setPageSize(job.page.page_size_for_content(content_width, content_height))
        printer.setPageOrientation(job.page.qt_orientation)
        printer.setPageMargins(job.page.qt_margins, QPageLayout.Unit.Millimeter)

    def physical_printer_gate(
        self,
        printer: QPrinter,
        widget: QWidget,
        job: PrintJobSettings,
        *,
        context: PrintDocumentContext | None = None,
    ) -> PhysicalPrinterGate:
        self.configure_printer(printer, widget, job)
        plan = build_document_plan(widget, job, context=context)
        content_width, content_height = printable_content_dimensions(widget, job)
        page_size = job.page.oriented_page_size_mm(content_width, content_height)
        capabilities = _printer_capabilities(printer)
        page_count = selected_page_count(plan.page_count, printer.fromPage(), printer.toPage())
        gate = evaluate_physical_printer_gate(
            PrinterGateRequest(
                page_format=job.page.page_format.value,
                page_size_mm=(page_size.width(), page_size.height()),
                margins_mm=job.page.margins_mm,
                requested_dpi=job.dpi,
                page_count=page_count,
            ),
            capabilities,
        )
        if gate.selected_dpi != job.dpi:
            printer.setResolution(gate.selected_dpi)
        return gate

    def render_to_printer(
        self,
        widget: QWidget,
        printer: QPrinter,
        job: PrintJobSettings,
        *,
        source_name: str,
        language: AppLanguage,
        passport: ReportPassport | None = None,
        require_physical_gate: bool = False,
        header_template: MasterlogTemplate | None = None,
        session: ProjectSession | None = None,
    ) -> PrintJobResult:
        context = PrintDocumentContext(
            source_name, language, header_template=header_template, session=session
        )
        gate = None
        if require_physical_gate:
            gate = self.physical_printer_gate(
                printer,
                widget,
                job,
                context=context,
            )
            if not gate.ok:
                localizer = Localizer.create(language)
                details = "; ".join(
                    _localized_gate_issue(localizer, issue.code) for issue in gate.errors
                )
                raise PhysicalPrintGateError(details or "Physical printer gate failed")
        print_copy = _physical_print_copy_path(source_name)
        pdf_job = replace(
            job,
            output_format=PrintOutputFormat.PDF,
            target=print_copy,
            printer_name=None,
            copy_count=1,
        )
        print_copy_result = export_document_pdf(
            widget,
            print_copy,
            pdf_job,
            context=context,
            overwrite=False,
        )
        page_count = render_document_to_printer(widget, printer, job, context=context)
        if require_physical_gate and _printer_state_name(printer).casefold() in {
            "error",
            "aborted",
        }:
            raise PhysicalPrintGateError(
                f"Printer job ended with state: {_printer_state_name(printer)}"
            )
        return PrintJobResult(
            PrintOutputFormat.PRINTER,
            page_count,
            paths=print_copy_result.paths,
            passport_sha256=passport.passport_sha256 if passport is not None else None,
            printer_gate=gate,
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
        header_template: MasterlogTemplate | None = None,
        session: ProjectSession | None = None,
    ) -> PrintJobResult:
        if job.output_format is PrintOutputFormat.PRINTER:
            raise ValueError("Физический принтер требует отдельного printer job")
        target = job.normalized_target()
        if target is None:
            raise ValueError("Для файлового экспорта необходимо выбрать путь")
        context = PrintDocumentContext(
            source_name, language, header_template=header_template, session=session
        )
        if passport is None:
            if job.output_format is PrintOutputFormat.PDF:
                result = export_document_pdf(
                    widget, target, job, context=context, overwrite=overwrite
                )
            else:
                result = export_document_pages(
                    widget, target, job, context=context, overwrite=overwrite
                )
            return PrintJobResult(job.output_format, result.page_count, result.paths)

        rendered_page_count = 0

        def produce(staged_target: Path) -> tuple[Path, ...]:
            nonlocal rendered_page_count
            if job.output_format is PrintOutputFormat.PDF:
                rendered = export_document_pdf(
                    widget, staged_target, job, context=context, overwrite=False
                )
            else:
                rendered = export_document_pages(
                    widget, staged_target, job, context=context, overwrite=False
                )
            rendered_page_count = rendered.page_count
            return rendered.paths

        transaction = execute_report_output_transaction(
            target, produce, passport, overwrite=overwrite
        )
        return PrintJobResult(
            job.output_format,
            rendered_page_count,
            transaction.output_paths,
            passport_path=transaction.passport_path,
            passport_sha256=transaction.passport.passport_sha256,
        )



def _physical_print_copy_path(source_name: str) -> Path:
    """Return a persistent PDF copy for a physical-printer job."""

    documents = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation
    )
    root = Path(documents) if documents else Path.home() / "Documents"
    folder = root / "GEOLOG GASRATIO Pixler" / "Печатные копии"
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", source_name).strip(" ._")
    safe_name = (safe_name or "document")[:96]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return folder / f"{safe_name}_{stamp}.pdf"

def report_render_settings(job: PrintJobSettings) -> ReportRenderSettings:
    page = job.page
    pagination = job.pagination
    return ReportRenderSettings(
        renderer="document-renderer:2",
        output_format=job.output_format.value,
        page_format=page.page_format.value,
        orientation=page.orientation.value,
        dpi=job.dpi,
        image_quality=job.image_quality,
        fit_form_columns=page.effective_fit_form_columns,
        scale_mode=page.scale_mode.value,
        continuation_overlap_mm=page.continuation_overlap_mm,
        margins_mm=page.margins_mm,
        range_mode=pagination.range_mode.value,
        units_per_page=pagination.units_per_page,
        overlap=pagination.overlap,
        show_page_numbers=pagination.show_page_numbers,
        show_page_range=pagination.show_page_range,
        strict_unicode=job.strict_unicode,
        options=tuple(
            item
            for item in (
                (
                    ("header_template_id", job.header_template_id)
                    if job.header_template_id is not None
                    else None
                ),
                ("header_placement", job.header_placement.value),
                (
                    "repeat_column_header_at_bottom",
                    str(job.repeat_column_header_at_bottom).lower(),
                ),
                (
                    "auto_units_per_page",
                    str(pagination.auto_units_per_page).lower(),
                ),
                (
                    (
                        "included_track_ids",
                        json.dumps(
                            job.included_track_ids,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    )
                    if job.included_track_ids is not None
                    else None
                ),
                (
                    (
                        "grid_print_overrides",
                        json.dumps(
                            job.grid_print_overrides,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    )
                    if job.grid_print_overrides
                    else None
                ),
            )
            if item is not None
        ),
    )


def _printer_capabilities(printer: QPrinter) -> PrinterCapabilities:
    info = QPrinterInfo(printer)
    supported_sizes = tuple(
        _page_size_mm(page_size) for page_size in info.supportedPageSizes() if page_size.isValid()
    )
    minimum_size = _optional_page_size_mm(_call_optional(info, "minimumPhysicalPageSize"))
    maximum_size = _optional_page_size_mm(_call_optional(info, "maximumPhysicalPageSize"))
    layout = printer.pageLayout()
    layout.setUnits(QPageLayout.Unit.Millimeter)
    minimum_margins = layout.minimumMargins()
    printable = printer.pageRect(QPrinter.Unit.Millimeter)
    return PrinterCapabilities(
        printer_name=info.printerName() or printer.printerName(),
        valid=bool(printer.isValid() and not info.isNull()),
        state=_printer_state_name(printer),
        supports_custom_page_sizes=bool(info.supportsCustomPageSizes()),
        supported_page_sizes_mm=supported_sizes,
        supported_resolutions=tuple(int(value) for value in info.supportedResolutions()),
        minimum_page_size_mm=minimum_size,
        maximum_page_size_mm=maximum_size,
        minimum_margins_mm=(
            float(minimum_margins.left()),
            float(minimum_margins.top()),
            float(minimum_margins.right()),
            float(minimum_margins.bottom()),
        ),
        printable_size_mm=(float(printable.width()), float(printable.height())),
    )


def _call_optional(value: object, name: str):
    method = getattr(value, name, None)
    return method() if callable(method) else None


def _optional_page_size_mm(value: object) -> tuple[float, float] | None:
    if not isinstance(value, QPageSize) or not value.isValid():
        return None
    return _page_size_mm(value)


def _page_size_mm(value: QPageSize) -> tuple[float, float]:
    size = value.size(QPageSize.Unit.Millimeter)
    return float(size.width()), float(size.height())


def _printer_state_name(printer: QPrinter) -> str:
    state = printer.printerState()
    name = getattr(state, "name", None)
    return str(name if name is not None else state)


def _localized_gate_issue(localizer: Localizer, code: str) -> str:
    key = "print_center.gate_" + code.replace("-", "_")
    return localizer.text(key)
