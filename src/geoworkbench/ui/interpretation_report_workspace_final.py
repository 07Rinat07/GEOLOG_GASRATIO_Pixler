from __future__ import annotations

import logging
from pathlib import Path
import tempfile

import fitz
from PySide6.QtPrintSupport import QAbstractPrintDialog, QPrintDialog, QPrinter
from PySide6.QtWidgets import QApplication, QDialog, QProgressDialog

from geoworkbench.data.hydrocarbon_interpretation_export import (
    HydrocarbonInterpretationExportError,
)
from geoworkbench.printing.gas_mixture_ramp_report import GasMixtureRampReport
from geoworkbench.printing.hydrocarbon_interpretation_chart_front import (
    hydrocarbon_interpretation_html_with_front_chart,
)
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    HydrocarbonInterpretationPdfError,
    export_hydrocarbon_interpretation_pdf,
)
from geoworkbench.printing.hydrocarbon_interpretation_system_print import (
    configure_interpretation_printer,
    print_pdf_page_selection,
    selected_report_pages,
)
from geoworkbench.ui.interpretation_print_layout_dialog import (
    InterpretationPrintLayoutDialog,
    InterpretationPrintOrder,
)
from geoworkbench.ui.interpretation_report_workspace_expert import (
    InterpretationReportWorkspace as _ExpertInterpretationReportWorkspace,
)


LOGGER = logging.getLogger(__name__)


class InterpretationReportWorkspace(_ExpertInterpretationReportWorkspace):
    """Final compatibility layer for the chart-enabled interpretation workspace."""

    def _retranslate_expert_controls(self) -> None:
        super()._retranslate_expert_controls()
        self.calculate_normalized_gas_button.setText(
            self._text(
                "Рассчитать локальный нормализованный газ",
                "Жергілікті нормаланған газды есептеу",
                "Calculate local normalized gas",
            )
        )
        self.show_normalized_gas_button.setText(
            self._text(
                "Показать кривые нормализованного газа на планшете",
                "Нормаланған газ қисықтарын планшетте көрсету",
                "Show normalized-gas curves on tablet",
            )
        )
        self.xlsx_button.setText(
            self._text(
                "Excel — сводная интерпретация (.xlsx)",
                "Excel — жиынтық интерпретация (.xlsx)",
                "Excel — consolidated interpretation (.xlsx)",
            )
        )
        self.xlsx_button.setToolTip(
            self._text(
                "Создаёт один основной лист с УВ-интервалами и абсолютными компонентами "
                "газа C1, C2, C3, iC4, nC4, iC5, nC5. Для каждой кривой приводятся "
                "минимум, среднее и максимум. Исходные данные сохраняются на скрытом листе.",
                "Көмірсутек аралықтары және C1, C2, C3, iC4, nC4, iC5, nC5 абсолюттік газ "
                "компоненттері бар негізгі парақ жасайды. Әр қисық үшін ең аз, орташа және "
                "ең көп мән беріледі. Бастапқы деректер жасырын парақта сақталады.",
                "Creates one main sheet with hydrocarbon intervals and absolute C1, C2, C3, "
                "iC4, nC4, iC5, and nC5 gas components. Each curve includes minimum, mean, "
                "and maximum values. Source data remain on a hidden audit sheet.",
            )
        )

    def _apply_chart_preview(self) -> None:
        dataset = self.controller.session.current_dataset
        if self.report is None or dataset is None or self._is_mixture_mode():
            return
        self.preview.setHtml(
            hydrocarbon_interpretation_html_with_front_chart(
                self.report,
                dataset,
                self.language,
            )
        )

    def _print_report(self) -> None:
        report = self._require_any_report()
        if report is None:
            return
        if isinstance(report, GasMixtureRampReport):
            super()._print_report()
            return
        dataset = self.controller.session.current_dataset
        if dataset is None:
            return

        layout_dialog = InterpretationPrintLayoutDialog(
            self,
            language=self.language,
        )
        if layout_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        layout = layout_dialog.selected_layout()

        with tempfile.TemporaryDirectory(prefix="geolog-interpretation-print-") as folder:
            prepared_pdf = Path(folder) / "interpretation-report.pdf"
            try:
                export_hydrocarbon_interpretation_pdf(
                    report,
                    prepared_pdf,
                    language=self.language,
                    dataset=dataset,
                    include_chart=True,
                    orientation=layout.orientation,
                    overwrite=True,
                )
                with fitz.open(prepared_pdf) as document:
                    total_pages = document.page_count
            except (OSError, HydrocarbonInterpretationPdfError, RuntimeError) as exc:
                self._show_export_error(exc)
                return
            if total_pages < 1:
                self._show_export_error(RuntimeError("Печатный отчёт не содержит страниц"))
                return

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            configure_interpretation_printer(printer, layout.orientation)
            printer.setDocName(self.tab_title(self.language))
            dialog = QPrintDialog(printer, self)
            dialog.setWindowTitle(self.tab_title(self.language))
            dialog.setOption(
                QAbstractPrintDialog.PrintDialogOption.PrintPageRange,
                True,
            )
            dialog.setOption(
                QAbstractPrintDialog.PrintDialogOption.PrintSelection,
                False,
            )
            dialog.setOption(
                QAbstractPrintDialog.PrintDialogOption.PrintCurrentPage,
                False,
            )
            dialog.setMinMax(1, total_pages)
            dialog.setFromTo(1, total_pages)
            dialog.setPrintRange(QAbstractPrintDialog.PrintRange.AllPages)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            range_selected = (
                dialog.printRange() is QAbstractPrintDialog.PrintRange.PageRange
                or printer.printRange() is QPrinter.PrintRange.PageRange
            )
            print_range = (
                QAbstractPrintDialog.PrintRange.PageRange
                if range_selected
                else QAbstractPrintDialog.PrintRange.AllPages
            )
            from_page = dialog.fromPage() or printer.fromPage()
            to_page = dialog.toPage() or printer.toPage()
            reverse = layout.order is InterpretationPrintOrder.LAST_TO_FIRST
            page_numbers = selected_report_pages(
                total_pages,
                print_range,
                from_page,
                to_page,
                reverse=reverse,
            )
            if not page_numbers:
                self._show_export_error(RuntimeError("Не выбран диапазон страниц"))
                return

            # Driver dialogs may change these values. Reapply the selected report
            # layout after acceptance so the prepared PDF and physical paper match.
            configure_interpretation_printer(printer, layout.orientation)
            LOGGER.info(
                "interpretation print start printer=%r orientation=%s range=%s-%s "
                "pages=%s order=%s copies=%s",
                printer.printerName(),
                layout.orientation.name,
                page_numbers[0],
                page_numbers[-1],
                len(page_numbers),
                layout.order.value,
                printer.copyCount(),
            )

            progress = QProgressDialog(
                self._text(
                    "Подготовка страниц для принтера…",
                    "Принтерге арналған беттер дайындалуда…",
                    "Preparing pages for the printer…",
                ),
                self._text("Остановить", "Тоқтату", "Stop"),
                0,
                len(page_numbers),
                self,
            )
            progress.setWindowTitle(self.tab_title(self.language))
            progress.setWindowModality(progress.windowModality().WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)

            def cancel_requested() -> bool:
                QApplication.processEvents()
                return progress.wasCanceled()

            def update_progress(current: int, total: int, page_number: int) -> None:
                progress.setLabelText(
                    self._text(
                        f"Отправляется страница {page_number} ({current} из {total})…",
                        f"{page_number}-бет жіберілуде ({current}/{total})…",
                        f"Sending page {page_number} ({current} of {total})…",
                    )
                )
                progress.setValue(current)
                QApplication.processEvents()

            try:
                completed = print_pdf_page_selection(
                    prepared_pdf,
                    printer,
                    page_numbers,
                    cancel_requested=cancel_requested,
                    progress=update_progress,
                )
            except (OSError, RuntimeError, ValueError) as exc:
                LOGGER.exception("interpretation print failed")
                self._show_export_error(exc)
                return
            finally:
                progress.close()

            if not completed:
                LOGGER.warning(
                    "interpretation print cancelled printer=%r state=%s",
                    printer.printerName(),
                    printer.printerState().name,
                )
                self.status.setText(
                    self._text(
                        "Печать остановлена. Уже переданные в Windows страницы "
                        "могут остаться в очереди принтера.",
                        "Басып шығару тоқтатылды. Windows жүйесіне жіберілген "
                        "беттер принтер кезегінде қалуы мүмкін.",
                        "Printing was stopped. Pages already sent to Windows may "
                        "remain in the printer queue.",
                    )
                )
                return

            LOGGER.info(
                "interpretation print completed printer=%r pages=%s state=%s",
                printer.printerName(),
                len(page_numbers),
                printer.printerState().name,
            )
            self.status.setText(
                self._text(
                    f"В очередь печати отправлено страниц: {len(page_numbers)}.",
                    f"Басып шығару кезегіне {len(page_numbers)} бет жіберілді.",
                    f"Pages sent to the print queue: {len(page_numbers)}.",
                )
            )

    def _export_xlsx(self) -> None:
        report = self._require_report()
        if report is None:
            return
        dataset = self.controller.session.current_dataset
        if dataset is None:
            return
        target = self._choose_target(".xlsx", "Excel (*.xlsx)")
        if target is None:
            return
        try:
            from geoworkbench.data.hydrocarbon_interpretation_export_readable import (
                export_readable_hydrocarbon_interpretation_xlsx,
            )

            with self._report_export_progress(
                self._text(
                    "Формируется Excel-отчёт…",
                    "Excel есебі құрылуда…",
                    "Building Excel report…",
                )
            ):
                exported = export_readable_hydrocarbon_interpretation_xlsx(
                    report,
                    dataset,
                    target,
                    overwrite=target.exists(),
                    progress=self._update_report_export_progress,
                )
        except (OSError, FileExistsError, HydrocarbonInterpretationExportError) as exc:
            self._show_export_error(exc)
            return
        self._show_export_success(exported)


__all__ = ["InterpretationReportWorkspace"]
