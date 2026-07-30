from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.data.hydrocarbon_interpretation_export import (
    HydrocarbonInterpretationExportError,
    export_hydrocarbon_interpretation_docx,
    export_hydrocarbon_interpretation_xlsx,
)
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    HydrocarbonInterpretationPdfError,
    export_hydrocarbon_interpretation_pdf,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
    build_hydrocarbon_interpretation_report,
    hydrocarbon_interpretation_html,
)
from geoworkbench.services.localization import AppLanguage


class InterpretationReportWorkspace(QWidget):
    calculation_completed = Signal(object)

    def __init__(
        self,
        controller: InterpretationCalculationController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.language = language
        self.report: HydrocarbonInterpretationReport | None = None
        self.setObjectName("interpretation-report-workspace")

        root = QVBoxLayout(self)
        self.explanation = QLabel(
            self._text(
                "Расчёт стандартных кривых, поиск относительных газовых аномалий и выпуск "
                "отчёта. Кандидаты не заменяют заключение геолога.",
                "Стандартты қисықтарды есептеу, салыстырмалы газ ауытқуларын іздеу және "
                "есеп шығару. Кандидаттар геолог қорытындысын алмастырмайды.",
                "Calculate standard curves, find relative gas anomalies, and issue a report. "
                "Candidates do not replace the geologist's interpretation.",
            )
        )
        self.explanation.setWordWrap(True)
        root.addWidget(self.explanation)

        form = QFormLayout()
        self.normal_density = QDoubleSpinBox()
        self.normal_density.setRange(0.0, 30.0)
        self.normal_density.setDecimals(2)
        self.normal_density.setSingleStep(0.1)
        self.normal_density.setSpecialValueText(
            self._text("не задана", "берілмеген", "not set")
        )
        self.normal_density.setSuffix(" ppg")
        self.normal_density.setToolTip(
            self._text(
                "Нужна только для DEXPC. Значение 0 не подставляет скрытое допущение.",
                "Тек DEXPC үшін қажет. 0 мәні жасырын болжам қоспайды.",
                "Used only for DEXPC. Zero does not inject a hidden assumption.",
            )
        )
        self.normal_density_label = QLabel()
        form.addRow(self.normal_density_label, self.normal_density)
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(2.0, 10.0)
        self.threshold.setDecimals(1)
        self.threshold.setSingleStep(0.5)
        self.threshold.setValue(3.0)
        self.threshold.setToolTip(
            self._text(
                "Порог относительно устойчивого фона всей текущей скважины.",
                "Ағымдағы ұңғыманың тұрақты фонына қатысты шек.",
                "Threshold relative to the robust baseline of the current well dataset.",
            )
        )
        self.threshold_label = QLabel()
        form.addRow(self.threshold_label, self.threshold)
        root.addLayout(form)

        actions = QHBoxLayout()
        self.calculate_button = QPushButton(
            self._text("Рассчитать стандартные методы", "Стандартты әдістерді есептеу", "Calculate standard methods")
        )
        self.calculate_button.clicked.connect(self.calculate_standard_methods)
        actions.addWidget(self.calculate_button)
        self.refresh_button = QPushButton(
            self._text("Обновить анализ", "Талдауды жаңарту", "Refresh analysis")
        )
        self.refresh_button.clicked.connect(self.refresh)
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)
        root.addLayout(actions)

        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.preview = QTextBrowser()
        self.preview.setObjectName("hydrocarbon-interpretation-preview")
        root.addWidget(self.preview, 1)

        export_row = QHBoxLayout()
        self.xlsx_button = QPushButton("Excel (.xlsx)")
        self.xlsx_button.clicked.connect(self._export_xlsx)
        export_row.addWidget(self.xlsx_button)
        self.docx_button = QPushButton("Word (.docx)")
        self.docx_button.clicked.connect(self._export_docx)
        export_row.addWidget(self.docx_button)
        self.pdf_button = QPushButton("PDF")
        self.pdf_button.clicked.connect(self._export_pdf)
        export_row.addWidget(self.pdf_button)
        self.print_button = QPushButton(self._text("Печать…", "Басып шығару…", "Print…"))
        self.print_button.clicked.connect(self._print_report)
        export_row.addWidget(self.print_button)
        export_row.addStretch(1)
        root.addLayout(export_row)
        self._retranslate()
        self._set_exports_enabled(False)
        self.refresh()

    @staticmethod
    def tab_title(language: AppLanguage) -> str:
        return {
            AppLanguage.RU: "Отчёты по интерпретации",
            AppLanguage.KK: "Интерпретация есептері",
            AppLanguage.EN: "Interpretation reports",
        }[language]

    def refresh(self) -> None:
        self.calculate_button.setEnabled(self.controller.session.current_dataset is not None)
        try:
            self.report = build_hydrocarbon_interpretation_report(
                self.controller.session,
                threshold=self.threshold.value(),
            )
        except RuntimeError:
            self.report = None
            self.preview.setHtml(
                "<p>"
                + self._text(
                    "Откройте LAS/GS2 и выберите скважину.",
                    "LAS/GS2 ашып, ұңғыманы таңдаңыз.",
                    "Open a LAS/GS2 dataset and select a well.",
                )
                + "</p>"
            )
            self.status.clear()
            self._set_exports_enabled(False)
            return
        self.preview.setHtml(hydrocarbon_interpretation_html(self.report, self.language))
        self.status.setText(
            self._text(
                f"Кандидатных интервалов: {len(self.report.candidates)}; "
                f"подтверждённых геологом: {len(self.report.manual_intervals)}.",
                f"Кандидат аралықтар: {len(self.report.candidates)}; "
                f"геолог растаған: {len(self.report.manual_intervals)}.",
                f"Candidate intervals: {len(self.report.candidates)}; "
                f"geologist-confirmed: {len(self.report.manual_intervals)}.",
            )
        )
        self._set_exports_enabled(True)

    def calculate_standard_methods(self) -> None:
        density = self.normal_density.value()
        try:
            result = self.controller.calculate_standard_curves(
                normal_mud_density_ppg=density if density > 0.0 else None
            )
        except (RuntimeError, ValueError, KeyError) as exc:
            QMessageBox.critical(
                self,
                self.tab_title(self.language),
                str(exc),
            )
            return
        self.calculation_completed.emit(result)
        self.refresh()
        issue_text = "\n".join(f"• {issue.message}" for issue in result.issues)
        changed = ", ".join(result.changed) or self._text("нет", "жоқ", "none")
        self.status.setText(
            self._text(
                f"Созданы/обновлены: {changed}.",
                f"Құрылған/жаңартылған: {changed}.",
                f"Created/updated: {changed}.",
            )
            + (f"\n{issue_text}" if issue_text else "")
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
            exported = export_hydrocarbon_interpretation_xlsx(
                report,
                dataset,
                target,
                overwrite=target.exists(),
            )
        except (OSError, FileExistsError, HydrocarbonInterpretationExportError) as exc:
            self._show_export_error(exc)
            return
        self._show_export_success(exported)

    def _export_docx(self) -> None:
        report = self._require_report()
        if report is None:
            return
        target = self._choose_target(".docx", "Word (*.docx)")
        if target is None:
            return
        try:
            exported = export_hydrocarbon_interpretation_docx(
                report,
                target,
                overwrite=target.exists(),
            )
        except (OSError, FileExistsError, HydrocarbonInterpretationExportError) as exc:
            self._show_export_error(exc)
            return
        self._show_export_success(exported)

    def _export_pdf(self) -> None:
        report = self._require_report()
        if report is None:
            return
        target = self._choose_target(".pdf", "PDF (*.pdf)")
        if target is None:
            return
        try:
            exported = export_hydrocarbon_interpretation_pdf(
                report,
                target,
                language=self.language,
                overwrite=target.exists(),
            )
        except (OSError, FileExistsError, HydrocarbonInterpretationPdfError) as exc:
            self._show_export_error(exc)
            return
        self._show_export_success(exported)

    def _print_report(self) -> None:
        report = self._require_report()
        if report is None:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle(self.tab_title(self.language))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        document = QTextDocument()
        document.setHtml(hydrocarbon_interpretation_html(report, self.language))
        document.print_(printer)

    def _choose_target(self, suffix: str, file_filter: str) -> Path | None:
        report = self._require_report()
        if report is None:
            return None
        safe_well = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in report.well_name
        ).strip("_")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self.tab_title(self.language),
            str(Path.cwd() / f"{safe_well or 'well'}-mud-gas-interpretation{suffix}"),
            file_filter,
        )
        if not filename:
            return None
        target = Path(filename)
        if target.suffix.casefold() != suffix:
            target = target.with_suffix(suffix)
        if target.exists():
            answer = QMessageBox.question(
                self,
                self.tab_title(self.language),
                self._text(
                    f"Файл {target.name} существует. Заменить?",
                    f"{target.name} файлы бар. Ауыстыру керек пе?",
                    f"{target.name} already exists. Replace it?",
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return None
        return target

    def _require_report(self) -> HydrocarbonInterpretationReport | None:
        if self.report is None:
            QMessageBox.information(
                self,
                self.tab_title(self.language),
                self._text(
                    "Сначала откройте набор данных.",
                    "Алдымен деректер жинағын ашыңыз.",
                    "Open a dataset first.",
                ),
            )
        return self.report

    def _set_exports_enabled(self, enabled: bool) -> None:
        for button in (self.xlsx_button, self.docx_button, self.pdf_button, self.print_button):
            button.setEnabled(enabled)

    def _show_export_error(self, error: Exception) -> None:
        QMessageBox.critical(self, self.tab_title(self.language), str(error))

    def _show_export_success(self, path: Path) -> None:
        QMessageBox.information(
            self,
            self.tab_title(self.language),
            self._text(
                f"Отчёт сохранён: {path.name}",
                f"Есеп сақталды: {path.name}",
                f"Report saved: {path.name}",
            ),
        )

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {AppLanguage.RU: ru, AppLanguage.KK: kk, AppLanguage.EN: en}[self.language]

    def set_language(self, language: AppLanguage) -> None:
        self.language = language
        self._retranslate()
        self.refresh()

    def _retranslate(self) -> None:
        self.explanation.setText(
            self._text(
                "Расчёт стандартных кривых, поиск относительных газовых аномалий и выпуск "
                "отчёта. Кандидаты не заменяют заключение геолога.",
                "Стандартты қисықтарды есептеу, салыстырмалы газ ауытқуларын іздеу және "
                "есеп шығару. Кандидаттар геолог қорытындысын алмастырмайды.",
                "Calculate standard curves, find relative gas anomalies, and issue a report. "
                "Candidates do not replace the geologist's interpretation.",
            )
        )
        self.normal_density_label.setText(
            self._text(
                "Нормальная плотность раствора:",
                "Қалыпты ерітінді тығыздығы:",
                "Normal mud density:",
            )
        )
        self.normal_density.setSpecialValueText(
            self._text("не задана", "берілмеген", "not set")
        )
        self.normal_density.setToolTip(
            self._text(
                "Нужна только для DEXPC. Значение 0 не подставляет скрытое допущение.",
                "Тек DEXPC үшін қажет. 0 мәні жасырын болжам қоспайды.",
                "Used only for DEXPC. Zero does not inject a hidden assumption.",
            )
        )
        self.threshold_label.setText(
            self._text(
                "Порог газовой аномалии:",
                "Газ ауытқуының шегі:",
                "Gas anomaly threshold:",
            )
        )
        self.threshold.setToolTip(
            self._text(
                "Порог относительно устойчивого фона всей текущей скважины.",
                "Ағымдағы ұңғыманың тұрақты фонына қатысты шек.",
                "Threshold relative to the robust baseline of the current well dataset.",
            )
        )
        self.calculate_button.setText(
            self._text(
                "Рассчитать стандартные методы",
                "Стандартты әдістерді есептеу",
                "Calculate standard methods",
            )
        )
        self.refresh_button.setText(
            self._text("Обновить анализ", "Талдауды жаңарту", "Refresh analysis")
        )
        self.print_button.setText(
            self._text("Печать…", "Басып шығару…", "Print…")
        )
