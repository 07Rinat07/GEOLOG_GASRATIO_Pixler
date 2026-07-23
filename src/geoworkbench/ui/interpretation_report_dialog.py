from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.printing.interpretation_report import (
    InterpretationReportError,
    build_interpretation_report,
    export_interpretation_report_pdf,
    interpretation_report_html,
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
        self.preview.setHtml(interpretation_report_html(self.report, language))
        layout.addWidget(self.preview)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self._t("common.close"))
        self.export_button = QPushButton(self._t("interpretation_report.export"))
        self.export_button.setObjectName("interpretation-report-export")
        self.export_button.clicked.connect(self._export_pdf)
        buttons.addButton(self.export_button, QDialogButtonBox.ButtonRole.ActionRole)
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
            str(Path.cwd() / f"{safe_well_name or 'well'}-interpretation.pdf"),
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
            passport = self._build_report_passport()
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

    def _build_report_passport(self):
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
                "schema_version": 1,
                "columns": ("interval", "calcimetry", "lba", "interpretation"),
                "page_format": "a4",
                "orientation": "portrait",
            },
        )
        request = ReportPassportRequest(
            report_kind=ReportKind.INTERPRETATION,
            report_name=self._t("interpretation_report.title"),
            language=self.language,
            render=ReportRenderSettings(
                renderer="interpretation-report-html:1",
                output_format="pdf",
                page_format="a4",
                orientation="portrait",
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
