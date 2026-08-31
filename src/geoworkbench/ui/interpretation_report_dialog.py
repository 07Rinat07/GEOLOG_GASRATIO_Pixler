from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
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
)
from geoworkbench.printing.interpretation_report_office import (
    InterpretationReportOfficeError,
    export_interpretation_report_docx,
    export_interpretation_report_xlsx,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.report_passport import (
    ReportKind,
    ReportPassportBuilder,
    ReportPassportError,
    ReportPassportRequest,
    ReportRenderSettings,
    depth_interval_snapshot,
    passport_sidecar_path,
    report_definition_snapshot,
)


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
        self.report = build_interpretation_report(session)
        self.setWindowTitle(self._t("interpretation_report.title"))
        self.resize(1000, 700)
        layout = QVBoxLayout(self)
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
        sidecar = passport_sidecar_path(target)
        existing = target if target.exists() else sidecar if sidecar.exists() else None
        if existing is not None:
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
            passport = self._build_report_passport(
                output_format="pdf", renderer="interpretation-report-html:3"
            )
            exported = export_interpretation_report_pdf(
                self.report,
                target,
                language=self.language,
                overwrite=overwrite,
                passport=passport,
            )
        except (
            FileExistsError,
            InterpretationReportError,
            OSError,
            ReportPassportError,
            ValueError,
        ) as exc:
            QMessageBox.critical(self, self._t("interpretation_report.title"), str(exc))
            return
        message = self._t("interpretation_report.exported", name=exported.name)
        message += "\n" + self._t(
            "report_passport.saved", name=passport_sidecar_path(exported).name
        )
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
        sidecar = passport_sidecar_path(target)
        existing = target if target.exists() else sidecar if sidecar.exists() else None
        if existing is not None:
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
            passport = self._build_report_passport(
                output_format=output_format,
                renderer=f"interpretation-report-{output_format}:1",
            )
            exporter = (
                export_interpretation_report_xlsx
                if is_xlsx
                else export_interpretation_report_docx
            )
            exported = exporter(
                self.report,
                target,
                language=self.language,
                overwrite=overwrite,
                passport=passport,
            )
        except (
            FileExistsError,
            InterpretationReportOfficeError,
            OSError,
            ReportPassportError,
            ValueError,
        ) as exc:
            QMessageBox.critical(self, self._t("interpretation_report.title"), str(exc))
            return
        message = self._t("interpretation_report.exported", name=exported.name)
        message += "\n" + self._t(
            "report_passport.saved", name=passport_sidecar_path(exported).name
        )
        QMessageBox.information(self, self._t("interpretation_report.title"), message)

    def _build_report_passport(self, *, output_format: str, renderer: str):
        dataset = self.session.current_dataset
        index_type = dataset.active_index.index_type.value if dataset is not None else "md"
        unit = dataset.active_index.unit if dataset is not None else None
        interval = depth_interval_snapshot(
            tuple((entry.top_depth, entry.bottom_depth) for entry in self.report.entries),
            index_id="interpretation-intervals",
            mnemonic="DEPTH",
            index_type=index_type,
            unit=unit,
        )
        form = report_definition_snapshot(
            "interpretation-report",
            self._t("interpretation_report.title"),
            {
                "schema_version": 3,
                "columns": (
                    "meter_geology",
                    "sampling_interval",
                    "rock_composition",
                    "rock_description",
                    "stratigraphy",
                    "calcimetry",
                    "gas_total",
                    "gas_components",
                    "gas_component_sum",
                    "lba",
                    "interpretation",
                ),
                "page_format": "a4",
                "orientation": "landscape",
            },
        )
        request = ReportPassportRequest(
            report_kind=ReportKind.INTERPRETATION,
            report_name=self._t("interpretation_report.title"),
            language=self.language,
            render=ReportRenderSettings(
                renderer=renderer,
                output_format=output_format,
                page_format="a4",
                orientation="landscape",
                dpi=300,
                margins_mm=(14.0, 14.0, 14.0, 14.0),
                strict_unicode=True,
            ),
            form=form,
        )
        well = self.session.current_well
        if well is None:
            raise ReportPassportError("Для отчёта требуется выбранная скважина")
        return ReportPassportBuilder().build_artifact(
            self.session,
            request,
            artifact_id=f"{well.well_id}:interpretation-report",
            artifact_name=self.report.dataset_name or self.report.well_name,
            payload=asdict(self.report),
            interval=interval,
        )
