from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QPageLayout, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
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
from geoworkbench.printing.gas_mixture_ramp_report import (
    GasMixtureRampReport,
    GasMixtureRampReportError,
    build_gas_mixture_ramp_report,
    export_gas_mixture_ramp_pdf,
    gas_mixture_ramp_html,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
    NormalizedGasReference,
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
        self.gas_mixture_report: GasMixtureRampReport | None = None
        self._export_in_progress = False
        self.setObjectName("interpretation-report-workspace")
        self.setStyleSheet(
            """
            QWidget#interpretation-report-workspace {
                background: #f4f7fb;
                color: #172033;
            }
            QWidget#interpretation-report-workspace QLabel {
                color: #172033;
                background: transparent;
            }
            QLabel#calculation-input-help {
                padding: 8px 10px;
                color: #22364d;
                background: #e8f0f8;
                border: 1px solid #b8c8d8;
                border-radius: 6px;
            }
            QWidget#interpretation-report-workspace QDoubleSpinBox,
            QWidget#interpretation-report-workspace QComboBox {
                min-height: 28px;
                padding: 2px 8px;
                color: #172033;
                background: #ffffff;
                border: 1px solid #aeb8c6;
                border-radius: 5px;
                selection-color: #ffffff;
                selection-background-color: #315a7d;
            }
            QWidget#interpretation-report-workspace QPushButton {
                min-height: 30px;
                padding: 3px 12px;
                color: #172033;
                background: #ffffff;
                border: 1px solid #aeb8c6;
                border-radius: 5px;
            }
            QWidget#interpretation-report-workspace QPushButton:hover {
                background: #e8f0f8;
                border-color: #547a9f;
            }
            QWidget#interpretation-report-workspace QPushButton:pressed {
                background: #d8e6f3;
            }
            QWidget#interpretation-report-workspace QPushButton:disabled {
                color: #7a8492;
                background: #e9edf2;
                border-color: #c9d0d9;
            }
            QTextBrowser#hydrocarbon-interpretation-preview {
                color: #172033;
                background: #ffffff;
                border: 1px solid #b7c1ce;
                border-radius: 6px;
                selection-color: #ffffff;
                selection-background-color: #315a7d;
            }
            QProgressBar#interpretation-report-export-progress {
                min-height: 22px;
                color: #172033;
                background: #ffffff;
                border: 1px solid #9fb2c5;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar#interpretation-report-export-progress::chunk {
                background: #4f7da8;
                border-radius: 4px;
            }
            """
        )

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
        self.calculation_inputs_help = QLabel()
        self.calculation_inputs_help.setObjectName("calculation-input-help")
        self.calculation_inputs_help.setWordWrap(True)
        root.addWidget(self.calculation_inputs_help)

        form = QFormLayout()
        self.report_mode = QComboBox()
        self.report_mode.currentIndexChanged.connect(self.refresh)
        self.report_mode_label = QLabel()
        form.addRow(self.report_mode_label, self.report_mode)
        self.normal_density = QDoubleSpinBox()
        self.normal_density.setRange(0.0, 30.0)
        self.normal_density.setDecimals(2)
        self.normal_density.setSingleStep(0.1)
        self.normal_density.setSpecialValueText(self._text("не задана", "берілмеген", "not set"))
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
        self.normalized_gas_reference_note = QLabel(
            self._text(
                "Эталонные условия для кривых C1–C5_NORM и TG_NORM:",
                "C1–C5_NORM және TG_NORM қисықтарының эталондық шарттары:",
                "Reference conditions for C1–C5_NORM and TG_NORM curves:",
            )
        )
        self.normalized_gas_reference_note.setWordWrap(True)
        form.addRow(self.normalized_gas_reference_note)

        self.rop_reference = QDoubleSpinBox()
        self.rop_reference.setRange(0.01, 10_000.0)
        self.rop_reference.setDecimals(2)
        self.rop_reference.setValue(50.0)
        self.rop_reference.setSuffix(" ft/h")
        self.rop_reference_label = QLabel()
        form.addRow(self.rop_reference_label, self.rop_reference)

        self.bit_reference = QDoubleSpinBox()
        self.bit_reference.setRange(0.01, 100.0)
        self.bit_reference.setDecimals(2)
        self.bit_reference.setValue(10.0)
        self.bit_reference.setSuffix(" in")
        self.bit_reference_label = QLabel()
        form.addRow(self.bit_reference_label, self.bit_reference)

        self.flow_reference = QDoubleSpinBox()
        self.flow_reference.setRange(0.01, 100_000.0)
        self.flow_reference.setDecimals(2)
        self.flow_reference.setValue(500.0)
        self.flow_reference.setSuffix(" gpm")
        self.flow_reference_label = QLabel()
        form.addRow(self.flow_reference_label, self.flow_reference)

        self.gas_efficiency = QDoubleSpinBox()
        self.gas_efficiency.setRange(0.01, 1.0)
        self.gas_efficiency.setDecimals(3)
        self.gas_efficiency.setSingleStep(0.05)
        self.gas_efficiency.setValue(1.0)
        self.gas_efficiency_label = QLabel()
        form.addRow(self.gas_efficiency_label, self.gas_efficiency)
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
            self._text(
                "Рассчитать стандартные методы",
                "Стандартты әдістерді есептеу",
                "Calculate standard methods",
            )
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

        self.export_progress = QProgressBar()
        self.export_progress.setObjectName("interpretation-report-export-progress")
        self.export_progress.setRange(0, 0)
        self.export_progress.setTextVisible(True)
        self.export_progress.hide()
        root.addWidget(self.export_progress)
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
        mixture_mode = self._is_mixture_mode()
        has_dataset = self.controller.session.current_dataset is not None
        self.calculate_button.setEnabled(has_dataset and not mixture_mode)
        self.normal_density.setEnabled(not mixture_mode)
        self.calculation_inputs_help.setEnabled(not mixture_mode)
        self.normalized_gas_reference_note.setEnabled(not mixture_mode)
        self.rop_reference.setEnabled(not mixture_mode)
        self.bit_reference.setEnabled(not mixture_mode)
        self.flow_reference.setEnabled(not mixture_mode)
        self.gas_efficiency.setEnabled(not mixture_mode)
        self.threshold.setEnabled(not mixture_mode)
        self.gas_mixture_report = None
        if mixture_mode:
            try:
                self.gas_mixture_report = build_gas_mixture_ramp_report(self.controller.session)
            except (RuntimeError, GasMixtureRampReportError):
                self.report = None
                self.preview.setHtml(
                    "<p>"
                    + self._text(
                        "Для разгонки откройте временной набор с согласованными C1–C5.",
                        "Айдау үшін C1–C5 келісілген уақыттық деректер жинағын ашыңыз.",
                        "Open a time dataset with consistent C1–C5 curves for ramp analysis.",
                    )
                    + "</p>"
                )
                self.status.clear()
                self._set_exports_enabled(False)
                return
            self.report = None
            include_chart = self._report_mode() == "mixture_chart"
            self.preview.setHtml(
                gas_mixture_ramp_html(
                    self.gas_mixture_report,
                    self.language,
                    include_chart=include_chart,
                )
            )
            self.status.setText(
                self._text(
                    "Разгонка рассчитана по временному отклику C1–C5.",
                    "Айдау C1–C5 уақыттық жауабы бойынша есептелді.",
                    "Ramp analysis was calculated from the C1–C5 time response.",
                )
            )
            self._set_exports_enabled(True)
            return

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
                normal_mud_density_ppg=density if density > 0.0 else None,
                normalized_gas_reference=NormalizedGasReference(
                    rop_ref_fph=self.rop_reference.value(),
                    bit_ref_in=self.bit_reference.value(),
                    flow_ref_gpm=self.flow_reference.value(),
                    gas_system_efficiency=self.gas_efficiency.value(),
                ),
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
            with self._report_export_progress(
                self._text(
                    "Формируется Excel-отчёт…",
                    "Excel есебі құрылуда…",
                    "Building Excel report…",
                )
            ):
                exported = export_hydrocarbon_interpretation_xlsx(
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

    def _export_docx(self) -> None:
        report = self._require_report()
        if report is None:
            return
        dataset = self.controller.session.current_dataset
        if dataset is None:
            return
        target = self._choose_target(".docx", "Word (*.docx)")
        if target is None:
            return
        try:
            with self._report_export_progress(
                self._text(
                    "Формируется Word-отчёт…",
                    "Word есебі құрылуда…",
                    "Building Word report…",
                )
            ):
                exported = export_hydrocarbon_interpretation_docx(
                    report,
                    target,
                    dataset=dataset,
                    overwrite=target.exists(),
                )
        except (OSError, FileExistsError, HydrocarbonInterpretationExportError) as exc:
            self._show_export_error(exc)
            return
        self._show_export_success(exported)

    def _export_pdf(self) -> None:
        report = self._require_any_report()
        if report is None:
            return
        target = self._choose_target(".pdf", "PDF (*.pdf)")
        if target is None:
            return
        try:
            with self._report_export_progress(
                self._text(
                    "Формируется PDF-отчёт…",
                    "PDF есебі құрылуда…",
                    "Building PDF report…",
                )
            ):
                if isinstance(report, GasMixtureRampReport):
                    exported = export_gas_mixture_ramp_pdf(
                        report,
                        target,
                        language=self.language,
                        include_chart=self._report_mode() == "mixture_chart",
                        overwrite=target.exists(),
                    )
                else:
                    exported = export_hydrocarbon_interpretation_pdf(
                        report,
                        target,
                        language=self.language,
                        dataset=self.controller.session.current_dataset,
                        overwrite=target.exists(),
                    )
        except (
            OSError,
            FileExistsError,
            GasMixtureRampReportError,
            HydrocarbonInterpretationPdfError,
        ) as exc:
            self._show_export_error(exc)
            return
        self._show_export_success(exported)

    def _print_report(self) -> None:
        report = self._require_any_report()
        if report is None:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        if isinstance(report, GasMixtureRampReport) and self._report_mode() == "mixture_chart":
            printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle(self.tab_title(self.language))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        document = QTextDocument()
        document.setHtml(
            gas_mixture_ramp_html(
                report,
                self.language,
                include_chart=self._report_mode() == "mixture_chart",
            )
            if isinstance(report, GasMixtureRampReport)
            else self._hydrocarbon_print_html(report)
        )
        document.print_(printer)

    def _choose_target(self, suffix: str, file_filter: str) -> Path | None:
        report = self._require_any_report()
        if report is None:
            return None
        safe_well = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in report.well_name
        ).strip("_")
        report_stem = (
            "gas-mixture-ramp"
            if isinstance(report, GasMixtureRampReport)
            else "mud-gas-interpretation"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._text(
                "Сохранить готовый отчёт",
                "Дайын есепті сақтау",
                "Save completed report",
            ),
            str(Path.cwd() / f"{safe_well or 'well'}-{report_stem}{suffix}"),
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

    def _hydrocarbon_print_html(
        self,
        report: HydrocarbonInterpretationReport,
    ) -> str:
        dataset = self.controller.session.current_dataset
        if dataset is None:
            return hydrocarbon_interpretation_html(report, self.language)
        from geoworkbench.printing.hydrocarbon_interpretation_chart_front import (
            hydrocarbon_interpretation_html_with_front_chart,
        )

        return hydrocarbon_interpretation_html_with_front_chart(
            report,
            dataset,
            self.language,
        )

    @contextmanager
    def _report_export_progress(self, message: str) -> Iterator[None]:
        self._export_in_progress = True
        self.export_progress.setRange(0, 0)
        self.export_progress.setFormat(message)
        self.export_progress.show()
        self.status.setText(message)
        self._set_exports_enabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            yield
        finally:
            QApplication.restoreOverrideCursor()
            self.export_progress.hide()
            self.export_progress.setRange(0, 0)
            self._export_in_progress = False
            self._set_exports_enabled((self.gas_mixture_report if self._is_mixture_mode() else self.report) is not None)
            QApplication.processEvents()

    def _update_report_export_progress(
        self,
        stage: str,
        current: int,
        total: int,
    ) -> None:
        safe_total = max(1, int(total))
        safe_current = min(safe_total, max(0, int(current)))
        self.export_progress.setRange(0, safe_total)
        self.export_progress.setValue(safe_current)
        self.export_progress.setFormat(f"{stage} — %p%")
        self.status.setText(stage)
        QApplication.processEvents()

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
        if self._export_in_progress:
            enabled = False
        tabular = enabled and self.report is not None
        self.xlsx_button.setEnabled(tabular)
        self.docx_button.setEnabled(tabular)
        self.pdf_button.setEnabled(enabled)
        self.print_button.setEnabled(enabled)

    def _show_export_error(self, error: Exception) -> None:
        self.status.setText(
            self._text(
                f"Ошибка формирования отчёта: {error}",
                f"Есепті құру қатесі: {error}",
                f"Report generation failed: {error}",
            )
        )
        QMessageBox.critical(self, self.tab_title(self.language), str(error))

    def _show_export_success(self, path: Path) -> None:
        self.status.setText(
            self._text(
                f"Отчёт готов: {path}",
                f"Есеп дайын: {path}",
                f"Report ready: {path}",
            )
        )
        answer = QMessageBox.question(
            self,
            self.tab_title(self.language),
            self._text(
                f"Отчёт готов и сохранён:\n{path}\n\nОткрыть сейчас?",
                f"Есеп дайын және сақталды:\n{path}\n\nҚазір ашу керек пе?",
                f"The report is ready and saved:\n{path}\n\nOpen it now?",
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
            if not opened:
                QMessageBox.warning(
                    self,
                    self.tab_title(self.language),
                    self._text(
                        "Не удалось открыть файл автоматически.",
                        "Файлды автоматты түрде ашу мүмкін болмады.",
                        "The file could not be opened automatically.",
                    ),
                )

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {AppLanguage.RU: ru, AppLanguage.KK: kk, AppLanguage.EN: en}[self.language]

    def set_language(self, language: AppLanguage) -> None:
        self.language = language
        self._retranslate()
        self.refresh()

    def _retranslate(self) -> None:
        current_mode = self._report_mode()
        self.report_mode.blockSignals(True)
        self.report_mode.clear()
        self.report_mode.addItem(
            self._text(
                "Интерпретация скважины — без графика",
                "Ұңғыманы интерпретациялау — графиксіз",
                "Well interpretation — no chart",
            ),
            "well_text",
        )
        self.report_mode.addItem(
            self._text(
                "Разгонка газовой смеси — временной график",
                "Газ қоспасын айдау — уақыт графигі",
                "Gas mixture ramp — time chart",
            ),
            "mixture_chart",
        )
        self.report_mode.addItem(
            self._text(
                "Разгонка газовой смеси — только интерпретация",
                "Газ қоспасын айдау — тек интерпретация",
                "Gas mixture ramp — interpretation only",
            ),
            "mixture_text",
        )
        index = self.report_mode.findData(current_mode)
        self.report_mode.setCurrentIndex(max(0, index))
        self.report_mode.blockSignals(False)
        self.report_mode_label.setText(self._text("Вид отчёта:", "Есеп түрі:", "Report type:"))
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
        self.calculation_inputs_help.setText(
            self._text(
                "Что нужно для расчётов: C1–C5 и фактические кривые ROP, BIT/BS "
                "(диаметр долота) и FLOW_IN/FLOW_OUT. Программа берёт их из открытого "
                "LAS/GS2 и приводит совместимые единицы автоматически. Если BIT отсутствует: "
                "откройте «Инспектор данных → Кривые», добавьте кривую BIT с единицей in, "
                "затем в таблице заполните её значением по соответствующему интервалу. "
                "Поля *_REF ниже — эталонные условия нормализации, а не фактические кривые.",
                "Есептеу үшін C1–C5 және нақты ROP, BIT/BS (қашау диаметрі), "
                "FLOW_IN/FLOW_OUT қисықтары қажет. Бағдарлама оларды ашық LAS/GS2 "
                "деректерінен алып, үйлесімді бірліктерді автоматты түрлендіреді. BIT жоқ "
                "болса, «Деректер инспекторы → Қисықтар» арқылы in бірлігіндегі BIT "
                "қисығын қосып, кестеде тиісті аралықтарды толтырыңыз. Төмендегі *_REF "
                "өрістері нақты қисықтар емес, нормалаудың эталондық шарттары.",
                "Required inputs: C1–C5 plus actual ROP, BIT/BS (bit diameter), and "
                "FLOW_IN/FLOW_OUT curves. They are read from the open LAS/GS2 dataset and "
                "compatible units are converted automatically. If BIT is missing, use "
                "Data Inspector → Curves to add BIT in inches, then fill its values over "
                "the relevant intervals in the table. The *_REF fields below are reference "
                "normalization conditions, not the actual curves.",
            )
        )
        self.normal_density_label.setText(
            self._text(
                "Нормальная плотность раствора:",
                "Қалыпты ерітінді тығыздығы:",
                "Normal mud density:",
            )
        )
        self.normal_density.setSpecialValueText(self._text("не задана", "берілмеген", "not set"))
        self.normal_density.setToolTip(
            self._text(
                "Нужна только для DEXPC. Значение 0 не подставляет скрытое допущение.",
                "Тек DEXPC үшін қажет. 0 мәні жасырын болжам қоспайды.",
                "Used only for DEXPC. Zero does not inject a hidden assumption.",
            )
        )
        self.normalized_gas_reference_note.setText(
            self._text(
                "Эталонные условия для C1–C5_NORM и TG_NORM — проверьте по методике "
                "заказчика или принятому опорному режиму:",
                "C1–C5_NORM және TG_NORM үшін эталондық шарттар — тапсырыс беруші "
                "әдістемесі немесе қабылданған тірек режимі бойынша тексеріңіз:",
                "Reference conditions for C1–C5_NORM and TG_NORM — verify against the "
                "client method or the accepted reference drilling regime:",
            )
        )
        self.rop_reference_label.setText(
            self._text(
                "Эталонная ROP_REF:",
                "Эталондық ROP_REF:",
                "Reference ROP_REF:",
            )
        )
        self.rop_reference.setToolTip(
            self._text(
                "Скорость проходки эталонного режима, ft/h. Фактическая ROP берётся из "
                "кривой LAS. Значение по умолчанию 50 ft/h нужно подтвердить для проекта.",
                "Эталондық өту жылдамдығы, ft/h. Нақты ROP LAS қисығынан алынады. "
                "Әдепкі 50 ft/h мәнін жоба үшін растаңыз.",
                "Reference-regime rate of penetration in ft/h. Actual ROP comes from the "
                "LAS curve. Confirm the default 50 ft/h for the project.",
            )
        )
        self.bit_reference_label.setText(
            self._text(
                "Эталонный диаметр BIT_REF:",
                "Эталондық BIT_REF диаметрі:",
                "Reference bit diameter BIT_REF:",
            )
        )
        self.bit_reference.setToolTip(
            self._text(
                "Эталонный диаметр долота, in. Это не текущий диаметр: фактический "
                "BIT/BS должен быть кривой по глубине в LAS/GS2.",
                "Эталондық қашау диаметрі, in. Бұл ағымдағы диаметр емес: нақты BIT/BS "
                "LAS/GS2 ішінде тереңдік бойынша қисық болуы керек.",
                "Reference bit diameter in inches. This is not the current diameter: "
                "actual BIT/BS must be a depth curve in LAS/GS2.",
            )
        )
        self.flow_reference_label.setText(
            self._text(
                "Эталонный расход FLOW_REF:",
                "Эталондық FLOW_REF шығыны:",
                "Reference flow FLOW_REF:",
            )
        )
        self.flow_reference.setToolTip(
            self._text(
                "Расход эталонного режима, gpm. Фактический расход берётся из "
                "FLOW_IN или FLOW_OUT открытого набора.",
                "Эталондық режим шығыны, gpm. Нақты шығын ашық деректердегі "
                "FLOW_IN немесе FLOW_OUT қисығынан алынады.",
                "Reference-regime flow in gpm. Actual flow comes from FLOW_IN or "
                "FLOW_OUT in the open dataset.",
            )
        )
        self.gas_efficiency_label.setText(
            self._text(
                "Эффективность газовой системы E:",
                "Газ жүйесінің тиімділігі E:",
                "Gas-system efficiency E:",
            )
        )
        self.gas_efficiency.setToolTip(
            self._text(
                "Коэффициент 0–1 для эффективности дегазатора и газоаналитической "
                "системы. Если калибровки нет, 1.000 означает отсутствие поправки; "
                "это допущение укажите в отчёте.",
                "Дегазатор мен газ талдау жүйесінің тиімділігі үшін 0–1 коэффициенті. "
                "Калибрлеу болмаса, 1.000 түзету жоқ екенін білдіреді; бұл болжамды "
                "есепте көрсетіңіз.",
                "Efficiency coefficient from 0 to 1 for the degasser and gas-analysis "
                "system. If no calibration is available, 1.000 means no correction; "
                "record that assumption in the report.",
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
        self.print_button.setText(self._text("Печать…", "Басып шығару…", "Print…"))

    def _report_mode(self) -> str:
        value = self.report_mode.currentData()
        return str(value) if isinstance(value, str) and value else "well_text"

    def _is_mixture_mode(self) -> bool:
        return self._report_mode().startswith("mixture_")

    def _require_any_report(
        self,
    ) -> HydrocarbonInterpretationReport | GasMixtureRampReport | None:
        report = self.gas_mixture_report if self._is_mixture_mode() else self.report
        if report is None:
            QMessageBox.information(
                self,
                self.tab_title(self.language),
                self._text(
                    "Сначала откройте подходящий набор данных.",
                    "Алдымен қолайлы деректер жинағын ашыңыз.",
                    "Open a suitable dataset first.",
                ),
            )
        return report
