from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.printing.interpretation_report import (
    InterpretationReportError,
    build_interpretation_report,
    export_interpretation_report_pdf,
    interpretation_report_html,
    localize_interpretation_report,
)
from geoworkbench.printing.interpretation_report_office import (
    InterpretationReportOfficeError,
    export_interpretation_report_docx,
    export_interpretation_report_xlsx,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.window_geometry import fit_window_to_screen


class InterpretationReportDialog(QDialog):
    def __init__(
        self,
        session: ProjectSession,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.language = language
        self.localizer = Localizer.create(language)
        # Freeze authored translations alongside the numerical snapshot so changing
        # output language cannot read later edits from the live project.
        self.report = build_interpretation_report(session, language=language)
        self._reports_by_language = {
            output_language: (
                self.report
                if output_language == language
                else localize_interpretation_report(self.report, session, output_language)
            )
            for output_language in AppLanguage
        }
        self.setWindowTitle(self._t("interpretation_report.title"))
        layout = QVBoxLayout(self)
        self.report_output_language = QComboBox()
        self.report_output_language.setObjectName("geology-report-output-language")
        for label, value in (
            ("Русский", AppLanguage.RU),
            ("Қазақша", AppLanguage.KK),
            ("English", AppLanguage.EN),
        ):
            self.report_output_language.addItem(label, value)
        self.report_output_language.setCurrentIndex(self.report_output_language.findData(language))
        self.report_output_language_label = QLabel(
            {
                AppLanguage.RU: "Язык отчёта:",
                AppLanguage.KK: "Есеп тілі:",
                AppLanguage.EN: "Report language:",
            }[language]
        )
        self.report_output_language_label.setBuddy(self.report_output_language)
        language_form = QFormLayout()
        language_form.addRow(self.report_output_language_label, self.report_output_language)
        layout.addLayout(language_form)
        self.preview = QTextBrowser()
        self.preview.setObjectName("interpretation-report-preview")
        self.preview.setStyleSheet(
            "QTextBrowser#interpretation-report-preview { "
            "background-color: #ffffff; color: #172033; "
            "border: 1px solid #cbd5e1; }"
            "QTextBrowser#interpretation-report-preview QScrollBar:vertical { "
            "width: 14px; background: #e2e8f0; margin: 0; }"
            "QTextBrowser#interpretation-report-preview QScrollBar:horizontal { "
            "height: 14px; background: #e2e8f0; margin: 0; }"
            "QTextBrowser#interpretation-report-preview QScrollBar::handle { "
            "background: #64748b; min-width: 28px; min-height: 28px; }"
            "QTextBrowser#interpretation-report-preview QScrollBar::add-line, "
            "QTextBrowser#interpretation-report-preview QScrollBar::sub-line { "
            "background: #cbd5e1; }"
        )
        self.preview.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self.preview.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self.preview.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.preview.setMinimumSize(0, 0)
        # Keep the multi-section report at a readable desktop width. The
        # viewport can then scroll horizontally instead of squeezing every
        # geological and gas column into the dialog width.
        self.preview.setLineWrapMode(QTextEdit.LineWrapMode.FixedPixelWidth)
        self.preview.setLineWrapColumnOrWidth(1600)
        self.preview.setHtml(interpretation_report_html(self.report, language))
        layout.addWidget(self.preview)
        self.report_output_language.currentIndexChanged.connect(self._apply_output_language)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self._t("common.close"))
        self.export_button = QPushButton(self._t("interpretation_report.export"))
        self.export_button.setObjectName("interpretation-report-export")
        self.export_button.clicked.connect(self._export_pdf)
        buttons.addButton(self.export_button, QDialogButtonBox.ButtonRole.ActionRole)
        self.export_xlsx_button = QPushButton(
            self._t("interpretation_report.export_xlsx")
        )
        self.export_xlsx_button.setObjectName("interpretation-report-export-xlsx")
        self.export_xlsx_button.clicked.connect(self._export_xlsx)
        buttons.addButton(
            self.export_xlsx_button, QDialogButtonBox.ButtonRole.ActionRole
        )
        self.export_docx_button = QPushButton(
            self._t("interpretation_report.export_docx")
        )
        self.export_docx_button.setObjectName("interpretation-report-export-docx")
        self.export_docx_button.clicked.connect(self._export_docx)
        buttons.addButton(
            self.export_docx_button, QDialogButtonBox.ButtonRole.ActionRole
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        fit_window_to_screen(
            self,
            preferred=QSize(1000, 700),
            minimum=QSize(560, 420),
        )

    def _report_output_language(self) -> AppLanguage:
        try:
            return AppLanguage(self.report_output_language.currentData())
        except (TypeError, ValueError):
            return self.language

    def _apply_output_language(self) -> None:
        language = self._report_output_language()
        self.report = self._reports_by_language[language]
        self.preview.setHtml(interpretation_report_html(self.report, language))

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _export_pdf(self) -> None:
        safe_well_name = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in self.report.well_name
        ).strip("_")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._t("interpretation_report.save_title"),
            str(Path.cwd() / f"{safe_well_name or 'well'}-geology-report.pdf"),
            "PDF (*.pdf)",
        )
        if not filename:
            return
        target = Path(filename)
        if target.suffix.casefold() != ".pdf":
            target = target.with_suffix(".pdf")
        overwrite = False
        if target.exists():
            existing = target
            answer = QMessageBox.question(
                self,
                self._t("interpretation_report.title"),
                self._t("export.overwrite_question", name=existing.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            overwrite = True
        try:
            exported = export_interpretation_report_pdf(
                self.report,
                target,
                language=self._report_output_language(),
                overwrite=overwrite,
            )
        except (
            FileExistsError,
            InterpretationReportError,
            OSError,
            ValueError,
        ) as exc:
            QMessageBox.critical(self, self._t("interpretation_report.title"), str(exc))
            return
        message = self._t("interpretation_report.exported", name=exported.name)
        QMessageBox.information(self, self._t("interpretation_report.title"), message)

    def _export_xlsx(self) -> None:
        self._export_office("xlsx")

    def _export_docx(self) -> None:
        self._export_office("docx")

    def _export_office(self, output_format: str) -> None:
        safe_well_name = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in self.report.well_name
        ).strip("_")
        is_xlsx = output_format == "xlsx"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._t(
                "interpretation_report.save_xlsx_title"
                if is_xlsx
                else "interpretation_report.save_docx_title"
            ),
            str(
                Path.cwd()
                / f"{safe_well_name or 'well'}-geology-report.{output_format}"
            ),
            "Excel (*.xlsx)" if is_xlsx else "Word (*.docx)",
        )
        if not filename:
            return
        target = Path(filename)
        suffix = f".{output_format}"
        if target.suffix.casefold() != suffix:
            target = target.with_suffix(suffix)
        overwrite = False
        if target.exists():
            existing = target
            answer = QMessageBox.question(
                self,
                self._t("interpretation_report.title"),
                self._t("export.overwrite_question", name=existing.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            overwrite = True
        try:
            exporter = (
                export_interpretation_report_xlsx
                if is_xlsx
                else export_interpretation_report_docx
            )
            exported = exporter(
                self.report,
                target,
                language=self._report_output_language(),
                overwrite=overwrite,
            )
        except (
            FileExistsError,
            InterpretationReportOfficeError,
            OSError,
            ValueError,
        ) as exc:
            QMessageBox.critical(self, self._t("interpretation_report.title"), str(exc))
            return
        message = self._t("interpretation_report.exported", name=exported.name)
        QMessageBox.information(self, self._t("interpretation_report.title"), message)
