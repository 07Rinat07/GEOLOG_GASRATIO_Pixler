from __future__ import annotations

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QDialog

from geoworkbench.data.hydrocarbon_interpretation_export import (
    HydrocarbonInterpretationExportError,
)
from geoworkbench.printing.gas_mixture_ramp_report import GasMixtureRampReport
from geoworkbench.printing.hydrocarbon_interpretation_chart_front import (
    hydrocarbon_interpretation_html_with_front_chart,
)
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.ui.interpretation_report_workspace_expert import (
    InterpretationReportWorkspace as _ExpertInterpretationReportWorkspace,
)


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

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        printer.setPageMargins(
            QMarginsF(14.0, 14.0, 14.0, 14.0),
            QPageLayout.Unit.Millimeter,
        )
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle(self.tab_title(self.language))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        html = hydrocarbon_interpretation_html_with_front_chart(
            report,
            dataset,
            self.language,
            print_layout=True,
        )
        document = QTextDocument()
        document.setDefaultFont(print_font(9.0, text=html))
        document.setPageSize(printer.pageLayout().paintRectPoints().size())
        document.setHtml(html)
        document.print_(printer)

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
